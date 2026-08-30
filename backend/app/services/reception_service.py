"""Reception: a truck arrives and a lot is booked in.

Business rule: a reception NEVER creates stock. It creates a Lot in
PENDING_INSPECTION and records the quantity check.

Tolerance rule (PROJECT_SLCC section 3):
  - SMALL parts accept a deviation up to a configurable percentage (default 5%).
  - LARGE parts must match the expected quantity exactly.
  - A part can override the percentage individually.
  - A deviation beyond tolerance sends the lot to the Red Cage for a decision.
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.catalog import Part
from app.models.enums import AuditAction, LotStatus, PartSize, ReceptionStatus
from app.models.flow import Lot, Reception
from app.repositories import PartRepository, SupplierRepository, UserRepository
from app.services import audit_service, reference_service, settings_service


@dataclass(frozen=True)
class ToleranceRule:
    """The tolerance actually applied to one reception, and where it came from."""

    percent: float
    source: str
    allowed_units: float

    def describe(self) -> str:
        if self.percent <= 0:
            return "exact quantity required (large part)"
        return f"{self.percent:g}% tolerance ({self.source})"


def resolve_tolerance(db: Session, part: Part, quantity_expected: int) -> ToleranceRule:
    """Resolve the tolerance for a part: per-part override, else the global setting."""
    if part.reception_tolerance_percent is not None:
        percent = float(part.reception_tolerance_percent)
        source = f"override on {part.reference}"
    elif part.size_class == PartSize.SMALL:
        percent = settings_service.get_float(db, "reception.tolerance_percent_small")
        source = "small-part setting"
    else:
        percent = settings_service.get_float(db, "reception.tolerance_percent_large")
        source = "large-part setting"

    return ToleranceRule(
        percent=percent,
        source=source,
        allowed_units=quantity_expected * percent / 100.0,
    )


def evaluate_quantity(
    *, quantity_expected: int, quantity_received: int, rule: ToleranceRule
) -> tuple[ReceptionStatus, int]:
    """Classify the quantity check. Pure function - easy to test exhaustively."""
    gap = quantity_received - quantity_expected
    if gap == 0:
        return ReceptionStatus.ACCEPTED, gap
    if abs(gap) <= rule.allowed_units:
        return ReceptionStatus.ACCEPTED_WITH_TOLERANCE, gap
    return ReceptionStatus.QUANTITY_MISMATCH, gap


def create_reception(
    db: Session,
    *,
    part_id: int,
    supplier_id: int,
    quantity_expected: int,
    quantity_received: int,
    delivery_note: str | None = None,
    notes: str | None = None,
    actor_id: int | None = None,
    lot_number: str | None = None,
) -> Reception:
    """Book a delivered lot in. Creates Lot + Reception, never stock."""
    if quantity_expected <= 0:
        raise ValidationError("Expected quantity must be strictly positive")
    if quantity_received < 0:
        raise ValidationError("Received quantity cannot be negative")

    parts = PartRepository(db)
    suppliers = SupplierRepository(db)
    users = UserRepository(db)

    part = parts.require(part_id)
    supplier = suppliers.require(supplier_id)
    actor = users.optional(actor_id)

    rule = resolve_tolerance(db, part, quantity_expected)
    status, gap = evaluate_quantity(
        quantity_expected=quantity_expected,
        quantity_received=quantity_received,
        rule=rule,
    )

    lot = Lot(
        lot_number=lot_number or reference_service.next_lot_number(db),
        part_id=part.id,
        supplier_id=supplier.id,
        quantity_expected=quantity_expected,
        quantity_received=quantity_received,
        quantity_approved=0,
        quantity_available=0,
        status=LotStatus.PENDING_INSPECTION,
    )

    if status is ReceptionStatus.QUANTITY_MISMATCH:
        # A delivery outside tolerance is a non-conformity: the lot waits in the
        # Red Cage until someone decides, exactly like a quality non-conformity.
        lot.status = LotStatus.RED_CAGE
        lot.blocked_reason = (
            f"Reception gap of {gap:+d} units on {part.reference} "
            f"(expected {quantity_expected}, received {quantity_received}); "
            f"{rule.describe()} exceeded."
        )

    db.add(lot)
    db.flush()

    reception = Reception(
        reference=reference_service.next_reception_reference(db),
        lot_id=lot.id,
        quantity_expected=quantity_expected,
        quantity_received=quantity_received,
        quantity_gap=gap,
        tolerance_percent_applied=rule.percent,
        status=status,
        delivery_note=delivery_note,
        notes=notes,
        received_by_id=actor.id if actor else None,
    )
    db.add(reception)
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.LOT_RECEIVED,
        entity_type="reception",
        entity_id=reception.id,
        entity_reference=reception.reference,
        actor=actor,
        lot_id=lot.id,
        part_id=part.id,
        quantity=quantity_received,
        status_before=None,
        status_after=lot.status.value,
        reason=(
            f"Received {quantity_received}/{quantity_expected} of {part.reference} "
            f"from {supplier.name} - {status.value} ({rule.describe()})"
        ),
    )
    return reception
