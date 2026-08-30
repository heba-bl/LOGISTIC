"""Seed a coherent demonstration dataset.

Reference data is inserted directly, but the operational history is replayed
THROUGH THE SERVICES: receptions, inspections, quality decisions, storage
confirmations, production requests and issues all go through the same code the
API calls. The resulting stock, movements and audit trail are therefore genuine
rather than fabricated, which is exactly what the AI and Power BI layers need.

Usage (from the backend/ directory):

    python scripts/seed.py            # seed if empty
    python scripts/seed.py --reset    # wipe and reseed
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import delete, select  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.models.catalog import Category, Part, Supplier  # noqa: E402
from app.models.enums import (  # noqa: E402
    LocationRole,
    PartSize,
    RoleName,
    Zone,
)
from app.models.organization import Role, User  # noqa: E402
from app.models.production import ProductionStation  # noqa: E402
from app.models.vehicle import Vehicle, VehicleBomLine  # noqa: E402
from app.models.warehouse import PartLocation, Warehouse, WarehouseLocation  # noqa: E402
from app.services import whap_source  # noqa: E402
from app.services import (  # noqa: E402
    inspection_service,
    production_service,
    quality_service,
    reception_service,
    settings_service,
    warehouse_service,
)
from app.services.warehouse_service import Allocation  # noqa: E402
from scripts.backdate import backdate  # noqa: E402
from scripts.seed_volume import seed_volume  # noqa: E402

# --------------------------------------------------------------------------- data
#: (role, label, description, can_validate)
#: `can_validate` marks the responsibles allowed to check what an operator entered.
ROLES = [
    (RoleName.RECEPTIONIST, "Receptionist", "Books deliveries in and checks quantities", False),
    (RoleName.RECEPTION_MANAGER, "Reception Manager", "Validates reception entries", True),
    (RoleName.QUALITY_INSPECTOR, "Quality Inspector", "Samples lots and records defects", False),
    (RoleName.QUALITY_MANAGER, "Quality Manager", "Approves, rejects or quarantines lots", True),
    (RoleName.WAREHOUSE_OPERATOR, "Warehouse Operator", "Confirms storage and issues", False),
    (RoleName.STATION_LEADER, "Station Leader", "Raises production parts requests", False),
    (RoleName.PRODUCTION_MANAGER, "Production Manager", "Validates production requests", True),
    (RoleName.LOGISTICS_MANAGER, "Logistics Manager", "Supervises the whole flow", True),
]

#: (matricule, username, prenom, nom, role, zone, service)
#: An operator is never anonymous: the employee number identifies every action.
#: SYNTHETIC identities - demonstration only.
USERS = [
    ("OP-1042", "k.moreau", "Karim", "Moreau", RoleName.RECEPTIONIST, Zone.RECEPTION, "Reception"),
    ("OP-1051", "h.bouzid", "Hicham", "Bouzid", RoleName.RECEPTIONIST, Zone.RECEPTION, "Reception"),
    ("RM-004", "f.chaoui", "Fatima", "Chaoui", RoleName.RECEPTION_MANAGER, Zone.RECEPTION, "Reception"),
    ("QL-1045", "s.haddad", "Sara", "Haddad", RoleName.QUALITY_INSPECTOR, Zone.INSPECTION, "Qualite"),
    ("QL-1046", "o.mansouri", "Omar", "Mansouri", RoleName.QUALITY_INSPECTOR, Zone.INSPECTION, "Qualite"),
    ("QM-002", "n.benali", "Nadia", "Benali", RoleName.QUALITY_MANAGER, Zone.QUALITY, "Qualite"),
    ("WH-008", "y.tazi", "Youssef", "Tazi", RoleName.WAREHOUSE_OPERATOR, Zone.WAREHOUSE, "Entrepot"),
    ("WH-M01", "r.alami", "Rachid", "Alami", RoleName.LOGISTICS_MANAGER, Zone.WAREHOUSE, "Entrepot"),
    ("ST-012", "m.dupont", "Marc", "Dupont", RoleName.STATION_LEADER, Zone.PRODUCTION, "Production"),
    ("PM-001", "l.ferrand", "Luc", "Ferrand", RoleName.PRODUCTION_MANAGER, Zone.PRODUCTION, "Production"),
    ("LM-001", "a.sahli", "Amine", "Sahli", RoleName.LOGISTICS_MANAGER, Zone.LOGISTICS, "Logistique"),
    ("OP-1063", "n.serrano", "Nora", "Serrano", RoleName.RECEPTIONIST, Zone.RECEPTION, "Reception"),
    ("OP-1078", "t.lefevre", "Thomas", "Lefevre", RoleName.RECEPTIONIST, Zone.RECEPTION, "Reception"),
    ("RM-005", "a.idrissi", "Amal", "Idrissi", RoleName.RECEPTION_MANAGER, Zone.RECEPTION, "Reception"),
    ("QL-1052", "j.rossi", "Julia", "Rossi", RoleName.QUALITY_INSPECTOR, Zone.INSPECTION, "Qualite"),
    ("QL-1058", "b.kacem", "Bilal", "Kacem", RoleName.QUALITY_INSPECTOR, Zone.INSPECTION, "Qualite"),
    ("QL-1064", "e.dubois", "Elodie", "Dubois", RoleName.QUALITY_INSPECTOR, Zone.INSPECTION, "Qualite"),
    ("QM-003", "s.ouali", "Samir", "Ouali", RoleName.QUALITY_MANAGER, Zone.QUALITY, "Qualite"),
    ("WH-012", "i.nakache", "Ines", "Nakache", RoleName.WAREHOUSE_OPERATOR, Zone.WAREHOUSE, "Entrepot"),
    ("WH-019", "d.morel", "David", "Morel", RoleName.WAREHOUSE_OPERATOR, Zone.WAREHOUSE, "Entrepot"),
    ("WH-024", "z.belkacem", "Zineb", "Belkacem", RoleName.WAREHOUSE_OPERATOR, Zone.WAREHOUSE, "Entrepot"),
    ("ST-021", "c.navarro", "Clara", "Navarro", RoleName.STATION_LEADER, Zone.PRODUCTION, "Production"),
    ("ST-034", "p.gauthier", "Paul", "Gauthier", RoleName.STATION_LEADER, Zone.PRODUCTION, "Production"),
    ("PM-002", "h.lemaire", "Helene", "Lemaire", RoleName.PRODUCTION_MANAGER, Zone.PRODUCTION, "Production"),
    ("LM-002", "k.benjelloun", "Khalid", "Benjelloun", RoleName.LOGISTICS_MANAGER, Zone.LOGISTICS, "Logistique"),
]

#: The six families the warehouse distinguishes, labelled for the interface.
#: Codes come from `whap_source`, so a family cannot exist on one side only.
CATEGORY_LABELS = {
    whap_source.CATEGORY_VEHICLE_PART: "Piece vehicule",
    whap_source.CATEGORY_CONSUMABLE: "Consommable",
    whap_source.CATEGORY_MATERIAL: "Matiere",
    whap_source.CATEGORY_VEHICLE_EQUIPMENT: "Equipement vehicule",
    whap_source.CATEGORY_ACCESSORY: "Accessoire",
    whap_source.CATEGORY_PACKAGING: "Emballage",
}

SUPPLIERS = [
    ("DEL", "Delphi Automotive", "France", 5),
    ("YZK", "Yazaki Europe", "Portugal", 9),
    ("SUM", "Sumitomo Electric", "Maroc", 7),
    ("VAL", "Valeo Systems", "France", 4),
    ("BOS", "Bosch Mobility", "Allemagne", 6),
    ("CTL", "Continental Automotive", "Allemagne", 8),
    ("MAG", "Magna Structures", "Espagne", 7),
    ("FAU", "Faurecia Interiors", "France", 5),
    ("HEL", "Hella Lighting", "Allemagne", 10),
    ("SKF", "SKF Bearings", "Italie", 12),
]

#: Accounts the shared workbook marks INACTIF. Kept in step with
#: `excel_operations.DEMO_USERS`.
INACTIVE_MATRICULES = {"RM-005"}

#: Demonstration validation codes. Only their digests reach the database, and
#: the shared workbook stores the same digests - so a code works on both sides
#: or neither.
VALIDATION_CODES = {
    "RM-004": "REC2026",
    "RM-005": "REC2026",
    "QM-002": "QUA2026",
    "QM-003": "QUA2026",
    "WH-M01": "WHS2026",
    "PM-001": "PRD2026",
    "PM-002": "PRD2026",
    "LM-001": "LOG2026",
    "LM-002": "LOG2026",
}

STATIONS = [
    ("ST-01", "Poste d'assemblage 01", "Ligne 1"),
    ("ST-02", "Poste d'assemblage 02", "Ligne 1"),
    ("ST-03", "Poste de cablage 03", "Ligne 2"),
    ("ST-04", "Assemblage final 04", "Ligne 2"),
    ("ST-05", "Poste trains roulants 05", "Ligne 1"),
    ("ST-06", "Poste d'habillage 06", "Ligne 2"),
    ("ST-07", "Poste electronique 07", "Ligne 3"),
    ("ST-08", "Controle final 08", "Ligne 3"),
]

#: The vehicle the nomenclature describes.
VEHICLE = {
    "code": "WHAP-8X8",
    "name": "Vehicule blinde 8x8",
    "segment": "Vehicule special",
    "model_year": 2026,
    "description": "Nomenclature fournie: WhAP_8x8_2200_pieces.xlsx",
}

#: Capacity of one address. Sized from the catalogue so the racks can actually
#: hold what the demonstration stores, with room left to exercise saturation.
LOCATION_CAPACITY = 4000


#: How many references the warehouse actually holds.
#:
#: The catalogue is the vehicle's bill of materials - 2 239 lines. A plant does
#: not stock all of it: most of a BOM arrives in kits, in direct flow, or is
#: fitted by a supplier. Sizing the perimeter here is also what makes the
#: demonstration legible: with 240 lots replayed, each managed reference gets a
#: real history of three or four movements instead of a single lonely lot.
MANAGED_SCOPE_SIZE = 80


def choose_managed_scope(catalogue) -> set[str]:
    """The references the magasin replenishes, spread across the systems.

    Picked deterministically and evenly rather than at random: a perimeter that
    ignored whole systems would look arbitrary on screen, and one drawn freshly
    each run would make two demonstrations disagree.
    """
    by_system: dict[str, list] = {}
    for article in catalogue:
        by_system.setdefault(article.system, []).append(article)

    for articles in by_system.values():
        articles.sort(key=lambda article: article.code)

    scope: set[str] = set()
    systems = sorted(by_system)
    position = 0
    # Round-robin over the systems until the perimeter is full, so every family
    # of the vehicle is represented.
    while len(scope) < MANAGED_SCOPE_SIZE:
        added = False
        for system in systems:
            articles = by_system[system]
            if position < len(articles):
                scope.add(articles[position].code)
                added = True
                if len(scope) >= MANAGED_SCOPE_SIZE:
                    break
        if not added:
            break
        position += 1
    return scope


def _address_parts(code: str) -> tuple[str, int]:
    """Split `A-01-02` into its zone and a sortable position.

    The workbook addresses a shelf as zone-aisle-level; the model stores a zone
    and one integer. Folding aisle and level into `aisle * 100 + level` keeps
    the natural order of the racks and lets the code stay identical on both
    sides - which is the whole point of this change.
    """
    zone, aisle, level = code.split("-")
    return zone, int(aisle) * 100 + int(level)


def wipe(db) -> None:
    """Delete every row, children first."""
    from app.models.flow import Inspection, Lot, QualityValidation, Reception
    from app.models.imports import DataImport, ImportRow
    from app.models.production import ProductionRequest
    from app.models.system import AIRecommendation, AuditLog, SystemSetting
    from app.models.warehouse import Stock, StockMovement

    from app.models.vehicle import Vehicle, VehicleBomLine

    for model in (
        VehicleBomLine,
        Vehicle,
        ImportRow,
        DataImport,
        AuditLog,
        AIRecommendation,
        StockMovement,
        Stock,
        QualityValidation,
        Inspection,
        Reception,
        ProductionRequest,
        Lot,
        PartLocation,
        WarehouseLocation,
        Warehouse,
        ProductionStation,
        Part,
        Category,
        Supplier,
        User,
        Role,
        SystemSetting,
    ):
        db.execute(delete(model))
    db.commit()
    print("  wiped existing data")


def seed_reference_data(db) -> dict:
    """Insert roles, users, the catalogue, the warehouse and the stations.

    The catalogue is read from `whap_source`, which reads the customer's file.
    Nothing is retyped here, so Excel and the database cannot drift apart.
    """
    settings_service.ensure_defaults(db)

    roles = {}
    for name, label, description, can_validate in ROLES:
        role = Role(name=name, label=label, description=description, can_validate=can_validate)
        db.add(role)
        roles[name] = role
    db.flush()

    users = {}
    users_by_matricule = {}
    for employee_number, username, first, last, role_name, zone, service in USERS:
        user = User(
            employee_number=employee_number,
            username=username,
            full_name=f"{first} {last}",
            first_name=first,
            last_name=last,
            role_id=roles[role_name].id,
            zone=zone,
            service=service,
            # The shared workbook shows the same status; a person the file
            # calls inactive must be inactive here too, or the two sides
            # disagree about who may sign anything off.
            is_active=employee_number not in INACTIVE_MATRICULES,
        )
        db.add(user)
        users.setdefault(role_name, user)
        users_by_matricule[employee_number] = user
    db.flush()

    categories = {}
    for code, label in CATEGORY_LABELS.items():
        category = Category(code=code, name=label)
        db.add(category)
        categories[code] = category
    db.flush()

    suppliers = {}
    for code, name, country, lead_time in SUPPLIERS:
        supplier = Supplier(code=code, name=name, country=country, lead_time_days=lead_time)
        db.add(supplier)
        suppliers[code] = supplier
    db.flush()

    catalogue = whap_source.load_catalogue()
    managed_scope = choose_managed_scope(catalogue)

    parts = {}
    for article in catalogue:
        part = Part(
            # The customer's own identifier is the key, unchanged.
            reference=article.code,
            designation=article.designation,
            description=(
                f"{article.system} / {article.subsystem} - reference interne "
                f"{article.reference}"
            ),
            category_id=categories[article.category].id,
            size_class=PartSize(article.size_class),
            unit=article.unit[:10],
            is_managed=article.code in managed_scope,
            # A safety level and a consumption describe a replenishment. Outside
            # the perimeter nobody replenishes, so leaving those figures set
            # would make the risk model read a promise the plant never made.
            safety_stock=article.minimum if article.code in managed_scope else 0,
            average_daily_consumption=(
                article.daily_consumption if article.code in managed_scope else 0.0
            ),
        )
        db.add(part)
        parts[article.code] = part
    db.flush()

    warehouse = Warehouse(code="WH-MAIN", name="Magasin principal")
    db.add(warehouse)
    db.flush()

    # Every address the catalogue mentions, primary or overflow.
    addresses = sorted(
        {article.location for article in catalogue}
        | {article.secondary_location for article in catalogue if article.secondary_location}
    )
    locations = {}
    for code in addresses:
        zone, position = _address_parts(code)
        location = WarehouseLocation(
            warehouse_id=warehouse.id,
            code=code,
            zone=zone,
            position=position,
            capacity=LOCATION_CAPACITY,
        )
        db.add(location)
        locations[code] = location
    db.flush()

    for article in catalogue:
        db.add(
            PartLocation(
                part_id=parts[article.code].id,
                location_id=locations[article.location].id,
                role=LocationRole.PRIMARY,
            )
        )
        if article.secondary_location:
            db.add(
                PartLocation(
                    part_id=parts[article.code].id,
                    location_id=locations[article.secondary_location].id,
                    role=LocationRole.SECONDARY,
                )
            )
    db.flush()

    stations = {}
    for code, name, line in STATIONS:
        station = ProductionStation(code=code, name=name, production_line=line)
        db.add(station)
        stations[code] = station
    db.flush()

    from app.services.excel_sync_service import code_digest

    for matricule, code in VALIDATION_CODES.items():
        person = users_by_matricule.get(matricule)
        if person is not None:
            person.validation_code_hash = code_digest(matricule, code)

    users[RoleName.STATION_LEADER].station_id = stations["ST-02"].id
    db.commit()

    secondary = sum(1 for article in catalogue if article.secondary_location)
    print(
        f"  reference data: {len(roles)} roles, {len(users_by_matricule)} identified operators, "
        f"{len(parts)} articles ({sum(1 for a in catalogue if a.source == 'WHAP')} du fichier WhAP), "
        f"{len(locations)} adresses, {secondary} references sur 2 adresses, "
        f"{len(stations)} stations"
    )
    return {
        "roles": roles,
        "users": users,
        "users_by_matricule": users_by_matricule,
        "parts": parts,
        "suppliers": suppliers,
        "locations": locations,
        "stations": stations,
        "catalogue": catalogue,
        "managed": managed_scope,
    }


def _full_inbound(db, ctx, *, part_ref: str, supplier_code: str, quantity: int) -> int:
    """Replay a complete inbound flow and return the lot id (now STORED)."""
    users = ctx["users"]
    reception = reception_service.create_reception(
        db,
        part_id=ctx["parts"][part_ref].id,
        supplier_id=ctx["suppliers"][supplier_code].id,
        quantity_expected=quantity,
        quantity_received=quantity,
        delivery_note=f"BL-{supplier_code}-{quantity}",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    lot = reception.lot

    inspection_service.start_inspection(
        db, lot_id=lot.id, actor_id=users[RoleName.QUALITY_INSPECTOR].id
    )
    inspection_service.record_inspection(
        db,
        lot_id=lot.id,
        sample_size=inspection_service.suggest_sample_size(db, lot),
        defects_found=0,
        observations="Sample conform",
        actor_id=users[RoleName.QUALITY_INSPECTOR].id,
    )
    quality_service.approve(
        db,
        lot_id=lot.id,
        justification="Sample conform, lot cleared for storage",
        actor_id=users[RoleName.QUALITY_MANAGER].id,
    )

    plan = warehouse_service.suggest_allocations(
        db, part=lot.part, quantity=lot.quantity_approved
    )
    warehouse_service.confirm_storage(
        db,
        lot_id=lot.id,
        allocations=[
            Allocation(location_id=item.location.id, quantity=item.quantity) for item in plan
        ],
        actor_id=users[RoleName.WAREHOUSE_OPERATOR].id,
    )
    db.commit()
    return lot.id



def seed_vehicle_bom(db, ctx) -> dict:
    """The vehicle and its nomenclature, straight from the supplied file.

    Every line is linked to its `Part`, so the bill of materials and the stock
    talk about the same objects - which is what makes "what do I need for five
    vehicles, and do I have it" answerable.
    """
    vehicle = Vehicle(
        code=VEHICLE["code"],
        name=VEHICLE["name"],
        segment=VEHICLE["segment"],
        model_year=VEHICLE["model_year"],
        description=VEHICLE["description"],
    )
    db.add(vehicle)
    db.flush()

    lines = 0
    for article in whap_source.bom_articles():
        part = ctx["parts"].get(article.code)
        db.add(
            VehicleBomLine(
                vehicle_id=vehicle.id,
                part_reference=article.code,
                part_description=article.designation,
                system_code=article.system[:20],
                system_label=article.system,
                subsystem=article.subsystem,
                category=article.category,
                size_class=PartSize(article.size_class),
                quantity_per_vehicle=article.quantity_per_vehicle,
                unit=article.unit[:10],
                supplier_code=article.supplier,
                is_managed=part is not None,
                part_id=part.id if part is not None else None,
            )
        )
        lines += 1
    db.commit()

    print(f"  nomenclature {vehicle.code}: {lines} references, toutes liees au stock")
    return {"total": lines, "systems": len({a.system for a in whap_source.bom_articles()})}


#: The hand-written scenario needs eight articles playing specific roles - four
#: counted in bulk and four counted one by one, because the reception tolerance
#: only applies to the first kind. They are picked from the catalogue rather
#: than named, so the scenario survives any change to the source file.
SCENARIO_ROLES = ("SMALL_A", "SMALL_B", "SMALL_C", "SMALL_D",
                  "LARGE_A", "LARGE_B", "LARGE_C", "LARGE_D")


def scenario_articles(catalogue, managed: set[str] | None = None) -> dict[str, str]:
    """Role -> article code, deterministic across runs.

    Drawn from the managed perimeter: the hand-written scenario receives, stores
    and issues these references, and a reference the warehouse does not hold has
    no business having a lot.
    """
    def pool(size_class: str) -> list[str]:
        return sorted(
            article.code
            for article in catalogue
            if article.source == "WHAP"
            and article.size_class == size_class
            and (not managed or article.code in managed)
        )

    small, large = pool("SMALL"), pool("LARGE")
    if len(small) < 4 or len(large) < 4:
        raise RuntimeError("perimetre gere trop petit pour le scenario de demonstration")
    return dict(zip(SCENARIO_ROLES, small[:4] + large[:4]))


def seed_history(db, ctx) -> None:
    """Build a realistic operational history across the whole flow."""
    users = ctx["users"]
    suppliers = ctx["suppliers"]
    stations = ctx["stations"]

    # The scenario refers to articles by the role they play, not by name.
    role = scenario_articles(ctx["catalogue"], ctx.get("managed"))
    parts = {name: ctx["parts"][code] for name, code in role.items()}

    # --- 1. Fully completed inbound flows -> real stock -------------------
    stored = [
        ("SMALL_A", "DEL", 420),
        ("SMALL_B", "DEL", 800),
        ("LARGE_A", "YZK", 160),
        ("SMALL_C", "SUM", 900),
        ("SMALL_D", "SUM", 500),
        ("LARGE_C", "VAL", 90),
        ("LARGE_D", "VAL", 60),
        ("LARGE_B", "YZK", 120),
    ]
    for scenario_role, supplier, quantity in stored:
        _full_inbound(
            db, ctx, part_ref=role[scenario_role],
            supplier_code=supplier, quantity=quantity,
        )
    print(f"  {len(stored)} lots received, inspected, approved and stored")

    # --- 2. Lots left in intermediate states ------------------------------
    # a) awaiting inspection
    reception_service.create_reception(
        db,
        part_id=parts["SMALL_C"].id,
        supplier_id=suppliers["SUM"].id,
        quantity_expected=250,
        quantity_received=250,
        delivery_note="BL-SUM-250",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    db.commit()

    # b) inspection in progress
    pending = reception_service.create_reception(
        db,
        part_id=parts["SMALL_A"].id,
        supplier_id=suppliers["DEL"].id,
        quantity_expected=180,
        quantity_received=180,
        delivery_note="BL-DEL-180",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    inspection_service.start_inspection(
        db, lot_id=pending.lot_id, actor_id=users[RoleName.QUALITY_INSPECTOR].id
    )
    db.commit()

    # c) inspected and conform, waiting for the quality decision
    waiting = reception_service.create_reception(
        db,
        part_id=parts["LARGE_A"].id,
        supplier_id=suppliers["YZK"].id,
        quantity_expected=80,
        quantity_received=80,
        delivery_note="BL-YZK-80",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    inspection_service.start_inspection(
        db, lot_id=waiting.lot_id, actor_id=users[RoleName.QUALITY_INSPECTOR].id
    )
    inspection_service.record_inspection(
        db,
        lot_id=waiting.lot_id,
        sample_size=8,
        defects_found=0,
        observations="Sample conform, awaiting manager decision",
        actor_id=users[RoleName.QUALITY_INSPECTOR].id,
    )
    db.commit()

    # d) approved but not yet stored
    approved = reception_service.create_reception(
        db,
        part_id=parts["SMALL_D"].id,
        supplier_id=suppliers["SUM"].id,
        quantity_expected=200,
        quantity_received=200,
        delivery_note="BL-SUM-200",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    inspection_service.start_inspection(
        db, lot_id=approved.lot_id, actor_id=users[RoleName.QUALITY_INSPECTOR].id
    )
    inspection_service.record_inspection(
        db,
        lot_id=approved.lot_id,
        sample_size=8,
        defects_found=0,
        actor_id=users[RoleName.QUALITY_INSPECTOR].id,
    )
    quality_service.approve(
        db,
        lot_id=approved.lot_id,
        justification="Conform, waiting for a free address",
        actor_id=users[RoleName.QUALITY_MANAGER].id,
    )
    db.commit()

    # --- 3. Red Cage: a non conform inspection ----------------------------
    non_conform = reception_service.create_reception(
        db,
        part_id=parts["SMALL_A"].id,
        supplier_id=suppliers["DEL"].id,
        quantity_expected=140,
        quantity_received=140,
        delivery_note="BL-DEL-140",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    inspection_service.start_inspection(
        db, lot_id=non_conform.lot_id, actor_id=users[RoleName.QUALITY_INSPECTOR].id
    )
    inspection_service.record_inspection(
        db,
        lot_id=non_conform.lot_id,
        sample_size=10,
        defects_found=3,
        observations="Machining marks on the mounting face",
        actor_id=users[RoleName.QUALITY_INSPECTOR].id,
    )
    db.commit()

    # --- 4. Red Cage: a reception outside tolerance ------------------------
    # CB-305 is a LARGE part: the expected quantity must match exactly.
    reception_service.create_reception(
        db,
        part_id=parts["LARGE_B"].id,
        supplier_id=suppliers["YZK"].id,
        quantity_expected=100,
        quantity_received=94,
        delivery_note="BL-YZK-94",
        notes="Six units missing on the delivery note",
        actor_id=users[RoleName.RECEPTIONIST].id,
    )
    db.commit()
    print("  2 lots in Red Cage (non conform inspection + quantity gap)")

    # --- 5. Production requests in several states -------------------------
    leader = users[RoleName.STATION_LEADER]
    manager = users[RoleName.PRODUCTION_MANAGER]
    operator = users[RoleName.WAREHOUSE_OPERATOR]
    now = datetime.now(timezone.utc)

    # a) Fully issued -> real consumption history
    for station_code, part_ref, quantity in (
        ("ST-02", "SMALL_A", 60),
        ("ST-01", "SMALL_C", 180),
        ("ST-03", "LARGE_A", 25),
        ("ST-02", "SMALL_B", 200),
    ):
        request = production_service.create_request(
            db,
            station_id=stations[station_code].id,
            part_id=parts[part_ref].id,
            quantity=quantity,
            priority=2,
            needed_at=now + timedelta(hours=6),
            actor_id=leader.id,
            submit_immediately=True,
        )
        production_service.approve(db, request_id=request.id, actor_id=manager.id)
        production_service.start_preparation(db, request_id=request.id, actor_id=operator.id)
        production_service.mark_ready(db, request_id=request.id, actor_id=operator.id)
        production_service.issue(db, request_id=request.id, actor_id=operator.id)
        db.commit()

    # b) Submitted, waiting for validation
    production_service.create_request(
        db,
        station_id=stations["ST-04"].id,
        part_id=parts["LARGE_C"].id,
        quantity=30,
        priority=1,
        needed_at=now + timedelta(hours=3),
        notes="Urgent for the line 2 changeover",
        actor_id=leader.id,
        submit_immediately=True,
    )

    # c) Approved, being prepared
    preparing = production_service.create_request(
        db,
        station_id=stations["ST-01"].id,
        part_id=parts["SMALL_D"].id,
        quantity=120,
        priority=2,
        actor_id=leader.id,
        submit_immediately=True,
    )
    production_service.approve(db, request_id=preparing.id, actor_id=manager.id)
    production_service.start_preparation(db, request_id=preparing.id, actor_id=operator.id)

    # d) A request larger than the stock on hand -> shortage signal
    production_service.create_request(
        db,
        station_id=stations["ST-03"].id,
        part_id=parts["LARGE_D"].id,
        quantity=95,
        priority=1,
        needed_at=now + timedelta(hours=2),
        notes="Requirement above the quantity currently in stock",
        actor_id=leader.id,
        submit_immediately=True,
    )
    db.commit()
    print("  7 production requests (4 issued, 3 open including 1 not covered)")


def summarise(db) -> None:
    from app.models.flow import Lot
    from app.models.production import ProductionRequest
    from app.models.system import AuditLog
    from app.models.warehouse import Stock, StockMovement

    def count(model) -> int:
        from sqlalchemy import func

        return db.execute(select(func.count()).select_from(model)).scalar_one()

    total_stock = db.execute(
        select(__import__("sqlalchemy").func.coalesce(
            __import__("sqlalchemy").func.sum(Stock.quantity_available), 0
        ))
    ).scalar_one()

    print("\n  Summary")
    print(f"    lots ................ {count(Lot)}")
    print(f"    stock rows .......... {count(Stock)}  (total {total_stock} units)")
    print(f"    stock movements ..... {count(StockMovement)}")
    print(f"    production requests . {count(ProductionRequest)}")
    print(f"    audit entries ....... {count(AuditLog)}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the SLCC demonstration dataset")
    parser.add_argument("--reset", action="store_true", help="wipe existing data first")
    args = parser.parse_args()

    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    try:
        existing = db.execute(select(Part).limit(1)).scalar_one_or_none()
        if existing and not args.reset:
            print("Database already seeded. Use --reset to rebuild it.")
            return
        if args.reset:
            wipe(db)

        print("Seeding Smart Logistics Control Center...")
        ctx = seed_reference_data(db)
        seed_vehicle_bom(db, ctx)
        seed_history(db, ctx)

        # The scenario above covers every case once; this adds the volume that
        # makes the exported workbooks and the analytics meaningful.
        tally = seed_volume(db, ctx)
        print(
            "  volume replayed through the services: "
            + ", ".join(f"{count} {name}" for name, count in tally.items() if count)
        )

        # The history is replayed through the services, so every event is stamped
        # "now". Spread it over the past days so lead times and the activity feed
        # are meaningful.
        spread = backdate(db)
        print(
            f"  history spread over the past days "
            f"({spread['lots']} lots, {spread['requests']} requests, {spread['events']} events)"
        )

        summarise(db)
        print("\nDone.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
