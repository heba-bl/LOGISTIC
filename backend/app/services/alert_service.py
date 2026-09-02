"""Supervision decisions taken on alerts.

An alert is derived, not stored: it exists only for as long as the situation
that raised it. So the decisions taken about it are stored separately and
matched back by the alert's own key.

The one rule: **none of this changes a business state**. Acknowledging does not
release a lot, snoozing does not cover a request, closing does not empty the Red
Cage. If the situation persists, the alert is still computed - it simply carries
a name and a date, and the count that matters becomes "how many nobody owns".
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ValidationError
from app.models.alerts import AlertAcknowledgement
from app.models.enums import AlertAction
from app.models.organization import User

#: How long a snooze lasts when the caller does not say.
DEFAULT_SNOOZE_HOURS = 24


def latest_by_alert(db: Session) -> dict[str, AlertAcknowledgement]:
    """The current standing of every alert that has ever been acted on.

    Only the newest decision counts: an alert acknowledged this morning and
    closed this afternoon is closed, and the morning row stays as trace.
    """
    rows = db.execute(
        select(AlertAcknowledgement)
        .options(selectinload(AlertAcknowledgement.actor))
        .order_by(AlertAcknowledgement.created_at.asc(), AlertAcknowledgement.id.asc())
    ).scalars().all()

    standing: dict[str, AlertAcknowledgement] = {}
    for row in rows:
        standing[row.alert_key] = row
    return standing


def _is_hidden(record: AlertAcknowledgement, now: datetime) -> bool:
    """Whether this decision keeps the alert out of the panel right now."""
    if record.action == AlertAction.CLOSED:
        return True
    if record.action == AlertAction.SNOOZED:
        due = record.snooze_until
        if due is None:
            return True
        if due.tzinfo is None:
            due = due.replace(tzinfo=timezone.utc)
        # A snooze that has expired hands the alert back rather than hiding it
        # for ever: the situation is still there, and nobody decided otherwise.
        return due > now
    return False


def apply(db: Session, alerts: list[dict]) -> tuple[list[dict], dict]:
    """Attach each alert's standing, drop the ones being held.

    Returns the visible alerts and the counts the panel puts above them. The
    number worth reading is not how many alerts exist but how many are in
    nobody's hands.
    """
    standing = latest_by_alert(db)
    now = datetime.now(timezone.utc)

    visible: list[dict] = []
    owned = snoozed = 0

    for alert in alerts:
        record = standing.get(str(alert.get("id", "")))
        if record is None:
            visible.append(alert)
            continue

        if _is_hidden(record, now):
            if record.action == AlertAction.SNOOZED:
                snoozed += 1
            continue

        if record.action == AlertAction.ACKNOWLEDGED:
            owned += 1
            alert = {
                **alert,
                "acknowledged_by": record.actor_reference,
                "acknowledged_by_name": record.actor.full_name if record.actor else None,
                "acknowledged_at": record.created_at,
                "acknowledged_reason": record.reason,
            }
        visible.append(alert)

    return visible, {
        "total": len(alerts),
        "owned": owned,
        "snoozed": snoozed,
        # The headline: alerts that exist and belong to nobody.
        "unowned": len(alerts) - owned - snoozed,
    }


def record(
    db: Session,
    *,
    alert_key: str,
    action: AlertAction,
    actor_reference: str,
    reason: str | None = None,
    snooze_hours: int | None = None,
) -> AlertAcknowledgement:
    """Write one decision. Never touches the situation that raised the alert."""
    key = alert_key.strip()
    if not key:
        raise ValidationError("Alerte inconnue.")

    actor = db.execute(
        select(User).where(User.employee_number == actor_reference.strip().upper())
    ).scalar_one_or_none()
    if actor is None or not actor.is_active:
        raise ValidationError("Matricule inconnu ou inactif.")

    # A hold without a reason tells the next reader nothing they did not
    # already know, and this panel exists so the next reader knows.
    if action == AlertAction.SNOOZED and not (reason or "").strip():
        raise ValidationError("Un report exige un motif.")

    until = None
    if action == AlertAction.SNOOZED:
        hours = snooze_hours if snooze_hours and snooze_hours > 0 else DEFAULT_SNOOZE_HOURS
        until = datetime.now(timezone.utc) + timedelta(hours=min(hours, 24 * 30))

    entry = AlertAcknowledgement(
        alert_key=key,
        action=action,
        actor_id=actor.id,
        actor_reference=actor.employee_number,
        reason=(reason or "").strip() or None,
        snooze_until=until,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry
