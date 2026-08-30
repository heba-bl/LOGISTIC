"""Test fixtures.

Every test runs against its own throwaway SQLite database so the suite never
touches development data and tests stay independent.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.base import Base  # noqa: E402
from app.models.catalog import Category, Part, Supplier  # noqa: E402
from app.models.enums import LocationRole, PartSize, RoleName  # noqa: E402
from app.models.organization import Role, User  # noqa: E402
from app.models.production import ProductionStation  # noqa: E402
from app.models.warehouse import PartLocation, Warehouse, WarehouseLocation  # noqa: E402
from app.services import settings_service  # noqa: E402


@pytest.fixture()
def engine():
    """In-memory SQLite with foreign keys and CHECK constraints enforced."""
    test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(test_engine, "connect")
    def _enable_foreign_keys(dbapi_connection, _):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    try:
        yield test_engine
    finally:
        Base.metadata.drop_all(bind=test_engine)
        test_engine.dispose()


@pytest.fixture()
def db(engine) -> Session:
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def world(db: Session) -> dict:
    """A minimal but complete world: roles, users, parts, warehouse, station.

    SMALL part  : SM-100, default tolerance
    LARGE part  : LG-200, exact quantity required
    OVERRIDE    : OV-300, its own 10% tolerance
    """
    settings_service.ensure_defaults(db)

    role = Role(name=RoleName.WAREHOUSE_OPERATOR, label="Warehouse Operator")
    db.add(role)
    db.flush()
    # Operators are never anonymous: a matricule is mandatory.
    user = User(
        employee_number="WH-001",
        username="tester",
        full_name="Test Operator",
        role_id=role.id,
        service="Warehouse",
    )
    db.add(user)

    category = Category(code="TST", name="Test category")
    supplier = Supplier(code="SUP", name="Test Supplier", lead_time_days=5)
    db.add_all([category, supplier])
    db.flush()

    small = Part(
        reference="SM-100",
        designation="Small test part",
        category_id=category.id,
        size_class=PartSize.SMALL,
        safety_stock=50,
        average_daily_consumption=10.0,
    )
    large = Part(
        reference="LG-200",
        designation="Large test part",
        category_id=category.id,
        size_class=PartSize.LARGE,
        safety_stock=10,
        average_daily_consumption=2.0,
    )
    override = Part(
        reference="OV-300",
        designation="Part with its own tolerance",
        category_id=category.id,
        size_class=PartSize.SMALL,
        reception_tolerance_percent=10.0,
        safety_stock=5,
        average_daily_consumption=1.0,
    )
    db.add_all([small, large, override])
    db.flush()

    warehouse = Warehouse(code="WH", name="Test warehouse")
    db.add(warehouse)
    db.flush()

    primary = WarehouseLocation(
        warehouse_id=warehouse.id, code="WH-A-01", zone="A", position=1, capacity=1000
    )
    secondary = WarehouseLocation(
        warehouse_id=warehouse.id, code="WH-A-02", zone="A", position=2, capacity=1000
    )
    tiny = WarehouseLocation(
        warehouse_id=warehouse.id, code="WH-B-01", zone="B", position=1, capacity=50
    )
    db.add_all([primary, secondary, tiny])
    db.flush()

    db.add_all(
        [
            PartLocation(part_id=small.id, location_id=primary.id, role=LocationRole.PRIMARY),
            PartLocation(
                part_id=small.id, location_id=secondary.id, role=LocationRole.SECONDARY
            ),
            PartLocation(part_id=large.id, location_id=secondary.id, role=LocationRole.PRIMARY),
            PartLocation(part_id=override.id, location_id=tiny.id, role=LocationRole.PRIMARY),
        ]
    )

    station = ProductionStation(code="ST-01", name="Test station", production_line="Line 1")
    db.add(station)
    db.commit()

    return {
        "user": user,
        "supplier": supplier,
        "small": small,
        "large": large,
        "override": override,
        "primary": primary,
        "secondary": secondary,
        "tiny": tiny,
        "station": station,
    }
