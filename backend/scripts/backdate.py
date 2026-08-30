"""Spread the seeded history over the past days.

The seed replays the whole flow through the services, which stamps every event
with "now". That is correct but useless for analytics: every lead time would be
zero and the activity feed would show one identical timestamp.

This module rewrites the timestamps of the seeded history so the demonstration
has a credible chronology - lots arriving over the past days, each one moving
through reception, inspection, quality and storage with realistic gaps.

Only ever run against demonstration data.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.flow import Inspection, Lot, QualityValidation, Reception
from app.models.production import ProductionRequest
from app.models.system import AuditLog
from app.models.warehouse import StockMovement

#: Minutes after the lot arrival at which each milestone happened.
MILESTONE_OFFSET_MINUTES: dict[AuditAction, int] = {
    AuditAction.LOT_RECEIVED: 0,
    AuditAction.INSPECTION_STARTED: 45,
    AuditAction.INSPECTION_RECORDED: 70,
    AuditAction.QUALITY_APPROVED: 155,
    AuditAction.QUALITY_REJECTED: 155,
    AuditAction.QUALITY_RED_CAGE: 155,
    AuditAction.RED_CAGE_RELEASED: 260,
    AuditAction.RED_CAGE_SCRAPPED: 260,
    AuditAction.STORAGE_CONFIRMED: 215,
    AuditAction.STOCK_INCREMENTED: 215,
}

#: Hours between two consecutive seeded lots. Sized so the seeded history
#: spans roughly six weeks: long enough for the month and year reports, short
#: enough that the "today" and "this week" reports are not empty.
HOURS_BETWEEN_LOTS = 4


def _utc(value: datetime) -> datetime:
    """Return an aware UTC datetime.

    Timezone-aware values are required: PostgreSQL columns are TIMESTAMP WITH
    TIME ZONE, and inserting a naive value there would be interpreted in the
    session timezone, shifting the whole seeded history. SQLite accepts aware
    values and stores the UTC wall time, so this is correct on both engines.
    """
    return value.astimezone(timezone.utc)


def backdate(db: Session) -> dict:
    """Rewrite seeded timestamps into a realistic chronology."""
    now = datetime.now(timezone.utc)
    lots = list(db.execute(select(Lot).order_by(Lot.id)).scalars())
    if not lots:
        return {"lots": 0, "events": 0}

    total_events = 0

    for index, lot in enumerate(lots):
        # Oldest lot first, most recent lot a couple of hours ago.
        age_hours = (len(lots) - index) * HOURS_BETWEEN_LOTS
        base = now - timedelta(hours=age_hours)

        lot.received_at = _utc(base)
        lot.created_at = _utc(base)

        entries = list(
            db.execute(
                select(AuditLog).where(AuditLog.lot_id == lot.id).order_by(AuditLog.id)
            ).scalars()
        )

        last_at = base
        for position, entry in enumerate(entries):
            if entry.action is AuditAction.STOCK_DECREMENTED:
                # Timed with the production request that consumed the lot.
                continue
            offset = MILESTONE_OFFSET_MINUTES.get(entry.action)
            moment = base + timedelta(minutes=offset if offset is not None else 20 * position)
            entry.occurred_at = _utc(moment)
            last_at = max(last_at, moment)
            total_events += 1

        lot.updated_at = _utc(last_at)

        # Reception, inspections and quality decisions follow the same timeline.
        reception = db.execute(
            select(Reception).where(Reception.lot_id == lot.id)
        ).scalar_one_or_none()
        if reception is not None:
            reception.received_at = _utc(base)
            reception.created_at = _utc(base)
            reception.updated_at = _utc(base)

        for inspection in db.execute(
            select(Inspection).where(Inspection.lot_id == lot.id).order_by(Inspection.id)
        ).scalars():
            started = base + timedelta(minutes=45)
            done = base + timedelta(minutes=70)
            inspection.started_at = _utc(started)
            inspection.inspected_at = _utc(done)
            inspection.created_at = _utc(done)
            inspection.updated_at = _utc(done)

        for validation in db.execute(
            select(QualityValidation)
            .where(QualityValidation.lot_id == lot.id)
            .order_by(QualityValidation.id)
        ).scalars():
            decided = base + timedelta(minutes=155)
            validation.decided_at = _utc(decided)
            validation.created_at = _utc(decided)
            validation.updated_at = _utc(decided)

        stored = base + timedelta(minutes=215)
        if lot.stored_at is not None:
            lot.stored_at = _utc(stored)

        for movement in db.execute(
            select(StockMovement)
            .where(StockMovement.lot_id == lot.id, StockMovement.movement_type == "IN")
            .order_by(StockMovement.id)
        ).scalars():
            movement.occurred_at = _utc(stored)

    db.flush()

    # Production requests: spread over the last two days, in creation order.
    requests = list(
        db.execute(select(ProductionRequest).order_by(ProductionRequest.id)).scalars()
    )
    for index, request in enumerate(requests):
        base = now - timedelta(hours=(len(requests) - index) * 3)
        request.created_on = _utc(base)
        request.created_at = _utc(base)

        steps = {
            "submitted_at": 15,
            "approved_at": 55,
            "prepared_at": 95,
            "ready_at": 120,
            "issued_at": 150,
        }
        last = base
        for field, minutes in steps.items():
            if getattr(request, field, None) is not None:
                moment = base + timedelta(minutes=minutes)
                setattr(request, field, _utc(moment))
                last = max(last, moment)
        request.updated_at = _utc(last)

        entries = list(
            db.execute(
                select(AuditLog)
                .where(AuditLog.entity_reference == request.reference)
                .order_by(AuditLog.id)
            ).scalars()
        )
        for position, entry in enumerate(entries):
            entry.occurred_at = _utc(base + timedelta(minutes=25 * position))
            total_events += 1

        for movement in db.execute(
            select(StockMovement)
            .where(StockMovement.production_request_id == request.id)
            .order_by(StockMovement.id)
        ).scalars():
            issued_at = _utc(base + timedelta(minutes=150))
            movement.occurred_at = issued_at
            # The STOCK_DECREMENTED audit entry references the movement, not the
            # request, so align it here.
            for entry in db.execute(
                select(AuditLog).where(AuditLog.entity_reference == movement.reference)
            ).scalars():
                entry.occurred_at = issued_at
                total_events += 1

    db.flush()
    db.commit()

    return {"lots": len(lots), "requests": len(requests), "events": total_events}
