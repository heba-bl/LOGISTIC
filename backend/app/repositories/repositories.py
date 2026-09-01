"""Concrete repositories.

Repositories own the queries; services own the rules. Keeping SQLAlchemy here
means a service reads like the business process it implements.
"""

from __future__ import annotations

from datetime import datetime
from typing import Sequence

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import joinedload, selectinload

from app.core.exceptions import NotFoundError
from app.models.catalog import Category, Part, Supplier
from app.models.enums import (
    LotStatus,
    ProductionRequestStatus,
)
from app.models.flow import Inspection, Lot, QualityValidation, Reception
from app.models.organization import Role, User
from app.models.production import ProductionRequest, ProductionStation
from app.models.system import AIRecommendation, AuditLog
from app.models.warehouse import (
    PartLocation,
    Stock,
    StockMovement,
    Warehouse,
    WarehouseLocation,
)
from app.repositories.base import BaseRepository


def _require(entity, label: str, identifier):
    if entity is None:
        raise NotFoundError(f"{label} {identifier} not found")
    return entity


class PartRepository(BaseRepository[Part]):
    model = Part

    def require(self, part_id: int) -> Part:
        return _require(self.get(part_id), "Part", part_id)

    def by_reference(self, reference: str) -> Part | None:
        return self.db.execute(
            select(Part).where(Part.reference == reference)
        ).scalar_one_or_none()

    def all_active(self) -> Sequence[Part]:
        return (
            self.db.execute(
                select(Part)
                .where(Part.is_active.is_(True))
                .options(joinedload(Part.category), joinedload(Part.stock))
                .order_by(Part.reference)
            )
            .scalars()
            .all()
        )

    def managed(self) -> Sequence[Part]:
        """The references the warehouse actually holds.

        Everything that reasons about replenishment - shortage risk, coverage,
        safety levels - reads this, not the whole catalogue. The catalogue is a
        bill of materials; the perimeter is what a magasinier is responsible for.
        """
        return (
            self.db.execute(
                select(Part)
                .where(Part.is_active.is_(True), Part.is_managed.is_(True))
                .options(joinedload(Part.category), joinedload(Part.stock))
                .order_by(Part.reference)
            )
            .scalars()
            .all()
        )

    def search(self, term: str | None, limit: int = 100) -> Sequence[Part]:
        stmt = select(Part).options(joinedload(Part.category), joinedload(Part.stock))
        if term:
            pattern = f"%{term.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Part.reference).like(pattern),
                    func.lower(Part.designation).like(pattern),
                )
            )
        return self.db.execute(stmt.order_by(Part.reference).limit(limit)).scalars().all()


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier

    def require(self, supplier_id: int) -> Supplier:
        return _require(self.get(supplier_id), "Supplier", supplier_id)

    def by_code(self, code: str) -> Supplier | None:
        return self.db.execute(
            select(Supplier).where(Supplier.code == code.strip().upper())
        ).scalar_one_or_none()

    def all_active(self) -> Sequence[Supplier]:
        return (
            self.db.execute(
                select(Supplier).where(Supplier.is_active.is_(True)).order_by(Supplier.name)
            )
            .scalars()
            .all()
        )


class CategoryRepository(BaseRepository[Category]):
    model = Category

    def all(self) -> Sequence[Category]:
        return self.db.execute(select(Category).order_by(Category.name)).scalars().all()


class UserRepository(BaseRepository[User]):
    model = User

    def require(self, user_id: int) -> User:
        return _require(self.get(user_id), "User", user_id)

    def optional(self, user_id: int | None) -> User | None:
        return self.get(user_id) if user_id else None

    def all_with_roles(self) -> Sequence[User]:
        return (
            self.db.execute(
                select(User).options(joinedload(User.role)).order_by(User.full_name)
            )
            .scalars()
            .all()
        )

    def by_role(self, role_name) -> Sequence[User]:
        return (
            self.db.execute(select(User).join(Role).where(Role.name == role_name))
            .scalars()
            .all()
        )


class LotRepository(BaseRepository[Lot]):
    model = Lot

    _LOADERS = (
        joinedload(Lot.part),
        joinedload(Lot.supplier),
        joinedload(Lot.location),
    )

    def require(self, lot_id: int) -> Lot:
        lot = self.db.execute(
            select(Lot).where(Lot.id == lot_id).options(*self._LOADERS)
        ).scalar_one_or_none()
        return _require(lot, "Lot", lot_id)

    def by_number(self, lot_number: str) -> Lot | None:
        return self.db.execute(
            select(Lot).where(Lot.lot_number == lot_number).options(*self._LOADERS)
        ).scalar_one_or_none()

    def _base(self) -> Select:
        return select(Lot).options(*self._LOADERS)

    def list_filtered(
        self,
        *,
        statuses: Sequence[LotStatus] | None = None,
        part_id: int | None = None,
        supplier_id: int | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> Sequence[Lot]:
        stmt = self._base()
        if statuses:
            stmt = stmt.where(Lot.status.in_(list(statuses)))
        if part_id:
            stmt = stmt.where(Lot.part_id == part_id)
        if supplier_id:
            stmt = stmt.where(Lot.supplier_id == supplier_id)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.join(Part).where(
                or_(
                    func.lower(Lot.lot_number).like(pattern),
                    func.lower(Part.reference).like(pattern),
                )
            )
        return self.db.execute(stmt.order_by(Lot.id.desc()).limit(limit)).scalars().all()

    def count_by_status(self) -> dict[str, int]:
        rows = self.db.execute(select(Lot.status, func.count()).group_by(Lot.status)).all()
        return {str(status.value if hasattr(status, "value") else status): count for status, count in rows}

    def in_stage(self, statuses: Sequence[LotStatus]) -> Sequence[Lot]:
        return (
            self.db.execute(self._base().where(Lot.status.in_(list(statuses))).order_by(Lot.id))
            .scalars()
            .all()
        )

    def blocked(self) -> Sequence[Lot]:
        return self.in_stage([LotStatus.RED_CAGE, LotStatus.REJECTED])

    def full_history(self, lot_id: int) -> Lot:
        lot = self.db.execute(
            select(Lot)
            .where(Lot.id == lot_id)
            .options(
                joinedload(Lot.part),
                joinedload(Lot.supplier),
                joinedload(Lot.location),
                joinedload(Lot.reception),
                selectinload(Lot.inspections),
                selectinload(Lot.quality_validations),
                selectinload(Lot.movements),
            )
        ).scalar_one_or_none()
        return _require(lot, "Lot", lot_id)


class ReceptionRepository(BaseRepository[Reception]):
    model = Reception

    def recent(self, limit: int = 100) -> Sequence[Reception]:
        return (
            self.db.execute(
                select(Reception)
                .options(
                    joinedload(Reception.lot).joinedload(Lot.part),
                    joinedload(Reception.lot).joinedload(Lot.supplier),
                    joinedload(Reception.received_by),
                )
                .order_by(Reception.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def require(self, reception_id: int) -> Reception:
        return _require(self.get(reception_id), "Reception", reception_id)


class InspectionRepository(BaseRepository[Inspection]):
    model = Inspection

    def recent(self, limit: int = 100) -> Sequence[Inspection]:
        return (
            self.db.execute(
                select(Inspection)
                .options(
                    joinedload(Inspection.lot).joinedload(Lot.part),
                    # The supervision report names the supplier too, so it is
                    # loaded here rather than fetched per row.
                    joinedload(Inspection.lot).joinedload(Lot.supplier),
                    joinedload(Inspection.inspector),
                )
                .order_by(Inspection.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def latest_for_lot(self, lot_id: int) -> Inspection | None:
        return self.db.execute(
            select(Inspection)
            .where(Inspection.lot_id == lot_id)
            .order_by(Inspection.id.desc())
            .limit(1)
        ).scalar_one_or_none()


class QualityRepository(BaseRepository[QualityValidation]):
    model = QualityValidation

    def recent(self, limit: int = 100) -> Sequence[QualityValidation]:
        return (
            self.db.execute(
                select(QualityValidation)
                .options(
                    joinedload(QualityValidation.lot).joinedload(Lot.part),
                    joinedload(QualityValidation.decided_by),
                )
                .order_by(QualityValidation.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )


class WarehouseRepository(BaseRepository[WarehouseLocation]):
    model = WarehouseLocation

    def require(self, location_id: int) -> WarehouseLocation:
        return _require(self.get(location_id), "Location", location_id)

    def by_code(self, code: str) -> WarehouseLocation | None:
        return self.db.execute(
            select(WarehouseLocation).where(WarehouseLocation.code == code)
        ).scalar_one_or_none()

    def all_locations(self) -> Sequence[WarehouseLocation]:
        return (
            self.db.execute(
                select(WarehouseLocation).order_by(
                    WarehouseLocation.zone, WarehouseLocation.position
                )
            )
            .scalars()
            .all()
        )

    def warehouses(self) -> Sequence[Warehouse]:
        return self.db.execute(select(Warehouse).order_by(Warehouse.code)).scalars().all()

    def lots_at(self, location_id: int) -> Sequence[Lot]:
        return (
            self.db.execute(
                select(Lot)
                .where(Lot.location_id == location_id, Lot.quantity_available > 0)
                .options(joinedload(Lot.part), joinedload(Lot.supplier))
                .order_by(Lot.id)
            )
            .scalars()
            .all()
        )

    def part_links(self, part_id: int) -> Sequence[PartLocation]:
        return (
            self.db.execute(
                select(PartLocation)
                .where(PartLocation.part_id == part_id)
                .options(joinedload(PartLocation.location))
                .order_by(PartLocation.role)
            )
            .scalars()
            .all()
        )

    def total_occupancy(self) -> tuple[int, int]:
        row = self.db.execute(
            select(
                func.coalesce(func.sum(WarehouseLocation.occupied), 0),
                func.coalesce(func.sum(WarehouseLocation.capacity), 0),
            ).where(WarehouseLocation.is_active.is_(True))
        ).one()
        return int(row[0]), int(row[1])


class StockRepository(BaseRepository[Stock]):
    model = Stock

    def for_part(self, part_id: int) -> Stock | None:
        return self.db.execute(select(Stock).where(Stock.part_id == part_id)).scalar_one_or_none()

    def all_with_parts(self) -> Sequence[Stock]:
        return (
            self.db.execute(
                select(Stock)
                .options(joinedload(Stock.part).joinedload(Part.category))
                .join(Part)
                .order_by(Part.reference)
            )
            .scalars()
            .all()
        )

    def total_quantity(self) -> int:
        return int(
            self.db.execute(
                select(func.coalesce(func.sum(Stock.quantity_available), 0))
            ).scalar_one()
        )

    def movements(
        self,
        *,
        part_id: int | None = None,
        lot_id: int | None = None,
        since: datetime | None = None,
        limit: int = 200,
    ) -> Sequence[StockMovement]:
        stmt = select(StockMovement).options(
            joinedload(StockMovement.part),
            joinedload(StockMovement.location),
            joinedload(StockMovement.lot),
            joinedload(StockMovement.station),
        )
        if part_id:
            stmt = stmt.where(StockMovement.part_id == part_id)
        if lot_id:
            stmt = stmt.where(StockMovement.lot_id == lot_id)
        if since:
            stmt = stmt.where(StockMovement.occurred_at >= since)
        return (
            self.db.execute(stmt.order_by(StockMovement.id.desc()).limit(limit)).scalars().all()
        )


class ProductionRepository(BaseRepository[ProductionRequest]):
    model = ProductionRequest

    _LOADERS = (
        joinedload(ProductionRequest.part),
        joinedload(ProductionRequest.station),
        joinedload(ProductionRequest.requested_by),
        joinedload(ProductionRequest.approved_by),
    )

    def require(self, request_id: int) -> ProductionRequest:
        request = self.db.execute(
            select(ProductionRequest)
            .where(ProductionRequest.id == request_id)
            .options(*self._LOADERS)
        ).scalar_one_or_none()
        return _require(request, "Production request", request_id)

    def list_filtered(
        self,
        *,
        statuses: Sequence[ProductionRequestStatus] | None = None,
        station_id: int | None = None,
        part_id: int | None = None,
        limit: int = 200,
    ) -> Sequence[ProductionRequest]:
        stmt = select(ProductionRequest).options(*self._LOADERS)
        if statuses:
            stmt = stmt.where(ProductionRequest.status.in_(list(statuses)))
        if station_id:
            stmt = stmt.where(ProductionRequest.station_id == station_id)
        if part_id:
            stmt = stmt.where(ProductionRequest.part_id == part_id)
        return (
            self.db.execute(stmt.order_by(ProductionRequest.id.desc()).limit(limit))
            .scalars()
            .all()
        )

    def open_requests(self) -> Sequence[ProductionRequest]:
        return self.list_filtered(
            statuses=[
                ProductionRequestStatus.SUBMITTED,
                ProductionRequestStatus.APPROVED,
                ProductionRequestStatus.PREPARING,
                ProductionRequestStatus.READY,
            ]
        )

    def demand_for_part(self, part_id: int) -> int:
        """Quantity committed to open requests but not yet issued."""
        return int(
            self.db.execute(
                select(
                    func.coalesce(
                        func.sum(
                            ProductionRequest.quantity_requested
                            - ProductionRequest.quantity_issued
                        ),
                        0,
                    )
                ).where(
                    ProductionRequest.part_id == part_id,
                    ProductionRequest.status.in_(
                        [
                            ProductionRequestStatus.SUBMITTED,
                            ProductionRequestStatus.APPROVED,
                            ProductionRequestStatus.PREPARING,
                            ProductionRequestStatus.READY,
                        ]
                    ),
                )
            ).scalar_one()
        )

    def stations(self) -> Sequence[ProductionStation]:
        return (
            self.db.execute(select(ProductionStation).order_by(ProductionStation.code))
            .scalars()
            .all()
        )

    def require_station(self, station_id: int) -> ProductionStation:
        return _require(
            self.db.get(ProductionStation, station_id), "Production station", station_id
        )


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    def timeline(
        self,
        *,
        lot_id: int | None = None,
        part_id: int | None = None,
        entity_type: str | None = None,
        entity_reference: str | None = None,
        search: str | None = None,
        limit: int = 200,
    ) -> Sequence[AuditLog]:
        stmt = select(AuditLog).options(joinedload(AuditLog.lot), joinedload(AuditLog.part))
        if lot_id:
            stmt = stmt.where(AuditLog.lot_id == lot_id)
        if part_id:
            stmt = stmt.where(AuditLog.part_id == part_id)
        if entity_type:
            stmt = stmt.where(AuditLog.entity_type == entity_type)
        if entity_reference:
            stmt = stmt.where(AuditLog.entity_reference == entity_reference)
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(AuditLog.entity_reference).like(pattern),
                    func.lower(AuditLog.reason).like(pattern),
                    func.lower(AuditLog.actor_name).like(pattern),
                )
            )
        return self.db.execute(stmt.order_by(AuditLog.id.desc()).limit(limit)).scalars().all()

    def recent(self, limit: int = 20) -> Sequence[AuditLog]:
        return self.timeline(limit=limit)


class RecommendationRepository(BaseRepository[AIRecommendation]):
    model = AIRecommendation

    def active(self, limit: int = 50) -> Sequence[AIRecommendation]:
        return (
            self.db.execute(
                select(AIRecommendation)
                .where(AIRecommendation.is_active.is_(True))
                .options(joinedload(AIRecommendation.part), joinedload(AIRecommendation.lot))
                .order_by(AIRecommendation.priority, AIRecommendation.id.desc())
                .limit(limit)
            )
            .scalars()
            .all()
        )

    def deactivate_all(self) -> None:
        for row in self.db.execute(
            select(AIRecommendation).where(AIRecommendation.is_active.is_(True))
        ).scalars():
            row.is_active = False
        self.db.flush()
