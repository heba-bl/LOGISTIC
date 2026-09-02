"""Who is looking after which alert.

An alert is not a business record. SLCC derives it from the state of the plant -
a lot in the Red Cage, a request stock cannot cover, an address filling up - so
it exists nowhere in the shared workbook and cannot be answered there.

What can be answered here is the supervision question: *who is on it*. An alert
nobody owns is an alert nobody handles, and forty-four of them a week teaches a
logistics manager to stop reading the panel entirely. That is alarm fatigue, and
it is how a real one gets missed.

The rule this table must never break: **an acknowledgement changes no business
state**. It does not release a lot, move stock, or validate a line - those are
decisions that belong to the workbook, taken by the zone chief who signs them.
It records only who is watching, since when, and until when.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AlertAction

if TYPE_CHECKING:
    from app.models.organization import User


class AlertAcknowledgement(Base):
    """One decision taken about one alert."""

    __tablename__ = "alert_acknowledgements"

    id: Mapped[int] = mapped_column(primary_key=True)

    #: The alert's own identifier - `redcage-42`, `req-118`, `loc-7`. Derived
    #: from the thing that raised it, so the same situation keeps the same key
    #: across refreshes and an acknowledgement survives a page reload.
    alert_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    action: Mapped[AlertAction] = mapped_column(
        SAEnum(AlertAction, native_enum=False, length=16), nullable=False, index=True
    )

    actor_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    #: Denormalised, so the trace survives the user record changing.
    actor_reference: Mapped[str] = mapped_column(String(20), nullable=False)

    #: Why it is being held. Mandatory on SNOOZED: "I have seen it" without a
    #: reason tells the next reader nothing they did not already know.
    reason: Mapped[str | None] = mapped_column(Text)

    #: When a snoozed alert comes back. Null for the other actions.
    snooze_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    actor: Mapped["User"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<AlertAcknowledgement {self.alert_key} {self.action}>"
