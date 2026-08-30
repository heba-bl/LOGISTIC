"""Audit trail writer.

Every important business event goes through ``record``. It is always called
inside the caller transaction, so an operation cannot be committed without its
trace: either both land, or neither does.

An entry is never anonymous: the acting operator is stored with their employee
number and role. Validation events additionally carry the maker/checker pair, the
decision and the source spreadsheet.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.enums import AuditAction
from app.models.organization import User
from app.models.system import AuditLog


def record(
    db: Session,
    *,
    action: AuditAction,
    entity_type: str,
    entity_id: int | None = None,
    entity_reference: str | None = None,
    actor: User | None = None,
    actor_name: str | None = None,
    lot_id: int | None = None,
    part_id: int | None = None,
    quantity: int | None = None,
    location_code: str | None = None,
    status_before: str | None = None,
    status_after: str | None = None,
    reason: str | None = None,
    # --- Maker-Checker ----------------------------------------------------
    maker: User | None = None,
    checker: User | None = None,
    decision: str | None = None,
    source_file: str | None = None,
    source_hash: str | None = None,
) -> AuditLog:
    """Append one entry to the audit trail.

    Answers the questions the specification requires: who entered, who checked,
    who validated, when, on what, which decision, which comment - plus how much,
    which lot, which location and the status transition.
    """
    entry = AuditLog(
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        entity_reference=entity_reference,
        lot_id=lot_id,
        part_id=part_id,
        quantity=quantity,
        location_code=location_code,
        status_before=status_before,
        status_after=status_after,
        reason=reason,
        actor_id=actor.id if actor else None,
        actor_name=actor_name or (actor.full_name if actor else "system"),
        actor_reference=actor.employee_number if actor else None,
        actor_role=actor.role_name if actor else None,
        maker_reference=maker.employee_number if maker else None,
        maker_role=maker.role_name if maker else None,
        checker_reference=checker.employee_number if checker else None,
        checker_role=checker.role_name if checker else None,
        decision=decision,
        source_file=source_file,
        source_hash=source_hash,
    )
    db.add(entry)
    db.flush()
    return entry


def high_water_mark(db: Session) -> int:
    """The id of the newest audit entry, before an operation runs.

    Paired with `stamp_provenance`, this is how a caller says "everything the
    next call writes belongs to this batch" without every business service
    having to know that an import exists.
    """
    return int(
        db.execute(select(func.coalesce(func.max(AuditLog.id), 0))).scalar_one()
    )


def stamp_provenance(
    db: Session,
    *,
    since_id: int,
    maker: User | None,
    checker: User | None,
    decision: str | None = None,
    source_file: str | None = None,
    source_hash: str | None = None,
) -> int:
    """Attach the Maker-Checker context to entries written since `since_id`.

    A lot created from a validated spreadsheet used to carry only the operator
    who typed the line: the responsible who approved it lived on the import
    batch, so the traceability screen showed an empty "who validated" column for
    a record that had, in fact, been validated. The business services stay
    unaware of imports - they write what they always write - and the import
    layer stamps the provenance onto the entries that its call produced.

    Returns how many entries were stamped.
    """
    entries = list(
        db.execute(select(AuditLog).where(AuditLog.id > since_id)).scalars()
    )
    for entry in entries:
        # Never overwrite a provenance a service set deliberately.
        if maker is not None and entry.maker_reference is None:
            entry.maker_reference = maker.employee_number
            entry.maker_role = maker.role_name
        if checker is not None and entry.checker_reference is None:
            entry.checker_reference = checker.employee_number
            entry.checker_role = checker.role_name
        if decision and entry.decision is None:
            entry.decision = decision
        if source_file and entry.source_file is None:
            entry.source_file = source_file
        if source_hash and entry.source_hash is None:
            entry.source_hash = source_hash
    db.flush()
    return len(entries)
