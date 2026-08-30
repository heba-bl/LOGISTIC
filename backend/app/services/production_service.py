"""Production requests and the outbound stock rule.

Workflow: DRAFT -> SUBMITTED -> APPROVED -> PREPARING -> READY -> ISSUED

Only the final confirmed issue decrements stock. Creating, submitting, approving
or preparing a request changes nothing in the stock balance - approval merely
reserves the quantity as bookkeeping.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError, WorkflowError
from app.models.enums import AuditAction, ProductionRequestStatus
from app.models.production import ProductionRequest
from app.models.warehouse import StockMovement
from app.repositories import PartRepository, ProductionRepository, UserRepository
from app.services import audit_service, reference_service, stock_service

#: Allowed status transitions. Any move outside this map is a WorkflowError.
TRANSITIONS: dict[ProductionRequestStatus, tuple[ProductionRequestStatus, ...]] = {
    ProductionRequestStatus.DRAFT: (
        ProductionRequestStatus.SUBMITTED,
        ProductionRequestStatus.CANCELLED,
    ),
    ProductionRequestStatus.SUBMITTED: (
        ProductionRequestStatus.APPROVED,
        ProductionRequestStatus.REJECTED,
        ProductionRequestStatus.CANCELLED,
    ),
    ProductionRequestStatus.APPROVED: (
        ProductionRequestStatus.PREPARING,
        ProductionRequestStatus.CANCELLED,
    ),
    ProductionRequestStatus.PREPARING: (
        ProductionRequestStatus.READY,
        ProductionRequestStatus.CANCELLED,
    ),
    ProductionRequestStatus.READY: (
        ProductionRequestStatus.ISSUED,
        ProductionRequestStatus.CANCELLED,
    ),
    ProductionRequestStatus.ISSUED: (),
    ProductionRequestStatus.REJECTED: (),
    ProductionRequestStatus.CANCELLED: (),
}


def _assert_transition(request: ProductionRequest, target: ProductionRequestStatus) -> None:
    allowed = TRANSITIONS[request.status]
    if target not in allowed:
        allowed_names = ", ".join(status.value for status in allowed) or "nothing"
        raise WorkflowError(
            f"Request {request.reference} cannot move from {request.status.value} "
            f"to {target.value} (allowed: {allowed_names})"
        )


def _transition(
    db: Session,
    *,
    request: ProductionRequest,
    target: ProductionRequestStatus,
    action: AuditAction,
    actor_id: int | None,
    reason: str,
    quantity: int | None = None,
) -> ProductionRequest:
    _assert_transition(request, target)
    actor = UserRepository(db).optional(actor_id)
    before = request.status.value
    request.status = target
    db.flush()

    audit_service.record(
        db,
        action=action,
        entity_type="production_request",
        entity_id=request.id,
        entity_reference=request.reference,
        actor=actor,
        part_id=request.part_id,
        quantity=quantity if quantity is not None else request.quantity_requested,
        status_before=before,
        status_after=target.value,
        reason=reason,
    )
    return request


def create_request(
    db: Session,
    *,
    station_id: int,
    part_id: int,
    quantity: int,
    priority: int = 3,
    needed_at: datetime | None = None,
    notes: str | None = None,
    actor_id: int | None = None,
    submit_immediately: bool = False,
) -> ProductionRequest:
    """Create a parts request. Never touches stock."""
    if quantity <= 0:
        raise ValidationError("Requested quantity must be strictly positive")
    if priority not in (1, 2, 3):
        raise ValidationError("Priority must be 1, 2 or 3")

    production = ProductionRepository(db)
    station = production.require_station(station_id)
    part = PartRepository(db).require(part_id)
    actor = UserRepository(db).optional(actor_id)

    request = ProductionRequest(
        reference=reference_service.next_request_reference(db),
        station_id=station.id,
        part_id=part.id,
        quantity_requested=quantity,
        priority=priority,
        needed_at=needed_at,
        notes=notes,
        requested_by_id=actor.id if actor else None,
        status=ProductionRequestStatus.DRAFT,
    )
    db.add(request)
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.REQUEST_CREATED,
        entity_type="production_request",
        entity_id=request.id,
        entity_reference=request.reference,
        actor=actor,
        part_id=part.id,
        quantity=quantity,
        status_after=request.status.value,
        reason=f"{station.code} requests {quantity} x {part.reference}",
    )

    if submit_immediately:
        submit(db, request_id=request.id, actor_id=actor_id)
    return request


def submit(db: Session, *, request_id: int, actor_id: int | None = None) -> ProductionRequest:
    """Send the request to the production manager for validation."""
    request = ProductionRepository(db).require(request_id)
    request.submitted_at = datetime.now(timezone.utc)
    return _transition(
        db,
        request=request,
        target=ProductionRequestStatus.SUBMITTED,
        action=AuditAction.REQUEST_SUBMITTED,
        actor_id=actor_id,
        reason=f"Request {request.reference} submitted for validation",
    )


def approve(db: Session, *, request_id: int, actor_id: int | None = None) -> ProductionRequest:
    """Validate a request. Reserves the quantity but does NOT decrement stock."""
    request = ProductionRepository(db).require(request_id)
    actor = UserRepository(db).optional(actor_id)

    available = stock_service.get_available(db, request.part_id)
    request.approved_at = datetime.now(timezone.utc)
    request.approved_by_id = actor.id if actor else None

    _transition(
        db,
        request=request,
        target=ProductionRequestStatus.APPROVED,
        action=AuditAction.REQUEST_APPROVED,
        actor_id=actor_id,
        reason=(
            f"Approved {request.quantity_requested} x {request.part.reference} "
            f"(stock available at approval: {available})"
        ),
    )
    # Bookkeeping only: available quantity is untouched.
    stock_service.reserve(db, part_id=request.part_id, quantity=request.quantity_requested)
    return request


def reject(
    db: Session, *, request_id: int, reason: str, actor_id: int | None = None
) -> ProductionRequest:
    if not reason or not reason.strip():
        raise ValidationError("Rejecting a request requires a reason")
    request = ProductionRepository(db).require(request_id)
    request.rejection_reason = reason
    return _transition(
        db,
        request=request,
        target=ProductionRequestStatus.REJECTED,
        action=AuditAction.REQUEST_REJECTED,
        actor_id=actor_id,
        reason=reason,
    )


def start_preparation(
    db: Session, *, request_id: int, actor_id: int | None = None
) -> ProductionRequest:
    """The warehouse operator starts picking the parts."""
    request = ProductionRepository(db).require(request_id)
    request.prepared_at = datetime.now(timezone.utc)
    return _transition(
        db,
        request=request,
        target=ProductionRequestStatus.PREPARING,
        action=AuditAction.REQUEST_PREPARING,
        actor_id=actor_id,
        reason=f"Preparation started for {request.reference}",
    )


def mark_ready(db: Session, *, request_id: int, actor_id: int | None = None) -> ProductionRequest:
    request = ProductionRepository(db).require(request_id)
    request.ready_at = datetime.now(timezone.utc)
    return _transition(
        db,
        request=request,
        target=ProductionRequestStatus.READY,
        action=AuditAction.REQUEST_READY,
        actor_id=actor_id,
        reason=f"{request.reference} ready for issue",
    )


def issue(
    db: Session,
    *,
    request_id: int,
    quantity: int | None = None,
    actor_id: int | None = None,
    notes: str | None = None,
) -> tuple[ProductionRequest, StockMovement]:
    """Confirm the physical issue. THIS is the only path that decrements stock."""
    production = ProductionRepository(db)
    request = production.require(request_id)
    actor = UserRepository(db).optional(actor_id)

    issued = request.quantity_requested if quantity is None else quantity
    if issued <= 0:
        raise ValidationError("Issued quantity must be strictly positive")
    if issued > request.quantity_requested:
        raise ValidationError(
            f"Cannot issue {issued}: the request only covers {request.quantity_requested}"
        )

    _assert_transition(request, ProductionRequestStatus.ISSUED)

    movement = stock_service.decrement(
        db,
        part=request.part,
        quantity=issued,
        request=request,
        actor=actor,
        reason=(
            f"Issued {issued} x {request.part.reference} to {request.station.code} "
            f"for {request.reference}" + (f" - {notes}" if notes else "")
        ),
    )

    request.quantity_issued = issued
    request.issued_at = datetime.now(timezone.utc)
    request.issued_by_id = actor.id if actor else None

    _transition(
        db,
        request=request,
        target=ProductionRequestStatus.ISSUED,
        action=AuditAction.REQUEST_ISSUED,
        actor_id=actor_id,
        quantity=issued,
        reason=(
            f"Issue confirmed: {issued} x {request.part.reference} to "
            f"{request.station.code} (movement {movement.reference})"
        ),
    )
    return request, movement


def cancel(
    db: Session, *, request_id: int, reason: str, actor_id: int | None = None
) -> ProductionRequest:
    if not reason or not reason.strip():
        raise ValidationError("Cancelling a request requires a reason")
    request = ProductionRepository(db).require(request_id)
    was_approved = request.status in (
        ProductionRequestStatus.APPROVED,
        ProductionRequestStatus.PREPARING,
        ProductionRequestStatus.READY,
    )
    result = _transition(
        db,
        request=request,
        target=ProductionRequestStatus.CANCELLED,
        action=AuditAction.REQUEST_CANCELLED,
        actor_id=actor_id,
        reason=reason,
    )
    if was_approved:
        stock_service.release_reservation(
            db, part_id=request.part_id, quantity=request.quantity_requested
        )
    return result
