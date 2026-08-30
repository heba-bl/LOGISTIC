"""Reference data schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import PartSize, Zone
from app.schemas.common import ORMModel


class CategoryOut(ORMModel):
    id: int
    code: str
    name: str


class SupplierOut(ORMModel):
    id: int
    code: str
    name: str
    country: str | None = None
    lead_time_days: int
    is_active: bool


class StockSummary(ORMModel):
    quantity_available: int
    quantity_reserved: int
    quantity_free: int


class PartOut(ORMModel):
    id: int
    reference: str
    designation: str
    description: str | None = None
    unit: str
    size_class: PartSize
    reception_tolerance_percent: float | None = None
    #: True when the warehouse actually holds the reference. The catalogue is a
    #: bill of materials; only the managed perimeter is replenished and assessed
    #: for shortage.
    is_managed: bool = False
    safety_stock: int
    average_daily_consumption: float
    is_active: bool
    category: CategoryOut | None = None
    stock: StockSummary | None = None


class PartCreate(BaseModel):
    reference: str = Field(min_length=2, max_length=40)
    designation: str = Field(min_length=2, max_length=160)
    description: str | None = None
    category_id: int | None = None
    size_class: PartSize = PartSize.SMALL
    reception_tolerance_percent: float | None = Field(default=None, ge=0, le=100)
    unit: str = "PCS"
    safety_stock: int = Field(default=0, ge=0)
    average_daily_consumption: float = Field(default=0.0, ge=0)


class StationOut(ORMModel):
    id: int
    code: str
    name: str
    production_line: str | None = None
    is_active: bool


class RoleOut(ORMModel):
    id: int
    name: str
    label: str
    description: str | None = None
    can_validate: bool = False


class UserOut(ORMModel):
    id: int
    employee_number: str
    username: str
    full_name: str
    first_name: str | None = None
    last_name: str | None = None
    service: str | None = None
    zone: Zone | None = None
    is_active: bool
    role: RoleOut | None = None


class SettingOut(ORMModel):
    id: int
    key: str
    value: str
    value_type: str
    label: str
    description: str | None = None
    group: str


class SettingUpdate(BaseModel):
    value: str
