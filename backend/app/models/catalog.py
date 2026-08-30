"""Reference data: suppliers, categories and part references."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PartSize
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.flow import Lot
    from app.models.warehouse import PartLocation, Stock


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    country: Mapped[str | None] = mapped_column(String(60))
    #: Contractual lead time, used by the shortage-risk model.
    lead_time_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    lots: Mapped[list["Lot"]] = relationship(back_populates="supplier")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Supplier {self.code}>"


class Category(Base, TimestampMixin):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    parts: Mapped[list["Part"]] = relationship(back_populates="category")


class Part(Base, TimestampMixin):
    """A part reference, e.g. BR-145."""

    __tablename__ = "parts"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    designation: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"))

    #: SMALL parts accept a reception tolerance, LARGE parts require an exact count.
    size_class: Mapped[PartSize] = mapped_column(
        SAEnum(PartSize, native_enum=False, length=16), default=PartSize.SMALL, nullable=False
    )
    #: Per-part override of the global tolerance, in percent. NULL = use the setting.
    reception_tolerance_percent: Mapped[float | None] = mapped_column()

    unit: Mapped[str] = mapped_column(String(10), default="PCS", nullable=False)

    #: Whether the warehouse actually holds this reference.
    #:
    #: The catalogue is the vehicle's bill of materials; a plant does not stock
    #: every line of it. Only a managed reference carries a safety level, is
    #: replenished, and takes part in the shortage analysis - a reference nobody
    #: replenishes cannot be short, and counting it as such buries the ones that
    #: can genuinely stop a line.
    is_managed: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)

    #: Below this quantity the part is considered at risk of shortage.
    #: Meaningful only inside the managed perimeter.
    safety_stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Average daily consumption, used for days-of-cover computation.
    average_daily_consumption: Mapped[float] = mapped_column(default=0.0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    category: Mapped["Category | None"] = relationship(back_populates="parts")
    lots: Mapped[list["Lot"]] = relationship(back_populates="part")
    stock: Mapped["Stock | None"] = relationship(back_populates="part", uselist=False)
    locations: Mapped[list["PartLocation"]] = relationship(
        back_populates="part", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Part {self.reference}>"
