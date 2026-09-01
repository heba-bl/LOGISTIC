"""Schemas for the inbound flow: receptions, lots, inspections, quality."""

from __future__ import annotations

import json

from pydantic import BaseModel, Field, field_validator

from app.models.enums import InspectionResult, LotStatus, QualityDecision, ReceptionStatus
from app.schemas.common import UtcDatetime, ActorRef, LocationRef, ORMModel, PartRef, SupplierRef


# --------------------------------------------------------------------------- lots
class LotOut(ORMModel):
    id: int
    lot_number: str
    status: LotStatus
    quantity_expected: int
    quantity_received: int
    quantity_approved: int
    quantity_available: int
    blocked_reason: str | None = None
    #: Set when the services composed the reason; the interface words it.
    blocked_reason_key: str | None = None
    blocked_reason_values: dict = Field(default_factory=dict)

    @field_validator("blocked_reason_values", mode="before")
    @classmethod
    def _decode_values(cls, value: object) -> dict:
        """The column stores JSON text; the API hands back an object.

        Decoding here rather than at every call site means a malformed row
        degrades to an empty object instead of breaking the whole response -
        the sentence in `blocked_reason` still explains the block.
        """
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return {}
        return decoded if isinstance(decoded, dict) else {}
    received_at: UtcDatetime
    stored_at: UtcDatetime | None = None
    #: Last movement on the lot. The supervision screens measure how long a
    #: blocked lot has been waiting from this.
    updated_at: UtcDatetime | None = None
    part: PartRef
    supplier: SupplierRef
    location: LocationRef | None = None


# --------------------------------------------------------------------- receptions
class ReceptionCreate(BaseModel):
    part_id: int
    supplier_id: int
    quantity_expected: int = Field(gt=0)
    quantity_received: int = Field(ge=0)
    delivery_note: str | None = None
    notes: str | None = None
    actor_id: int | None = None


class ReceptionOut(ORMModel):
    id: int
    reference: str
    status: ReceptionStatus
    quantity_expected: int
    quantity_received: int
    quantity_gap: int
    tolerance_percent_applied: float
    delivery_note: str | None = None
    notes: str | None = None
    received_at: UtcDatetime
    lot: LotOut
    received_by: ActorRef | None = None


class TolerancePreview(BaseModel):
    """What the reception screen shows before the operator confirms."""

    part_reference: str
    size_class: str
    tolerance_percent: float
    tolerance_source: str
    allowed_units: float
    quantity_expected: int
    minimum_accepted: int
    maximum_accepted: int


# -------------------------------------------------------------------- inspections
class InspectionCreate(BaseModel):
    sample_size: int = Field(gt=0)
    defects_found: int = Field(ge=0)
    observations: str | None = None
    actor_id: int | None = None


class InspectionLotRef(ORMModel):
    """Just enough of a lot to caption an inspection row."""

    id: int
    lot_number: str
    part: PartRef
    supplier: SupplierRef


class InspectionOut(ORMModel):
    id: int
    reference: str
    lot_id: int
    sample_size: int
    defects_found: int
    defect_rate_percent: float
    defect_threshold_percent: float
    result: InspectionResult
    observations: str | None = None
    inspected_at: UtcDatetime
    inspector: ActorRef | None = None
    #: The lot the sample was drawn from. A report that cannot say which part
    #: was checked, and from which supplier, is not a report.
    lot: InspectionLotRef | None = None


class SampleSuggestion(BaseModel):
    lot_number: str
    quantity_received: int
    suggested_sample_size: int
    sample_percent: float
    minimum_sample: int
    defect_threshold_percent: float


# ------------------------------------------------------------------------ quality
class QualityDecisionIn(BaseModel):
    justification: str = Field(min_length=3)
    quantity_approved: int | None = Field(default=None, ge=0)
    actor_id: int | None = None


class QualityValidationOut(ORMModel):
    id: int
    lot_id: int
    decision: QualityDecision
    quantity_approved: int
    justification: str
    decided_at: UtcDatetime
    decided_by: ActorRef | None = None
