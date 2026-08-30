"""Cross-cutting tables: audit trail, AI recommendations and runtime settings."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AuditAction, RecommendationKind, RiskLevel, Severity
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.catalog import Part
    from app.models.flow import Lot
    from app.models.organization import User


class AuditLog(Base):
    """Append-only trace answering: who, what, when, how much, on what, why.

    Written inside the same transaction as the operation it describes, so an
    operation can never succeed without leaving a trace.
    """

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[AuditAction] = mapped_column(
        SAEnum(AuditAction, native_enum=False, length=40), nullable=False, index=True
    )

    #: Logical target, e.g. "lot" / "production_request" / "stock".
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, index=True)
    entity_reference: Mapped[str | None] = mapped_column(String(40), index=True)

    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"), index=True)
    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), index=True)
    quantity: Mapped[int | None] = mapped_column(Integer)
    location_code: Mapped[str | None] = mapped_column(String(20))

    status_before: Mapped[str | None] = mapped_column(String(40))
    status_after: Mapped[str | None] = mapped_column(String(40))
    reason: Mapped[str | None] = mapped_column(Text)

    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    actor_name: Mapped[str] = mapped_column(String(120), default="system", nullable=False)
    #: Employee number of the operator who acted, so the trail is never anonymous.
    actor_reference: Mapped[str | None] = mapped_column(String(20), index=True)
    actor_role: Mapped[str | None] = mapped_column(String(32))

    # --- Maker-Checker -----------------------------------------------------
    # Filled on validation events: who entered the data, who confirmed it.
    maker_reference: Mapped[str | None] = mapped_column(String(20), index=True)
    maker_role: Mapped[str | None] = mapped_column(String(32))
    checker_reference: Mapped[str | None] = mapped_column(String(20), index=True)
    checker_role: Mapped[str | None] = mapped_column(String(32))
    decision: Mapped[str | None] = mapped_column(String(20))
    #: Source spreadsheet and its hash, when the event comes from an import.
    source_file: Mapped[str | None] = mapped_column(String(255))
    source_hash: Mapped[str | None] = mapped_column(String(64))

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    lot: Mapped["Lot | None"] = relationship()
    part: Mapped["Part | None"] = relationship()
    actor: Mapped["User | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Audit {self.action} {self.entity_reference}>"


class AIRecommendation(Base, TimestampMixin):
    """A recommendation produced by the analysis engine.

    ``rationale`` is mandatory: the specification forbids a recommendation
    without an explanation of why it was produced.
    """

    __tablename__ = "ai_recommendations"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[RecommendationKind] = mapped_column(
        SAEnum(RecommendationKind, native_enum=False, length=32), nullable=False, index=True
    )
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, native_enum=False, length=16), nullable=False, index=True
    )
    risk_level: Mapped[RiskLevel | None] = mapped_column(
        SAEnum(RiskLevel, native_enum=False, length=16)
    )
    #: 1 = treat first.
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    #: Why the engine reached this conclusion, in plain language.
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    #: Concrete action suggested to the logistics manager.
    recommended_action: Mapped[str | None] = mapped_column(Text)

    part_id: Mapped[int | None] = mapped_column(ForeignKey("parts.id"), index=True)
    lot_id: Mapped[int | None] = mapped_column(ForeignKey("lots.id"), index=True)
    location_code: Mapped[str | None] = mapped_column(String(20))

    #: Machine-readable numbers backing the message (stock, cover, thresholds).
    metrics_json: Mapped[str | None] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    part: Mapped["Part | None"] = relationship()
    lot: Mapped["Lot | None"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation {self.kind} p{self.priority}>"


class SystemSetting(Base, TimestampMixin):
    """Runtime configuration editable from the Settings screen.

    Business thresholds (reception tolerance, defect threshold, sampling rules)
    live here rather than being hardcoded across the codebase.
    """

    __tablename__ = "system_settings"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(60), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(String(120), nullable=False)
    value_type: Mapped[str] = mapped_column(String(20), default="float", nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    group: Mapped[str] = mapped_column(String(40), default="general", nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Setting {self.key}={self.value}>"
