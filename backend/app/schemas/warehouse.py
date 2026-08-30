"""Warehouse, stock and movement schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import LocationRole, MovementType
from app.schemas.common import UtcDatetime, ORMModel, PartRef
from app.schemas.flow import LotOut


class LocationOut(ORMModel):
    id: int
    code: str
    zone: str
    position: int
    capacity: int
    occupied: int
    occupancy_percent: float
    free_capacity: int
    is_active: bool


class LocationDetail(LocationOut):
    """Location plus what it currently holds."""

    severity: str
    lots: list[LotOut] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class WarehouseGrid(BaseModel):
    """Layout rendered by the interactive warehouse map."""

    warehouse_code: str
    warehouse_name: str
    zones: list[str]
    locations: list[LocationOut]
    total_capacity: int
    total_occupied: int
    occupancy_percent: float
    warning_threshold: float
    critical_threshold: float


class AllocationIn(BaseModel):
    location_id: int
    quantity: int = Field(gt=0)


class StorageConfirmIn(BaseModel):
    allocations: list[AllocationIn] = Field(min_length=1)
    actor_id: int | None = None
    notes: str | None = None


class AllocationSuggestion(BaseModel):
    location_id: int
    location_code: str
    role: LocationRole
    quantity: int
    free_capacity: int
    occupancy_percent: float
    rationale: str


class StoragePlan(BaseModel):
    """Server-computed storage proposal shown to the warehouse operator."""

    lot_number: str
    part_reference: str
    quantity_to_store: int
    fully_allocatable: bool
    suggestions: list[AllocationSuggestion]


class StockOut(ORMModel):
    part: PartRef
    quantity_available: int
    quantity_reserved: int
    quantity_free: int
    last_movement_at: UtcDatetime | None = None


class StockRow(BaseModel):
    """Stock line enriched with the indicators the stock screen displays."""

    part_id: int
    reference: str
    designation: str
    category: str | None = None
    unit: str
    quantity_available: int
    quantity_reserved: int
    quantity_free: int
    safety_stock: int
    average_daily_consumption: float
    days_of_cover: float | None = None
    open_demand: int
    locations: list[str]
    severity: str


class MovementOut(ORMModel):
    id: int
    reference: str
    movement_type: MovementType
    quantity: int
    quantity_before: int
    quantity_after: int
    actor_name: str
    reason: str | None = None
    occurred_at: UtcDatetime
    part: PartRef
    lot: LotOut | None = None
