"""Stock engine - the only place where stock quantities are ever modified.

Non-negotiable invariants enforced here:

1. Stock is incremented ONLY by a confirmed storage of a quality-approved lot.
2. Stock is decremented ONLY by a confirmed issue of an approved, prepared request.
3. Every change writes a StockMovement AND an AuditLog, in the same transaction.
4. Stock can never go negative.

No other module writes ``Stock.quantity_available``. Callers pass an open Session
and own the commit, so a stock change is atomic with the workflow transition that
justified it.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import CapacityError, InsufficientStockError, ValidationError
from app.models.catalog import Part
from app.models.enums import AuditAction, MovementType
from app.models.flow import Lot
from app.models.organization import User
from app.models.production import ProductionRequest
from app.models.warehouse import Stock, StockMovement, WarehouseLocation
from app.services import audit_service, reference_service


def get_or_create_stock(db: Session, part_id: int) -> Stock:
    """Return the stock row for a part, creating it at zero if absent."""
    stock = db.execute(select(Stock).where(Stock.part_id == part_id)).scalar_one_or_none()
    if stock is None:
        stock = Stock(part_id=part_id, quantity_available=0, quantity_reserved=0)
        db.add(stock)
        db.flush()
    return stock


def get_available(db: Session, part_id: int) -> int:
    stock = db.execute(select(Stock).where(Stock.part_id == part_id)).scalar_one_or_none()
    return stock.quantity_available if stock else 0


def _record_movement(
    db: Session,
    *,
    movement_type: MovementType,
    part: Part,
    quantity: int,
    quantity_before: int,
    quantity_after: int,
    lot: Lot | None,
    location: WarehouseLocation | None,
    request: ProductionRequest | None,
    actor: User | None,
    reason: str,
) -> StockMovement:
    movement = StockMovement(
        reference=reference_service.next_movement_reference(db),
        movement_type=movement_type,
        part_id=part.id,
        quantity=quantity,
        quantity_before=quantity_before,
        quantity_after=quantity_after,
        lot_id=lot.id if lot else None,
        location_id=location.id if location else None,
        production_request_id=request.id if request else None,
        station_id=request.station_id if request else None,
        actor_id=actor.id if actor else None,
        actor_name=actor.full_name if actor else "system",
        reason=reason,
    )
    db.add(movement)
    db.flush()
    return movement


def increment(
    db: Session,
    *,
    part: Part,
    quantity: int,
    lot: Lot,
    location: WarehouseLocation,
    actor: User | None,
    reason: str,
) -> StockMovement:
    """Add quantity to stock following a confirmed storage.

    Callers must have already verified that the lot is quality-approved; this
    function owns the arithmetic, the ledger and the audit entry.
    """
    if quantity <= 0:
        raise ValidationError("Stock increment must be strictly positive")

    if location.free_capacity < quantity:
        raise CapacityError(
            f"Location {location.code} can only take {location.free_capacity} more units "
            f"({quantity} requested)",
            details={
                "location": location.code,
                "capacity": location.capacity,
                "occupied": location.occupied,
                "requested": quantity,
            },
        )

    stock = get_or_create_stock(db, part.id)
    before = stock.quantity_available
    after = before + quantity

    stock.quantity_available = after
    stock.last_movement_at = datetime.now(timezone.utc)
    location.occupied = location.occupied + quantity

    movement = _record_movement(
        db,
        movement_type=MovementType.IN,
        part=part,
        quantity=quantity,
        quantity_before=before,
        quantity_after=after,
        lot=lot,
        location=location,
        request=None,
        actor=actor,
        reason=reason,
    )

    audit_service.record(
        db,
        action=AuditAction.STOCK_INCREMENTED,
        entity_type="stock",
        entity_id=stock.id,
        entity_reference=movement.reference,
        actor=actor,
        lot_id=lot.id,
        part_id=part.id,
        quantity=quantity,
        location_code=location.code,
        status_before=str(before),
        status_after=str(after),
        reason=reason,
    )
    return movement


def decrement(
    db: Session,
    *,
    part: Part,
    quantity: int,
    request: ProductionRequest,
    actor: User | None,
    reason: str,
    lot: Lot | None = None,
    location: WarehouseLocation | None = None,
) -> StockMovement:
    """Remove quantity from stock following a confirmed issue.

    Raises InsufficientStockError rather than ever producing a negative balance.
    """
    if quantity <= 0:
        raise ValidationError("Stock decrement must be strictly positive")

    stock = get_or_create_stock(db, part.id)
    before = stock.quantity_available

    if before < quantity:
        raise InsufficientStockError(
            f"Insufficient stock for {part.reference}: {before} available, {quantity} requested",
            details={
                "part": part.reference,
                "available": before,
                "requested": quantity,
                "missing": quantity - before,
            },
        )

    after = before - quantity
    stock.quantity_available = after
    stock.quantity_reserved = max(0, stock.quantity_reserved - quantity)
    stock.last_movement_at = datetime.now(timezone.utc)

    consumed_from = _consume_from_lots(db, part_id=part.id, quantity=quantity, location=location)
    target_location = location
    if target_location is None and consumed_from:
        first_lot = consumed_from[0][0]
        if first_lot.location_id is not None:
            target_location = db.get(WarehouseLocation, first_lot.location_id)

    movement = _record_movement(
        db,
        movement_type=MovementType.OUT,
        part=part,
        quantity=quantity,
        quantity_before=before,
        quantity_after=after,
        lot=lot or (consumed_from[0][0] if consumed_from else None),
        location=target_location,
        request=request,
        actor=actor,
        reason=reason,
    )

    audit_service.record(
        db,
        action=AuditAction.STOCK_DECREMENTED,
        entity_type="stock",
        entity_id=stock.id,
        entity_reference=movement.reference,
        actor=actor,
        lot_id=movement.lot_id,
        part_id=part.id,
        quantity=quantity,
        location_code=target_location.code if target_location else None,
        status_before=str(before),
        status_after=str(after),
        reason=reason,
    )
    return movement


def _lot_storage_map(db: Session, lot: Lot) -> list[tuple[WarehouseLocation, int]]:
    """How many units of this lot went into each location, in storage order.

    Derived from the IN movements of the lot, so a lot split across a primary and
    several secondary addresses is released from the right shelves.
    """
    rows = db.execute(
        select(StockMovement.location_id, StockMovement.quantity)
        .where(
            StockMovement.lot_id == lot.id,
            StockMovement.movement_type == MovementType.IN,
            StockMovement.location_id.is_not(None),
        )
        .order_by(StockMovement.id)
    ).all()

    storage: list[tuple[WarehouseLocation, int]] = []
    for location_id, quantity in rows:
        location = db.get(WarehouseLocation, location_id)
        if location is not None:
            storage.append((location, int(quantity)))
    return storage


def _release_capacity(db: Session, lot: Lot, quantity: int, already_consumed: int) -> None:
    """Free ``quantity`` units of shelf space for a lot.

    Locations are emptied in the order they were filled. ``already_consumed``
    skips the space freed by previous issues, so repeated partial issues never
    free the same shelf twice.
    """
    storage = _lot_storage_map(db, lot)
    if not storage:
        return

    skip = already_consumed
    remaining = quantity

    for location, stored in storage:
        if remaining <= 0:
            break
        if skip >= stored:
            skip -= stored
            continue
        available_here = stored - skip
        skip = 0
        freed = min(available_here, remaining)
        location.occupied = max(0, location.occupied - freed)
        remaining -= freed


def _consume_from_lots(
    db: Session,
    *,
    part_id: int,
    quantity: int,
    location: WarehouseLocation | None,
) -> list[tuple[Lot, int]]:
    """Deplete stored lots FIFO and free the matching location capacity.

    Keeps ``Lot.quantity_available`` and ``WarehouseLocation.occupied`` consistent
    with the global stock figure, and marks a lot CONSUMED once emptied.
    """
    from app.models.enums import LotStatus

    stmt = (
        select(Lot)
        .where(Lot.part_id == part_id, Lot.quantity_available > 0)
        .order_by(Lot.stored_at.asc().nulls_last(), Lot.id.asc())
    )
    if location is not None:
        stmt = stmt.where(Lot.location_id == location.id)

    remaining = quantity
    consumed: list[tuple[Lot, int]] = []

    for lot in db.execute(stmt).scalars():
        if remaining <= 0:
            break
        taken = min(lot.quantity_available, remaining)
        already_consumed = max(0, lot.quantity_approved - lot.quantity_available)
        lot.quantity_available -= taken
        remaining -= taken
        consumed.append((lot, taken))

        _release_capacity(db, lot, taken, already_consumed)
        if lot.quantity_available == 0:
            lot.status = LotStatus.CONSUMED

    db.flush()
    return consumed


def reserve(db: Session, *, part_id: int, quantity: int) -> None:
    """Flag stock as committed to an approved request.

    A reservation is bookkeeping only: it does not change the available quantity,
    so it never violates the stock rule.
    """
    stock = get_or_create_stock(db, part_id)
    stock.quantity_reserved = stock.quantity_reserved + quantity
    db.flush()


def release_reservation(db: Session, *, part_id: int, quantity: int) -> None:
    """Undo a reservation when a request is cancelled or rejected."""
    stock = get_or_create_stock(db, part_id)
    stock.quantity_reserved = max(0, stock.quantity_reserved - quantity)
    db.flush()
