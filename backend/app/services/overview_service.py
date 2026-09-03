"""The decision layer: what a logistics manager needs, in reading order.

`analytics_service` answers "what are the numbers". This module answers the
questions a manager actually asks - is production about to stop, which
reference, which zone, where is the flow slowing down, what do I do first - and
returns each answer already shaped for the visualisation that carries it.

Two rules run through the whole module:

* Nothing is invented. Every figure is read from the database; where a series
  cannot be reconstructed honestly, the field is null and the screen says so
  rather than drawing a plausible line.
* Every block exists to support a decision. A number that leads nowhere is not
  returned.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.timeutils import as_utc, to_local
from app.models.catalog import Category, Part
from app.models.enums import (
    AuditAction,
    InspectionResult,
    LotStatus,
    MovementType,
    ProductionRequestStatus,
)
from app.models.flow import Inspection, Lot
from app.models.production import ProductionRequest
from app.models.system import AuditLog
from app.models.warehouse import Stock, StockMovement, WarehouseLocation
from app.repositories import LotRepository, ProductionRepository, StockRepository
from app.services import ai_service, analytics_service, dashboard_service, settings_service

#: Period keys accepted by the screen.
PERIODS = ("today", "7d", "30d", "custom")

#: Days covered by each preset, used for the window and for the previous-period
#: comparison.
PRESET_DAYS = {"today": 1, "7d": 7, "30d": 30}

#: A daily series longer than this is downsampled - a sparkline with ninety
#: points is a smudge, not a trend.
MAX_TREND_POINTS = 30


# --------------------------------------------------------------------- period
def resolve_window(
    period: str, date_from: date | None = None, date_to: date | None = None
) -> dict:
    """Turn a period key into a UTC window plus the comparable previous one."""
    if period not in PERIODS:
        raise ValidationError(f"Periode inconnue: {period}")

    today = to_local(datetime.now(timezone.utc)).date()

    if period == "custom":
        if not date_from or not date_to:
            raise ValidationError("Une periode personnalisee exige une date de debut et de fin")
        if date_to < date_from:
            raise ValidationError("La date de fin precede la date de debut")
        start, end = date_from, date_to
    else:
        days = PRESET_DAYS[period]
        end = today
        start = today - timedelta(days=days - 1)

    span_days = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=span_days - 1)

    def bounds(first: date, last: date) -> tuple[datetime, datetime]:
        # Local day boundaries converted to UTC: "today" means the operator's
        # today, not UTC's.
        begin = datetime.combine(first, time.min).astimezone().astimezone(timezone.utc)
        finish = datetime.combine(last, time.max).astimezone().astimezone(timezone.utc)
        return begin, finish

    start_at, end_at = bounds(start, end)
    previous_start_at, previous_end_at = bounds(previous_start, previous_end)

    return {
        "key": period,
        "start_date": start,
        "end_date": end,
        "start_at": start_at,
        "end_at": end_at,
        "previous_start_at": previous_start_at,
        "previous_end_at": previous_end_at,
        "days": span_days,
    }


def _days_between(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def _downsample(points: list[dict]) -> list[dict]:
    """Keep a readable number of points, always keeping the last one."""
    if len(points) <= MAX_TREND_POINTS:
        return points
    step = len(points) / MAX_TREND_POINTS
    picked = [points[int(index * step)] for index in range(MAX_TREND_POINTS)]
    if picked[-1] is not points[-1]:
        picked[-1] = points[-1]
    return picked


# ---------------------------------------------------------------- stock level
def _movement_deltas(db: Session, since: datetime) -> list[tuple[datetime, int]]:
    rows = db.execute(
        select(StockMovement.occurred_at, StockMovement.movement_type, StockMovement.quantity)
        .where(StockMovement.occurred_at >= since)
        .order_by(StockMovement.occurred_at)
    ).all()
    return [
        (occurred_at, quantity if movement_type is MovementType.IN else -quantity)
        for occurred_at, movement_type, quantity in rows
    ]


def stock_level_series(db: Session, window: dict) -> list[dict]:
    """End-of-day total stock, rebuilt backwards from the ledger.

    The stock table holds only the current balance, so the history is
    reconstructed by unwinding the movements: today's total minus everything
    that moved after a given day is that day's closing balance. This is exact,
    not estimated - the ledger records `quantity_before` and `quantity_after`
    for every movement.
    """
    current = db.execute(
        select(func.coalesce(func.sum(Stock.quantity_available), 0))
    ).scalar_one()

    days = _days_between(window["start_date"], window["end_date"])
    deltas = _movement_deltas(db, window["start_at"])

    # Net movement per local day.
    per_day: dict[date, int] = defaultdict(int)
    for occurred_at, delta in deltas:
        per_day[to_local(occurred_at).date()] += delta

    # Walk backwards from the most recent day.
    series: list[dict] = []
    running = int(current)
    for day in reversed(days):
        series.append({"date": day.isoformat(), "stock": running})
        running -= per_day.get(day, 0)
    series.reverse()

    # Attach the flows of the same day, so one chart can carry both.
    per_day_in: dict[date, int] = defaultdict(int)
    per_day_out: dict[date, int] = defaultdict(int)
    for occurred_at, delta in deltas:
        day = to_local(occurred_at).date()
        if delta >= 0:
            per_day_in[day] += delta
        else:
            per_day_out[day] += -delta

    for point, day in zip(series, days):
        point["received"] = per_day_in.get(day, 0)
        point["consumed"] = per_day_out.get(day, 0)

    return series


def stock_at(db: Session, moment: datetime) -> int:
    """Total stock as it stood at `moment`."""
    current = db.execute(
        select(func.coalesce(func.sum(Stock.quantity_available), 0))
    ).scalar_one()
    after = _movement_deltas(db, moment)
    return int(current) - sum(delta for _, delta in after)


# ------------------------------------------------------------------ waterfall
def stock_waterfall(db: Session, window: dict) -> list[dict]:
    """Why did the stock move? Opening, receipts, issues, closing."""
    opening = stock_at(db, window["start_at"])
    closing = db.execute(
        select(func.coalesce(func.sum(Stock.quantity_available), 0))
    ).scalar_one()

    rows = db.execute(
        select(StockMovement.movement_type, func.coalesce(func.sum(StockMovement.quantity), 0))
        .where(
            StockMovement.occurred_at >= window["start_at"],
            StockMovement.occurred_at <= window["end_at"],
        )
        .group_by(StockMovement.movement_type)
    ).all()
    totals = {movement_type: int(quantity) for movement_type, quantity in rows}
    received = totals.get(MovementType.IN, 0)
    issued = totals.get(MovementType.OUT, 0)

    steps = [
        {"key": "opening", "value": int(opening), "kind": "START"},
        {"key": "received", "value": received, "kind": "IN"},
        {"key": "issued", "value": -issued, "kind": "OUT"},
    ]

    # Anything the two flows do not explain is shown rather than hidden.
    residual = int(closing) - (int(opening) + received - issued)
    if residual:
        steps.append({"key": "adjustment", "value": residual, "kind": "IN" if residual > 0 else "OUT"})

    steps.append({"key": "closing", "value": int(closing), "kind": "END"})
    return steps


# ------------------------------------------------------------ stock vs demand
#: Units travel as tokens ("pcs", "days", "%"), never as words: the API has
#: no business deciding whether the screen says "j" or "d".
#: What to do about a reference, keyed so the UI translates it.
ACTION_KEYS = {
    "CRITICAL": "action.checkIncoming",
    "WARNING": "action.watchCoverage",
    "OK": "action.none",
}


def stock_vs_demand(db: Session, limit: int = 12) -> list[dict]:
    """Available stock against confirmed production demand, per reference.

    Sorted by how close the reference is to stopping a line, so the first rows
    are the ones worth looking at - but never only those. See the selection at
    the end: a chart that shows shortfalls alone cannot say where the line
    between short and covered falls.
    """
    stocks = StockRepository(db)
    # One grouped query rather than one per reference: at 2 239 articles the
    # per-row version turned this page into a ten-second wait.
    demand_map = ai_service.demand_by_part(db)

    rows: list[dict] = []
    for stock in stocks.all_with_parts():
        part = stock.part
        demand = demand_map.get(part.id, 0)
        consumption = part.average_daily_consumption or 0.0
        available = stock.quantity_available
        cover = round(available / consumption, 1) if consumption > 0 else None

        if available < demand:
            risk = "CRITICAL"
        elif part.safety_stock and available < part.safety_stock:
            risk = "WARNING"
        else:
            risk = "OK"

        rows.append(
            {
                "part_id": part.id,
                "reference": part.reference,
                "designation": part.designation,
                "category": part.category.name if part.category else None,
                "available": available,
                "reserved": stock.quantity_reserved,
                "demand": demand,
                "safety_stock": part.safety_stock,
                "coverage_days": cover,
                "gap": available - demand,
                "daily_consumption": part.average_daily_consumption,
                "risk": risk,
                "action_key": ACTION_KEYS[risk],
            }
        )

    severity_rank = {"CRITICAL": 0, "WARNING": 1, "OK": 2}
    rows.sort(
        key=lambda row: (
            severity_rank[row["risk"]],
            row["coverage_days"] if row["coverage_days"] is not None else 9_999,
            -row["demand"],
        )
    )

    # Both sides of the line, not just the wrong one.
    #
    # Ranking by severity and cutting at twelve meant every row returned was a
    # shortfall - by construction, since CRITICAL is exactly `available <
    # demand` and there are more than twelve of those. Twelve red bars read as
    # an empty warehouse, while in fact most open requests are covered, and a
    # chart whose bars all carry the same sign says nothing about where the
    # line actually falls.
    #
    # So the worst keep the front - that is where a manager acts - and the tail
    # is filled with covered references, most-demanded first, so the reader can
    # see what "covered" looks like beside what "short" looks like.
    short = [row for row in rows if row["gap"] < 0]
    covered = [row for row in rows if row["gap"] >= 0]

    keep_short = min(len(short), max(limit - 4, limit // 2))
    chosen = short[:keep_short]
    chosen += sorted(covered, key=lambda row: -row["demand"])[: limit - len(chosen)]

    # Back into one ranking, so the chart still reads worst-first.
    chosen.sort(key=lambda row: (severity_rank[row["risk"]], -row["demand"]))
    return chosen


def stock_totals(db: Session) -> dict:
    """Totals over every reference, not just the ones a chart happens to show.

    `stock_vs_demand` is deliberately truncated to the rows worth acting on. A
    composition chart that sums those rows would contradict the KPI two
    centimetres above it, which is the fastest way to lose a manager's trust in
    the whole screen.
    """
    available, reserved, references = db.execute(
        select(
            func.coalesce(func.sum(Stock.quantity_available), 0),
            func.coalesce(func.sum(Stock.quantity_reserved), 0),
            func.count(Stock.part_id),
        )
    ).one()
    return {
        "available": int(available),
        "reserved": int(reserved),
        "free": max(int(available) - int(reserved), 0),
        "references": int(references),
    }


def stock_by_category(db: Session) -> list[dict]:
    """Where the stock actually sits, by family."""
    rows = db.execute(
        select(
            func.coalesce(Category.name, "Non classe"),
            func.sum(Stock.quantity_available),
            func.count(Stock.part_id),
        )
        .select_from(Stock)
        .join(Part, Part.id == Stock.part_id)
        .outerjoin(Category, Category.id == Part.category_id)
        .group_by(Category.name)
        .order_by(func.sum(Stock.quantity_available).desc())
    ).all()

    total = sum(int(value or 0) for _, value, _ in rows) or 1
    return [
        {
            "label": str(label),
            "value": int(value or 0),
            "references": int(count),
            "share_percent": round(int(value or 0) / total * 100, 1),
        }
        for label, value, count in rows
    ]


# -------------------------------------------------------------------- quality
def quality_block(db: Session, window: dict) -> dict:
    """Conformity of what was received, and which references degrade it."""
    inspections = db.execute(
        select(Inspection)
        .where(
            Inspection.inspected_at >= window["start_at"],
            Inspection.inspected_at <= window["end_at"],
        )
        .order_by(Inspection.inspected_at)
    ).scalars().all()

    conform = sum(1 for row in inspections if row.result is InspectionResult.CONFORM)
    non_conform = len(inspections) - conform
    red_cage = db.execute(
        select(func.count()).select_from(Lot).where(Lot.status == LotStatus.RED_CAGE)
    ).scalar_one()

    conformity = round(conform / len(inspections) * 100, 1) if inspections else None

    # Daily conformity, only on days that actually had an inspection.
    per_day: dict[date, list[int]] = defaultdict(list)
    for row in inspections:
        per_day[to_local(row.inspected_at).date()].append(
            1 if row.result is InspectionResult.CONFORM else 0
        )
    trend = [
        {
            "date": day.isoformat(),
            "value": round(sum(values) / len(values) * 100, 1),
            "sample": len(values),
        }
        for day, values in sorted(per_day.items())
    ]

    # References that carry the defects, with the rate that makes them comparable.
    defect_rows = db.execute(
        select(
            Part.reference,
            Part.designation,
            func.sum(Inspection.defects_found),
            func.sum(Inspection.sample_size),
            func.count(Inspection.id),
        )
        .select_from(Inspection)
        .join(Lot, Lot.id == Inspection.lot_id)
        .join(Part, Part.id == Lot.part_id)
        .where(
            Inspection.inspected_at >= window["start_at"],
            Inspection.inspected_at <= window["end_at"],
        )
        .group_by(Part.reference, Part.designation)
        .having(func.sum(Inspection.defects_found) > 0)
        .order_by(func.sum(Inspection.defects_found).desc())
        .limit(8)
    ).all()

    top_defects = [
        {
            "reference": reference,
            "designation": designation,
            "defects": int(defects or 0),
            "inspected": int(sample or 0),
            "inspections": int(count),
            "rate_percent": round(int(defects or 0) / int(sample) * 100, 2) if sample else 0.0,
        }
        for reference, designation, defects, sample, count in defect_rows
    ]

    return {
        "conform": conform,
        "non_conform": non_conform,
        "red_cage": int(red_cage),
        "conformity_percent": conformity,
        "inspections": len(inspections),
        "trend": _downsample(trend),
        "top_defects": top_defects,
    }


# ------------------------------------------------------------------ warehouse
def warehouse_block(db: Session) -> dict:
    """Pressure on the racks: by zone for the decision, by cell for the detail."""
    warning = settings_service.get_float(db, "warehouse.warning_occupancy_percent")
    critical = settings_service.get_float(db, "warehouse.critical_occupancy_percent")

    locations = db.execute(
        select(WarehouseLocation).order_by(WarehouseLocation.zone, WarehouseLocation.position)
    ).scalars().all()

    # References held per location, so a zone can say what is inside it.
    reference_rows = db.execute(
        select(Lot.location_id, func.count(func.distinct(Lot.part_id)))
        .where(Lot.location_id.is_not(None), Lot.status == LotStatus.STORED)
        .group_by(Lot.location_id)
    ).all()
    references_per_location = {location_id: int(count) for location_id, count in reference_rows}

    zones: dict[str, dict] = {}
    heatmap: list[dict] = []

    for location in locations:
        zone = zones.setdefault(
            location.zone,
            {
                "zone": location.zone,
                "capacity": 0,
                "occupied": 0,
                "locations": 0,
                "references": 0,
                "saturated_locations": 0,
            },
        )
        zone["capacity"] += location.capacity
        zone["occupied"] += location.occupied
        zone["locations"] += 1
        zone["references"] += references_per_location.get(location.id, 0)
        if location.occupancy_percent >= critical:
            zone["saturated_locations"] += 1

        heatmap.append(
            {
                "zone": location.zone,
                "position": location.position,
                "code": location.code,
                "capacity": location.capacity,
                "occupied": location.occupied,
                "occupancy_percent": location.occupancy_percent,
                "references": references_per_location.get(location.id, 0),
                "severity": (
                    "CRITICAL"
                    if location.occupancy_percent >= critical
                    else "WARNING"
                    if location.occupancy_percent >= warning
                    else "OK"
                    if location.occupied
                    else "INFO"
                ),
            }
        )

    zone_rows = []
    for zone in zones.values():
        percent = round(zone["occupied"] / zone["capacity"] * 100, 1) if zone["capacity"] else 0.0
        zone_rows.append(
            {
                **zone,
                "free": zone["capacity"] - zone["occupied"],
                "occupancy_percent": percent,
                "severity": (
                    "CRITICAL" if percent >= critical
                    else "WARNING" if percent >= warning
                    else "OK"
                ),
            }
        )
    zone_rows.sort(key=lambda row: row["occupancy_percent"], reverse=True)

    total_capacity = sum(row["capacity"] for row in zone_rows)
    total_occupied = sum(row["occupied"] for row in zone_rows)

    return {
        "zones": zone_rows,
        "heatmap": heatmap,
        "total_capacity": total_capacity,
        "total_occupied": total_occupied,
        "occupancy_percent": (
            round(total_occupied / total_capacity * 100, 1) if total_capacity else 0.0
        ),
        "warning_threshold": warning,
        "critical_threshold": critical,
    }


# ----------------------------------------------------------------------- flow
def flow_block(db: Session) -> dict:
    """The six stages, the time between them, and where it jams."""
    stages = dashboard_service.build_stages(db)
    transitions = analytics_service.stage_durations(db)

    # Anomalies sitting at each stage, so a stage box can flag itself.
    lots = LotRepository(db)
    blocked = len(list(lots.in_stage([LotStatus.RED_CAGE])))
    anomalies = {
        "QUALITY": blocked,
        "INSPECTION": len(list(lots.in_stage([LotStatus.INSPECTION_IN_PROGRESS]))),
    }

    # SUPPLIER and RECEIVING count the same lots on Mission Control - one is the
    # origin, the other the desk. A funnel that shows the same figure twice
    # teaches nothing, so the funnel starts at RECEIVING: five boxes, and the
    # four measured transitions sit between them.
    stage_rows = [
        {
            "id": stage["id"],
            "lot_count": stage["lot_count"],
            "quantity": stage["quantity"],
            "severity": stage["severity"],
            "anomalies": anomalies.get(stage["id"], 0),
        }
        for stage in stages
        if stage["id"] != "SUPPLIER"
    ]

    # Keys rather than English labels: the screen is translated.
    transition_keys = ("receptionToInspection", "inspectionToQuality", "qualityToStorage", "storageToIssue")
    transition_rows = [
        {**row, "key": key}
        for row, key in zip(transitions, transition_keys)
    ]

    bottleneck = next((row for row in transition_rows if row["is_bottleneck"]), None)

    return {
        "stages": stage_rows,
        "transitions": transition_rows,
        "bottleneck": bottleneck["key"] if bottleneck else None,
        "bottleneck_hours": bottleneck["average_hours"] if bottleneck else None,
    }


# -------------------------------------------------------------------- scatter
def risk_scatter(db: Session) -> list[dict]:
    """Consumption against stock: the top-left corner is where lines stop."""
    points = []
    for row in stock_vs_demand(db, limit=1_000):
        if row["daily_consumption"] is None:
            continue
        points.append(
            {
                "part_id": row["part_id"],
                "reference": row["reference"],
                "daily_consumption": row["daily_consumption"],
                "available": row["available"],
                "demand": row["demand"],
                "coverage_days": row["coverage_days"],
                "risk": row["risk"],
            }
        )
    return points


# ----------------------------------------------------------------- production
def production_block(db: Session, window: dict) -> dict:
    """Demand raised, demand served, and what is still open."""
    requests = db.execute(
        select(ProductionRequest).where(
            ProductionRequest.created_on >= window["start_at"],
            ProductionRequest.created_on <= window["end_at"],
        )
    ).scalars().all()

    # A cancelled or rejected request was never meant to be served: leaving it
    # in the denominator would sink the service rate for a decision that was
    # deliberately taken, and hide a real supply problem behind it.
    servable = [
        row
        for row in requests
        if row.status
        not in (ProductionRequestStatus.CANCELLED, ProductionRequestStatus.REJECTED)
    ]
    requested = sum(row.quantity_requested for row in servable)
    issued = sum(row.quantity_issued for row in servable)

    by_status: dict[str, int] = defaultdict(int)
    for row in requests:
        by_status[row.status.value] += 1

    open_requests = ProductionRepository(db).open_requests()
    uncovered = []
    for request in open_requests:
        available = dashboard_service._stock_of(db, request.part_id)
        if available < request.quantity_requested:
            uncovered.append(
                {
                    "reference": request.reference,
                    "part_reference": request.part.reference,
                    "station": request.station.code,
                    "requested": request.quantity_requested,
                    "available": available,
                    "shortfall": request.quantity_requested - available,
                    "priority": request.priority,
                }
            )
    uncovered.sort(key=lambda row: (-row["shortfall"], row["priority"]))

    # Consumption per reference over the window, from the ledger.
    consumption_rows = db.execute(
        select(Part.reference, func.coalesce(func.sum(StockMovement.quantity), 0))
        .select_from(StockMovement)
        .join(Part, Part.id == StockMovement.part_id)
        .where(
            StockMovement.movement_type == MovementType.OUT,
            StockMovement.occurred_at >= window["start_at"],
            StockMovement.occurred_at <= window["end_at"],
        )
        .group_by(Part.reference)
        .order_by(func.coalesce(func.sum(StockMovement.quantity), 0).desc())
        .limit(10)
    ).all()

    return {
        "requested": int(requested),
        "issued": int(issued),
        "service_rate_percent": round(issued / requested * 100, 1) if requested else None,
        "by_status": [{"status": key, "count": value} for key, value in sorted(by_status.items())],
        "open_count": len(open_requests),
        "uncovered": uncovered[:8],
        "consumption": [
            {"reference": reference, "value": int(value)} for reference, value in consumption_rows
        ],
    }


# ------------------------------------------------------------------------ KPI
def _delta(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return round((current - previous) / abs(previous) * 100, 1)


def build_kpis(db: Session, window: dict, *, levels: list[dict], quality: dict) -> list[dict]:
    """Five figures. Any more and the eye stops ranking them."""
    stock_now = levels[-1]["stock"] if levels else 0
    stock_before = stock_at(db, window["start_at"])

    daily_consumption = db.execute(
        select(func.coalesce(func.sum(Part.average_daily_consumption), 0.0))
        .select_from(Stock)
        .join(Part, Part.id == Stock.part_id)
    ).scalar_one()
    coverage = round(stock_now / daily_consumption, 1) if daily_consumption else None
    coverage_before = (
        round(stock_before / daily_consumption, 1) if daily_consumption else None
    )

    # Conformity of the previous window, for the comparison.
    previous_inspections = db.execute(
        select(Inspection.result).where(
            Inspection.inspected_at >= window["previous_start_at"],
            Inspection.inspected_at <= window["previous_end_at"],
        )
    ).scalars().all()
    previous_conformity = (
        round(
            sum(1 for result in previous_inspections if result is InspectionResult.CONFORM)
            / len(previous_inspections)
            * 100,
            1,
        )
        if previous_inspections
        else None
    )

    blocked = quality["red_cage"]
    blocked_quantity = db.execute(
        select(func.coalesce(func.sum(Lot.quantity_received), 0)).where(
            Lot.status == LotStatus.RED_CAGE
        )
    ).scalar_one()

    # Lots that entered the Red Cage each day - a real series, not a guess.
    red_cage_events = db.execute(
        select(AuditLog.occurred_at).where(
            AuditLog.action == AuditAction.QUALITY_RED_CAGE,
            AuditLog.occurred_at >= window["start_at"],
            AuditLog.occurred_at <= window["end_at"],
        )
    ).scalars().all()
    per_day: dict[date, int] = defaultdict(int)
    for occurred_at in red_cage_events:
        per_day[to_local(occurred_at).date()] += 1
    blocked_trend = [
        {"date": day.isoformat(), "value": per_day.get(day, 0)}
        for day in _days_between(window["start_date"], window["end_date"])
    ]

    production = ProductionRepository(db)
    at_risk = 0
    for request in production.open_requests():
        if dashboard_service._stock_of(db, request.part_id) < request.quantity_requested:
            at_risk += 1

    stock_trend = [{"date": row["date"], "value": row["stock"]} for row in levels]
    coverage_trend = (
        [
            {"date": row["date"], "value": round(row["stock"] / daily_consumption, 1)}
            for row in levels
        ]
        if daily_consumption
        else []
    )

    return [
        {
            "id": "stock-total",
            "value": float(stock_now),
            "unit": "pcs",
            "decimals": 0,
            "delta_percent": _delta(stock_now, stock_before),
            "severity": "OK" if stock_now > 0 else "WARNING",
            "trend": _downsample(stock_trend),
            "context_key": "kpi.context.references",
            "context_value": db.execute(select(func.count()).select_from(Stock)).scalar_one(),
        },
        {
            "id": "coverage",
            "value": coverage,
            "unit": "days",
            "decimals": 1,
            "delta_percent": _delta(coverage, coverage_before),
            "severity": (
                "OK" if coverage is None or coverage >= 5
                else "WARNING" if coverage >= 2
                else "CRITICAL"
            ),
            "trend": _downsample(coverage_trend),
            "context_key": "kpi.context.dailyConsumption",
            "context_value": round(daily_consumption, 1),
        },
        {
            "id": "conformity",
            "value": quality["conformity_percent"],
            "unit": "%",
            "decimals": 1,
            "delta_percent": _delta(quality["conformity_percent"], previous_conformity),
            "severity": (
                "OK" if quality["conformity_percent"] is None
                or quality["conformity_percent"] >= 95
                else "WARNING" if quality["conformity_percent"] >= 90
                else "CRITICAL"
            ),
            "trend": _downsample(
                [{"date": row["date"], "value": row["value"]} for row in quality["trend"]]
            ),
            "context_key": "kpi.context.inspections",
            "context_value": quality["inspections"],
        },
        {
            "id": "blocked-lots",
            "value": float(blocked),
            "unit": None,
            "decimals": 0,
            "delta_percent": None,
            "severity": "CRITICAL" if blocked else "OK",
            "trend": _downsample(blocked_trend),
            "context_key": "kpi.context.blockedQuantity",
            "context_value": int(blocked_quantity),
        },
        {
            "id": "production-risk",
            "value": float(at_risk),
            "unit": None,
            "decimals": 0,
            "delta_percent": None,
            # No honest daily series exists for this one: it is a snapshot of
            # open requests against the stock as it stands now.
            "severity": "CRITICAL" if at_risk else "OK",
            "trend": [],
            "context_key": "kpi.context.openRequests",
            "context_value": len(production.open_requests()),
        },
    ]


# ------------------------------------------------------------------ decisions
def _shortage_reason(risk: dict) -> dict:
    """Why this reference is at risk, as a key the interface translates.

    The wording is rebuilt from the same figures the assessment used, so the
    card says exactly what the English rationale says - in the reader's
    language. The rationale itself stays where it belongs: the audit trail and
    the copilot, which quote it verbatim.
    """
    available = risk["stock_available"]
    demand = risk["open_demand"]
    cover = risk["days_of_cover"]
    incoming = risk["incoming_quantity"]

    if demand > available:
        payload = {
            "reason_key": "decision.reason.shortfall",
            "reason_values": {
                "demand": demand,
                "stock": available,
                "shortfall": demand - available,
            },
        }
    elif risk["safety_stock"] and available < risk["safety_stock"]:
        payload = {
            "reason_key": "decision.reason.belowSafety",
            "reason_values": {"stock": available, "safety": risk["safety_stock"]},
        }
    elif cover is not None:
        payload = {
            "reason_key": "decision.reason.thinCover",
            "reason_values": {"days": cover},
        }
    else:
        payload = {
            "reason_key": "decision.reason.watch",
            "reason_values": {"stock": available, "demand": demand},
        }

    # Goods already on site change the answer, so they are part of the reason.
    if incoming:
        payload["reason_key"] += "WithIncoming"
        payload["reason_values"]["incoming"] = incoming
    return payload


def _blocked_reason(db: Session, lot) -> dict:
    """Why this lot is in the Red Cage, from its own figures.

    `lot.blocked_reason` is a stored record written by the services in one
    fixed language. It is the right thing to show on the Quality screen, where
    it is the recorded justification; on a translated dashboard it would be the
    only English sentence on the page, so the card restates it from the
    inspection instead.
    """
    inspection = db.execute(
        select(Inspection)
        .where(Inspection.lot_id == lot.id)
        .order_by(Inspection.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    if inspection is not None and inspection.result is not InspectionResult.CONFORM:
        return {
            "reason_key": "decision.reason.nonConform",
            "reason_values": {
                "defects": inspection.defects_found,
                "sample": inspection.sample_size,
                "rate": inspection.defect_rate_percent,
                "threshold": inspection.defect_threshold_percent,
            },
        }

    gap = lot.quantity_received - lot.quantity_expected
    if gap:
        return {
            "reason_key": "decision.reason.quantityGap",
            "reason_values": {
                "expected": lot.quantity_expected,
                "received": lot.quantity_received,
                "gap": gap,
            },
        }

    return {"reason_key": "decision.reason.blocked", "reason_values": {}}


def decisions(db: Session, *, warehouse: dict, limit: int = 6) -> list[dict]:
    """What to do first, built from the same data the charts show.

    Each entry carries its figures and its reason: a recommendation without the
    numbers behind it is an opinion, and an operator is right to ignore it.
    """
    items: list[dict] = []

    # 1. References about to stop a line, from the shortage assessment.
    for risk in ai_service.shortage_risks(db, only_at_risk=True)[:4]:
        items.append(
            {
                "kind": "SHORTAGE_RISK",
                "severity": "CRITICAL" if risk["risk_level"].value == "HIGH" else "WARNING",
                "subject": risk["part_reference"],
                "subject_id": risk["part_id"],
                "target": "stock",
                "metrics": [
                    {"key": "metric.stock", "value": risk["stock_available"]},
                    {"key": "metric.demand", "value": risk["open_demand"]},
                    {
                        "key": "metric.coverage",
                        "value": risk["days_of_cover"],
                        "unit": "days",
                    },
                ],
                **_shortage_reason(risk),
                "action_key": "action.checkIncoming",
            }
        )

    # 2. Zones that will refuse the next pallet.
    for zone in warehouse["zones"]:
        if zone["severity"] != "CRITICAL":
            continue
        items.append(
            {
                "kind": "WAREHOUSE_SATURATION",
                "severity": "WARNING",
                "subject": f"ZONE {zone['zone']}",
                "subject_id": None,
                "target": "warehouse",
                "metrics": [
                    {"key": "metric.occupancy", "value": zone["occupancy_percent"], "unit": "%"},
                    {"key": "metric.free", "value": zone["free"], "unit": "pcs"},
                    {"key": "metric.locations", "value": zone["locations"]},
                ],
                "reason_key": "decision.reason.saturation",
                "reason_values": {
                    "percent": zone["occupancy_percent"],
                    "free": zone["free"],
                },
                "action_key": "action.prepareSecondary",
            }
        )
        if len(items) >= limit:
            break

    # 3. Lots waiting for a quality decision they cannot leave without.
    for lot in list(LotRepository(db).in_stage([LotStatus.RED_CAGE]))[:3]:
        items.append(
            {
                "kind": "BLOCKED_LOT",
                "severity": "CRITICAL",
                "subject": lot.lot_number,
                "subject_id": lot.id,
                "target": "quality",
                "metrics": [
                    {"key": "metric.quantity", "value": lot.quantity_received, "unit": "pcs"},
                    {"key": "metric.reference", "value": lot.part.reference},
                ],
                **_blocked_reason(db, lot),
                "action_key": "action.qualityDecision",
            }
        )

    rank = {"CRITICAL": 0, "WARNING": 1, "INFO": 2}
    items.sort(key=lambda item: rank.get(item["severity"], 9))

    shortlist = items[:limit]
    for index, item in enumerate(shortlist, start=1):
        item["rank"] = index
        # Every entry carries both reason shapes: a sentence the backend built,
        # or a key the interface translates. Emitting one or the other would
        # make every consumer guess which one it got.
        item.setdefault("reason", None)
        item.setdefault("reason_key", None)
        item.setdefault("reason_values", {})
    return shortlist


# ---------------------------------------------------------------- histogram
#: Upper bound of each bucket, in hours. The last bucket is open-ended.
LEAD_TIME_BUCKETS = (2, 4, 8, 12, 24, 48)

#: Below this many measured lots a distribution says more about the sample than
#: about the plant, so the screen is told to show nothing rather than a shape.
MIN_DISTRIBUTION_SAMPLE = 8


def lead_time_distribution(db: Session, window: dict) -> dict:
    """How long a lot takes from the receiving desk to the shelf.

    An average hides the tail: two lots at thirty hours and forty at two look
    the same as forty-two lots at three. The distribution is what shows the
    tail, and the tail is what a manager can act on.
    """
    rows = db.execute(
        select(AuditLog.lot_id, AuditLog.action, AuditLog.occurred_at)
        .where(
            AuditLog.lot_id.is_not(None),
            AuditLog.action.in_([AuditAction.LOT_RECEIVED, AuditAction.STORAGE_CONFIRMED]),
            AuditLog.occurred_at >= window["start_at"],
            AuditLog.occurred_at <= window["end_at"],
        )
        .order_by(AuditLog.occurred_at)
    ).all()

    received: dict[int, datetime] = {}
    durations: list[float] = []
    for lot_id, action, occurred_at in rows:
        if action is AuditAction.LOT_RECEIVED:
            received[lot_id] = occurred_at
        elif lot_id in received:
            hours = (as_utc(occurred_at) - as_utc(received.pop(lot_id))).total_seconds() / 3600.0
            if hours >= 0:
                durations.append(hours)

    if len(durations) < MIN_DISTRIBUTION_SAMPLE:
        return {"buckets": [], "sample_size": len(durations), "median_hours": None}

    counts = [0] * (len(LEAD_TIME_BUCKETS) + 1)
    for value in durations:
        for index, bound in enumerate(LEAD_TIME_BUCKETS):
            if value < bound:
                counts[index] += 1
                break
        else:
            counts[-1] += 1

    buckets = []
    lower = 0.0
    for index, bound in enumerate(LEAD_TIME_BUCKETS):
        buckets.append({"from_hours": lower, "to_hours": float(bound), "count": counts[index]})
        lower = float(bound)
    buckets.append({"from_hours": lower, "to_hours": None, "count": counts[-1]})

    ordered = sorted(durations)
    middle = len(ordered) // 2
    median = (
        ordered[middle]
        if len(ordered) % 2
        else (ordered[middle - 1] + ordered[middle]) / 2
    )

    return {
        "buckets": buckets,
        "sample_size": len(durations),
        "median_hours": round(median, 2),
    }


# ------------------------------------------------------------------- matrix
def part_zone_matrix(db: Session, limit: int = 10) -> dict:
    """Which reference sits in which zone, and how much of it.

    Answers the question a bar chart cannot: a reference held entirely in one
    saturated zone is a different problem from the same quantity spread over
    three.
    """
    rows = db.execute(
        select(
            Part.reference,
            Part.designation,
            WarehouseLocation.zone,
            func.sum(Lot.quantity_available),
        )
        .select_from(Lot)
        .join(Part, Part.id == Lot.part_id)
        .join(WarehouseLocation, WarehouseLocation.id == Lot.location_id)
        .where(Lot.status == LotStatus.STORED, Lot.quantity_available > 0)
        .group_by(Part.reference, Part.designation, WarehouseLocation.zone)
    ).all()

    if not rows:
        return {"zones": [], "rows": []}

    zones = sorted({zone for _, _, zone, _ in rows})

    per_part: dict[str, dict] = {}
    for reference, designation, zone, quantity in rows:
        entry = per_part.setdefault(
            reference,
            {"reference": reference, "designation": designation, "total": 0, "cells": {}},
        )
        entry["cells"][zone] = int(quantity or 0)
        entry["total"] += int(quantity or 0)

    # The risk verdict already computed for the same references, so the matrix
    # and the priority table cannot disagree.
    risk_by_reference = {
        row["reference"]: row["risk"] for row in stock_vs_demand(db, limit=1_000)
    }

    ordered = sorted(per_part.values(), key=lambda row: -row["total"])[:limit]
    return {
        "zones": zones,
        "rows": [
            {
                "reference": row["reference"],
                "designation": row["designation"],
                "total": row["total"],
                "risk": risk_by_reference.get(row["reference"], "OK"),
                "cells": [
                    {"zone": zone, "quantity": row["cells"].get(zone, 0)} for zone in zones
                ],
            }
            for row in ordered
        ],
    }


# ------------------------------------------------------------------- dwell
def zone_dwell(db: Session) -> list[dict]:
    """Occupancy against how long the parts have been sitting there.

    A zone that is full and slow is congested; full and fast is simply busy.
    One number cannot tell those apart, which is why they go on two axes.
    """
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(WarehouseLocation.zone, Lot.stored_at, Lot.quantity_available)
        .select_from(Lot)
        .join(WarehouseLocation, WarehouseLocation.id == Lot.location_id)
        .where(Lot.status == LotStatus.STORED, Lot.stored_at.is_not(None))
    ).all()

    per_zone: dict[str, list[float]] = defaultdict(list)
    quantities: dict[str, int] = defaultdict(int)
    for zone, stored_at, quantity in rows:
        per_zone[zone].append((now - as_utc(stored_at)).total_seconds() / 86400.0)
        quantities[zone] += int(quantity or 0)

    occupancy = {
        row["zone"]: row for row in warehouse_block(db)["zones"]
    }

    points = []
    for zone, ages in sorted(per_zone.items()):
        zone_row = occupancy.get(zone)
        if zone_row is None:
            continue
        points.append(
            {
                "zone": zone,
                "occupancy_percent": zone_row["occupancy_percent"],
                "average_days": round(sum(ages) / len(ages), 1),
                "lots": len(ages),
                "quantity": quantities[zone],
                "severity": zone_row["severity"],
            }
        )
    return points


# ------------------------------------------------------------------- assembly
def build_overview(
    db: Session,
    *,
    period: str = "7d",
    date_from: date | None = None,
    date_to: date | None = None,
) -> dict:
    """One payload for the whole Logistics Overview screen."""
    window = resolve_window(period, date_from, date_to)

    levels = stock_level_series(db, window)
    quality = quality_block(db, window)
    warehouse = warehouse_block(db)

    return {
        "generated_at": datetime.now(timezone.utc),
        "period": {
            "key": window["key"],
            "start_date": window["start_date"],
            "end_date": window["end_date"],
            "days": window["days"],
        },
        "kpis": build_kpis(db, window, levels=levels, quality=quality),
        "stock_trend": _downsample(levels),
        "stock_waterfall": stock_waterfall(db, window),
        "stock_totals": stock_totals(db),
        "stock_by_category": stock_by_category(db),
        "stock_vs_demand": stock_vs_demand(db),
        "risk_scatter": risk_scatter(db),
        "quality": quality,
        "warehouse": warehouse,
        "lead_time_distribution": lead_time_distribution(db, window),
        "part_zone_matrix": part_zone_matrix(db),
        "zone_dwell": zone_dwell(db),
        "flow": flow_block(db),
        "production": production_block(db, window),
        "decisions": decisions(db, warehouse=warehouse),
    }
