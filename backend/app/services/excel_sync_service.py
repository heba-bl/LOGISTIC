"""Take in rows from the shared workbook - and trust none of them.

Excel is where the work happens, not where the truth lives. A row arriving here
has already been through the workbook's own Maker-Checker macros, but those run
on a machine we do not control, in a file anyone can open with Alt+F11. So every
check the workbook makes is made again here, from the database:

    the maker exists, and is active
    the checker exists, is active, may validate, and belongs to the zone
    the checker is not the maker
    the validation code matches the stored digest
    the row is actually approved
    this row has not already been taken in

Only then is the row handed to the existing domain services. And even a fully
approved reception does not move the stock: it creates a lot, exactly as the
API does, because the stock rule lives in `stock_service` and nothing here is
allowed around it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.models.enums import (
    ImportRowStatus,
    ImportStatus,
    ImportType,
    LotStatus,
    MovementType,
    ValidationDecision,
    Zone,
)
from app.models.imports import DataImport, ImportRow
from app.models.organization import Role, User
from app.services import audit_service, reception_service, validation_token_service

#: Status words the workbook writes. Only the last one is operational data.
STATUS_DRAFT = "BROUILLON"
STATUS_PENDING = "EN ATTENTE DE VALIDATION"
STATUS_APPROVED = "VALIDE"
STATUS_REJECTED = "REJETE"

#: Must match `excel_operations.CODE_SALT`; the workbook and the server derive
#: the same digest from the same three parts.
CODE_SALT = "SLCC-2026-OPS"

#: Which zones may sign off which sheet. A manager from anywhere else is
#: refused here even if the workbook let them through.
#:
#: Inspection carries two zones on purpose: the inspectors who fill it in have
#: no validation right - by design, an inspector does not approve their own
#: trade - so the sheet would otherwise have no possible checker at all. The
#: quality manager signs it, which is also how it works on a shop floor.
SHEET_ZONES: dict[str, tuple[Zone, ...]] = {
    "RECEPTION": (Zone.RECEPTION,),
    "INSPECTION": (Zone.INSPECTION, Zone.QUALITY),
    "QUALITE": (Zone.QUALITY,),
    "RED_CAGE": (Zone.QUALITY,),
    "WAREHOUSE": (Zone.WAREHOUSE,),
    "SORTIES": (Zone.WAREHOUSE,),
    "PRODUCTION": (Zone.PRODUCTION,),
}

SHEET_IMPORT_TYPES: dict[str, ImportType] = {
    "RECEPTION": ImportType.RECEPTION,
    "INSPECTION": ImportType.INSPECTION,
    "QUALITE": ImportType.INSPECTION,
    "RED_CAGE": ImportType.INSPECTION,
    "WAREHOUSE": ImportType.RECEPTION,
    "PRODUCTION": ImportType.PRODUCTION_REQUEST,
    "SORTIES": ImportType.PRODUCTION_REQUEST,
}


def code_digest(matricule: str, code: str, salt: str = CODE_SALT) -> str:
    payload = f"{matricule.strip().upper()}:{code.strip()}:{salt}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class RowOutcome:
    """What became of one submitted row."""

    sync_id: str
    source_row: int
    accepted: bool
    reason: str | None = None
    result_reference: str | None = None


@dataclass
class SyncOutcome:
    sheet: str
    file: str
    received: int
    accepted: int
    rejected: int
    duplicates: int
    rows: list[RowOutcome]
    import_reference: str | None = None


# ------------------------------------------------------------------- lookups
def _user_by_matricule(db: Session, matricule: str) -> User | None:
    if not matricule:
        return None
    return db.execute(
        select(User).where(func.upper(User.employee_number) == matricule.strip().upper())
    ).scalar_one_or_none()


def _role_of(db: Session, user: User) -> Role | None:
    return db.get(Role, user.role_id)


def _already_taken(db: Session, sync_id: str) -> bool:
    """Has this exact line been accepted before?

    The workbook stamps every submitted line with a stable `ID_SYNC`. Pressing
    the sync button twice - or two operators syncing the same shared file - must
    not create the same reception twice.
    """
    if not sync_id:
        return False
    return (
        db.execute(
            select(func.count())
            .select_from(ImportRow)
            .where(ImportRow.result_reference.is_not(None), ImportRow.payload_json.like(f'%"{sync_id}"%'))
        ).scalar_one()
        > 0
    )


# ------------------------------------------------------------------ checking
def validate_row(db: Session, sheet: str, row: dict[str, Any]) -> str | None:
    """Return why a row must be refused, or None when it may pass.

    Deliberately returns a sentence rather than raising: one bad line should not
    stop the other forty, and the operator needs to be told which is which.
    """
    status = str(row.get("statut", "")).strip().upper()
    if status != STATUS_APPROVED:
        return (
            f"statut '{status or 'vide'}': seules les lignes {STATUS_APPROVED} "
            "sont des donnees operationnelles"
        )

    maker_reference = str(row.get("matricule_operateur", "")).strip()
    checker_reference = str(row.get("matricule_checker", "")).strip()

    if not maker_reference:
        return "matricule operateur absent"
    if not checker_reference:
        return "matricule responsable absent"

    # The rule the whole workflow exists for, re-checked away from Excel.
    if maker_reference.upper() == checker_reference.upper():
        return "le responsable ne peut pas valider sa propre saisie (maker = checker)"

    maker = _user_by_matricule(db, maker_reference)
    if maker is None:
        return f"matricule operateur inconnu: {maker_reference}"
    if not maker.is_active:
        return f"operateur inactif: {maker_reference}"

    checker = _user_by_matricule(db, checker_reference)
    if checker is None:
        return f"matricule responsable inconnu: {checker_reference}"
    if not checker.is_active:
        return f"responsable inactif: {checker_reference}"

    role = _role_of(db, checker)
    if role is None or not role.can_validate:
        return f"{checker_reference} n'a pas le droit de validation"

    allowed = SHEET_ZONES.get(sheet.upper())
    # Logistics oversees every zone, so it is accepted everywhere.
    if allowed is not None and checker.zone not in (*allowed, Zone.LOGISTICS):
        expected = " ou ".join(zone.value for zone in allowed)
        return (
            f"{checker_reference} depend de la zone "
            f"{checker.zone.value if checker.zone else 'inconnue'}, "
            f"pas de {expected}"
        )

    # The signature is what turns "the cell says VALIDE" into proof. Only the
    # server can mint it, and only after the manager's code checked out, so a
    # hand-typed status or a borrowed matricule gets no further than here.
    sync_id = str(row.get("id_sync", "")).strip()
    token = str(row.get("jeton_validation", "")).strip()
    if not sync_id:
        return "identifiant de synchronisation absent: la ligne ne peut pas etre signee"
    if not validation_token_service.token_is_valid(
        sheet=sheet,
        sync_id=sync_id,
        maker=maker_reference,
        checker=checker_reference,
        token=token,
    ):
        return (
            "jeton de validation absent ou invalide: le code du responsable "
            "n'a pas ete verifie par SLCC"
        )

    return None


def verify_validation_code(db: Session, matricule: str, code: str) -> bool:
    """Check a manager's code against the digest held for them.

    The plain code is never stored, here or in the workbook. This is the same
    computation the VBA performs, so a code that works on the shop floor works
    on the server and the other way round.
    """
    user = _user_by_matricule(db, matricule)
    if user is None or not user.is_active:
        return False
    role = _role_of(db, user)
    if role is None or not role.can_validate:
        return False
    if not user.validation_code_hash:
        return False
    return code_digest(matricule, code) == user.validation_code_hash


# ------------------------------------------------------------------- applying
def _apply_reception(db: Session, row: dict[str, Any], maker: User) -> str:
    """A validated reception becomes a lot. It does NOT become stock.

    This calls the same service the web form calls, so the tolerance rule, the
    Red Cage routing and the audit entry all behave identically. The stock only
    moves later, when the warehouse confirms storage.
    """
    from app.repositories import PartRepository, SupplierRepository

    reference = str(row.get("reference_piece", "")).strip()
    supplier_code = str(row.get("fournisseur", "")).strip()

    part = PartRepository(db).by_reference(reference)
    if part is None:
        raise ValidationError(f"reference inconnue: {reference}")
    supplier = SupplierRepository(db).by_code(supplier_code)
    if supplier is None:
        raise ValidationError(f"fournisseur inconnu: {supplier_code}")

    expected = _as_int(row.get("quantite_attendue"), "quantite attendue")
    received = _as_int(row.get("quantite_recue"), "quantite recue")

    reception = reception_service.create_reception(
        db,
        part_id=part.id,
        supplier_id=supplier.id,
        quantity_expected=expected,
        quantity_received=received,
        # The sheet renamed these; accept the old names too so a workbook
        # kept from before this change still synchronises.
        delivery_note=str(row.get("bon_livraison") or row.get("bl") or "") or None,
        notes=str(row.get("commentaire") or row.get("observation") or "") or None,
        actor_id=maker.id,
    )
    return reception.reference


def _as_int(value: Any, field: str) -> int:
    text = str(value or "").strip().replace(" ", "").replace(" ", "")
    if not text:
        raise ValidationError(f"{field} absente")
    try:
        return int(float(text.replace(",", ".")))
    except ValueError as error:
        raise ValidationError(f"{field} invalide: {value}") from error


def _lot_from(db: Session, row: dict[str, Any]):
    """Find the lot a row talks about, by number or by reference."""
    from app.models.enums import LotStatus
    from app.models.flow import Lot

    number = str(row.get("id_lot", "")).strip()
    if number:
        lot = db.execute(select(Lot).where(Lot.lot_number == number)).scalar_one_or_none()
        if lot is None:
            raise ValidationError(f"lot inconnu: {number}")
        return lot

    # No lot number: take the oldest lot of that reference still waiting, which
    # is what an operator writing only the part number means.
    reference = str(row.get("reference_piece", "")).strip()
    part = _part_from(db, reference)
    lot = db.execute(
        select(Lot)
        .where(
            Lot.part_id == part.id,
            Lot.status.in_(
                [
                    LotStatus.PENDING_INSPECTION,
                    LotStatus.INSPECTION_IN_PROGRESS,
                    LotStatus.QUALITY_PENDING,
                    LotStatus.APPROVED,
                    LotStatus.RED_CAGE,
                ]
            ),
        )
        .order_by(Lot.id)
        .limit(1)
    ).scalar_one_or_none()
    if lot is None:
        raise ValidationError(f"aucun lot en cours pour {reference}")
    return lot


def _part_from(db: Session, reference: str):
    from app.repositories import PartRepository

    part = PartRepository(db).by_reference(reference.strip())
    if part is None:
        raise ValidationError(f"reference inconnue: {reference}")
    return part


def _apply_inspection(db: Session, row: dict[str, Any], maker: User) -> str:
    """Record a sampling result through `inspection_service`.

    The sample size the operator wrote is used as typed; the defect threshold
    and the conform/non-conform verdict stay with the service, so Excel and the
    web form reach the same conclusion from the same numbers.
    """
    from app.models.enums import LotStatus
    from app.services import inspection_service

    lot = _lot_from(db, row)
    if lot.status is LotStatus.PENDING_INSPECTION:
        inspection_service.start_inspection(db, lot_id=lot.id, actor_id=maker.id)

    sample = _as_int(row.get("taille_echantillon"), "taille de l'echantillon")
    defects = _as_int(row.get("quantite_non_conforme") or "0", "quantite non conforme")

    inspection = inspection_service.record_inspection(
        db,
        lot_id=lot.id,
        sample_size=sample,
        defects_found=defects,
        observations=str(row.get("commentaire") or "") or None,
        actor_id=maker.id,
    )
    return inspection.reference


def _apply_quality(db: Session, row: dict[str, Any], maker: User) -> str:
    """Record a quality decision. Approving unlocks storage; it is not stock."""
    from app.services import quality_service

    lot = _lot_from(db, row)
    decision = str(row.get("decision", "")).strip().upper()
    justification = str(row.get("commentaire") or "").strip()
    if not justification:
        raise ValidationError("une decision qualite exige une justification")

    if decision in ("APPROUVE", "APPROVE", "APPROVED"):
        approved = row.get("quantite_approuvee")
        validation = quality_service.approve(
            db,
            lot_id=lot.id,
            justification=justification,
            actor_id=maker.id,
            quantity_approved=int(approved) if str(approved or "").strip() else None,
        )
    elif decision in ("REJETE", "REJECT", "REJECTED"):
        validation = quality_service.reject(
            db, lot_id=lot.id, justification=justification, actor_id=maker.id
        )
    elif decision in ("RED_CAGE", "REDCAGE", "QUARANTAINE"):
        validation = quality_service.send_to_red_cage(
            db, lot_id=lot.id, justification=justification, actor_id=maker.id
        )
    else:
        raise ValidationError(
            f"decision inconnue: {decision or 'vide'} "
            "(attendu APPROUVE, REJETE ou RED_CAGE)"
        )
    return validation.reference if hasattr(validation, "reference") else lot.lot_number


def _apply_red_cage(db: Session, row: dict[str, Any], maker: User) -> str:
    """Take a quarantined lot out of the Red Cage - never without a reason."""
    from app.models.enums import LotStatus
    from app.services import quality_service

    lot = _lot_from(db, row)
    if lot.status is not LotStatus.RED_CAGE:
        raise ValidationError(f"{lot.lot_number} n'est pas en Red Cage")

    decision = str(row.get("decision", "")).strip().upper()
    justification = str(row.get("justification") or "").strip()
    if not justification:
        raise ValidationError("une sortie de Red Cage exige une justification")

    if decision in ("LIBERE", "LIBERER", "RELEASE", "APPROUVE"):
        quality_service.approve(
            db, lot_id=lot.id, justification=justification, actor_id=maker.id
        )
    elif decision in ("REBUT", "REBUTE", "SCRAP"):
        quality_service.scrap(
            db, lot_id=lot.id, justification=justification, actor_id=maker.id
        )
    else:
        raise ValidationError(
            f"decision inconnue: {decision or 'vide'} (attendu LIBERE ou REBUT)"
        )
    return lot.lot_number


def _apply_warehouse(db: Session, row: dict[str, Any], maker: User) -> str:
    """Confirm storage. This is one of the two moments the stock moves.

    The quantity goes where the operator wrote it; if they named no address, the
    service's own plan is used, which spreads a lot over several shelves when
    the first one cannot take it all.
    """
    from app.repositories import WarehouseRepository
    from app.services import warehouse_service
    from app.services.warehouse_service import Allocation

    lot = _lot_from(db, row)
    code = str(row.get("emplacement", "")).strip()

    if code:
        location = WarehouseRepository(db).by_code(code)
        if location is None:
            raise ValidationError(f"emplacement inconnu: {code}")
        quantity = _as_int(row.get("quantite"), "quantite")
        allocations = [Allocation(location_id=location.id, quantity=quantity)]
    else:
        plan = warehouse_service.suggest_allocations(
            db, part=lot.part, quantity=lot.quantity_approved
        )
        allocations = [
            Allocation(location_id=item.location.id, quantity=item.quantity)
            for item in plan
        ]

    movements = warehouse_service.confirm_storage(
        db,
        lot_id=lot.id,
        allocations=allocations,
        actor_id=maker.id,
        notes=str(row.get("commentaire") or "") or None,
    )
    return ", ".join(movement.reference for movement in movements)


def _apply_production(db: Session, row: dict[str, Any], maker: User) -> str:
    """Raise a parts request. A request never moves the stock."""
    from app.models.production import ProductionStation
    from app.services import production_service

    part = _part_from(db, str(row.get("reference_piece", "")))
    code = str(row.get("station", "")).strip()
    station = db.execute(
        select(ProductionStation).where(ProductionStation.code == code)
    ).scalar_one_or_none()
    if station is None:
        raise ValidationError(f"station inconnue: {code}")

    priority = str(row.get("priorite") or "3").strip() or "3"
    request = production_service.create_request(
        db,
        station_id=station.id,
        part_id=part.id,
        quantity=_as_int(row.get("quantite_demandee"), "quantite demandee"),
        priority=int(float(priority)),
        notes=str(row.get("commentaire") or "") or None,
        actor_id=maker.id,
        submit_immediately=True,
    )
    return request.reference


def _apply_issue(db: Session, row: dict[str, Any], maker: User) -> str:
    """Confirm an issue. This is the only moment the stock goes down.

    The request must already have travelled its own workflow; the service
    refuses anything else, and refuses to take out more than there is.
    """
    from app.models.enums import ProductionRequestStatus
    from app.models.production import ProductionRequest
    from app.services import production_service

    reference = str(row.get("id_demande", "")).strip()
    request = db.execute(
        select(ProductionRequest).where(ProductionRequest.reference == reference)
    ).scalar_one_or_none()
    if request is None:
        raise ValidationError(f"demande inconnue: {reference}")

    # Walk the steps the request still owes, each through its own service.
    if request.status is ProductionRequestStatus.SUBMITTED:
        production_service.approve(db, request_id=request.id, actor_id=maker.id)
    if request.status is ProductionRequestStatus.APPROVED:
        production_service.start_preparation(db, request_id=request.id, actor_id=maker.id)
    if request.status is ProductionRequestStatus.PREPARING:
        production_service.mark_ready(db, request_id=request.id, actor_id=maker.id)

    quantity = row.get("quantite_sortie")
    # `issue` hands back the request and the movement it created.
    _request, movement = production_service.issue(
        db,
        request_id=request.id,
        quantity=_as_int(quantity, "quantite sortie") if str(quantity or "").strip() else None,
        actor_id=maker.id,
    )
    return movement.reference


#: Every sheet now reaches the service that owns its part of the workflow.
APPLIERS = {
    "RECEPTION": _apply_reception,
    "INSPECTION": _apply_inspection,
    "QUALITE": _apply_quality,
    "RED_CAGE": _apply_red_cage,
    "WAREHOUSE": _apply_warehouse,
    "PRODUCTION": _apply_production,
    "SORTIES": _apply_issue,
}


# ------------------------------------------------------------------ ingestion
def sync_rows(
    db: Session,
    *,
    sheet: str,
    file_name: str,
    rows: list[dict[str, Any]],
) -> SyncOutcome:
    """Take in one sheet's worth of approved rows."""
    sheet_key = sheet.strip().upper()
    if sheet_key not in SHEET_ZONES:
        raise ValidationError(f"Feuille inconnue: {sheet}")

    outcomes: list[RowOutcome] = []
    accepted_payloads: list[tuple[dict, str]] = []
    duplicates = 0

    for row in rows:
        sync_id = str(row.get("id_sync", "")).strip()
        source_row = int(row.get("source_row") or 0)

        if _already_taken(db, sync_id):
            duplicates += 1
            outcomes.append(
                RowOutcome(sync_id, source_row, False, "ligne deja synchronisee")
            )
            continue

        problem = validate_row(db, sheet_key, row)
        if problem:
            outcomes.append(RowOutcome(sync_id, source_row, False, problem))
            continue

        accepted_payloads.append((row, sync_id))

    if not accepted_payloads:
        return SyncOutcome(
            sheet=sheet_key,
            file=file_name,
            received=len(rows),
            accepted=0,
            rejected=len(rows) - duplicates,
            duplicates=duplicates,
            rows=outcomes,
        )

    # One DataImport per sync, so the web page can show who entered and who
    # signed off, exactly like a manual upload.
    first_row = accepted_payloads[0][0]
    maker = _user_by_matricule(db, str(first_row.get("matricule_operateur", "")))
    checker = _user_by_matricule(db, str(first_row.get("matricule_checker", "")))
    assert maker is not None and checker is not None  # validate_row proved both

    digest_source = json.dumps(
        [payload for payload, _ in accepted_payloads], sort_keys=True, ensure_ascii=False
    ).encode("utf-8")

    batch = DataImport(
        reference=_next_reference(db),
        import_type=SHEET_IMPORT_TYPES.get(sheet_key, ImportType.RECEPTION),
        status=ImportStatus.APPROVED,
        source_filename=file_name,
        source_hash=hashlib.sha256(digest_source).hexdigest(),
        source_size_bytes=len(digest_source),
        row_count=len(rows),
        valid_row_count=len(accepted_payloads),
        invalid_row_count=len(rows) - len(accepted_payloads),
        maker_id=maker.id,
        maker_reference=maker.employee_number,
        maker_role=_role_of(db, maker).name.value if _role_of(db, maker) else "",
        maker_service=maker.service,
        submitted_at=datetime.now(timezone.utc),
        checker_id=checker.id,
        checker_reference=checker.employee_number,
        checker_role=_role_of(db, checker).name.value if _role_of(db, checker) else "",
        checker_service=checker.service,
        checked_at=datetime.now(timezone.utc),
        decision=ValidationDecision.APPROVED,
        decision_comment=f"Synchronisation Excel - feuille {sheet_key}",
        notes=f"Source: {file_name}",
    )
    db.add(batch)
    db.flush()

    applier = APPLIERS.get(sheet_key)
    applied = 0

    for index, (payload, sync_id) in enumerate(accepted_payloads, start=1):
        row_maker = _user_by_matricule(db, str(payload.get("matricule_operateur", "")))
        record = ImportRow(
            import_id=batch.id,
            row_number=int(payload.get("source_row") or index),
            status=ImportRowStatus.APPLIED,
            payload_json=json.dumps(payload, ensure_ascii=False),
        )
        db.add(record)

        if applier is None:
            outcomes.append(
                RowOutcome(
                    sync_id,
                    int(payload.get("source_row") or index),
                    True,
                    "enregistree et tracee; aucun enregistrement metier pour cette feuille",
                )
            )
            continue

        try:
            # The business services stamp the operator and nothing else, because
            # they have no idea a spreadsheet is involved. Marking the audit
            # trail before the call lets the provenance - who validated, from
            # which file - be attached to whatever the call wrote.
            mark = audit_service.high_water_mark(db)
            reference = applier(db, payload, row_maker or maker)
            audit_service.stamp_provenance(
                db,
                since_id=mark,
                maker=row_maker or maker,
                checker=checker,
                decision=ValidationDecision.APPROVED.value,
                source_file=file_name,
                source_hash=batch.source_hash,
            )
            record.result_reference = reference
            applied += 1
            outcomes.append(
                RowOutcome(
                    sync_id,
                    int(payload.get("source_row") or index),
                    True,
                    None,
                    reference,
                )
            )
        except ValidationError as error:
            record.status = ImportRowStatus.INVALID
            record.error_message = str(error)
            outcomes.append(
                RowOutcome(sync_id, int(payload.get("source_row") or index), False, str(error))
            )

    batch.applied_row_count = applied
    db.commit()

    accepted = sum(1 for outcome in outcomes if outcome.accepted)
    return SyncOutcome(
        sheet=sheet_key,
        file=file_name,
        received=len(rows),
        accepted=accepted,
        rejected=len(rows) - accepted - duplicates,
        duplicates=duplicates,
        rows=outcomes,
        import_reference=batch.reference,
    )


def _next_reference(db: Session) -> str:
    count = db.execute(select(func.count()).select_from(DataImport)).scalar_one()
    return f"XLS-{datetime.now(timezone.utc):%Y}-{count + 1:04d}"


def workbook_status(db: Session) -> dict:
    """Everything the "Fichier operationnel" screen shows, from the database.

    Two different questions live side by side here, and the screen keeps them
    apart because conflating them is how a dashboard starts lying:

    * **Activity** is what the plant actually holds - receptions, inspections,
      quality decisions, stock movements. These count real records whatever
      created them, Excel or the web forms.
    * **Validation** is the Maker-Checker state of the batches that arrived
      *from the workbook*. A batch pending review has changed nothing yet.

    Nothing here is estimated: every figure is a count.
    """
    from app.models.flow import Inspection, Lot, QualityValidation, Reception
    from app.models.production import ProductionRequest
    from app.models.warehouse import Stock, StockMovement, WarehouseLocation
    from app.services.excel_operations import WORKBOOK_NAME

    def count(model, *where) -> int:
        statement = select(func.count()).select_from(model)
        if where:
            statement = statement.where(*where)
        return int(db.execute(statement).scalar_one())

    # --- activity: the operational records themselves --------------------
    activity = {
        "receptions": count(Reception),
        "inspections": count(Inspection),
        "quality": count(QualityValidation),
        "red_cage": count(Lot, Lot.status == LotStatus.RED_CAGE),
        "warehouse_articles": count(Stock),
        "stock_movements": count(StockMovement),
        "production_requests": count(ProductionRequest),
        "issues": count(StockMovement, StockMovement.movement_type == MovementType.OUT),
    }

    # --- warehouse pressure, for the process card ------------------------
    occupancy = db.execute(
        select(
            func.count(),
            func.coalesce(func.sum(WarehouseLocation.capacity), 0),
            func.coalesce(func.sum(WarehouseLocation.occupied), 0),
        ).select_from(WarehouseLocation)
    ).one()
    locations_used = count(WarehouseLocation, WarehouseLocation.occupied > 0)
    capacity = int(occupancy[1])
    occupied = int(occupancy[2])

    warehouse = {
        "locations": int(occupancy[0]),
        "locations_used": locations_used,
        "capacity": capacity,
        "occupied": occupied,
        "occupancy_percent": round(occupied / capacity * 100, 1) if capacity else 0.0,
    }

    # --- validation: the Maker-Checker state of the workbook batches ------
    batches = db.execute(
        select(DataImport).where(DataImport.source_filename.like("%.xlsm"))
    ).scalars().all()

    per_status = {"pending": 0, "approved": 0, "rejected": 0}
    per_process: dict[str, dict[str, int]] = {}
    for batch in batches:
        key = batch.import_type.value if hasattr(batch.import_type, "value") else str(batch.import_type)
        bucket = per_process.setdefault(
            key, {"batches": 0, "rows": 0, "pending": 0, "approved": 0, "rejected": 0}
        )
        bucket["batches"] += 1
        bucket["rows"] += batch.row_count

        if batch.status is ImportStatus.APPROVED:
            per_status["approved"] += 1
            bucket["approved"] += 1
        elif batch.status is ImportStatus.REJECTED:
            per_status["rejected"] += 1
            bucket["rejected"] += 1
        else:
            per_status["pending"] += 1
            bucket["pending"] += 1

    totals = db.execute(
        select(
            func.coalesce(func.sum(DataImport.row_count), 0),
            func.coalesce(func.sum(DataImport.valid_row_count), 0),
            func.coalesce(func.sum(DataImport.invalid_row_count), 0),
            func.coalesce(func.sum(DataImport.applied_row_count), 0),
        ).where(DataImport.source_filename.like("%.xlsm"))
    ).one()

    last_batch = db.execute(
        select(DataImport)
        .where(DataImport.source_filename.like("%.xlsm"))
        .order_by(DataImport.checked_at.desc().nullslast(), DataImport.id.desc())
        .limit(1)
    ).scalar_one_or_none()

    # The workbook is only "synchronised" once something has actually come in.
    if last_batch is None:
        connection_state = "NEVER_SYNCED"
    elif per_status["pending"]:
        connection_state = "PENDING"
    else:
        connection_state = "SYNCED"

    # A browser cannot launch Excel, so the page shows where the file actually
    # is and offers a download. Checked on disk rather than assumed.
    shared = (
        Path(__file__).resolve().parents[3]
        / "shared-folder"
        / "00_FICHIER_PARTAGE"
        / WORKBOOK_NAME
    )
    exists = shared.exists()

    return {
        "workbook": WORKBOOK_NAME,
        "state": connection_state,
        "local_path": str(shared) if exists else None,
        "local_size_bytes": shared.stat().st_size if exists else None,
        "local_modified_at": (
            datetime.fromtimestamp(shared.stat().st_mtime, tz=timezone.utc) if exists else None
        ),
        "last_sync_at": last_batch.checked_at if last_batch else None,
        "last_actor": last_batch.checker_reference if last_batch else None,
        "last_maker": last_batch.maker_reference if last_batch else None,
        "last_reference": last_batch.reference if last_batch else None,
        "rows_received": int(totals[0]),
        "rows_approved": int(totals[1]),
        "rows_rejected": int(totals[2]),
        "rows_applied": int(totals[3]),
        "batches": {
            "total": len(batches),
            "pending": per_status["pending"],
            "approved": per_status["approved"],
            "rejected": per_status["rejected"],
        },
        "activity": activity,
        "warehouse": warehouse,
        "per_process": per_process,
    }


def sync_history(
    db: Session,
    *,
    matricule: str | None = None,
    role: str | None = None,
    zone: str | None = None,
    status: str | None = None,
    import_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = 100,
) -> list[dict]:
    """Who entered what, who signed it off, and when.

    One row per batch, with both matricules resolved. The filters exist because
    the question a manager actually asks is never "show me everything" - it is
    "what did this person do", or "what is still waiting in my zone".
    """
    statement = select(DataImport).order_by(DataImport.id.desc())

    if status:
        statement = statement.where(DataImport.status == ImportStatus(status))
    if import_type:
        statement = statement.where(DataImport.import_type == ImportType(import_type))
    if matricule:
        needle = matricule.strip().upper()
        statement = statement.where(
            (func.upper(DataImport.maker_reference) == needle)
            | (func.upper(DataImport.checker_reference) == needle)
        )
    if role:
        statement = statement.where(
            (DataImport.maker_role == role) | (DataImport.checker_role == role)
        )
    if zone:
        needle = zone.strip().upper()
        statement = statement.where(
            (func.upper(DataImport.maker_service) == needle)
            | (func.upper(DataImport.checker_service) == needle)
        )
    if date_from:
        statement = statement.where(
            DataImport.submitted_at >= datetime.combine(date_from, time.min).replace(tzinfo=timezone.utc)
        )
    if date_to:
        statement = statement.where(
            DataImport.submitted_at <= datetime.combine(date_to, time.max).replace(tzinfo=timezone.utc)
        )

    batches = db.execute(statement.limit(min(limit, 500))).scalars().all()

    return [
        {
            "reference": batch.reference,
            "import_type": batch.import_type.value
            if hasattr(batch.import_type, "value")
            else str(batch.import_type),
            "status": batch.status.value if hasattr(batch.status, "value") else str(batch.status),
            "decision": batch.decision.value
            if batch.decision is not None and hasattr(batch.decision, "value")
            else None,
            "maker_reference": batch.maker_reference,
            "maker_role": batch.maker_role,
            "maker_service": batch.maker_service,
            "submitted_at": batch.submitted_at,
            "checker_reference": batch.checker_reference,
            "checker_role": batch.checker_role,
            "checker_service": batch.checker_service,
            "checked_at": batch.checked_at,
            "comment": batch.decision_comment,
            "source_filename": batch.source_filename,
            "row_count": batch.row_count,
            "valid_row_count": batch.valid_row_count,
            "invalid_row_count": batch.invalid_row_count,
            "applied_row_count": batch.applied_row_count,
            "result_references": [
                row.result_reference for row in batch.rows if row.result_reference
            ],
        }
        for batch in batches
    ]
