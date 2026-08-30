"""Warehouse topology, stock and stock movements.

Stock is the single source of truth for availability. It is only ever changed by
``app.services.stock_service`` inside a transaction, and every change produces a
StockMovement plus an AuditLog entry.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import LocationRole, MovementType
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Part
    from app.models.flow import Lot
    from app.models.organization import User
    from app.models.production import ProductionRequest, ProductionStation


class Warehouse(Base, TimestampMixin):
    __tablename__ = "warehouses"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    locations: Mapped[list["WarehouseLocation"]] = relationship(
        back_populates="warehouse", cascade="all, delete-orphan"
    )


class WarehouseLocation(Base, TimestampMixin):
    """A physical address, e.g. WH-A-03.

    ``occupied`` is denormalised for fast dashboard queries and is maintained by
    the stock service in the same transaction as the movement.
    """

    __tablename__ = "warehouse_locations"
    __table_args__ = (
        CheckConstraint("occupied >= 0", name="occupied_non_negative"),
        CheckConstraint("capacity > 0", name="capacity_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    warehouse_id: Mapped[int] = mapped_column(ForeignKey("warehouses.id"), nullable=False)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    #: Row identifier used to lay the grid out (A, B, C...).
    zone: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)

    capacity: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    occupied: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Occupancy ratio above which the location is flagged as nearly saturated.
    warning_threshold_percent: Mapped[float] = mapped_column(default=75.0, nullable=False)
    critical_threshold_percent: Mapped[float] = mapped_column(default=90.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    warehouse: Mapped["Warehouse"] = relationship(back_populates="locations")
    lots: Mapped[list["Lot"]] = relationship(back_populates="location")
    part_links: Mapped[list["PartLocation"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )

    @property
    def occupancy_percent(self) -> float:
        if self.capacity <= 0:
            return 0.0
        return round(self.occupied / self.capacity * 100, 1)

    @property
    def free_capacity(self) -> int:
        return max(0, self.capacity - self.occupied)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location {self.code} {self.occupied}/{self.capacity}>"


class PartLocation(Base, TimestampMixin):
    """Addressing of a part: one primary address plus optional secondary ones.

    A bulky part, or a delivery larger than the primary location can hold, spills
    over onto secondary addresses.
    """

    __tablename__ = "part_locations"
    __table_args__ = (UniqueConstraint("part_id", "location_id", name="part_location_unique"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)
    location_id: Mapped[int] = mapped_column(
        ForeignKey("warehouse_locations.id"), nullable=False, index=True
    )
    role: Mapped[LocationRole] = mapped_column(
        SAEnum(LocationRole, native_enum=False, length=16),
        default=LocationRole.SECONDARY,
        nullable=False,
    )

    part: Mapped["Part"] = relationship(back_populates="locations")
    location: Mapped["WarehouseLocation"] = relationship(back_populates="part_links")


class Stock(Base, TimestampMixin):
    """Available quantity per part reference.

    One row per part. The CHECK constraint is the last line of defence behind the
    service layer: the database itself refuses a negative stock.
    """

    __tablename__ = "stock"
    __table_args__ = (CheckConstraint("quantity_available >= 0", name="quantity_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    part_id: Mapped[int] = mapped_column(
        ForeignKey("parts.id"), nullable=False, unique=True, index=True
    )
    quantity_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Quantity committed to approved production requests but not yet issued.
    quantity_reserved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_movement_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    part: Mapped["Part"] = relationship(back_populates="stock")

    @property
    def quantity_free(self) -> int:
        """Stock that is neither reserved nor issued."""
        return max(0, self.quantity_available - self.quantity_reserved)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Stock part={self.part_id} qty={self.quantity_available}>"


class StockMovement(Base):
    """Immutable ledger of every stock change.

    Rows are never updated or deleted: the movement history is the accounting
    record behind the current stock value.
    """

    __tablename__ = "stock_movements"
    __table_args__ = (CheckConstraint("quantity > 0", name="movement_quantity_positive"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    movement_type: Mapped[MovementType] = mapped_column(
        SAEnum(MovementType, native_enum=False, length=16), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    #: Stock level before and after the movement - makes the ledger self-checking.
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False)

    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"), index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id"))
    production_request_id: Mapped[int | None] = mapped_column(
        ForeignKey("production_requests.id"), index=True
    )
    station_id: Mapped[int | None] = mapped_column(ForeignKey("production_stations.id"))

    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    part: Mapped["Part"] = relationship()
    lot: Mapped["Lot | None"] = relationship(back_populates="movements")
    location: Mapped["WarehouseLocation | None"] = relationship()
    production_request: Mapped["ProductionRequest | None"] = relationship(
        back_populates="movements"
    )
    station: Mapped["ProductionStation | None"] = relationship()
    actor: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Movement {self.reference} {self.movement_type} {self.quantity}>"
