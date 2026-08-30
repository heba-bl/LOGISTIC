"""Production stations and their parts requests."""

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
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import ProductionRequestStatus
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Part
    from app.models.organization import User
    from app.models.warehouse import StockMovement


class ProductionStation(Base, TimestampMixin):
    __tablename__ = "production_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    production_line: Mapped[str | None] = mapped_column(String(60))
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    requests: Mapped[list["ProductionRequest"]] = relationship(back_populates="station")
    leaders: Mapped[list["User"]] = relationship(back_populates="station")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Station {self.code}>"


class ProductionRequest(Base, TimestampMixin):
    """A request for parts raised by a station leader.

    Creating, submitting or approving a request never moves stock. Only the
    confirmed issue (``ISSUED``) decrements it.
    """

    __tablename__ = "production_requests"
    __table_args__ = (
        CheckConstraint("quantity_requested > 0", name="request_quantity_positive"),
        CheckConstraint("quantity_issued >= 0", name="request_issued_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    station_id: Mapped[int] = mapped_column(
        ForeignKey("production_stations.id"), nullable=False, index=True
    )
    part_id: Mapped[int] = mapped_column(ForeignKey("parts.id"), nullable=False, index=True)

    quantity_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity_issued: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    status: Mapped[ProductionRequestStatus] = mapped_column(
        SAEnum(ProductionRequestStatus, native_enum=False, length=24),
        default=ProductionRequestStatus.DRAFT,
        nullable=False,
        index=True,
    )
    #: 1 = highest. Used by the AI prioritisation model.
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    needed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    rejection_reason: Mapped[str | None] = mapped_column(Text)

    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    issued_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))

    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    prepared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_on: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    station: Mapped["ProductionStation"] = relationship(back_populates="requests")
    part: Mapped["Part"] = relationship()
    requested_by: Mapped["User | None"] = relationship(foreign_keys=[requested_by_id])
    approved_by: Mapped["User | None"] = relationship(foreign_keys=[approved_by_id])
    issued_by: Mapped["User | None"] = relationship(foreign_keys=[issued_by_id])
    movements: Mapped[list["StockMovement"]] = relationship(back_populates="production_request")

    @property
    def is_open(self) -> bool:
        return self.status not in (
            ProductionRequestStatus.ISSUED,
            ProductionRequestStatus.REJECTED,
            ProductionRequestStatus.CANCELLED,
        )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Request {self.reference} {self.status}>"
