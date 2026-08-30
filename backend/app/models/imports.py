"""Excel imports and the Maker-Checker validation workflow.

An operator (the MAKER) fills a spreadsheet and uploads it. The file is parsed
and stored, but **nothing is written to the business tables and no stock
operation is executed** until a habilitated responsible (the CHECKER, always a
different person) approves it inside SLCC.

The record keeps everything the audit requires: who entered the data, who
checked it, when, the decision, the justification on rejection, the source file
and its SHA-256 hash.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
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
from app.models.enums import (
    ImportRowStatus,
    ImportStatus,
    ImportType,
    ValidationDecision,
)
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.organization import User


class DataImport(Base, TimestampMixin):
    """One uploaded spreadsheet awaiting - or having received - a decision."""

    __tablename__ = "data_imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    reference: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)

    import_type: Mapped[ImportType] = mapped_column(
        SAEnum(ImportType, native_enum=False, length=32), nullable=False, index=True
    )
    status: Mapped[ImportStatus] = mapped_column(
        SAEnum(ImportStatus, native_enum=False, length=24),
        default=ImportStatus.IMPORTED,
        nullable=False,
        index=True,
    )

    # --- Source file -------------------------------------------------------
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    #: SHA-256 of the uploaded bytes: proves which exact file was validated.
    source_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    valid_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    invalid_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    applied_row_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # --- MAKER: the operator who entered the data --------------------------
    maker_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    #: Denormalised so the trace survives even if the user record changes.
    maker_reference: Mapped[str] = mapped_column(String(20), nullable=False)
    maker_role: Mapped[str] = mapped_column(String(32), nullable=False)
    maker_service: Mapped[str | None] = mapped_column(String(60))
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # --- CHECKER: the responsible who validated ----------------------------
    checker_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    checker_reference: Mapped[str | None] = mapped_column(String(20))
    checker_role: Mapped[str | None] = mapped_column(String(32))
    checker_service: Mapped[str | None] = mapped_column(String(60))
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    decision: Mapped[ValidationDecision | None] = mapped_column(
        SAEnum(ValidationDecision, native_enum=False, length=20), index=True
    )
    #: Mandatory when the decision is REJECTED.
    decision_comment: Mapped[str | None] = mapped_column(Text)

    notes: Mapped[str | None] = mapped_column(Text)

    maker: Mapped["User"] = relationship(foreign_keys=[maker_id])
    checker: Mapped["User | None"] = relationship(foreign_keys=[checker_id])
    rows: Mapped[list["ImportRow"]] = relationship(
        back_populates="data_import",
        cascade="all, delete-orphan",
        order_by="ImportRow.row_number",
    )

    @property
    def is_pending(self) -> bool:
        return self.status in (ImportStatus.IMPORTED, ImportStatus.PENDING_REVIEW)

    @property
    def is_decided(self) -> bool:
        return self.status in (ImportStatus.APPROVED, ImportStatus.REJECTED)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<DataImport {self.reference} {self.status}>"


class ImportRow(Base):
    """One line of an imported spreadsheet.

    The parsed payload is kept verbatim so a rejected or failed line stays fully
    traceable: what was entered, why it was refused, and what it produced when it
    was applied.
    """

    __tablename__ = "import_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("data_imports.id"), nullable=False, index=True
    )
    #: 1-based line number in the source file, so the operator can find it.
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)

    status: Mapped[ImportRowStatus] = mapped_column(
        SAEnum(ImportRowStatus, native_enum=False, length=16),
        default=ImportRowStatus.PENDING,
        nullable=False,
        index=True,
    )
    #: JSON of the parsed columns, exactly as read from the file.
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    #: Why the line was refused, when it was.
    error_message: Mapped[str | None] = mapped_column(Text)
    #: Business reference created once the line is applied (lot, inspection...).
    result_reference: Mapped[str | None] = mapped_column(String(40))

    data_import: Mapped["DataImport"] = relationship(back_populates="rows")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ImportRow {self.import_id}#{self.row_number} {self.status}>"
