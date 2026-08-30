"""Vehicle nomenclature (BOM).

The engineering bill of materials of the demonstration vehicle. It is the
reference catalogue the plant works from: every logistics reference managed in
the flow comes from it, but only a subset is actively managed as stock.

SYNTHETIC DATA - generated for the demonstration, not company data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import PartSize
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Part


class Vehicle(Base, TimestampMixin):
    """A vehicle model produced on the line."""

    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    segment: Mapped[str | None] = mapped_column(String(60))
    model_year: Mapped[int | None] = mapped_column(Integer)
    description: Mapped[str | None] = mapped_column(Text)

    bom_lines: Mapped[list["VehicleBomLine"]] = relationship(
        back_populates="vehicle", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Vehicle {self.code}>"


class VehicleBomLine(Base, TimestampMixin):
    """One reference of the vehicle nomenclature.

    ``part_id`` is set only for the references actually managed in the logistics
    flow; the rest of the nomenclature exists as engineering data.
    """

    __tablename__ = "vehicle_bom"
    __table_args__ = (
        UniqueConstraint("vehicle_id", "part_reference", name="bom_vehicle_reference_unique"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False, index=True)

    part_reference: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    part_description: Mapped[str] = mapped_column(String(200), nullable=False)

    #: Top-level system, e.g. BRK (braking), ELE (electrical).
    system_code: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    system_label: Mapped[str] = mapped_column(String(80), nullable=False)
    subsystem: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    size_class: Mapped[PartSize] = mapped_column(
        SAEnum(PartSize, native_enum=False, length=16), default=PartSize.SMALL, nullable=False
    )
    quantity_per_vehicle: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit: Mapped[str] = mapped_column(String(10), default="PCS", nullable=False)
    supplier_code: Mapped[str | None] = mapped_column(String(20), index=True)

    #: True when the reference is followed by the logistics flow (has stock).
    is_managed: Mapped[bool] = mapped_column(default=False, nullable=False, index=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), index=True)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="bom_lines")
    part: Mapped["Part | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BOM {self.part_reference}>"
