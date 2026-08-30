"""Mission Control aggregation.

Everything the main screen shows is computed here from real data: KPIs, the six
flow stages, smart alerts and the activity feed. No figure is hardcoded.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.timeutils import to_local
from app.models.enums import AuditAction, LotStatus, ProductionRequestStatus
from app.models.flow import Lot
from app.models.production import ProductionRequest
from app.repositories import (
    AuditRepository,
    LotRepository,
    ProductionRepository,
    StockRepository,
)
from app.services import settings_service, warehouse_service

#: Lot statuses mapped onto the six visual stages of the flow.
STAGE_DEFINITION: tuple[tuple[str, str, str, tuple[LotStatus, ...]], ...] = (
    ("SUPPLIER", "Supplier", "Inbound deliveries", ()),
    ("RECEIVING", "Receiving", "Quantity check", (LotStatus.PENDING_INSPECTION,)),
    ("INSPECTION", "Inspection", "Sampling in progress", (LotStatus.INSPECTION_IN_PROGRESS,)),
    ("QUALITY", "Quality", "Awaiting decision", (LotStatus.QUALITY_PENDING, LotStatus.APPROVED)),
    ("WAREHOUSE", "Warehouse", "Stored and available", (LotStatus.STORED,)),
    ("PRODUCTION", "Production", "Consumed by the lines", (LotStatus.CONSUMED,)),
)

#: Lot statuses considered "in flow" (not yet stored, not terminal).
IN_FLOW_STATUSES = (
    LotStatus.PENDING_INSPECTION,
    LotStatus.INSPECTION_IN_PROGRESS,
    LotStatus.QUALITY_PENDING,
    LotStatus.APPROVED,
    LotStatus.RED_CAGE,
)

_ACTION_LABELS: dict[AuditAction, tuple[str, str]] = {
    AuditAction.LOT_RECEIVED: ("Lot received", "INFO"),
    AuditAction.INSPECTION_STARTED: ("Inspection started", "INFO"),
    AuditAction.INSPECTION_RECORDED: ("Inspection recorded", "INFO"),
    AuditAction.QUALITY_APPROVED: ("Quality approved", "OK"),
    AuditAction.QUALITY_REJECTED: ("Quality rejected", "CRITICAL"),
    AuditAction.QUALITY_RED_CAGE: ("Sent to Red Cage", "CRITICAL"),
    AuditAction.RED_CAGE_RELEASED: ("Released from Red Cage", "OK"),
    AuditAction.RED_CAGE_SCRAPPED: ("Scrapped from Red Cage", "CRITICAL"),
    AuditAction.STORAGE_CONFIRMED: ("Storage confirmed", "OK"),
    AuditAction.STOCK_INCREMENTED: ("Stock incremented", "OK"),
    AuditAction.STOCK_DECREMENTED: ("Stock issued", "INFO"),
    AuditAction.REQUEST_CREATED: ("Production request created", "INFO"),
    AuditAction.REQUEST_SUBMITTED: ("Request submitted", "INFO"),
    AuditAction.REQUEST_APPROVED: ("Request approved", "OK"),
    AuditAction.REQUEST_REJECTED: ("Request rejected", "CRITICAL"),
    AuditAction.REQUEST_PREPARING: ("Preparation started", "INFO"),
    AuditAction.REQUEST_READY: ("Ready for issue", "INFO"),
    AuditAction.REQUEST_ISSUED: ("Parts issued", "OK"),
    AuditAction.REQUEST_CANCELLED: ("Request cancelled", "WARNING"),
    AuditAction.SETTING_UPDATED: ("Setting updated", "INFO"),
    AuditAction.SIMULATION_RUN: ("Simulation executed", "INFO"),
}


def describe_action(action: AuditAction) -> tuple[str, str]:
    return _ACTION_LABELS.get(action, (action.value.replace("_", " ").title(), "INFO"))


def build_kpis(db: Session) -> list[dict]:
    """The six Mission Control indicators, all computed from live data."""
    lots = LotRepository(db)
    stock = StockRepository(db)
    production = ProductionRepository(db)

    counts = lots.count_by_status()
    total_stock = stock.total_quantity()
    distinct_parts = db.execute(
        select(func.count()).select_from(
            select(Lot.part_id).distinct().subquery()
        )
    ).scalar_one()

    active_lots = sum(
        counts.get(status.value, 0)
        for status in (
            LotStatus.PENDING_INSPECTION,
            LotStatus.INSPECTION_IN_PROGRESS,
            LotStatus.QUALITY_PENDING,
            LotStatus.APPROVED,
            LotStatus.STORED,
        )
    )
    pending_inspections = counts.get(LotStatus.PENDING_INSPECTION.value, 0) + counts.get(
        LotStatus.INSPECTION_IN_PROGRESS.value, 0
    )
    red_cage = counts.get(LotStatus.RED_CAGE.value, 0)

    open_requests = production.open_requests()
    blocked_requests = [
        request
        for request in open_requests
        if _stock_of(db, request.part_id) < request.quantity_requested
    ]

    occupancy = warehouse_service.occupancy_overview(db)
    critical_alerts = red_cage + len(blocked_requests) + len(occupancy["saturated"])

    stored_lots = counts.get(LotStatus.STORED.value, 0)

    return [
        {
            "id": "total-stock",
            "label": "Total Stock",
            "value": total_stock,
            "unit": "PCS",
            "hint": f"{distinct_parts} part references in circulation",
            "severity": "OK" if total_stock > 0 else "WARNING",
        },
        {
            "id": "active-lots",
            "label": "Active Lots",
            "value": active_lots,
            "unit": None,
            "hint": f"{active_lots - stored_lots} in flow · {stored_lots} stored",
            "severity": "INFO",
        },
        {
            "id": "pending-inspections",
            "label": "Pending Inspections",
            "value": pending_inspections,
            "unit": None,
            "hint": (
                f"{counts.get(LotStatus.QUALITY_PENDING.value, 0)} awaiting quality decision"
            ),
            "severity": "WARNING" if pending_inspections else "OK",
        },
        {
            "id": "production-requests",
            "label": "Production Requests",
            "value": len(open_requests),
            "unit": None,
            "hint": (
                f"{len(blocked_requests)} not covered by stock"
                if blocked_requests
                else "all covered by available stock"
            ),
            "severity": "CRITICAL" if blocked_requests else "INFO",
        },
        {
            "id": "warehouse-occupancy",
            "label": "Warehouse Occupancy",
            "value": occupancy["occupancy_percent"],
            "unit": "%",
            "hint": (
                f"{len(occupancy['saturated'])} saturated · "
                f"{len(occupancy['nearly_full'])} nearly full"
            ),
            "severity": (
                "CRITICAL"
                if occupancy["saturated"]
                else "WARNING"
                if occupancy["nearly_full"]
                else "OK"
            ),
            "ratio": occupancy["occupancy_percent"],
        },
        {
            "id": "critical-alerts",
            "label": "Critical Alerts",
            "value": critical_alerts,
            "unit": None,
            "hint": (
                f"{red_cage} in Red Cage · {len(blocked_requests)} blocked requests"
                if critical_alerts
                else "no critical situation"
            ),
            "severity": "CRITICAL" if critical_alerts else "OK",
        },
    ]


def _stock_of(db: Session, part_id: int) -> int:
    from app.services import stock_service

    return stock_service.get_available(db, part_id)


def build_stages(db: Session) -> list[dict]:
    """The six stages with the lots physically sitting at each of them."""
    lots = LotRepository(db)
    stages: list[dict] = []

    for stage_id, label, caption, statuses in STAGE_DEFINITION:
        if stage_id == "SUPPLIER":
            # Inbound = everything received today but not yet inspected.
            stage_lots = list(lots.in_stage([LotStatus.PENDING_INSPECTION]))
            quantity = sum(lot.quantity_received for lot in stage_lots)
            stages.append(
                {
                    "id": stage_id,
                    "label": label,
                    "caption": f"{len(stage_lots)} inbound deliveries",
                    "lot_count": len(stage_lots),
                    "quantity": quantity,
                    "severity": "INFO",
                    "lots": [],
                }
            )
            continue

        stage_lots = list(lots.in_stage(list(statuses))) if statuses else []
        quantity = sum(
            lot.quantity_available if lot.status is LotStatus.STORED else lot.quantity_received
            for lot in stage_lots
        )
        severity = "OK"
        if any(lot.status is LotStatus.QUALITY_PENDING for lot in stage_lots):
            severity = "WARNING"
        if stage_id in ("RECEIVING", "INSPECTION") and stage_lots:
            severity = "INFO"

        if stage_id == "PRODUCTION":
            issued = db.execute(
                select(func.coalesce(func.sum(ProductionRequest.quantity_issued), 0)).where(
                    ProductionRequest.status == ProductionRequestStatus.ISSUED
                )
            ).scalar_one()
            open_count = len(ProductionRepository(db).open_requests())
            stages.append(
                {
                    "id": stage_id,
                    "label": label,
                    "caption": f"{open_count} open requests",
                    "lot_count": open_count,
                    "quantity": int(issued),
                    "severity": "OK",
                    "lots": [],
                }
            )
            continue

        stages.append(
            {
                "id": stage_id,
                "label": label,
                "caption": caption,
                "lot_count": len(stage_lots),
                "quantity": quantity,
                "severity": severity,
                "lots": stage_lots[:4],
            }
        )

    return stages


SEVERITY_ORDER = {"CRITICAL": 0, "WARNING": 1, "INFO": 2, "OK": 3}

#: Business priority inside one severity level. A blocked lot and an uncovered
#: request stop the line; a saturated rack is a housekeeping problem.
KIND_ORDER = {
    "RED_CAGE": 0,
    "REQUEST_UNCOVERED": 1,
    "SAFETY_STOCK": 2,
    "QUALITY_PENDING": 3,
    "LOCATION_SATURATED": 4,
    "LOCATION_FILLING": 5,
    "MORE": 8,
}


def build_alerts(db: Session) -> list[dict]:
    """Smart alerts derived from the real state of the system."""
    alerts: list[dict] = []
    now = datetime.now(timezone.utc)

    lots = LotRepository(db)
    production = ProductionRepository(db)
    stocks = StockRepository(db)

    # 1. Blocked lots (Red Cage) - critical.
    for lot in lots.in_stage([LotStatus.RED_CAGE]):
        alerts.append(
            {
                "id": f"redcage-{lot.id}",
                "kind": "RED_CAGE",
                "severity": "CRITICAL",
                "title": "Lot blocked in Red Cage",
                "message": lot.blocked_reason
                or f"{lot.lot_number} is quarantined and waiting for a decision.",
                "source": f"Quality · {lot.part.reference}",
                "timestamp": lot.updated_at or now,
                "lot_number": lot.lot_number,
                "part_reference": lot.part.reference,
                "location_code": None,
            }
        )

    # 2. Production requests not covered by available stock - critical.
    for request in production.open_requests():
        available = _stock_of(db, request.part_id)
        if available < request.quantity_requested:
            alerts.append(
                {
                    "id": f"request-{request.id}",
                "kind": "REQUEST_UNCOVERED",
                    "severity": "CRITICAL",
                    "title": "Production request not covered",
                    "message": (
                        f"{request.part.reference} stock ({available}) is below the "
                        f"{request.quantity_requested} required by {request.reference}."
                    ),
                    "source": f"Production · {request.station.code}",
                    "timestamp": request.created_on,
                    "lot_number": None,
                    "part_reference": request.part.reference,
                    "location_code": None,
                }
            )

    # 3. Parts below safety stock - warning.
    for stock in stocks.all_with_parts():
        if stock.part.safety_stock and stock.quantity_available < stock.part.safety_stock:
            alerts.append(
                {
                    "id": f"safety-{stock.part_id}",
                "kind": "SAFETY_STOCK",
                    "severity": "WARNING",
                    "title": "Stock below safety level",
                    "message": (
                        f"{stock.part.reference}: {stock.quantity_available} units available "
                        f"for a safety stock of {stock.part.safety_stock}."
                    ),
                    "source": "Warehouse",
                    "timestamp": stock.last_movement_at or now,
                    "lot_number": None,
                    "part_reference": stock.part.reference,
                    "location_code": None,
                }
            )

    # 4. Lots waiting for a quality decision - warning.
    for lot in lots.in_stage([LotStatus.QUALITY_PENDING]):
        alerts.append(
            {
                "id": f"quality-{lot.id}",
                "kind": "QUALITY_PENDING",
                "severity": "WARNING",
                "title": "Quality decision pending",
                "message": f"{lot.lot_number} is waiting for quality validation.",
                "source": "Quality",
                "timestamp": lot.updated_at or now,
                "lot_number": lot.lot_number,
                "part_reference": lot.part.reference,
                "location_code": None,
            }
        )

    # 5. Warehouse saturation - critical / info.
    occupancy = warehouse_service.occupancy_overview(db)
    for location in occupancy["saturated"]:
        alerts.append(
            {
                "id": f"loc-{location.id}",
                "kind": "LOCATION_SATURATED",
                "severity": "CRITICAL",
                "title": "Location saturated",
                "message": (
                    f"{location.code} is at {location.occupancy_percent}% "
                    f"({location.occupied}/{location.capacity})."
                ),
                "source": "Warehouse",
                "timestamp": now,
                "lot_number": None,
                "part_reference": None,
                "location_code": location.code,
            }
        )
    for location in occupancy["nearly_full"]:
        alerts.append(
            {
                "id": f"loc-{location.id}",
                "kind": "LOCATION_FILLING",
                "severity": "INFO",
                "title": "Location filling up",
                "message": f"{location.code} occupancy is {location.occupancy_percent}%.",
                "source": "Warehouse",
                "timestamp": now,
                "lot_number": None,
                "part_reference": None,
                "location_code": location.code,
            }
        )

    alerts.sort(
        key=lambda alert: (
            SEVERITY_ORDER.get(alert["severity"], 9),
            KIND_ORDER.get(alert.get("kind", ""), 9),
            alert["id"],
        )
    )
    return alerts


def top_alerts(alerts: list[dict], *, limit: int = 8) -> list[dict]:
    """The shortlist shown on Mission Control.

    A plant with thirty blocked lots and eight saturated racks produces far more
    alerts than a panel can hold. Taking the first eight by severity would fill
    the panel with one repeated situation and hide every other one, so the
    shortlist walks the kinds in turn - most serious kind first - and gives each
    one a slot before any kind gets a second. Whatever does not fit is counted
    on a final line rather than dropped silently.
    """
    if len(alerts) <= limit:
        return alerts

    buckets: dict[str, list[dict]] = {}
    for alert in alerts:
        buckets.setdefault(alert.get("kind", "OTHER"), []).append(alert)

    # Kinds in the order they already carry: severity of their first alert,
    # then business priority.
    kinds = sorted(
        buckets,
        key=lambda kind: (
            SEVERITY_ORDER.get(buckets[kind][0]["severity"], 9),
            KIND_ORDER.get(kind, 9),
        ),
    )

    # One slot is kept for the "and N more" line, since we know there is a tail.
    room = max(1, limit - 1)
    shown: list[dict] = []
    round_index = 0
    while len(shown) < room and any(len(buckets[kind]) > round_index for kind in kinds):
        for kind in kinds:
            if len(shown) >= room:
                break
            if len(buckets[kind]) > round_index:
                shown.append(buckets[kind][round_index])
        round_index += 1

    shown_ids = {alert["id"] for alert in shown}
    remaining = [alert for alert in alerts if alert["id"] not in shown_ids]
    if remaining:
        breakdown: dict[str, int] = {}
        for alert in remaining:
            breakdown[alert["title"]] = breakdown.get(alert["title"], 0) + 1
        detail = ", ".join(
            f"{count} x {title}" for title, count in sorted(breakdown.items())
        )
        worst = min(remaining, key=lambda a: SEVERITY_ORDER.get(a["severity"], 9))
        shown.append(
            {
                "id": "more-alerts",
                "kind": "MORE",
                "severity": worst["severity"],
                "title": f"{len(remaining)} autres alertes",
                "message": f"Non affichees ici: {detail}.",
                "source": "Supervision",
                "timestamp": worst["timestamp"],
                "lot_number": None,
                "part_reference": None,
                "location_code": None,
            }
        )

    shown.sort(
        key=lambda alert: (
            SEVERITY_ORDER.get(alert["severity"], 9),
            KIND_ORDER.get(alert.get("kind", ""), 9),
            alert["id"],
        )
    )
    return shown[:limit]


def build_activity(db: Session, limit: int = 12) -> list[dict]:
    """Recent operator actions, straight from the audit trail."""
    entries = AuditRepository(db).recent(limit=limit)
    activity: list[dict] = []

    for entry in entries:
        label, severity = describe_action(entry.action)
        occurred = entry.occurred_at
        activity.append(
            {
                "id": entry.id,
                "time": to_local(occurred).strftime("%H:%M"),
                "action": entry.action.value,
                "label": label,
                "detail": entry.reason or entry.entity_reference or "",
                "severity": severity,
                "actor_name": entry.actor_name,
                "occurred_at": occurred,
                "lot_number": entry.lot.lot_number if entry.lot else None,
            }
        )
    return activity


def build_dashboard(db: Session) -> dict:
    """One payload for the whole Mission Control screen."""
    settings_service.ensure_defaults(db)
    lots = LotRepository(db)
    alerts = build_alerts(db)
    critical = [alert for alert in alerts if alert["severity"] == "CRITICAL"]

    return {
        "generated_at": datetime.now(timezone.utc),
        "system_status": "DEGRADED" if critical else "OPERATIONAL",
        "kpis": build_kpis(db),
        "stages": build_stages(db),
        "lots_in_flow": list(lots.in_stage(list(IN_FLOW_STATUSES)))[:12],
        "alerts": top_alerts(alerts),
        "activity": build_activity(db),
    }
