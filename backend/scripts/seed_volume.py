"""Replay a large operational history through the services.

`seed.py` builds a hand-written scenario that covers every interesting case one
by one. That is what the tests and the demonstration script rely on, but eight
lots make for empty spreadsheets: an exported workbook that shows nothing but a
header row is useless for a review.

This module adds volume on top of that scenario. Nothing is fabricated - every
lot is created by `reception_service`, inspected by `inspection_service`,
decided by `quality_service`, stored by `warehouse_service` and consumed by
`production_service`, exactly as the API would. The stock, the movements and the
audit trail are therefore genuine, and the ABSOLUTE STOCK RULE still holds:

    reception -> inspection -> quality -> storage confirmed  => STOCK +
    request -> validation -> preparation -> issue confirmed   => STOCK -

Generation is seeded, so two runs produce the same demonstration data.

Only ever run against demonstration data.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import DomainError
from app.models.enums import PartSize, RoleName
from app.models.organization import Role, User
from app.services import (
    inspection_service,
    production_service,
    quality_service,
    reception_service,
    warehouse_service,
)
from app.services.warehouse_service import Allocation

#: Fixed so the demonstration is reproducible from one run to the next.
SEED = 20260820

#: How many additional lots and requests to replay.
LOT_COUNT = 240
REQUEST_COUNT = 110

#: Where each generated lot stops. The weights are what makes the demonstration
#: look like a working plant rather than a happy path: most lots reach the
#: shelf, a few are still moving, and a handful are blocked.
LOT_OUTCOMES = (
    ("stored", 57),
    ("awaiting_inspection", 8),
    ("inspection_started", 4),
    ("awaiting_quality", 7),
    ("approved_not_stored", 5),
    ("non_conform", 8),
    ("quantity_gap", 4),
    ("rejected", 3),
    ("scrapped", 4),
)

#: Where each generated production request stops.
REQUEST_OUTCOMES = (
    ("issued", 58),
    ("submitted", 14),
    ("approved", 9),
    ("preparing", 7),
    ("ready", 6),
    ("rejected", 6),
)

OBSERVATIONS_CONFORM = (
    "Echantillon conforme, aucun defaut releve",
    "Controle visuel et dimensionnel conformes",
    "Cotes dans l'intervalle de tolerance",
    "Aspect de surface conforme au plan",
    "Marquage fournisseur present et lisible",
)

OBSERVATIONS_DEFECT = (
    "Traces d'usinage sur la face d'appui",
    "Defaut de revetement sur plusieurs pieces",
    "Cote hors tolerance sur l'echantillon",
    "Bavures constatees sur le bord de coupe",
    "Marquage absent sur une partie du lot",
    "Corrosion naissante en fond d'emballage",
)

REQUEST_NOTES = (
    "Besoin pour le lancement de serie",
    "Reappro poste avant changement d'equipe",
    "Complement suite a rebut ligne",
    "Preparation du chantier de nuit",
    "Besoin planifie semaine suivante",
    None,
    None,
)

REJECTION_REASONS = (
    "Besoin non justifie pour ce poste",
    "Quantite demandee superieure au besoin reel",
    "Demande doublon, deja couverte",
    "Report de production, demande annulee",
)


def _weighted(rng: random.Random, options: tuple[tuple[str, int], ...]) -> str:
    names = [name for name, _ in options]
    weights = [weight for _, weight in options]
    return rng.choices(names, weights=weights, k=1)[0]


def _pools(db: Session) -> dict[RoleName, list[User]]:
    """Every operator of a role, so actions are spread across real matricules."""
    pools: dict[RoleName, list[User]] = {}
    rows = db.execute(select(User, Role).join(Role, User.role_id == Role.id)).all()
    for user, role in rows:
        pools.setdefault(role.name, []).append(user)
    return pools


def _quantity(rng: random.Random, part) -> int:
    """A plausible delivered quantity for this class of part."""
    if part.size_class is PartSize.SMALL:
        base = rng.choice((120, 180, 240, 300, 360, 420, 480, 600, 720, 900))
    else:
        base = rng.choice((12, 18, 24, 30, 40, 50, 60, 80, 100, 120))
    return base


def seed_volume(db: Session, ctx: dict) -> dict:
    """Add depth to the seeded history. Returns a small report."""
    rng = random.Random(SEED)
    pools = _pools(db)

    # Only the managed perimeter is replayed. Spreading 240 lots over the whole
    # 2 239-line catalogue gave almost every reference a single lot and no
    # coherent history; concentrating them on what the warehouse actually holds
    # gives each one a story worth reading.
    managed = ctx.get("managed") or set()
    parts = [
        part for reference, part in ctx["parts"].items()
        if not managed or reference in managed
    ]
    suppliers = list(ctx["suppliers"].values())
    stations = list(ctx["stations"].values())

    receptionists = pools.get(RoleName.RECEPTIONIST, [])
    inspectors = pools.get(RoleName.QUALITY_INSPECTOR, [])
    quality_managers = pools.get(RoleName.QUALITY_MANAGER, [])
    warehouse_operators = pools.get(RoleName.WAREHOUSE_OPERATOR, [])
    leaders = pools.get(RoleName.STATION_LEADER, [])
    production_managers = pools.get(RoleName.PRODUCTION_MANAGER, [])

    if not all(
        (receptionists, inspectors, quality_managers, warehouse_operators, leaders, production_managers)
    ):
        raise RuntimeError("seed_volume requires the reference operators to exist")

    tally = {f"lot:{name}": 0 for name, _ in LOT_OUTCOMES}
    tally.update({f"req:{name}": 0 for name, _ in REQUEST_OUTCOMES})
    capacity_full = 0

    # ------------------------------------------------------------- inbound
    for index in range(LOT_COUNT):
        part = rng.choice(parts)
        supplier = rng.choice(suppliers)
        expected = _quantity(rng, part)
        outcome = _weighted(rng, LOT_OUTCOMES)

        received = expected
        notes = None
        if outcome == "quantity_gap":
            # A small part may land inside the configurable tolerance; a large
            # one must match exactly, so any gap sends it to the Red Cage.
            drift = rng.choice((-6, -4, -3, 3, 4, 6))
            received = max(1, expected + drift)
            notes = f"Ecart constate au comptage: {received - expected:+d}"

        reception = reception_service.create_reception(
            db,
            part_id=part.id,
            supplier_id=supplier.id,
            quantity_expected=expected,
            quantity_received=received,
            delivery_note=f"BL-{supplier.code}-{2600 + index}",
            notes=notes,
            actor_id=rng.choice(receptionists).id,
        )
        lot = reception.lot
        db.commit()

        if outcome in ("awaiting_inspection", "quantity_gap"):
            tally[f"lot:{outcome}"] += 1
            continue

        inspector = rng.choice(inspectors)
        inspection_service.start_inspection(db, lot_id=lot.id, actor_id=inspector.id)
        db.commit()

        if outcome == "inspection_started":
            tally[f"lot:{outcome}"] += 1
            continue

        sample = inspection_service.suggest_sample_size(db, lot)
        defects = 0
        observations = rng.choice(OBSERVATIONS_CONFORM)
        if outcome == "non_conform":
            # Enough defects to cross the configured threshold.
            defects = max(1, round(sample * rng.uniform(0.12, 0.35)))
            observations = rng.choice(OBSERVATIONS_DEFECT)

        inspection_service.record_inspection(
            db,
            lot_id=lot.id,
            sample_size=sample,
            defects_found=defects,
            observations=observations,
            actor_id=inspector.id,
        )
        db.commit()

        if outcome in ("awaiting_quality", "non_conform"):
            tally[f"lot:{outcome}"] += 1
            continue

        manager = rng.choice(quality_managers)

        if outcome == "rejected":
            quality_service.reject(
                db,
                lot_id=lot.id,
                justification="Lot refuse: non conformite confirmee en contre-expertise",
                actor_id=manager.id,
            )
            db.commit()
            tally[f"lot:{outcome}"] += 1
            continue

        if outcome == "scrapped":
            quality_service.send_to_red_cage(
                db,
                lot_id=lot.id,
                justification="Doute sur la tracabilite fournisseur",
                actor_id=manager.id,
            )
            quality_service.scrap(
                db,
                lot_id=lot.id,
                justification="Lot rebute apres analyse, non recuperable",
                actor_id=manager.id,
            )
            db.commit()
            tally[f"lot:{outcome}"] += 1
            continue

        quality_service.approve(
            db,
            lot_id=lot.id,
            justification="Echantillon conforme, lot libere pour stockage",
            actor_id=manager.id,
        )
        db.commit()

        if outcome == "approved_not_stored":
            tally[f"lot:{outcome}"] += 1
            continue

        # Storage is the only operation that increments the stock.
        try:
            plan = warehouse_service.suggest_allocations(
                db, part=lot.part, quantity=lot.quantity_approved
            )
            warehouse_service.confirm_storage(
                db,
                lot_id=lot.id,
                allocations=[
                    Allocation(location_id=item.location.id, quantity=item.quantity)
                    for item in plan
                ],
                actor_id=rng.choice(warehouse_operators).id,
            )
            db.commit()
            tally["lot:stored"] += 1
        except DomainError:
            # No free address left: the lot legitimately stays APPROVED, waiting
            # for space. Never force the stock past the warehouse capacity.
            db.rollback()
            capacity_full += 1
            tally["lot:approved_not_stored"] += 1

    # ------------------------------------------------------------ outbound
    now = datetime.now(timezone.utc)
    for index in range(REQUEST_COUNT):
        part = rng.choice(parts)
        station = rng.choice(stations)
        outcome = _weighted(rng, REQUEST_OUTCOMES)
        priority = rng.choices((1, 2, 3), weights=(2, 5, 3), k=1)[0]

        if part.size_class is PartSize.SMALL:
            quantity = rng.choice((20, 30, 40, 60, 80, 100, 120, 150))
        else:
            quantity = rng.choice((2, 4, 6, 8, 10, 12, 15))

        leader = rng.choice(leaders)
        try:
            request = production_service.create_request(
                db,
                station_id=station.id,
                part_id=part.id,
                quantity=quantity,
                priority=priority,
                needed_at=now + timedelta(hours=rng.choice((3, 6, 12, 24, 48))),
                notes=rng.choice(REQUEST_NOTES),
                actor_id=leader.id,
                submit_immediately=True,
            )
            db.commit()
        except DomainError:
            db.rollback()
            continue

        if outcome == "submitted":
            tally[f"req:{outcome}"] += 1
            continue

        manager = rng.choice(production_managers)

        if outcome == "rejected":
            production_service.reject(
                db,
                request_id=request.id,
                reason=rng.choice(REJECTION_REASONS),
                actor_id=manager.id,
            )
            db.commit()
            tally[f"req:{outcome}"] += 1
            continue

        try:
            production_service.approve(db, request_id=request.id, actor_id=manager.id)
            db.commit()
        except DomainError:
            # Not enough stock to reserve: the request stays submitted, which is
            # exactly the shortage signal the assistant is meant to surface.
            db.rollback()
            tally["req:submitted"] += 1
            continue

        if outcome == "approved":
            tally[f"req:{outcome}"] += 1
            continue

        operator = rng.choice(warehouse_operators)
        production_service.start_preparation(db, request_id=request.id, actor_id=operator.id)
        db.commit()

        if outcome == "preparing":
            tally[f"req:{outcome}"] += 1
            continue

        production_service.mark_ready(db, request_id=request.id, actor_id=operator.id)
        db.commit()

        if outcome == "ready":
            tally[f"req:{outcome}"] += 1
            continue

        try:
            production_service.issue(db, request_id=request.id, actor_id=operator.id)
            db.commit()
            tally["req:issued"] += 1
        except DomainError:
            db.rollback()
            tally["req:ready"] += 1

    if capacity_full:
        print(f"  {capacity_full} lots left APPROVED - no free address (warehouse full)")

    return tally
