"""End-to-end simulation of the logistics process.

Drives the demonstration scenario:

    truck arrives -> reception -> inspection -> quality -> storage -> STOCK +
    -> production request -> approval -> preparation -> issue -> STOCK -

Every step calls the same services the UI calls, so the simulation proves the
real workflow rather than faking it. Stock levels are captured before and after
so the demonstration can show the exact effect of each step.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.catalog import Part, Supplier
from app.models.enums import AuditAction, LotStatus, RoleName
from app.models.organization import Role, User
from app.models.production import ProductionStation
from app.services import (
    audit_service,
    inspection_service,
    production_service,
    quality_service,
    reception_service,
    stock_service,
    warehouse_service,
)
from app.services.warehouse_service import Allocation

#: Ordered steps of the demonstration scenario.
STEP_KEYS = (
    "reception",
    "inspection",
    "quality",
    "storage",
    "request",
    "approval",
    "preparation",
    "issue",
)


def _actor(db: Session, role: RoleName) -> User | None:
    """Pick the simulated operator that owns a given step."""
    return db.execute(
        select(User).join(Role).where(Role.name == role).limit(1)
    ).scalar_one_or_none()


def _pick_part(db: Session, part_id: int | None) -> Part:
    if part_id:
        part = db.get(Part, part_id)
        if part is None:
            raise ValidationError(f"Part {part_id} not found")
        return part
    part = db.execute(select(Part).where(Part.is_active.is_(True)).limit(1)).scalar_one_or_none()
    if part is None:
        raise ValidationError("No part reference available - seed the database first")
    return part


def _pick_supplier(db: Session, supplier_id: int | None) -> Supplier:
    if supplier_id:
        supplier = db.get(Supplier, supplier_id)
        if supplier is None:
            raise ValidationError(f"Supplier {supplier_id} not found")
        return supplier
    supplier = db.execute(select(Supplier).limit(1)).scalar_one_or_none()
    if supplier is None:
        raise ValidationError("No supplier available - seed the database first")
    return supplier


def _pick_station(db: Session, station_id: int | None) -> ProductionStation:
    if station_id:
        station = db.get(ProductionStation, station_id)
        if station is None:
            raise ValidationError(f"Station {station_id} not found")
        return station
    station = db.execute(select(ProductionStation).limit(1)).scalar_one_or_none()
    if station is None:
        raise ValidationError("No production station available - seed the database first")
    return station


def run_scenario(
    db: Session,
    *,
    part_id: int | None = None,
    supplier_id: int | None = None,
    station_id: int | None = None,
    quantity: int = 120,
    production_quantity: int = 20,
    stop_after: str | None = None,
) -> dict:
    """Run the complete demonstration and return a step-by-step report."""
    if stop_after is not None and stop_after not in STEP_KEYS:
        raise ValidationError(
            f"Unknown step '{stop_after}'. Valid steps: {', '.join(STEP_KEYS)}"
        )

    part = _pick_part(db, part_id)
    supplier = _pick_supplier(db, supplier_id)
    station = _pick_station(db, station_id)

    if production_quantity > quantity:
        raise ValidationError(
            "The production quantity cannot exceed the quantity delivered by the truck"
        )

    stock_before = stock_service.get_available(db, part.id)
    steps: list[dict] = []
    order = 0

    def add_step(key: str, title: str, detail: str, reference: str | None = None) -> None:
        nonlocal order
        order += 1
        steps.append(
            {
                "order": order,
                "key": key,
                "title": title,
                "detail": detail,
                "entity_reference": reference,
                "stock_before": None,
                "stock_after": stock_service.get_available(db, part.id),
                "occurred_at": datetime.now(timezone.utc),
            }
        )

    def should_stop(key: str) -> bool:
        return stop_after == key

    # --- 1. Truck arrives, lot is received -------------------------------
    receptionist = _actor(db, RoleName.RECEPTIONIST)
    reception = reception_service.create_reception(
        db,
        part_id=part.id,
        supplier_id=supplier.id,
        quantity_expected=quantity,
        quantity_received=quantity,
        delivery_note=f"SIM-{datetime.now(timezone.utc).strftime('%H%M%S')}",
        notes="Simulated truck arrival",
        actor_id=receptionist.id if receptionist else None,
    )
    lot = reception.lot
    add_step(
        "reception",
        "Truck arrived and lot received",
        f"{quantity} x {part.reference} from {supplier.name}. "
        f"Quantity check: {reception.status.value}. Stock unchanged - a reception "
        "never creates stock.",
        reception.reference,
    )
    if should_stop("reception"):
        return _finalise(db, part, lot, steps, stock_before, "reception")

    # --- 2. Inspection ----------------------------------------------------
    inspector = _actor(db, RoleName.QUALITY_INSPECTOR)
    inspection_service.start_inspection(
        db, lot_id=lot.id, actor_id=inspector.id if inspector else None
    )
    sample = inspection_service.suggest_sample_size(db, lot)
    inspection = inspection_service.record_inspection(
        db,
        lot_id=lot.id,
        sample_size=sample,
        defects_found=0,
        observations="Simulated sampling - no defect found",
        actor_id=inspector.id if inspector else None,
    )
    add_step(
        "inspection",
        "Inspection performed on a sample",
        f"Sample of {sample} units out of {quantity}, {inspection.defects_found} defects "
        f"({inspection.defect_rate_percent}%). Result: {inspection.result.value}.",
        inspection.reference,
    )
    if should_stop("inspection"):
        return _finalise(db, part, lot, steps, stock_before, "inspection")

    # --- 3. Quality validation -------------------------------------------
    quality_manager = _actor(db, RoleName.QUALITY_MANAGER)
    quality_service.approve(
        db,
        lot_id=lot.id,
        justification="Simulation: sample conform, lot cleared for storage",
        actor_id=quality_manager.id if quality_manager else None,
    )
    add_step(
        "quality",
        "Quality approved the lot",
        f"{lot.quantity_approved} units cleared. Stock still unchanged - approval only "
        "unlocks storage.",
        lot.lot_number,
    )
    if should_stop("quality"):
        return _finalise(db, part, lot, steps, stock_before, "quality")

    # --- 4. Storage confirmation -> STOCK + ------------------------------
    operator = _actor(db, RoleName.WAREHOUSE_OPERATOR)
    plan = warehouse_service.suggest_allocations(db, part=part, quantity=lot.quantity_approved)
    if not plan:
        raise ValidationError("No warehouse location has enough free capacity")

    allocations = [
        Allocation(location_id=item.location.id, quantity=item.quantity) for item in plan
    ]
    before_storage = stock_service.get_available(db, part.id)
    warehouse_service.confirm_storage(
        db,
        lot_id=lot.id,
        allocations=allocations,
        actor_id=operator.id if operator else None,
        notes="Simulated storage confirmation",
    )
    after_storage = stock_service.get_available(db, part.id)
    add_step(
        "storage",
        "Storage confirmed - STOCK INCREMENTED",
        f"Stored at {', '.join(item.location.code for item in plan)}. "
        f"Stock {before_storage} -> {after_storage} (+{after_storage - before_storage}).",
        lot.lot_number,
    )
    if should_stop("storage"):
        return _finalise(db, part, lot, steps, stock_before, "storage")

    # --- 5. Production request -------------------------------------------
    leader = _actor(db, RoleName.STATION_LEADER)
    request = production_service.create_request(
        db,
        station_id=station.id,
        part_id=part.id,
        quantity=production_quantity,
        priority=2,
        needed_at=datetime.now(timezone.utc) + timedelta(hours=4),
        notes="Simulated production request",
        actor_id=leader.id if leader else None,
        submit_immediately=True,
    )
    add_step(
        "request",
        "Production raised a request",
        f"{station.code} requests {production_quantity} x {part.reference}. "
        "Stock unchanged - a request never decrements stock.",
        request.reference,
    )
    if should_stop("request"):
        return _finalise(db, part, lot, steps, stock_before, "request")

    # --- 6. Approval ------------------------------------------------------
    production_manager = _actor(db, RoleName.PRODUCTION_MANAGER)
    production_service.approve(
        db, request_id=request.id, actor_id=production_manager.id if production_manager else None
    )
    add_step(
        "approval",
        "Production manager approved the request",
        f"{request.reference} approved. Quantity reserved, stock still unchanged.",
        request.reference,
    )
    if should_stop("approval"):
        return _finalise(db, part, lot, steps, stock_before, "approval")

    # --- 7. Preparation ---------------------------------------------------
    production_service.start_preparation(
        db, request_id=request.id, actor_id=operator.id if operator else None
    )
    production_service.mark_ready(
        db, request_id=request.id, actor_id=operator.id if operator else None
    )
    add_step(
        "preparation",
        "Warehouse prepared the parts",
        f"{request.reference} picked and ready for issue. Stock still unchanged.",
        request.reference,
    )
    if should_stop("preparation"):
        return _finalise(db, part, lot, steps, stock_before, "preparation")

    # --- 8. Issue -> STOCK - ---------------------------------------------
    before_issue = stock_service.get_available(db, part.id)
    _, movement = production_service.issue(
        db,
        request_id=request.id,
        quantity=production_quantity,
        actor_id=operator.id if operator else None,
        notes="Simulated issue to production",
    )
    after_issue = stock_service.get_available(db, part.id)
    add_step(
        "issue",
        "Issue confirmed - STOCK DECREMENTED",
        f"{production_quantity} x {part.reference} handed to {station.code}. "
        f"Stock {before_issue} -> {after_issue} (-{before_issue - after_issue}). "
        f"Movement {movement.reference}.",
        request.reference,
    )

    return _finalise(db, part, lot, steps, stock_before, "issue")


def _finalise(
    db: Session,
    part: Part,
    lot,
    steps: list[dict],
    stock_before: int,
    last_step: str,
) -> dict:
    stock_after = stock_service.get_available(db, part.id)

    audit_service.record(
        db,
        action=AuditAction.SIMULATION_RUN,
        entity_type="simulation",
        entity_reference=lot.lot_number,
        lot_id=lot.id,
        part_id=part.id,
        quantity=lot.quantity_received,
        status_after=last_step,
        reason=(
            f"Simulation executed up to '{last_step}' on {lot.lot_number}: "
            f"stock {stock_before} -> {stock_after}"
        ),
    )

    delta = stock_after - stock_before
    return {
        "scenario": "Truck to production - full logistics chain",
        "lot_number": lot.lot_number,
        "part_reference": part.reference,
        "steps": steps,
        "stock_before": stock_before,
        "stock_after": stock_after,
        "message": (
            f"{len(steps)} step(s) executed on {lot.lot_number}. "
            f"Stock for {part.reference}: {stock_before} -> {stock_after} "
            f"({delta:+d})."
        ),
    }


def reset_simulation_state(db: Session) -> dict:
    """Report what a fresh demonstration would start from.

    Deliberately non-destructive: the demo is meant to add to the history, and
    the audit trail must never be erased.
    """
    from app.repositories import LotRepository

    lots = LotRepository(db)
    return {
        "lots_total": len(lots.list_filtered(limit=1000)),
        "lots_in_red_cage": len(lots.in_stage([LotStatus.RED_CAGE])),
        "note": (
            "The simulation is additive: it creates a new lot each run and never "
            "deletes history, so the audit trail stays complete."
        ),
    }
