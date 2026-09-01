"""Quality decisions and the Red Cage.

The Red Cage is the quarantine area where a lot waits for a human decision. A lot
lands there when an inspection is non conform, or when a reception is outside the
quantity tolerance.

Approving a lot does NOT create stock - it only unlocks storage. Every decision
requires a justification.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError, WorkflowError
from app.models.enums import AuditAction, LotStatus, QualityDecision
from app.models.flow import Lot, QualityValidation
from app.repositories import InspectionRepository, LotRepository, UserRepository
from app.services import audit_service

#: Lots awaiting a quality decision.
DECIDABLE = (LotStatus.QUALITY_PENDING, LotStatus.RED_CAGE)

_AUDIT_BY_DECISION = {
    QualityDecision.APPROVED: AuditAction.QUALITY_APPROVED,
    QualityDecision.REJECTED: AuditAction.QUALITY_REJECTED,
    QualityDecision.RED_CAGE: AuditAction.QUALITY_RED_CAGE,
}


def _decide(
    db: Session,
    *,
    lot: Lot,
    decision: QualityDecision,
    justification: str,
    quantity_approved: int,
    actor_id: int | None,
    action: AuditAction | None = None,
) -> QualityValidation:
    actor = UserRepository(db).optional(actor_id)
    inspection = InspectionRepository(db).latest_for_lot(lot.id)

    validation = QualityValidation(
        lot_id=lot.id,
        inspection_id=inspection.id if inspection else None,
        decision=decision,
        quantity_approved=quantity_approved,
        justification=justification,
        decided_by_id=actor.id if actor else None,
    )
    db.add(validation)
    db.flush()

    audit_service.record(
        db,
        action=action or _AUDIT_BY_DECISION[decision],
        entity_type="quality_validation",
        entity_id=validation.id,
        entity_reference=lot.lot_number,
        actor=actor,
        lot_id=lot.id,
        part_id=lot.part_id,
        quantity=quantity_approved or lot.quantity_received,
        status_after=lot.status.value,
        reason=justification,
    )
    return validation


def approve(
    db: Session,
    *,
    lot_id: int,
    justification: str,
    quantity_approved: int | None = None,
    actor_id: int | None = None,
) -> QualityValidation:
    """Clear a lot for storage. Does not create stock."""
    if not justification or not justification.strip():
        raise ValidationError("A quality decision requires a justification")

    lot = LotRepository(db).require(lot_id)
    if lot.status not in DECIDABLE:
        raise WorkflowError(
            f"Lot {lot.lot_number} cannot be approved from status {lot.status.value}"
        )

    quantity = lot.quantity_received if quantity_approved is None else quantity_approved
    if quantity <= 0:
        raise ValidationError("Approved quantity must be strictly positive")
    if quantity > lot.quantity_received:
        raise ValidationError(
            f"Approved quantity {quantity} exceeds the received quantity {lot.quantity_received}"
        )

    before = lot.status.value
    lot.status = LotStatus.APPROVED
    lot.quantity_approved = quantity
    lot.blocked_reason = None
    lot.blocked_reason_key = None
    lot.blocked_reason_values = None
    db.flush()

    validation = _decide(
        db,
        lot=lot,
        decision=QualityDecision.APPROVED,
        justification=justification,
        quantity_approved=quantity,
        actor_id=actor_id,
        action=(
            AuditAction.RED_CAGE_RELEASED
            if before == LotStatus.RED_CAGE.value
            else AuditAction.QUALITY_APPROVED
        ),
    )
    return validation


def reject(
    db: Session, *, lot_id: int, justification: str, actor_id: int | None = None
) -> QualityValidation:
    """Definitively refuse a lot. It will never become stock."""
    if not justification or not justification.strip():
        raise ValidationError("A quality decision requires a justification")

    lot = LotRepository(db).require(lot_id)
    if lot.status not in DECIDABLE:
        raise WorkflowError(
            f"Lot {lot.lot_number} cannot be rejected from status {lot.status.value}"
        )

    lot.status = LotStatus.REJECTED
    lot.quantity_approved = 0
    lot.blocked_reason = justification
    lot.blocked_reason_key = None
    lot.blocked_reason_values = None
    db.flush()

    return _decide(
        db,
        lot=lot,
        decision=QualityDecision.REJECTED,
        justification=justification,
        quantity_approved=0,
        actor_id=actor_id,
        action=AuditAction.QUALITY_REJECTED,
    )


def send_to_red_cage(
    db: Session, *, lot_id: int, justification: str, actor_id: int | None = None
) -> QualityValidation:
    """Quarantine a lot pending a decision."""
    if not justification or not justification.strip():
        raise ValidationError("Sending a lot to the Red Cage requires a justification")

    lot = LotRepository(db).require(lot_id)
    if lot.status in (LotStatus.STORED, LotStatus.CONSUMED):
        raise WorkflowError(
            f"Lot {lot.lot_number} is already stored and cannot be quarantined from stock"
        )

    lot.status = LotStatus.RED_CAGE
    lot.blocked_reason = justification
    lot.blocked_reason_key = None
    lot.blocked_reason_values = None
    db.flush()

    return _decide(
        db,
        lot=lot,
        decision=QualityDecision.RED_CAGE,
        justification=justification,
        quantity_approved=0,
        actor_id=actor_id,
        action=AuditAction.QUALITY_RED_CAGE,
    )


def scrap(
    db: Session, *, lot_id: int, justification: str, actor_id: int | None = None
) -> QualityValidation:
    """Scrap a quarantined lot: a terminal rejection out of the Red Cage."""
    lot = LotRepository(db).require(lot_id)
    if lot.status is not LotStatus.RED_CAGE:
        raise WorkflowError(f"Lot {lot.lot_number} is not in the Red Cage")
    if not justification or not justification.strip():
        raise ValidationError("Scrapping a lot requires a justification")

    lot.status = LotStatus.REJECTED
    lot.quantity_approved = 0
    lot.blocked_reason = f"Scrapped: {justification}"
    lot.blocked_reason_key = None
    lot.blocked_reason_values = None
    db.flush()

    return _decide(
        db,
        lot=lot,
        decision=QualityDecision.REJECTED,
        justification=justification,
        quantity_approved=0,
        actor_id=actor_id,
        action=AuditAction.RED_CAGE_SCRAPPED,
    )


def red_cage_lots(db: Session) -> list[Lot]:
    """Lots currently quarantined."""
    return list(LotRepository(db).in_stage([LotStatus.RED_CAGE]))
