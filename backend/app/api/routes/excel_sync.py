"""Endpoints the shared workbook talks to.

The workbook posts approved rows here; nothing it says is taken on trust. See
`excel_sync_service` for what gets re-checked and why.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.schemas.common import UtcDatetime
from app.services import excel_operations, excel_sync_service, validation_token_service

router = APIRouter(prefix="/excel", tags=["excel"])

XLSM_MEDIA = "application/vnd.ms-excel.sheet.macroEnabled.12"


class SyncRequest(BaseModel):
    sheet: str
    file: str = excel_operations.WORKBOOK_NAME
    #: Header-keyed values, exactly as the sheet holds them. Deliberately loose:
    #: the workbook may gain a column without breaking the contract, and every
    #: field is validated server-side anyway.
    rows: list[dict[str, Any]] = Field(default_factory=list)


class RowResult(BaseModel):
    sync_id: str
    source_row: int
    accepted: bool
    reason: str | None = None
    result_reference: str | None = None


class SyncResult(BaseModel):
    sheet: str
    file: str
    received: int
    accepted: int
    rejected: int
    duplicates: int
    import_reference: str | None = None
    rows: list[RowResult] = []


class ActivityCounts(BaseModel):
    receptions: int
    inspections: int
    quality: int
    red_cage: int
    warehouse_articles: int
    stock_movements: int
    production_requests: int
    issues: int


class WarehousePressure(BaseModel):
    locations: int
    locations_used: int
    capacity: int
    occupied: int
    occupancy_percent: float


class BatchCounts(BaseModel):
    total: int
    pending: int
    approved: int
    rejected: int


class ProcessCounts(BaseModel):
    batches: int
    rows: int
    pending: int
    approved: int
    rejected: int


class WorkbookStatus(BaseModel):
    workbook: str
    #: SYNCED, PENDING or NEVER_SYNCED - computed, never assumed.
    state: str
    #: Where the file really sits, when it is on this machine.
    local_path: str | None = None
    local_size_bytes: int | None = None
    local_modified_at: UtcDatetime | None = None
    last_sync_at: UtcDatetime | None = None
    last_actor: str | None = None
    last_maker: str | None = None
    last_reference: str | None = None
    rows_received: int
    rows_approved: int
    rows_rejected: int
    rows_applied: int
    batches: BatchCounts
    activity: ActivityCounts
    warehouse: WarehousePressure
    per_process: dict[str, ProcessCounts] = {}


class HistoryEntry(BaseModel):
    reference: str
    import_type: str
    status: str
    decision: str | None = None
    maker_reference: str
    maker_role: str
    maker_service: str | None = None
    submitted_at: UtcDatetime
    checker_reference: str | None = None
    checker_role: str | None = None
    checker_service: str | None = None
    checked_at: UtcDatetime | None = None
    comment: str | None = None
    source_filename: str
    row_count: int
    valid_row_count: int
    invalid_row_count: int
    applied_row_count: int
    result_references: list[str] = []


class CodeCheck(BaseModel):
    matricule: str
    code: str


class ValidationRequest(BaseModel):
    """What the workbook sends when a manager presses Valider."""

    sheet: str
    sync_id: str
    maker: str
    checker: str
    #: Never stored, never logged, never echoed back.
    code: str


class ValidationResponse(BaseModel):
    accepted: bool
    #: Present only when the code checked out.
    token: str | None = None
    reason: str | None = None


@router.post("/sync", response_model=SyncResult, summary="Synchroniser les lignes validees")
def sync(payload: SyncRequest, db: Session = Depends(get_session)) -> SyncResult:
    """Take in one sheet's approved rows.

    Returns a verdict per row rather than failing the batch: forty good lines
    should not be held back by one bad one, and the operator needs to know which
    line to fix.
    """
    outcome = excel_sync_service.sync_rows(
        db, sheet=payload.sheet, file_name=payload.file, rows=payload.rows
    )
    return SyncResult(
        sheet=outcome.sheet,
        file=outcome.file,
        received=outcome.received,
        accepted=outcome.accepted,
        rejected=outcome.rejected,
        duplicates=outcome.duplicates,
        import_reference=outcome.import_reference,
        rows=[
            RowResult(
                sync_id=row.sync_id,
                source_row=row.source_row,
                accepted=row.accepted,
                reason=row.reason,
                result_reference=row.result_reference,
            )
            for row in outcome.rows
        ],
    )


@router.get("/status", response_model=WorkbookStatus, summary="Etat du fichier partage")
def status(db: Session = Depends(get_session)) -> WorkbookStatus:
    return WorkbookStatus.model_validate(excel_sync_service.workbook_status(db))


@router.get(
    "/history",
    response_model=list[HistoryEntry],
    summary="Tracabilite Maker-Checker",
)
def history(
    matricule: str | None = Query(default=None, description="maker ou checker"),
    role: str | None = Query(default=None),
    zone: str | None = Query(default=None),
    status: str | None = Query(default=None),
    import_type: str | None = Query(default=None),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    db: Session = Depends(get_session),
) -> list[HistoryEntry]:
    """Who entered what, who signed it off, and when."""
    return [
        HistoryEntry.model_validate(entry)
        for entry in excel_sync_service.sync_history(
            db,
            matricule=matricule,
            role=role,
            zone=zone,
            status=status,
            import_type=import_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )
    ]


@router.post(
    "/validate",
    response_model=ValidationResponse,
    summary="Valider une ligne: le serveur verifie le code et signe",
)
def validate_line(
    payload: ValidationRequest, db: Session = Depends(get_session)
) -> ValidationResponse:
    """Check a manager's code and, if it holds, sign the line.

    This is where the Maker-Checker rule is actually enforced. The workbook can
    ask, but only this endpoint can answer with a token, and it only does so
    after the code has been checked against the stored digest.

    The code is read and discarded. It is not written to the database, not put
    in a log line, and not returned.
    """
    maker = payload.maker.strip().upper()
    checker = payload.checker.strip().upper()

    if not maker or not checker:
        return ValidationResponse(accepted=False, reason="matricule manquant")
    if maker == checker:
        return ValidationResponse(
            accepted=False,
            reason="vous ne pouvez pas valider votre propre saisie",
        )

    sheet = payload.sheet.strip().upper()
    allowed = excel_sync_service.SHEET_ZONES.get(sheet)
    if allowed is None:
        return ValidationResponse(accepted=False, reason=f"feuille inconnue: {sheet}")

    person = validation_token_service.user_by_matricule(db, checker)
    if person is None:
        return ValidationResponse(accepted=False, reason="matricule inconnu")
    if not person.is_active:
        return ValidationResponse(accepted=False, reason="compte inactif")

    from app.models.enums import Zone

    if person.zone not in (*allowed, Zone.LOGISTICS):
        return ValidationResponse(
            accepted=False,
            reason=f"{checker} ne depend pas de la zone de la feuille {sheet}",
        )

    if not validation_token_service.verify_code(
        db, checker, payload.code, excel_operations.CODE_SALT
    ):
        return ValidationResponse(accepted=False, reason="code de validation incorrect")

    return ValidationResponse(
        accepted=True,
        token=validation_token_service.build_token(
            sheet=sheet, sync_id=payload.sync_id, maker=maker, checker=checker
        ),
    )


@router.post("/verify-code", summary="Verifier un code de validation")
def verify_code(payload: CodeCheck, db: Session = Depends(get_session)) -> dict:
    """Server-side check of a manager's code.

    The workbook checks the code locally so a manager gets an instant answer;
    this is the check that actually counts.
    """
    return {
        "matricule": payload.matricule,
        "valid": excel_sync_service.verify_validation_code(db, payload.matricule, payload.code),
    }


@router.get("/workbook", summary="Telecharger le fichier operationnel")
def download(db: Session = Depends(get_session)) -> Response:
    """Build the workbook now, so its ARTICLES sheet carries today's stock."""
    content = excel_operations.build_workbook(db=db)
    return Response(
        content=content,
        media_type=XLSM_MEDIA,
        headers={
            "Content-Disposition": f'attachment; filename="{excel_operations.WORKBOOK_NAME}"'
        },
    )
