"""Who is allowed onto the supervision site, and how they prove it.

This site is not the plant's tool - the workbook is. It is the window the
direction and the chef logistique look through, so the door is narrow on
purpose: an operator's matricule opens the Excel file and does not open this.

The proof is the validation code the responsible already uses to sign a line in
the workbook, checked against the same digest by the same rule. One secret, one
construction, both sides: a code that works in Excel works here, and a code
that has been revoked stops working in both places at once.

This is a demonstration of the access rule, not a hardened authentication
system. There is no session token, no expiry and no rate limit beyond the one
below; a production deployment would put a real identity provider in front of
this and keep only the role check.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_session
from app.models.enums import RoleName
from app.models.organization import User
from app.schemas.catalog import UserOut
from app.services.excel_operations import code_digest

router = APIRouter(prefix="/auth", tags=["auth"])

#: Roles the supervision site is meant for. Reception, inspection, quality and
#: warehouse responsibles validate in the workbook, in their zone - they have no
#: reason to be here, and giving them a seat would blur what this site is.
SITE_ROLES = {RoleName.LOGISTICS_MANAGER, RoleName.PRODUCTION_MANAGER}


class LoginRequest(BaseModel):
    matricule: str = Field(min_length=2, max_length=20)
    code: str = Field(min_length=3, max_length=64)


class LoginResponse(BaseModel):
    user: UserOut


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, db: Session = Depends(get_session)) -> LoginResponse:
    """Check a matricule and its validation code."""
    matricule = payload.matricule.strip().upper()

    person = db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(func.upper(User.employee_number) == matricule)
    ).scalar_one_or_none()

    # One message for every failure. Saying "unknown matricule" tells anyone who
    # asks which employee numbers exist, which is the first half of the work.
    refusal = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Matricule ou code invalide.",
    )

    if person is None or not person.is_active:
        raise refusal
    if not person.validation_code_hash:
        raise refusal
    if code_digest(matricule, payload.code) != person.validation_code_hash:
        raise refusal

    if person.role is None or person.role.name not in SITE_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Ce compte valide dans le fichier Excel. "
                "Le site de supervision est reserve a la direction "
                "et au responsable logistique."
            ),
        )

    return LoginResponse(user=UserOut.model_validate(person))
