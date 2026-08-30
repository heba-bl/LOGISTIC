"""Excel import and Maker-Checker validation endpoints.

Uploading writes nothing to the business tables. Only an approval by a
habilitated checker - never the maker - applies the data.
"""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import ImportStatus, ImportType
from app.models.imports import DataImport
from app.schemas.imports import (
    DecisionIn,
    ImportDetailOut,
    ImportOut,
    ImportRowOut,
    ImportTypeInfo,
    OperatorRef,
    RejectionIn,
)
from app.services import import_service

router = APIRouter(prefix="/imports", tags=["imports"])

TYPE_LABELS: dict[ImportType, tuple[str, str]] = {
    ImportType.RECEPTION: (
        "Receptions",
        "Deliveries booked in by the reception operator. Creates lots in "
        "PENDING_INSPECTION once validated - never stock.",
    ),
    ImportType.INSPECTION: (
        "Inspections",
        "Sampling results entered by the quality inspector. Validated by the "
        "quality manager, who can never validate their own inspection.",
    ),
    ImportType.PRODUCTION_REQUEST: (
        "Production requests",
        "Parts requests entered by a station leader and validated by the "
        "production manager.",
    ),
}


def _serialise(batch: DataImport) -> dict:
    """ORM -> API shape, resolving the maker and checker identities."""
    return {
        "id": batch.id,
        "reference": batch.reference,
        "import_type": batch.import_type,
        "status": batch.status,
        "source_filename": batch.source_filename,
        "source_hash": batch.source_hash,
        "source_size_bytes": batch.source_size_bytes,
        "row_count": batch.row_count,
        "valid_row_count": batch.valid_row_count,
        "invalid_row_count": batch.invalid_row_count,
        "applied_row_count": batch.applied_row_count,
        "maker_reference": batch.maker_reference,
        "maker_role": batch.maker_role,
        "maker_service": batch.maker_service,
        "maker_name": batch.maker.full_name if batch.maker else None,
        "submitted_at": batch.submitted_at,
        "checker_reference": batch.checker_reference,
        "checker_role": batch.checker_role,
        "checker_service": batch.checker_service,
        "checker_name": batch.checker.full_name if batch.checker else None,
        "checked_at": batch.checked_at,
        "decision": batch.decision,
        "decision_comment": batch.decision_comment,
        "notes": batch.notes,
    }


def _serialise_row(row) -> dict:
    try:
        payload = json.loads(row.payload_json)
    except json.JSONDecodeError:
        payload = {}
    return {
        "id": row.id,
        "row_number": row.row_number,
        "status": row.status,
        "payload": payload if isinstance(payload, dict) else {},
        "error_message": row.error_message,
        "result_reference": row.result_reference,
    }


def _operator(user) -> dict:
    return {
        "id": user.id,
        "employee_number": user.employee_number,
        "full_name": user.full_name,
        "role": user.role.label if user.role else "",
        "service": user.service,
        "is_active": user.is_active,
    }


@router.get("/types", response_model=list[ImportTypeInfo], summary="Supported import types")
def import_types() -> list[ImportTypeInfo]:
    """Expected columns and habilitated roles, per import type."""
    payload = []
    for import_type, (label, description) in TYPE_LABELS.items():
        payload.append(
            ImportTypeInfo(
                value=import_type.value,
                label=label,
                description=description,
                columns=[
                    {"name": name, "required": required}
                    for name, required in import_service.COLUMNS[import_type]
                ],
                maker_roles=[r.value for r in import_service.MAKER_ROLES[import_type]],
                checker_roles=[r.value for r in import_service.CHECKER_ROLES[import_type]],
            )
        )
    return payload


@router.get("/template", summary="Download an Excel template")
def download_template(import_type: ImportType) -> Response:
    content = import_service.build_template(import_type)
    filename = f"slcc_template_{import_type.value.lower()}.xlsx"
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("", response_model=list[ImportOut], summary="List imports")
def list_imports(
    status: ImportStatus | None = None,
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_session),
) -> list[ImportOut]:
    batches = import_service.list_imports(db, status=status, limit=limit)
    return [ImportOut.model_validate(_serialise(batch)) for batch in batches]


@router.get("/{import_id}", response_model=ImportDetailOut, summary="Import detail")
def get_import(import_id: int, db: Session = Depends(get_session)) -> ImportDetailOut:
    batch = import_service.get_import(db, import_id)
    payload = _serialise(batch)
    payload["rows"] = [_serialise_row(row) for row in batch.rows]
    payload["eligible_checkers"] = [
        _operator(user) for user in import_service.eligible_checkers(db, import_id)
    ]
    return ImportDetailOut.model_validate(payload)


@router.post(
    "",
    response_model=ImportDetailOut,
    status_code=201,
    summary="Upload a spreadsheet (MAKER) - creates no business record",
)
async def create_import(
    import_type: ImportType = Form(...),
    maker_id: int = Form(...),
    file: UploadFile = File(...),
    notes: str | None = Form(default=None),
    db: Session = Depends(get_session),
) -> ImportDetailOut:
    content = await file.read()
    batch = import_service.create_import(
        db,
        import_type=import_type,
        filename=file.filename or "upload.xlsx",
        content=content,
        maker_id=maker_id,
        notes=notes,
    )
    db.commit()
    db.refresh(batch)

    payload = _serialise(batch)
    payload["rows"] = [_serialise_row(row) for row in batch.rows]
    payload["eligible_checkers"] = [
        _operator(user) for user in import_service.eligible_checkers(db, batch.id)
    ]
    return ImportDetailOut.model_validate(payload)


@router.post(
    "/{import_id}/approve",
    response_model=ImportDetailOut,
    summary="Validate an import (CHECKER) - only now is the data applied",
)
def approve_import(
    import_id: int, payload: DecisionIn, db: Session = Depends(get_session)
) -> ImportDetailOut:
    batch = import_service.approve_import(
        db, import_id=import_id, checker_id=payload.checker_id, comment=payload.comment
    )
    db.commit()
    db.refresh(batch)

    body = _serialise(batch)
    body["rows"] = [_serialise_row(row) for row in batch.rows]
    body["eligible_checkers"] = []
    return ImportDetailOut.model_validate(body)


@router.post(
    "/{import_id}/reject",
    response_model=ImportDetailOut,
    summary="Reject an import (CHECKER) - comment mandatory, nothing applied",
)
def reject_import(
    import_id: int, payload: RejectionIn, db: Session = Depends(get_session)
) -> ImportDetailOut:
    batch = import_service.reject_import(
        db, import_id=import_id, checker_id=payload.checker_id, comment=payload.comment
    )
    db.commit()
    db.refresh(batch)

    body = _serialise(batch)
    body["rows"] = [_serialise_row(row) for row in batch.rows]
    body["eligible_checkers"] = []
    return ImportDetailOut.model_validate(body)


@router.get(
    "/{import_id}/checkers",
    response_model=list[OperatorRef],
    summary="Operators habilitated to validate this import",
)
def list_checkers(import_id: int, db: Session = Depends(get_session)) -> list[OperatorRef]:
    return [
        OperatorRef.model_validate(_operator(user))
        for user in import_service.eligible_checkers(db, import_id)
    ]


@router.get(
    "/{import_id}/rows", response_model=list[ImportRowOut], summary="Rows of an import"
)
def list_rows(import_id: int, db: Session = Depends(get_session)) -> list[ImportRowOut]:
    batch = import_service.get_import(db, import_id)
    return [ImportRowOut.model_validate(_serialise_row(row)) for row in batch.rows]
