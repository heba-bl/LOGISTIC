"""Reference data endpoints: parts, suppliers, categories, stations, users, settings."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import AuditAction
from app.repositories import (
    CategoryRepository,
    PartRepository,
    ProductionRepository,
    SupplierRepository,
    UserRepository,
)
from app.schemas.catalog import (
    CategoryOut,
    PartOut,
    SettingOut,
    SettingUpdate,
    StationOut,
    SupplierOut,
    UserOut,
)
from app.services import audit_service, settings_service

router = APIRouter(tags=["catalog"])


@router.get("/parts", response_model=list[PartOut], summary="List part references")
def list_parts(
    search: str | None = Query(default=None, description="Filter on reference or designation"),
    limit: int = Query(
        default=100,
        le=5000,
        description="Maximum rows. The catalogue holds thousands of references, "
        "so a picker that needs them all must ask for them.",
    ),
    db: Session = Depends(get_session),
) -> list[PartOut]:
    return [
        PartOut.model_validate(part) for part in PartRepository(db).search(search, limit=limit)
    ]


@router.get("/parts/{part_id}", response_model=PartOut, summary="Get one part reference")
def get_part(part_id: int, db: Session = Depends(get_session)) -> PartOut:
    return PartOut.model_validate(PartRepository(db).require(part_id))


@router.get("/suppliers", response_model=list[SupplierOut], summary="List suppliers")
def list_suppliers(db: Session = Depends(get_session)) -> list[SupplierOut]:
    return [SupplierOut.model_validate(item) for item in SupplierRepository(db).all_active()]


@router.get("/categories", response_model=list[CategoryOut], summary="List categories")
def list_categories(db: Session = Depends(get_session)) -> list[CategoryOut]:
    return [CategoryOut.model_validate(item) for item in CategoryRepository(db).all()]


@router.get("/stations", response_model=list[StationOut], summary="List production stations")
def list_stations(db: Session = Depends(get_session)) -> list[StationOut]:
    return [StationOut.model_validate(item) for item in ProductionRepository(db).stations()]


@router.get("/users", response_model=list[UserOut], summary="List simulated operators")
def list_users(db: Session = Depends(get_session)) -> list[UserOut]:
    return [UserOut.model_validate(item) for item in UserRepository(db).all_with_roles()]


@router.get("/settings", response_model=list[SettingOut], summary="List business settings")
def list_settings(db: Session = Depends(get_session)) -> list[SettingOut]:
    settings = settings_service.list_settings(db)
    db.commit()
    return [SettingOut.model_validate(item) for item in settings]


@router.put("/settings/{key}", response_model=SettingOut, summary="Update a business setting")
def update_setting(
    key: str, payload: SettingUpdate, db: Session = Depends(get_session)
) -> SettingOut:
    setting = settings_service.update_setting(db, key, payload.value)
    audit_service.record(
        db,
        action=AuditAction.SETTING_UPDATED,
        entity_type="system_setting",
        entity_id=setting.id,
        entity_reference=setting.key,
        reason=f"{setting.key} set to {setting.value}",
    )
    db.commit()
    return SettingOut.model_validate(setting)
