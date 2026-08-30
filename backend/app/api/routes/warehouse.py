"""Warehouse, storage confirmation and stock endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import (
    LotRepository,
    PartRepository,
    ProductionRepository,
    StockRepository,
    WarehouseRepository,
)
from app.schemas.flow import LotOut
from app.schemas.warehouse import (
    AllocationSuggestion,
    LocationDetail,
    LocationOut,
    MovementOut,
    StockRow,
    StoragePlan,
    StorageConfirmIn,
)
from app.schemas.warehouse import WarehouseGrid
from app.services import stock_service, warehouse_service
from app.services.warehouse_service import Allocation

router = APIRouter(tags=["warehouse"])


# ------------------------------------------------------------------ warehouse map
@router.get("/warehouse/grid", response_model=WarehouseGrid, summary="Interactive warehouse map")
def warehouse_grid(db: Session = Depends(get_session)) -> WarehouseGrid:
    warehouses = WarehouseRepository(db)
    locations = list(warehouses.all_locations())
    overview = warehouse_service.occupancy_overview(db)
    houses = list(warehouses.warehouses())
    house = houses[0] if houses else None

    return WarehouseGrid(
        warehouse_code=house.code if house else "WH",
        warehouse_name=house.name if house else "Warehouse",
        zones=sorted({location.zone for location in locations}),
        locations=[LocationOut.model_validate(location) for location in locations],
        total_capacity=overview["total_capacity"],
        total_occupied=overview["total_occupied"],
        occupancy_percent=overview["occupancy_percent"],
        warning_threshold=overview["warning_threshold"],
        critical_threshold=overview["critical_threshold"],
    )


@router.get(
    "/warehouse/locations",
    response_model=list[LocationOut],
    summary="List warehouse locations",
)
def list_locations(db: Session = Depends(get_session)) -> list[LocationOut]:
    return [
        LocationOut.model_validate(item) for item in WarehouseRepository(db).all_locations()
    ]


@router.get(
    "/warehouse/locations/{location_id}",
    response_model=LocationDetail,
    summary="Location detail with its content",
)
def location_detail(location_id: int, db: Session = Depends(get_session)) -> LocationDetail:
    warehouses = WarehouseRepository(db)
    location = warehouses.require(location_id)
    lots = list(warehouses.lots_at(location_id))

    payload = LocationOut.model_validate(location).model_dump()
    return LocationDetail(
        **payload,
        severity=warehouse_service.location_severity(location),
        lots=[LotOut.model_validate(lot) for lot in lots],
        references=sorted({lot.part.reference for lot in lots}),
    )


# ------------------------------------------------------------- storage confirmation
@router.get(
    "/lots/{lot_id}/storage-plan",
    response_model=StoragePlan,
    summary="Server-computed storage proposal for an approved lot",
)
def storage_plan(lot_id: int, db: Session = Depends(get_session)) -> StoragePlan:
    lot = LotRepository(db).require(lot_id)
    quantity = lot.quantity_approved or lot.quantity_received
    plan = warehouse_service.suggest_allocations(db, part=lot.part, quantity=quantity)
    allocated = sum(item.quantity for item in plan)

    return StoragePlan(
        lot_number=lot.lot_number,
        part_reference=lot.part.reference,
        quantity_to_store=quantity,
        fully_allocatable=allocated >= quantity,
        suggestions=[
            AllocationSuggestion(
                location_id=item.location.id,
                location_code=item.location.code,
                role=item.role,
                quantity=item.quantity,
                free_capacity=item.location.free_capacity,
                occupancy_percent=item.location.occupancy_percent,
                rationale=item.rationale,
            )
            for item in plan
        ],
    )


@router.post(
    "/lots/{lot_id}/storage/confirm",
    response_model=list[MovementOut],
    status_code=201,
    summary="Confirm storage - the only operation that increments stock",
)
def confirm_storage(
    lot_id: int, payload: StorageConfirmIn, db: Session = Depends(get_session)
) -> list[MovementOut]:
    movements = warehouse_service.confirm_storage(
        db,
        lot_id=lot_id,
        allocations=[
            Allocation(location_id=item.location_id, quantity=item.quantity)
            for item in payload.allocations
        ],
        actor_id=payload.actor_id,
        notes=payload.notes,
    )
    db.commit()
    for movement in movements:
        db.refresh(movement)
    return [MovementOut.model_validate(movement) for movement in movements]


# ----------------------------------------------------------------------- stock
@router.get("/stock", response_model=list[StockRow], summary="Stock per part reference")
def list_stock(db: Session = Depends(get_session)) -> list[StockRow]:
    stocks = StockRepository(db)
    warehouses = WarehouseRepository(db)
    production = ProductionRepository(db)

    rows: list[StockRow] = []
    for stock in stocks.all_with_parts():
        part = stock.part
        demand = production.demand_for_part(part.id)
        consumption = part.average_daily_consumption or 0.0
        cover = round(stock.quantity_available / consumption, 1) if consumption > 0 else None

        if stock.quantity_available < demand:
            severity = "CRITICAL"
        elif part.safety_stock and stock.quantity_available < part.safety_stock:
            severity = "WARNING"
        else:
            severity = "OK"

        rows.append(
            StockRow(
                part_id=part.id,
                reference=part.reference,
                designation=part.designation,
                category=part.category.name if part.category else None,
                unit=part.unit,
                quantity_available=stock.quantity_available,
                quantity_reserved=stock.quantity_reserved,
                quantity_free=stock.quantity_free,
                safety_stock=part.safety_stock,
                average_daily_consumption=part.average_daily_consumption,
                days_of_cover=cover,
                open_demand=demand,
                locations=[link.location.code for link in warehouses.part_links(part.id)],
                severity=severity,
            )
        )
    return rows


@router.get("/stock/{part_id}", response_model=StockRow, summary="Stock of one reference")
def get_stock(part_id: int, db: Session = Depends(get_session)) -> StockRow:
    part = PartRepository(db).require(part_id)
    warehouses = WarehouseRepository(db)
    demand = ProductionRepository(db).demand_for_part(part_id)
    available = stock_service.get_available(db, part_id)
    stock = StockRepository(db).for_part(part_id)
    consumption = part.average_daily_consumption or 0.0

    return StockRow(
        part_id=part.id,
        reference=part.reference,
        designation=part.designation,
        category=part.category.name if part.category else None,
        unit=part.unit,
        quantity_available=available,
        quantity_reserved=stock.quantity_reserved if stock else 0,
        quantity_free=stock.quantity_free if stock else 0,
        safety_stock=part.safety_stock,
        average_daily_consumption=part.average_daily_consumption,
        days_of_cover=round(available / consumption, 1) if consumption > 0 else None,
        open_demand=demand,
        locations=[link.location.code for link in warehouses.part_links(part_id)],
        severity=(
            "CRITICAL"
            if available < demand
            else "WARNING"
            if part.safety_stock and available < part.safety_stock
            else "OK"
        ),
    )


@router.get("/stock-movements", response_model=list[MovementOut], summary="Stock ledger")
def list_movements(
    part_id: int | None = None,
    lot_id: int | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_session),
) -> list[MovementOut]:
    movements = StockRepository(db).movements(part_id=part_id, lot_id=lot_id, limit=limit)
    return [MovementOut.model_validate(movement) for movement in movements]
