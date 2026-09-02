"""Taking charge of an alert.

Three actions, and none of them changes what the plant did. Releasing a lot,
covering a request or validating a line are decisions taken in the shared
workbook by the chief who signs them. What happens here is the other half of
supervision: saying who is watching, so an alert stops being a number that only
grows.
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import AlertAction
from app.schemas.dashboard import AlertOut
from app.services import alert_service
from app.services.dashboard_service import build_alerts

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertListOut(BaseModel):
    """Every alert, not the shortlist Mission Control shows.

    The dashboard deliberately keeps eight, one per kind, so no single situation
    fills the panel. That is right for a dashboard and wrong for working through
    a backlog: taking eight in charge only makes the next eight appear, and
    nothing lets a manager say "show me every shortage".
    """

    alerts: list[AlertOut]
    standing: dict[str, int]
    #: The kinds actually present, so the filter offers only what exists.
    kinds: list[str]


@router.get("", response_model=AlertListOut)
def list_alerts(
    severity: str | None = Query(default=None),
    kind: str | None = Query(default=None),
    db: Session = Depends(get_session),
) -> AlertListOut:
    """All current alerts, filtered, with their standing applied."""
    visible, standing = alert_service.apply(db, build_alerts(db))

    # The kinds come from the unfiltered set: a filter that hides its own
    # options as soon as it is applied cannot be undone from the screen.
    kinds = sorted({str(alert.get("kind") or "OTHER") for alert in visible})

    if severity:
        wanted = severity.strip().upper()
        visible = [a for a in visible if str(a.get("severity", "")).upper() == wanted]
    if kind:
        chosen = kind.strip().upper()
        visible = [a for a in visible if str(a.get("kind") or "OTHER").upper() == chosen]

    return AlertListOut(
        alerts=[AlertOut.model_validate(a) for a in visible],
        standing=standing,
        kinds=kinds,
    )


class DecisionRequest(BaseModel):
    #: The alert's own key, as the dashboard returned it: `redcage-42`.
    alert_key: str = Field(min_length=1, max_length=64)
    #: Who is taking it on. The site is in the hands of the direction and the
    #: logistics manager, so this is one of them.
    actor_reference: str = Field(min_length=2, max_length=20)
    reason: str | None = Field(default=None, max_length=500)
    #: Snooze only. Capped at a month by the service.
    snooze_hours: int | None = Field(default=None, ge=1, le=24 * 30)


class DecisionResponse(BaseModel):
    alert_key: str
    action: AlertAction
    actor_reference: str
    reason: str | None = None


def _record(db: Session, payload: DecisionRequest, action: AlertAction) -> DecisionResponse:
    entry = alert_service.record(
        db,
        alert_key=payload.alert_key,
        action=action,
        actor_reference=payload.actor_reference,
        reason=payload.reason,
        snooze_hours=payload.snooze_hours,
    )
    return DecisionResponse(
        alert_key=entry.alert_key,
        action=entry.action,
        actor_reference=entry.actor_reference,
        reason=entry.reason,
    )


@router.post("/acknowledge", response_model=DecisionResponse)
def acknowledge(
    payload: DecisionRequest, db: Session = Depends(get_session)
) -> DecisionResponse:
    """Seen and owned. The alert stays visible, now with a name on it."""
    return _record(db, payload, AlertAction.ACKNOWLEDGED)


@router.post("/snooze", response_model=DecisionResponse)
def snooze(payload: DecisionRequest, db: Session = Depends(get_session)) -> DecisionResponse:
    """Held until a date, with a reason. Hidden until then - never resolved."""
    return _record(db, payload, AlertAction.SNOOZED)


@router.post("/close", response_model=DecisionResponse)
def close(payload: DecisionRequest, db: Session = Depends(get_session)) -> DecisionResponse:
    """Dealt with. Leaves the panel; if the situation persists it comes back."""
    return _record(db, payload, AlertAction.CLOSED)


@router.post("/reopen", response_model=DecisionResponse)
def reopen(payload: DecisionRequest, db: Session = Depends(get_session)) -> DecisionResponse:
    """Undo. Hands the alert back to nobody."""
    return _record(db, payload, AlertAction.REOPENED)
