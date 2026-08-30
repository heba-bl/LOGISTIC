"""Lot endpoints, plus the inspection and quality actions that apply to a lot."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import LotStatus
from app.repositories import InspectionRepository, LotRepository, QualityRepository
from app.schemas.flow import (
    InspectionCreate,
    InspectionOut,
    LotOut,
    QualityDecisionIn,
    QualityValidationOut,
    SampleSuggestion,
)
from app.services import inspection_service, quality_service, settings_service

router = APIRouter(tags=["lots"])


# ----------------------------------------------------------------------- reads
@router.get("/lots", response_model=list[LotOut], summary="List lots")
def list_lots(
    status: list[LotStatus] | None = Query(default=None),
    part_id: int | None = None,
    supplier_id: int | None = None,
    search: str | None = None,
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_session),
) -> list[LotOut]:
    lots = LotRepository(db).list_filtered(
        statuses=status, part_id=part_id, supplier_id=supplier_id, search=search, limit=limit
    )
    return [LotOut.model_validate(lot) for lot in lots]


@router.get("/lots/{lot_id}", response_model=LotOut, summary="Get one lot")
def get_lot(lot_id: int, db: Session = Depends(get_session)) -> LotOut:
    return LotOut.model_validate(LotRepository(db).require(lot_id))


# ----------------------------------------------------------------- inspection
@router.get(
    "/lots/{lot_id}/sample-suggestion",
    response_model=SampleSuggestion,
    summary="Suggested sample size for a lot",
)
def sample_suggestion(lot_id: int, db: Session = Depends(get_session)) -> SampleSuggestion:
    lot = LotRepository(db).require(lot_id)
    return SampleSuggestion(
        lot_number=lot.lot_number,
        quantity_received=lot.quantity_received,
        suggested_sample_size=inspection_service.suggest_sample_size(db, lot),
        sample_percent=settings_service.get_float(db, "inspection.sample_percent"),
        minimum_sample=settings_service.get_int(db, "inspection.sample_minimum"),
        defect_threshold_percent=settings_service.get_float(
            db, "inspection.defect_threshold_percent"
        ),
    )


@router.post(
    "/lots/{lot_id}/inspection/start",
    response_model=LotOut,
    summary="Open the inspection of a lot",
)
def start_inspection(
    lot_id: int, actor_id: int | None = None, db: Session = Depends(get_session)
) -> LotOut:
    lot = inspection_service.start_inspection(db, lot_id=lot_id, actor_id=actor_id)
    db.commit()
    db.refresh(lot)
    return LotOut.model_validate(lot)


@router.post(
    "/lots/{lot_id}/inspect",
    response_model=InspectionOut,
    status_code=201,
    summary="Record the sampling result",
)
def record_inspection(
    lot_id: int, payload: InspectionCreate, db: Session = Depends(get_session)
) -> InspectionOut:
    inspection = inspection_service.record_inspection(
        db,
        lot_id=lot_id,
        sample_size=payload.sample_size,
        defects_found=payload.defects_found,
        observations=payload.observations,
        actor_id=payload.actor_id,
    )
    db.commit()
    db.refresh(inspection)
    return InspectionOut.model_validate(inspection)


@router.get("/inspections", response_model=list[InspectionOut], summary="List inspections")
def list_inspections(
    limit: int = Query(default=100, le=500), db: Session = Depends(get_session)
) -> list[InspectionOut]:
    return [
        InspectionOut.model_validate(item)
        for item in InspectionRepository(db).recent(limit=limit)
    ]


# -------------------------------------------------------------------- quality
@router.post(
    "/lots/{lot_id}/quality/approve",
    response_model=QualityValidationOut,
    summary="Approve a lot (unlocks storage, does not create stock)",
)
def approve_lot(
    lot_id: int, payload: QualityDecisionIn, db: Session = Depends(get_session)
) -> QualityValidationOut:
    validation = quality_service.approve(
        db,
        lot_id=lot_id,
        justification=payload.justification,
        quantity_approved=payload.quantity_approved,
        actor_id=payload.actor_id,
    )
    db.commit()
    db.refresh(validation)
    return QualityValidationOut.model_validate(validation)


@router.post(
    "/lots/{lot_id}/quality/reject",
    response_model=QualityValidationOut,
    summary="Reject a lot",
)
def reject_lot(
    lot_id: int, payload: QualityDecisionIn, db: Session = Depends(get_session)
) -> QualityValidationOut:
    validation = quality_service.reject(
        db, lot_id=lot_id, justification=payload.justification, actor_id=payload.actor_id
    )
    db.commit()
    db.refresh(validation)
    return QualityValidationOut.model_validate(validation)


@router.post(
    "/lots/{lot_id}/quality/red-cage",
    response_model=QualityValidationOut,
    summary="Send a lot to the Red Cage",
)
def red_cage_lot(
    lot_id: int, payload: QualityDecisionIn, db: Session = Depends(get_session)
) -> QualityValidationOut:
    validation = quality_service.send_to_red_cage(
        db, lot_id=lot_id, justification=payload.justification, actor_id=payload.actor_id
    )
    db.commit()
    db.refresh(validation)
    return QualityValidationOut.model_validate(validation)


@router.post(
    "/lots/{lot_id}/quality/scrap",
    response_model=QualityValidationOut,
    summary="Scrap a quarantined lot",
)
def scrap_lot(
    lot_id: int, payload: QualityDecisionIn, db: Session = Depends(get_session)
) -> QualityValidationOut:
    validation = quality_service.scrap(
        db, lot_id=lot_id, justification=payload.justification, actor_id=payload.actor_id
    )
    db.commit()
    db.refresh(validation)
    return QualityValidationOut.model_validate(validation)


@router.get("/quality/pending", response_model=list[LotOut], summary="Lots awaiting a decision")
def quality_pending(db: Session = Depends(get_session)) -> list[LotOut]:
    lots = LotRepository(db).in_stage([LotStatus.QUALITY_PENDING])
    return [LotOut.model_validate(lot) for lot in lots]


@router.get("/quality/red-cage", response_model=list[LotOut], summary="Lots in the Red Cage")
def red_cage(db: Session = Depends(get_session)) -> list[LotOut]:
    return [LotOut.model_validate(lot) for lot in quality_service.red_cage_lots(db)]


@router.get(
    "/quality/validations",
    response_model=list[QualityValidationOut],
    summary="Quality decision history",
)
def quality_history(
    limit: int = Query(default=100, le=500), db: Session = Depends(get_session)
) -> list[QualityValidationOut]:
    return [
        QualityValidationOut.model_validate(item)
        for item in QualityRepository(db).recent(limit=limit)
    ]
