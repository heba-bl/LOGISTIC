"""The Logistics Overview payload.

The rule these tests protect is the one a dashboard lives or dies by: every
block is computed from the same window, so two figures on the same screen can
never contradict each other.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.exceptions import ValidationError
from app.services import overview_service


def test_period_presets_resolve_to_a_window():
    for key, days in (("today", 1), ("7d", 7), ("30d", 30)):
        window = overview_service.resolve_window(key)
        assert window["days"] == days
        assert window["start_at"] <= window["end_at"]
        # The comparison window sits immediately before, same length.
        assert window["previous_end_at"] < window["start_at"]
        assert (window["end_date"] - window["start_date"]).days == days - 1


def test_custom_period_needs_both_ends():
    with pytest.raises(ValidationError):
        overview_service.resolve_window("custom", date(2026, 1, 1), None)
    with pytest.raises(ValidationError):
        overview_service.resolve_window("custom", date(2026, 2, 1), date(2026, 1, 1))
    with pytest.raises(ValidationError):
        overview_service.resolve_window("last-tuesday")


def test_unknown_period_is_refused(db, world):
    with pytest.raises(ValidationError):
        overview_service.build_overview(db, period="yesterday")


def test_stock_totals_match_the_headline_kpi(db, world):
    """The composition chart and the KPI must never disagree.

    `stock_vs_demand` is truncated to the rows worth acting on, so summing it
    would under-report the total by however many references the chart chose not
    to show.
    """
    payload = overview_service.build_overview(db, period="30d")

    totals = payload["stock_totals"]
    headline = next(kpi for kpi in payload["kpis"] if kpi["id"] == "stock-total")

    assert totals["available"] == headline["value"]
    assert totals["free"] == totals["available"] - totals["reserved"]


def test_waterfall_closes_on_the_current_stock(db, world):
    """Opening + in - out must land exactly on the closing balance."""
    payload = overview_service.build_overview(db, period="30d")
    steps = {step["key"]: step for step in payload["stock_waterfall"]}

    opening = steps["opening"]["value"]
    closing = steps["closing"]["value"]
    moves = sum(
        step["value"] for step in payload["stock_waterfall"] if step["kind"] in ("IN", "OUT")
    )

    assert opening + moves == closing, payload["stock_waterfall"]
    assert closing == payload["stock_totals"]["available"]


def test_stock_trend_ends_on_the_current_balance(db, world):
    payload = overview_service.build_overview(db, period="30d")
    trend = payload["stock_trend"]
    assert trend, "la serie ne doit pas etre vide"
    assert trend[-1]["stock"] == payload["stock_totals"]["available"]
    # One point per day of the window, in order.
    dates = [point["date"] for point in trend]
    assert dates == sorted(dates)


def test_flow_funnel_has_no_duplicated_stage(db, world):
    """Mission Control counts SUPPLIER and RECEIVING identically.

    Showing both in a funnel would print the same figure twice and teach
    nothing, so the funnel starts at the receiving desk.
    """
    payload = overview_service.build_overview(db, period="30d")
    stages = [stage["id"] for stage in payload["flow"]["stages"]]

    assert "SUPPLIER" not in stages
    assert stages == ["RECEIVING", "INSPECTION", "QUALITY", "WAREHOUSE", "PRODUCTION"]
    # Four measured gaps between five boxes.
    assert len(payload["flow"]["transitions"]) == len(stages) - 1
    for transition in payload["flow"]["transitions"]:
        assert transition["key"], "chaque transition porte une cle traduisible"


def test_service_rate_ignores_cancelled_and_rejected_requests(db, world):
    """A request nobody meant to serve must not sink the service rate."""
    from app.models.enums import ProductionRequestStatus
    from app.models.production import ProductionRequest

    window = overview_service.resolve_window("30d")
    now = datetime.now(timezone.utc) - timedelta(hours=1)

    db.add(
        ProductionRequest(
            reference="PR-TEST-CANCELLED",
            station_id=world["station"].id,
            part_id=world["small"].id,
            quantity_requested=100_000,
            quantity_issued=0,
            status=ProductionRequestStatus.CANCELLED,
            priority=3,
            created_on=now,
        )
    )
    db.flush()

    block = overview_service.production_block(db, window)
    assert block["requested"] < 100_000, "la demande annulee est comptee"


def test_every_kpi_is_named_and_scored(db, world):
    payload = overview_service.build_overview(db, period="7d")
    assert len(payload["kpis"]) == 5

    for kpi in payload["kpis"]:
        assert kpi["id"]
        assert kpi["severity"] in {"OK", "WARNING", "CRITICAL", "INFO"}
        # A trend is either a real series or absent - never a fabricated line.
        assert isinstance(kpi["trend"], list)
        for point in kpi["trend"]:
            assert point["date"]


def test_decisions_carry_their_figures_and_an_action(db, world):
    """A recommendation without the numbers behind it is an opinion."""
    payload = overview_service.build_overview(db, period="30d")

    for decision in payload["decisions"]:
        assert decision["action_key"], decision
        assert decision["reason"] or decision["reason_key"], decision
        assert decision["severity"] in {"OK", "WARNING", "CRITICAL", "INFO"}
    ranks = [decision["rank"] for decision in payload["decisions"]]
    assert ranks == sorted(ranks)


def test_warehouse_zones_sum_to_the_global_occupancy(db, world):
    payload = overview_service.build_overview(db, period="30d")
    warehouse = payload["warehouse"]

    assert sum(zone["capacity"] for zone in warehouse["zones"]) == warehouse["total_capacity"]
    assert sum(zone["occupied"] for zone in warehouse["zones"]) == warehouse["total_occupied"]
    assert len(warehouse["heatmap"]) == sum(zone["locations"] for zone in warehouse["zones"])


# ------------------------------------------------- the analysis aggregations
def test_distribution_stays_silent_on_a_thin_sample(db, world):
    """A histogram built on three lots describes the sample, not the plant."""
    payload = overview_service.build_overview(db, period="30d")
    distribution = payload["lead_time_distribution"]

    if distribution["sample_size"] < overview_service.MIN_DISTRIBUTION_SAMPLE:
        assert distribution["buckets"] == []
        assert distribution["median_hours"] is None
    else:
        assert distribution["buckets"]
        # The buckets partition the sample exactly - none lost, none counted twice.
        assert sum(bucket["count"] for bucket in distribution["buckets"]) == (
            distribution["sample_size"]
        )


def test_distribution_buckets_are_contiguous_and_open_ended(db, world):
    """Whatever the sample, the buckets must partition the axis without a hole.

    Built by replaying real lots through the services rather than by writing
    audit rows by hand: a fabricated trail would test the bucketing against
    data the application can never produce.
    """
    from app.services import inspection_service, quality_service, reception_service, warehouse_service
    from app.services.warehouse_service import Allocation

    for index in range(overview_service.MIN_DISTRIBUTION_SAMPLE + 1):
        reception = reception_service.create_reception(
            db,
            part_id=world["small"].id,
            supplier_id=world["supplier"].id,
            quantity_expected=60,
            quantity_received=60,
            actor_id=world["user"].id,
        )
        lot = reception.lot
        inspection_service.start_inspection(db, lot_id=lot.id, actor_id=world["user"].id)
        inspection_service.record_inspection(
            db,
            lot_id=lot.id,
            sample_size=inspection_service.suggest_sample_size(db, lot),
            defects_found=0,
            actor_id=world["user"].id,
        )
        quality_service.approve(
            db, lot_id=lot.id, justification="conforme", actor_id=world["user"].id
        )
        plan = warehouse_service.suggest_allocations(
            db, part=lot.part, quantity=lot.quantity_approved
        )
        warehouse_service.confirm_storage(
            db,
            lot_id=lot.id,
            allocations=[
                Allocation(location_id=item.location.id, quantity=item.quantity)
                for item in plan
            ],
            actor_id=world["user"].id,
        )
        db.flush()

    window = overview_service.resolve_window("30d")
    distribution = overview_service.lead_time_distribution(db, window)

    assert distribution["sample_size"] >= overview_service.MIN_DISTRIBUTION_SAMPLE
    buckets = distribution["buckets"]
    assert buckets, "un echantillon suffisant doit produire des tranches"

    # Each bucket starts where the previous one ended; the last stays open.
    assert buckets[0]["from_hours"] == 0
    for previous, current in zip(buckets, buckets[1:]):
        assert previous["to_hours"] == current["from_hours"]
    assert buckets[-1]["to_hours"] is None

    assert sum(bucket["count"] for bucket in buckets) == distribution["sample_size"]
    assert distribution["median_hours"] is not None


def test_matrix_rows_sum_to_their_cells(db, world):
    payload = overview_service.build_overview(db, period="30d")
    matrix = payload["part_zone_matrix"]

    for row in matrix["rows"]:
        assert sum(cell["quantity"] for cell in row["cells"]) == row["total"]
        # Every row is laid out over the same columns, so the grid is square.
        assert [cell["zone"] for cell in row["cells"]] == matrix["zones"]
        assert row["risk"] in {"OK", "WARNING", "CRITICAL", "INFO"}


def test_dwell_points_reuse_the_warehouse_occupancy(db, world):
    """The scatter and the zone bars must not disagree about the same zone."""
    payload = overview_service.build_overview(db, period="30d")
    occupancy = {zone["zone"]: zone for zone in payload["warehouse"]["zones"]}

    for point in payload["zone_dwell"]:
        assert point["zone"] in occupancy
        assert point["occupancy_percent"] == occupancy[point["zone"]]["occupancy_percent"]
        assert point["severity"] == occupancy[point["zone"]]["severity"]
        assert point["average_days"] >= 0
        assert point["lots"] > 0
