"""Inspection: sampling-based quality control of a received lot.

Quality does not check every part. A sample is drawn from the lot and the defect
rate on that sample decides the outcome:

  - conform      -> the lot moves on to the quality decision (QUALITY_PENDING)
  - non conform  -> the lot goes to the RED CAGE and waits for a decision

An inspection never touches stock.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError, WorkflowError
from app.models.enums import AuditAction, InspectionResult, LotStatus
from app.models.flow import Inspection, Lot
from app.repositories import LotRepository, UserRepository
from app.services import audit_service, reference_service, settings_service

#: States from which an inspection may be recorded.
INSPECTABLE = (LotStatus.PENDING_INSPECTION, LotStatus.INSPECTION_IN_PROGRESS)


def suggest_sample_size(db: Session, lot: Lot) -> int:
    """Compute the sample size from the configured rate and floor.

    Both the percentage and the minimum are settings, never hardcoded constants.
    """
    percent = settings_service.get_float(db, "inspection.sample_percent")
    minimum = settings_service.get_int(db, "inspection.sample_minimum")
    computed = math.ceil(lot.quantity_received * percent / 100.0)
    # The floor is applied first, then capped by the lot: a 3-unit lot can never
    # yield a 5-unit sample.
    return min(lot.quantity_received, max(minimum, computed))


def start_inspection(db: Session, *, lot_id: int, actor_id: int | None = None) -> Lot:
    """Move a lot into INSPECTION_IN_PROGRESS."""
    lots = LotRepository(db)
    actor = UserRepository(db).optional(actor_id)
    lot = lots.require(lot_id)

    if lot.status is not LotStatus.PENDING_INSPECTION:
        raise WorkflowError(
            f"Lot {lot.lot_number} cannot start inspection from status {lot.status.value}"
        )

    before = lot.status.value
    lot.status = LotStatus.INSPECTION_IN_PROGRESS
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.INSPECTION_STARTED,
        entity_type="lot",
        entity_id=lot.id,
        entity_reference=lot.lot_number,
        actor=actor,
        lot_id=lot.id,
        part_id=lot.part_id,
        quantity=lot.quantity_received,
        status_before=before,
        status_after=lot.status.value,
        reason=f"Inspection opened on {lot.lot_number}",
    )
    return lot


def record_inspection(
    db: Session,
    *,
    lot_id: int,
    sample_size: int,
    defects_found: int,
    observations: str | None = None,
    actor_id: int | None = None,
) -> Inspection:
    """Record the sampling result and route the lot accordingly."""
    lots = LotRepository(db)
    actor = UserRepository(db).optional(actor_id)
    lot = lots.require(lot_id)

    if lot.status not in INSPECTABLE:
        raise WorkflowError(
            f"Lot {lot.lot_number} cannot be inspected from status {lot.status.value}"
        )
    if sample_size <= 0:
        raise ValidationError("Sample size must be strictly positive")
    if sample_size > lot.quantity_received:
        raise ValidationError(
            f"Sample size {sample_size} exceeds the received quantity {lot.quantity_received}"
        )
    if defects_found < 0:
        raise ValidationError("Defect count cannot be negative")
    if defects_found > sample_size:
        raise ValidationError("Defect count cannot exceed the sample size")

    threshold = settings_service.get_float(db, "inspection.defect_threshold_percent")
    defect_rate = defects_found / sample_size * 100.0
    result = (
        InspectionResult.CONFORM if defect_rate <= threshold else InspectionResult.NON_CONFORM
    )

    inspection = Inspection(
        reference=reference_service.next_inspection_reference(db),
        lot_id=lot.id,
        sample_size=sample_size,
        defects_found=defects_found,
        defect_threshold_percent=threshold,
        result=result,
        observations=observations,
        inspector_id=actor.id if actor else None,
        started_at=datetime.now(timezone.utc),
    )
    db.add(inspection)

    before = lot.status.value
    if result is InspectionResult.CONFORM:
        lot.status = LotStatus.QUALITY_PENDING
        lot.blocked_reason = None
    else:
        lot.status = LotStatus.RED_CAGE
        lot.blocked_reason = (
            f"Non conform on inspection {inspection.reference}: "
            f"{defects_found}/{sample_size} defects = {defect_rate:.2f}% "
            f"(threshold {threshold:g}%)"
        )
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.INSPECTION_RECORDED,
        entity_type="inspection",
        entity_id=inspection.id,
        entity_reference=inspection.reference,
        actor=actor,
        lot_id=lot.id,
        part_id=lot.part_id,
        quantity=sample_size,
        status_before=before,
        status_after=lot.status.value,
        reason=(
            f"Sample {sample_size} units, {defects_found} defects "
            f"({defect_rate:.2f}% vs {threshold:g}% threshold) -> {result.value}"
        ),
    )
    return inspection
