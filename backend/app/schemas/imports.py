"""Schemas for the Excel import and Maker-Checker validation workflow."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import ImportRowStatus, ImportStatus, ImportType, ValidationDecision
from app.schemas.common import ORMModel, UtcDatetime


class OperatorRef(ORMModel):
    """An operator is never anonymous."""

    id: int
    employee_number: str
    full_name: str
    role: str
    service: str | None = None
    is_active: bool


class ImportRowOut(ORMModel):
    id: int
    row_number: int
    status: ImportRowStatus
    payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    result_reference: str | None = None


class ImportOut(ORMModel):
    id: int
    reference: str
    import_type: ImportType
    status: ImportStatus

    source_filename: str
    source_hash: str
    source_size_bytes: int

    row_count: int
    valid_row_count: int
    invalid_row_count: int
    applied_row_count: int

    # --- Maker ------------------------------------------------------------
    maker_reference: str
    maker_role: str
    maker_service: str | None = None
    maker_name: str | None = None
    submitted_at: UtcDatetime

    # --- Checker ----------------------------------------------------------
    checker_reference: str | None = None
    checker_role: str | None = None
    checker_service: str | None = None
    checker_name: str | None = None
    checked_at: UtcDatetime | None = None

    decision: ValidationDecision | None = None
    decision_comment: str | None = None
    notes: str | None = None


class ImportDetailOut(ImportOut):
    rows: list[ImportRowOut] = Field(default_factory=list)
    #: Operators habilitated to validate this batch (the maker is excluded).
    eligible_checkers: list[OperatorRef] = Field(default_factory=list)


class DecisionIn(BaseModel):
    checker_id: int
    comment: str | None = None


class RejectionIn(BaseModel):
    checker_id: int
    #: Mandatory: a rejection is never recorded without a reason.
    comment: str = Field(min_length=3)


class ImportTypeInfo(BaseModel):
    """What the UI needs to build the upload form for one import type."""

    value: str
    label: str
    description: str
    columns: list[dict[str, Any]]
    maker_roles: list[str]
    checker_roles: list[str]
