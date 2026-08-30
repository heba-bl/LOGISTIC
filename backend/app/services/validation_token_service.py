"""Prove that a manager really typed their code.

An audit found the hole this closes. The workbook checked the validation code
locally and then wrote `VALIDE` into a cell; the server took that word on trust.
Anyone able to type in the sheet - or to call the API directly - could mark a
line validated in someone else's name without ever knowing their code.

The fix moves the decision to the server:

    responsible types matricule + code in Excel
        -> POST /api/excel/validate
        -> the server checks the code against `users.validation_code_hash`
        -> the server returns a token it signed with a secret it never shares
        -> Excel writes the token beside the line
        -> on synchronisation the server verifies its own signature

The code is never stored: not in the workbook, not in the database, not in the
logs, not in any response. Only its digest is stored, and only the server can
mint a token, because only the server holds the signing secret.

The token is bound to the line - sheet, row identity, maker and checker - so it
cannot be moved to another row, another operator or another sheet.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.organization import Role, User

#: Where the signing secret is kept when the environment does not provide one.
#: Outside the file so it survives a restart; a real deployment sets the
#: environment variable and never touches this.
_SECRET_FILE = Path(__file__).resolve().parents[2] / ".validation_secret"
_ENVIRONMENT_KEY = "SLCC_VALIDATION_SECRET"


def signing_secret() -> bytes:
    """The server's own secret. Generated once, never sent anywhere."""
    from_environment = os.environ.get(_ENVIRONMENT_KEY)
    if from_environment:
        return from_environment.encode("utf-8")

    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_bytes().strip()

    generated = secrets.token_hex(32).encode("ascii")
    _SECRET_FILE.write_bytes(generated)
    # Readable by the service account only; best effort on Windows.
    try:
        _SECRET_FILE.chmod(0o600)
    except OSError:
        pass
    return generated


def code_digest(matricule: str, code: str, salt: str) -> str:
    """`sha256(MATRICULE:code:salt)` - the same construction the workbook uses."""
    payload = f"{matricule.strip().upper()}:{code.strip()}:{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def build_token(*, sheet: str, sync_id: str, maker: str, checker: str) -> str:
    """Sign one line for one pair of people.

    Everything that identifies the line goes into the signature, so a token
    lifted from a validated row is worthless on any other row.
    """
    message = "|".join(
        [
            sheet.strip().upper(),
            sync_id.strip(),
            maker.strip().upper(),
            checker.strip().upper(),
        ]
    )
    return hmac.new(signing_secret(), message.encode("utf-8"), hashlib.sha256).hexdigest()


def token_is_valid(*, sheet: str, sync_id: str, maker: str, checker: str, token: str) -> bool:
    """Constant-time comparison, so a wrong token leaks nothing by timing."""
    if not token:
        return False
    expected = build_token(sheet=sheet, sync_id=sync_id, maker=maker, checker=checker)
    return hmac.compare_digest(expected, token.strip().lower())


def user_by_matricule(db: Session, matricule: str) -> User | None:
    if not matricule:
        return None
    return db.execute(
        select(User).where(func.upper(User.employee_number) == matricule.strip().upper())
    ).scalar_one_or_none()


def verify_code(db: Session, matricule: str, code: str, salt: str) -> bool:
    """Does this code belong to this person?

    Compared against the stored digest in constant time. A person with no code
    recorded can never validate, whatever they type.
    """
    user = user_by_matricule(db, matricule)
    if user is None or not user.is_active or not user.validation_code_hash:
        return False
    role = db.get(Role, user.role_id)
    if role is None or not role.can_validate:
        return False
    return hmac.compare_digest(
        user.validation_code_hash, code_digest(matricule, code, salt)
    )
