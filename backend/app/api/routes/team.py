"""Managing who signs in the shared workbook.

This is administration, not production: granting somebody the right to validate
is the logistics manager's job, and it changes nothing the plant did. The
operational acts - approving a reception, deciding on a lot - stay in the
workbook, signed by the zone chief.

One consequence the interface must state out loud: the workbook is a file, not
a window. It carries the roster and the code digests that were current when it
was generated, so a new arrival cannot sign until it is regenerated.
"""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_session
from app.models.enums import Zone
from app.schemas.catalog import UserOut
from app.services import excel_operations, team_service

router = APIRouter(prefix="/team", tags=["team"])


class MemberOut(UserOut):
    #: Whether this person's role may sign a line in the workbook.
    can_validate: bool = False
    #: True once a code has been issued. The code itself is never returned.
    has_code: bool = False


class CreateRequest(BaseModel):
    employee_number: str = Field(min_length=2, max_length=20)
    first_name: str = Field(min_length=1, max_length=60)
    last_name: str = Field(min_length=1, max_length=60)
    role_name: str = Field(min_length=2, max_length=40)
    zone: Zone | None = None
    service: str | None = Field(default=None, max_length=60)


class MemberWithCode(BaseModel):
    """The one moment the plain code exists outside somebody's memory."""

    member: MemberOut
    #: Shown once, never stored, never returned again. Null for a role that
    #: does not validate.
    code: str | None = None


def _to_out(user) -> MemberOut:
    data = UserOut.model_validate(user).model_dump()
    return MemberOut(
        **data,
        can_validate=bool(user.role and user.role.can_validate),
        has_code=bool(user.validation_code_hash),
    )


@router.get("", response_model=list[MemberOut], summary="Everyone, active or not")
def list_team(db: Session = Depends(get_session)) -> list[MemberOut]:
    return [_to_out(user) for user in team_service.list_team(db)]


@router.post("", response_model=MemberWithCode, summary="Add somebody")
def create_member(
    payload: CreateRequest, db: Session = Depends(get_session)
) -> MemberWithCode:
    user, code = team_service.create(
        db,
        employee_number=payload.employee_number,
        first_name=payload.first_name,
        last_name=payload.last_name,
        role_name=payload.role_name,
        zone=payload.zone.value if payload.zone else None,
        service=payload.service,
    )
    return MemberWithCode(member=_to_out(user), code=code)


@router.post("/{employee_number}/deactivate", response_model=MemberOut)
def deactivate(employee_number: str, db: Session = Depends(get_session)) -> MemberOut:
    """A departure. The account closes; every line they signed keeps their name."""
    return _to_out(team_service.set_active(db, employee_number=employee_number, active=False))


@router.post("/{employee_number}/activate", response_model=MemberOut)
def activate(employee_number: str, db: Session = Depends(get_session)) -> MemberOut:
    return _to_out(team_service.set_active(db, employee_number=employee_number, active=True))


@router.post("/{employee_number}/reissue-code", response_model=MemberWithCode)
def reissue(employee_number: str, db: Session = Depends(get_session)) -> MemberWithCode:
    """A new code. The old one stops working in Excel and here at once."""
    user, code = team_service.reissue_code(db, employee_number=employee_number)
    return MemberWithCode(member=_to_out(user), code=code)


class RegenerateOut(BaseModel):
    path: str
    size_bytes: int
    sheet_count: int


@router.post("/workbook/regenerate", response_model=RegenerateOut)
def regenerate_workbook() -> RegenerateOut:
    """Rewrite the shared workbook from the current roster.

    The file on the shared folder is a snapshot: it carries the operators and
    the code digests that existed when it was built. Somebody added here cannot
    sign until this runs - so the button exists, rather than leaving a manager
    to wonder why a brand new matricule is refused.

    The workbook is deliberately not rebuilt on every change. Regenerating
    while an operator has it open fails, and silently rewriting a file people
    are typing in is worse than asking.
    """
    from app.db.session import SessionLocal

    session = SessionLocal()
    try:
        content = excel_operations.build_workbook(db=session)
    finally:
        session.close()

    target = (
        Path(__file__).resolve().parents[4]
        / "shared-folder"
        / "00_FICHIER_PARTAGE"
        / excel_operations.WORKBOOK_NAME
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        target.write_bytes(content)
    except PermissionError as error:
        # Excel holds the file open. Say so plainly: the caller can close it.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Le classeur est ouvert dans Excel. Fermez-le, puis relancez "
                "la regeneration."
            ),
        ) from error

    summary = excel_operations.workbook_summary(content)
    return RegenerateOut(
        path=str(target),
        size_bytes=len(content),
        sheet_count=summary["sheet_count"],
    )
