"""Production request endpoints.

Only the final issue endpoint decrements stock.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import ProductionRequestStatus
from app.repositories import ProductionRepository
from app.schemas.production import (
    ActorIn,
    IssueIn,
    ProductionRequestCreate,
    ProductionRequestOut,
    ProductionRequestRow,
    ReasonIn,
)
from app.schemas.warehouse import MovementOut
from app.services import production_service, stock_service

router = APIRouter(prefix="/production", tags=["production"])


def _row(db: Session, request) -> ProductionRequestRow:
    available = stock_service.get_available(db, request.part_id)
    outstanding = request.quantity_requested - request.quantity_issued
    return ProductionRequestRow(
        request=ProductionRequestOut.model_validate(request),
        stock_available=available,
        is_coverable=available >= outstanding,
        shortfall=max(0, outstanding - available),
    )


@router.get(
    "/requests", response_model=list[ProductionRequestRow], summary="List production requests"
)
def list_requests(
    status: list[ProductionRequestStatus] | None = Query(default=None),
    station_id: int | None = None,
    part_id: int | None = None,
    limit: int = Query(default=200, le=500),
    db: Session = Depends(get_session),
) -> list[ProductionRequestRow]:
    requests = ProductionRepository(db).list_filtered(
        statuses=status, station_id=station_id, part_id=part_id, limit=limit
    )
    return [_row(db, request) for request in requests]


@router.get(
    "/requests/{request_id}", response_model=ProductionRequestRow, summary="Get one request"
)
def get_request(request_id: int, db: Session = Depends(get_session)) -> ProductionRequestRow:
    return _row(db, ProductionRepository(db).require(request_id))


@router.post(
    "/requests",
    response_model=ProductionRequestOut,
    status_code=201,
    summary="Create a parts request (does not move stock)",
)
def create_request(
    payload: ProductionRequestCreate, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.create_request(
        db,
        station_id=payload.station_id,
        part_id=payload.part_id,
        quantity=payload.quantity,
        priority=payload.priority,
        needed_at=payload.needed_at,
        notes=payload.notes,
        actor_id=payload.actor_id,
        submit_immediately=payload.submit_immediately,
    )
    db.commit()
    db.refresh(request)
    return ProductionRequestOut.model_validate(request)


def _action(db: Session, request) -> ProductionRequestOut:
    db.commit()
    db.refresh(request)
    return ProductionRequestOut.model_validate(request)


@router.post(
    "/requests/{request_id}/submit",
    response_model=ProductionRequestOut,
    summary="Submit for validation",
)
def submit_request(
    request_id: int, payload: ActorIn | None = None, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.submit(
        db, request_id=request_id, actor_id=payload.actor_id if payload else None
    )
    return _action(db, request)


@router.post(
    "/requests/{request_id}/approve",
    response_model=ProductionRequestOut,
    summary="Approve (reserves the quantity, stock unchanged)",
)
def approve_request(
    request_id: int, payload: ActorIn | None = None, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.approve(
        db, request_id=request_id, actor_id=payload.actor_id if payload else None
    )
    return _action(db, request)


@router.post(
    "/requests/{request_id}/reject",
    response_model=ProductionRequestOut,
    summary="Reject a request",
)
def reject_request(
    request_id: int, payload: ReasonIn, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.reject(
        db, request_id=request_id, reason=payload.reason, actor_id=payload.actor_id
    )
    return _action(db, request)


@router.post(
    "/requests/{request_id}/prepare",
    response_model=ProductionRequestOut,
    summary="Start preparation",
)
def prepare_request(
    request_id: int, payload: ActorIn | None = None, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.start_preparation(
        db, request_id=request_id, actor_id=payload.actor_id if payload else None
    )
    return _action(db, request)


@router.post(
    "/requests/{request_id}/ready",
    response_model=ProductionRequestOut,
    summary="Mark ready for issue",
)
def ready_request(
    request_id: int, payload: ActorIn | None = None, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.mark_ready(
        db, request_id=request_id, actor_id=payload.actor_id if payload else None
    )
    return _action(db, request)


@router.post(
    "/requests/{request_id}/issue",
    response_model=MovementOut,
    summary="Confirm the issue - the only operation that decrements stock",
)
def issue_request(
    request_id: int, payload: IssueIn | None = None, db: Session = Depends(get_session)
) -> MovementOut:
    payload = payload or IssueIn()
    _, movement = production_service.issue(
        db,
        request_id=request_id,
        quantity=payload.quantity,
        actor_id=payload.actor_id,
        notes=payload.notes,
    )
    db.commit()
    db.refresh(movement)
    return MovementOut.model_validate(movement)


@router.post(
    "/requests/{request_id}/cancel",
    response_model=ProductionRequestOut,
    summary="Cancel a request",
)
def cancel_request(
    request_id: int, payload: ReasonIn, db: Session = Depends(get_session)
) -> ProductionRequestOut:
    request = production_service.cancel(
        db, request_id=request_id, reason=payload.reason, actor_id=payload.actor_id
    )
    return _action(db, request)
