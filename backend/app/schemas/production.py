"""Production request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import ProductionRequestStatus
from app.schemas.common import UtcDatetime, ActorRef, ORMModel, PartRef, StationRef


class ProductionRequestCreate(BaseModel):
    station_id: int
    part_id: int
    quantity: int = Field(gt=0)
    priority: int = Field(default=3, ge=1, le=3)
    needed_at: UtcDatetime | None = None
    notes: str | None = None
    actor_id: int | None = None
    submit_immediately: bool = False


class ProductionRequestOut(ORMModel):
    id: int
    reference: str
    status: ProductionRequestStatus
    quantity_requested: int
    quantity_issued: int
    priority: int
    needed_at: UtcDatetime | None = None
    notes: str | None = None
    rejection_reason: str | None = None
    created_on: UtcDatetime
    submitted_at: UtcDatetime | None = None
    approved_at: UtcDatetime | None = None
    ready_at: UtcDatetime | None = None
    issued_at: UtcDatetime | None = None
    part: PartRef
    station: StationRef
    requested_by: ActorRef | None = None
    approved_by: ActorRef | None = None


class ProductionRequestRow(BaseModel):
    """Request enriched with live stock feasibility for the production screen."""

    request: ProductionRequestOut
    stock_available: int
    is_coverable: bool
    shortfall: int


class ActorIn(BaseModel):
    actor_id: int | None = None


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3)
    actor_id: int | None = None


class IssueIn(BaseModel):
    quantity: int | None = Field(default=None, gt=0)
    actor_id: int | None = None
    notes: str | None = None
