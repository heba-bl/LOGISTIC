"""Adding, retiring and re-keying the people who sign in the workbook.

Until now the roster only existed in the seed script. Adding a storeman or
retiring a leaver meant editing `USERS` and running `seed.py --reset`, which
wipes every lot, inspection and audit line in the database. Acceptable while
preparing a demonstration; impossible in a plant, where nobody destroys six
months of history because somebody resigned.

Two rules hold everything here together.

**Nobody is ever deleted.** A user who has signed a line stays in the database
for good: the audit trail names them, and a trail that can lose its author is
not a trail. A departure is `is_active = False`, and the macro checks that
before it checks anything else.

**The plain code exists for one instant.** It is generated here, returned once
so it can be handed over, and never stored - only the same SHA-256 digest the
workbook carries. Losing it means issuing a new one, which is the correct
outcome: a code somebody can look up is a code somebody can borrow.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import ValidationError
from app.models.enums import Zone
from app.models.organization import Role, User
from app.services.excel_operations import code_digest

#: Codes are read aloud and typed on a shop floor. No I, O, 0 or 1: a code that
#: is misread is a code the responsible blames the system for.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 8


def generate_code() -> str:
    """A code somebody can read off a slip of paper without hesitating."""
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))


def _normalise(matricule: str) -> str:
    return matricule.strip().upper()


def list_team(db: Session) -> list[User]:
    """Everyone, active or not - a retired account still explains old lines."""
    return list(
        db.execute(
            select(User).options(selectinload(User.role)).order_by(User.employee_number)
        ).scalars()
    )


def create(
    db: Session,
    *,
    employee_number: str,
    first_name: str,
    last_name: str,
    role_name: str,
    zone: str | None,
    service: str | None,
) -> tuple[User, str | None]:
    """Add somebody, and hand back their code once if the role signs.

    Returns `(user, plain_code)`. The code is None for a role that does not
    validate: issuing one to an operator who cannot sign would only teach them
    that codes are decorative.
    """
    matricule = _normalise(employee_number)
    if not matricule:
        raise ValidationError("Le matricule est obligatoire.")

    exists = db.execute(
        select(User).where(func.upper(User.employee_number) == matricule)
    ).scalar_one_or_none()
    if exists is not None:
        raise ValidationError(f"Le matricule {matricule} existe deja.")

    role = db.execute(select(Role).where(Role.name == role_name)).scalar_one_or_none()
    if role is None:
        raise ValidationError("Role inconnu.")

    first = first_name.strip()
    last = last_name.strip()
    if not first or not last:
        raise ValidationError("Le nom et le prenom sont obligatoires.")

    # `p.lahlou` style, and made unique: two Karim Lahlou would otherwise
    # collide on a column the database refuses to duplicate.
    base = f"{first[0]}.{last}".lower().replace(" ", "")
    username = base
    suffix = 2
    while db.execute(select(User).where(User.username == username)).scalar_one_or_none():
        username = f"{base}{suffix}"
        suffix += 1

    plain = generate_code() if role.can_validate else None

    user = User(
        employee_number=matricule,
        username=username,
        full_name=f"{first} {last}",
        first_name=first,
        last_name=last,
        role_id=role.id,
        service=(service or "").strip() or None,
        zone=Zone(zone) if zone else None,
        is_active=True,
        validation_code_hash=code_digest(matricule, plain) if plain else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user, plain


def set_active(db: Session, *, employee_number: str, active: bool) -> User:
    """Retire somebody, or bring them back. Never deletes."""
    user = _require(db, employee_number)
    user.is_active = active
    db.commit()
    db.refresh(user)
    return user


def reissue_code(db: Session, *, employee_number: str) -> tuple[User, str]:
    """Issue a new signing code, once.

    The old one stops working on both sides at the same instant, because both
    sides compare against the same digest. That is the point: a code that has
    been shared is not a code any more.
    """
    user = _require(db, employee_number)
    if user.role is None or not user.role.can_validate:
        raise ValidationError("Ce role ne valide pas: aucun code a delivrer.")

    plain = generate_code()
    user.validation_code_hash = code_digest(user.employee_number, plain)
    db.commit()
    db.refresh(user)
    return user, plain


def _require(db: Session, employee_number: str) -> User:
    user = db.execute(
        select(User)
        .options(selectinload(User.role))
        .where(func.upper(User.employee_number) == _normalise(employee_number))
    ).scalar_one_or_none()
    if user is None:
        raise ValidationError("Matricule inconnu.")
    return user
