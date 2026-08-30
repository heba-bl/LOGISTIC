"""Receiving endpoints.

A reception records what physically arrived. It never creates stock.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.repositories import PartRepository, ReceptionRepository
from app.schemas.flow import ReceptionCreate, ReceptionOut, TolerancePreview
from app.services import reception_service

router = APIRouter(prefix="/receptions", tags=["receiving"])


@router.get("", response_model=list[ReceptionOut], summary="List receptions")
def list_receptions(
    limit: int = Query(default=100, le=500), db: Session = Depends(get_session)
) -> list[ReceptionOut]:
    return [
        ReceptionOut.model_validate(item) for item in ReceptionRepository(db).recent(limit=limit)
    ]


@router.get(
    "/tolerance-preview",
    response_model=TolerancePreview,
    summary="Preview the tolerance rule before confirming a reception",
)
def tolerance_preview(
    part_id: int,
    quantity_expected: int = Query(gt=0),
    db: Session = Depends(get_session),
) -> TolerancePreview:
    """Show the operator which rule applies and the accepted quantity window."""
    part = PartRepository(db).require(part_id)
    rule = reception_service.resolve_tolerance(db, part, quantity_expected)
    allowed = rule.allowed_units

    return TolerancePreview(
        part_reference=part.reference,
        size_class=part.size_class.value,
        tolerance_percent=rule.percent,
        tolerance_source=rule.source,
        allowed_units=allowed,
        quantity_expected=quantity_expected,
        minimum_accepted=int(quantity_expected - allowed),
        maximum_accepted=int(quantity_expected + allowed),
    )


@router.post(
    "",
    response_model=ReceptionOut,
    status_code=201,
    summary="Register a delivered lot",
)
def create_reception(
    payload: ReceptionCreate, db: Session = Depends(get_session)
) -> ReceptionOut:
    reception = reception_service.create_reception(
        db,
        part_id=payload.part_id,
        supplier_id=payload.supplier_id,
        quantity_expected=payload.quantity_expected,
        quantity_received=payload.quantity_received,
        delivery_note=payload.delivery_note,
        notes=payload.notes,
        actor_id=payload.actor_id,
    )
    db.commit()
    db.refresh(reception)
    return ReceptionOut.model_validate(reception)
