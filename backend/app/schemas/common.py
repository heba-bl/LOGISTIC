"""Shared schema building blocks."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _as_utc(value: datetime | str) -> datetime | str:
    """Treat a naive timestamp as UTC.

    SQLite has no timezone support, so `func.now()` values come back naive even
    though they are UTC. Normalising here means the API always emits an explicit
    offset and the browser never mis-reads a timestamp as local time.
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return value


#: Datetime that is always serialised with an explicit UTC offset.
UtcDatetime = Annotated[datetime, BeforeValidator(_as_utc)]


class ORMModel(BaseModel):
    """Base for every response model read from an ORM object."""

    model_config = ConfigDict(from_attributes=True)


class ActorRef(ORMModel):
    id: int
    full_name: str
    username: str


class PartRef(ORMModel):
    id: int
    reference: str
    designation: str
    unit: str = "PCS"


class SupplierRef(ORMModel):
    id: int
    code: str
    name: str


class LocationRef(ORMModel):
    id: int
    code: str
    zone: str


class StationRef(ORMModel):
    id: int
    code: str
    name: str


class ActionResult(BaseModel):
    """Uniform envelope for a workflow action."""

    success: bool = True
    message: str
    entity_reference: str | None = None
    status: str | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: dict = Field(default_factory=dict)


class Paginated(BaseModel):
    total: int
    items: list


class TimestampedEvent(BaseModel):
    occurred_at: datetime
    label: str
