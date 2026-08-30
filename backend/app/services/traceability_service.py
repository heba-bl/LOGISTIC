"""Traceability: reconstruct the complete life of a lot from the audit trail."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.enums import AuditAction, MovementType
from app.repositories import AuditRepository, LotRepository, StockRepository
from app.services.dashboard_service import describe_action


def lot_trace(db: Session, lot_id: int) -> dict:
    """Full history of one lot: every event, in order, with its context."""
    lots = LotRepository(db)
    lot = lots.full_history(lot_id)

    entries = AuditRepository(db).timeline(lot_id=lot_id, limit=500)
    movements = StockRepository(db).movements(lot_id=lot_id, limit=500)

    events = []
    for entry in sorted(entries, key=lambda item: item.id):
        label, severity = describe_action(entry.action)
        events.append(
            {
                "id": entry.id,
                "action": entry.action.value,
                "label": label,
                "detail": entry.reason or "",
                "actor_name": entry.actor_name,
                "occurred_at": entry.occurred_at,
                "quantity": entry.quantity,
                "location_code": entry.location_code,
                "status_before": entry.status_before,
                "status_after": entry.status_after,
                "severity": severity,
                # Identification and Maker-Checker: never anonymous.
                "actor_reference": entry.actor_reference,
                "actor_role": entry.actor_role,
                "maker_reference": entry.maker_reference,
                "maker_role": entry.maker_role,
                "checker_reference": entry.checker_reference,
                "checker_role": entry.checker_role,
                "decision": entry.decision,
                "source_file": entry.source_file,
                "source_hash": entry.source_hash,
            }
        )

    total_in = sum(m.quantity for m in movements if m.movement_type is MovementType.IN)
    total_out = sum(m.quantity for m in movements if m.movement_type is MovementType.OUT)

    return {
        "lot": lot,
        "reception_reference": lot.reception.reference if lot.reception else None,
        "inspection_count": len(lot.inspections),
        "quality_decisions": len(lot.quality_validations),
        "total_in": total_in,
        "total_out": total_out,
        "events": events,
    }


def trace_by_lot_number(db: Session, lot_number: str) -> dict:
    from app.core.exceptions import NotFoundError

    lot = LotRepository(db).by_number(lot_number)
    if lot is None:
        raise NotFoundError(f"Lot {lot_number} not found")
    return lot_trace(db, lot.id)


def search_audit(
    db: Session,
    *,
    search: str | None = None,
    entity_type: str | None = None,
    part_id: int | None = None,
    limit: int = 200,
) -> list:
    """Global audit search used by the Traceability screen."""
    return list(
        AuditRepository(db).timeline(
            search=search, entity_type=entity_type, part_id=part_id, limit=limit
        )
    )


def part_history(db: Session, part_id: int, limit: int = 200) -> list:
    """Every stock event for one reference - answers 'why is stock dropping?'."""
    return list(StockRepository(db).movements(part_id=part_id, limit=limit))


#: Audit actions that mark a milestone in the lot journey, in flow order.
MILESTONES: tuple[AuditAction, ...] = (
    AuditAction.LOT_RECEIVED,
    AuditAction.INSPECTION_STARTED,
    AuditAction.INSPECTION_RECORDED,
    AuditAction.QUALITY_APPROVED,
    AuditAction.STORAGE_CONFIRMED,
    AuditAction.REQUEST_ISSUED,
)
