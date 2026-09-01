"""The inbound flow: lots, receptions, inspections and quality decisions."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import (
    InspectionResult,
    LotStatus,
    QualityDecision,
    ReceptionStatus,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Part, Supplier
    from app.models.organization import User
    from app.models.warehouse import StockMovement, WarehouseLocation


class Lot(Base, TimestampMixin):
    """A batch of one part reference delivered by one supplier.

    ``quantity_received`` is what physically arrived; ``quantity_available`` is
    what is left of the lot once it has been stored and partially consumed. A lot
    only becomes stock after quality approval *and* storage confirmation.
    """

    __tablename__ = "lots"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), nullable=False, index=True)

    quantity_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Quantity cleared by quality; set when the lot is approved.
    quantity_approved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Remaining quantity of this lot still held in stock.
    quantity_available: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[LotStatus] = mapped_column(
        SAEnum(LotStatus, native_enum=False, length=32),
        default=LotStatus.PENDING_INSPECTION,
        nullable=False,
        index=True,
    )

    #: Location where the lot was stored (set at storage confirmation).
    location_id: Mapped[int | None] = mapped_column(ForeignKey("warehouse_locations.id"))
    stored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    blocked_reason: Mapped[str | None] = mapped_column(Text)
    #: Set only when the services composed the reason themselves, so the screen
    #: can word it in the reader's language. A justification typed by a manager
    #: has no key: their words are the record.
    blocked_reason_key: Mapped[str | None] = mapped_column(String(40))
    blocked_reason_values: Mapped[str | None] = mapped_column(Text)

    part: Mapped["Part"] = relationship(back_populates="lots")
    supplier: Mapped["Supplier"] = relationship(back_populates="lots")
    location: Mapped["WarehouseLocation | None"] = relationship(back_populates="lots")
    reception: Mapped["Reception | None"] = relationship(
        back_populates="lot", uselist=False, cascade="all, delete-orphan"
    )
    inspections: Mapped[list["Inspection"]] = relationship(
        back_populates="lot", cascade="all, delete-orphan", order_by="Inspection.id"
    )
    quality_validations: Mapped[list["QualityValidation"]] = relationship(
        back_populates="lot", cascade="all, delete-orphan", order_by="QualityValidation.id"
    )
    movements: Mapped[list["StockMovement"]] = relationship(back_populates="lot")

    @property
    def is_blocked(self) -> bool:
        return self.status in (LotStatus.RED_CAGE, LotStatus.REJECTED)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Lot {self.lot_number} {self.status}>"


class Reception(Base, TimestampMixin):
    """Quantity check performed when the truck is unloaded.

    A reception NEVER changes stock - it only records what arrived.
    """

    __tablename__ = "receptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), nullable=False, unique=True)

    quantity_expected: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_received: Mapped[int] = mapped_column(Integer, nullable=False)
    #: Signed difference received - expected.
    quantity_gap: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Tolerance actually applied for this reception, in percent.
    tolerance_percent_applied: Mapped[float] = mapped_column(default=0.0, nullable=False)

    status: Mapped[ReceptionStatus] = mapped_column(
        SAEnum(ReceptionStatus, native_enum=False, length=32), nullable=False, index=True
    )
    delivery_note: Mapped[str | None] = mapped_column(String(60))
    notes: Mapped[str | None] = mapped_column(Text)

    received_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lot: Mapped["Lot"] = relationship(back_populates="reception")
    received_by: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Reception {self.reference} {self.status}>"


class Inspection(Base, TimestampMixin):
    """Sampling-based quality inspection of a lot.

    Quality does not check every part: a sample is drawn and the defect count on
    that sample determines whether the lot is conform.
    """

    __tablename__ = "inspections"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), nullable=False, index=True)

    sample_size: Mapped[int] = mapped_column(Integer, nullable=False)
    defects_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Maximum defect rate tolerated on the sample, in percent.
    defect_threshold_percent: Mapped[float] = mapped_column(default=0.0, nullable=False)

    result: Mapped[InspectionResult] = mapped_column(
        SAEnum(InspectionResult, native_enum=False, length=20), nullable=False, index=True
    )
    observations: Mapped[str | None] = mapped_column(Text)

    inspector_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    inspected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lot: Mapped["Lot"] = relationship(back_populates="inspections")
    inspector: Mapped["User | None"] = relationship()

    @property
    def defect_rate_percent(self) -> float:
        if self.sample_size <= 0:
            return 0.0
        return round(self.defects_found / self.sample_size * 100, 2)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Inspection {self.reference} {self.result}>"


class QualityValidation(Base, TimestampMixin):
    """The decision taken by quality on an inspected lot.

    Approving a lot does NOT create stock; it only unlocks storage.
    """

    __tablename__ = "quality_validations"

    id: Mapped[int] = mapped_column(primary_key=True)
    lot_id: Mapped[int] = mapped_column(ForeignKey("lots.id"), nullable=False, index=True)
    inspection_id: Mapped[int | None] = mapped_column(ForeignKey("inspections.id"))

    decision: Mapped[QualityDecision] = mapped_column(
        SAEnum(QualityDecision, native_enum=False, length=20), nullable=False, index=True
    )
    quantity_approved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    #: Mandatory justification - a decision is never recorded without a reason.
    justification: Mapped[str] = mapped_column(Text, nullable=False)

    decided_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    lot: Mapped["Lot"] = relationship(back_populates="quality_validations")
    inspection: Mapped["Inspection | None"] = relationship()
    decided_by: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<QualityValidation lot={self.lot_id} {self.decision}>"
