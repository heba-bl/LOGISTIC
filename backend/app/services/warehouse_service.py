"""Warehouse: addressing, storage confirmation and occupancy.

Storage confirmation is the ONLY operation that increments stock, and only when:
  1. quality approved the lot;
  2. the warehouse operator confirmed the storage;
  3. a location is provided.

A lot larger than its primary location can be split across secondary addresses -
the caller passes several allocations and each one produces its own movement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import CapacityError, ValidationError, WorkflowError
from app.models.catalog import Part
from app.models.enums import AuditAction, LocationRole, LotStatus
from app.models.warehouse import PartLocation, StockMovement, WarehouseLocation
from app.repositories import LotRepository, UserRepository, WarehouseRepository
from app.services import audit_service, settings_service, stock_service


@dataclass(frozen=True)
class Allocation:
    """How much of a lot goes to one location."""

    location_id: int
    quantity: int


@dataclass(frozen=True)
class LocationSuggestion:
    location: WarehouseLocation
    role: LocationRole
    quantity: int
    rationale: str


def location_severity(location: WarehouseLocation) -> str:
    """Functional state of a location from its occupancy."""
    ratio = location.occupancy_percent
    if ratio >= location.critical_threshold_percent:
        return "CRITICAL"
    if ratio >= location.warning_threshold_percent:
        return "WARNING"
    return "OK"


def suggest_allocations(db: Session, *, part: Part, quantity: int) -> list[LocationSuggestion]:
    """Propose where to store a quantity: primary address first, then secondaries.

    Also used by the AI optimisation engine to justify a secondary-address advice.
    """
    warehouses = WarehouseRepository(db)
    links = list(warehouses.part_links(part.id))
    ordered = sorted(links, key=lambda link: 0 if link.role is LocationRole.PRIMARY else 1)

    suggestions: list[LocationSuggestion] = []
    remaining = quantity

    for link in ordered:
        if remaining <= 0:
            break
        free = link.location.free_capacity
        if free <= 0:
            continue
        take = min(free, remaining)
        remaining -= take
        suggestions.append(
            LocationSuggestion(
                location=link.location,
                role=link.role,
                quantity=take,
                rationale=(
                    f"{link.role.value.lower()} address of {part.reference}, "
                    f"{free} units free of {link.location.capacity}"
                ),
            )
        )

    if remaining > 0:
        # Spill over onto any other location with room, emptiest first.
        known = {link.location_id for link in links}
        candidates = [
            location
            for location in warehouses.all_locations()
            if location.is_active and location.id not in known and location.free_capacity > 0
        ]
        candidates.sort(key=lambda location: location.occupancy_percent)
        for location in candidates:
            if remaining <= 0:
                break
            take = min(location.free_capacity, remaining)
            remaining -= take
            suggestions.append(
                LocationSuggestion(
                    location=location,
                    role=LocationRole.SECONDARY,
                    quantity=take,
                    rationale=(
                        f"overflow address, {location.free_capacity} units free "
                        f"({location.occupancy_percent:g}% occupied)"
                    ),
                )
            )

    return suggestions


def _link_part_to_location(db: Session, *, part_id: int, location_id: int) -> None:
    """Register the address for the part if it is not already known."""
    existing = db.execute(
        select(PartLocation).where(
            PartLocation.part_id == part_id, PartLocation.location_id == location_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        return

    has_primary = db.execute(
        select(PartLocation).where(
            PartLocation.part_id == part_id, PartLocation.role == LocationRole.PRIMARY
        )
    ).scalar_one_or_none()

    db.add(
        PartLocation(
            part_id=part_id,
            location_id=location_id,
            role=LocationRole.SECONDARY if has_primary else LocationRole.PRIMARY,
        )
    )
    db.flush()


def confirm_storage(
    db: Session,
    *,
    lot_id: int,
    allocations: list[Allocation],
    actor_id: int | None = None,
    notes: str | None = None,
) -> list[StockMovement]:
    """Confirm physical storage of an approved lot and increment stock.

    Validated server-side before anything moves: the lot exists, quality approved
    it, the quantities add up, and every target location has room.
    """
    lots = LotRepository(db)
    warehouses = WarehouseRepository(db)
    actor = UserRepository(db).optional(actor_id)

    lot = lots.require(lot_id)

    if lot.status is not LotStatus.APPROVED:
        raise WorkflowError(
            f"Lot {lot.lot_number} cannot be stored from status {lot.status.value}. "
            "Quality approval is required before storage."
        )
    if not allocations:
        raise ValidationError("At least one storage allocation is required")

    total = sum(allocation.quantity for allocation in allocations)
    if total <= 0:
        raise ValidationError("Stored quantity must be strictly positive")
    if total != lot.quantity_approved:
        raise ValidationError(
            f"Allocated quantity {total} does not match the approved quantity "
            f"{lot.quantity_approved} for lot {lot.lot_number}"
        )

    # Validate capacity for every target before mutating anything.
    resolved: list[tuple[WarehouseLocation, int]] = []
    for allocation in allocations:
        if allocation.quantity <= 0:
            raise ValidationError("Each allocation must carry a strictly positive quantity")
        location = warehouses.require(allocation.location_id)
        if not location.is_active:
            raise ValidationError(f"Location {location.code} is not active")
        resolved.append((location, allocation.quantity))

    pending: dict[int, int] = {}
    for location, quantity in resolved:
        pending[location.id] = pending.get(location.id, 0) + quantity
        if pending[location.id] > location.free_capacity:
            raise CapacityError(
                f"Location {location.code} cannot hold {pending[location.id]} units "
                f"({location.free_capacity} free)",
                details={"location": location.code, "free": location.free_capacity},
            )

    before = lot.status.value
    movements: list[StockMovement] = []

    for location, quantity in resolved:
        movements.append(
            stock_service.increment(
                db,
                part=lot.part,
                quantity=quantity,
                lot=lot,
                location=location,
                actor=actor,
                reason=(
                    f"Storage confirmed for {lot.lot_number} at {location.code}"
                    + (f" - {notes}" if notes else "")
                ),
            )
        )
        _link_part_to_location(db, part_id=lot.part_id, location_id=location.id)

    lot.status = LotStatus.STORED
    lot.quantity_available = total
    # Assign the relationship, not just the foreign key, so an already-loaded
    # `lot.location` does not stay cached as None.
    lot.location = resolved[0][0]
    lot.stored_at = datetime.now(timezone.utc)
    db.flush()

    audit_service.record(
        db,
        action=AuditAction.STORAGE_CONFIRMED,
        entity_type="lot",
        entity_id=lot.id,
        entity_reference=lot.lot_number,
        actor=actor,
        lot_id=lot.id,
        part_id=lot.part_id,
        quantity=total,
        location_code=", ".join(location.code for location, _ in resolved),
        status_before=before,
        status_after=lot.status.value,
        reason=(
            f"Stored {total} units of {lot.part.reference} across "
            f"{len(resolved)} location(s)" + (f" - {notes}" if notes else "")
        ),
    )
    return movements


def occupancy_overview(db: Session) -> dict:
    """Aggregate occupancy used by the dashboard and the saturation alerts."""
    warehouses = WarehouseRepository(db)
    locations = list(warehouses.all_locations())
    occupied, capacity = warehouses.total_occupancy()

    warning = settings_service.get_float(db, "warehouse.warning_occupancy_percent")
    critical = settings_service.get_float(db, "warehouse.critical_occupancy_percent")

    saturated = [loc for loc in locations if loc.occupancy_percent >= critical]
    nearly_full = [
        loc for loc in locations if warning <= loc.occupancy_percent < critical
    ]

    return {
        "total_capacity": capacity,
        "total_occupied": occupied,
        "occupancy_percent": round(occupied / capacity * 100, 1) if capacity else 0.0,
        "location_count": len(locations),
        "saturated": saturated,
        "nearly_full": nearly_full,
        "warning_threshold": warning,
        "critical_threshold": critical,
    }
