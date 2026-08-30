"""Compile the application schema and queries for PostgreSQL.

PostgreSQL is the target engine but development may run on the SQLite fallback.
This script proves, without needing a running server, that:

  * the whole schema renders as valid PostgreSQL DDL;
  * every non-trivial query the application issues compiles for the PostgreSQL
    dialect (ordering with NULLS LAST, aggregates, GROUP BY / HAVING, subqueries,
    LIKE on lowered columns...).

Run from the backend/ directory:

    python scripts/check_postgres_compat.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, or_, select  # noqa: E402
from sqlalchemy.dialects import postgresql  # noqa: E402
from sqlalchemy.orm import joinedload  # noqa: E402
from sqlalchemy.schema import CreateTable  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.models.catalog import Category, Part, Supplier  # noqa: E402
from app.models.enums import (  # noqa: E402
    InspectionResult,
    LotStatus,
    MovementType,
    ProductionRequestStatus,
)
from app.models.flow import Inspection, Lot, QualityValidation, Reception  # noqa: E402
from app.models.production import ProductionRequest, ProductionStation  # noqa: E402
from app.models.system import AIRecommendation, AuditLog  # noqa: E402
from app.models.warehouse import (  # noqa: E402
    PartLocation,
    Stock,
    StockMovement,
    WarehouseLocation,
)

DIALECT = postgresql.dialect()


def compile_statement(label: str, statement) -> tuple[str, bool, str]:
    try:
        statement.compile(dialect=DIALECT, compile_kwargs={"literal_binds": False})
        return label, True, ""
    except Exception as exc:  # noqa: BLE001
        return label, False, str(exc)


#: The queries that are not plain selects - the ones a dialect can actually break.
def build_statements() -> list[tuple[str, object]]:
    now = datetime.now(timezone.utc)

    return [
        (
            "stock_service._consume_from_lots (ORDER BY ... NULLS LAST)",
            select(Lot)
            .where(Lot.part_id == 1, Lot.quantity_available > 0)
            .order_by(Lot.stored_at.asc().nulls_last(), Lot.id.asc()),
        ),
        (
            "stock_service._lot_storage_map (IN movements per location)",
            select(StockMovement.location_id, StockMovement.quantity)
            .where(
                StockMovement.lot_id == 1,
                StockMovement.movement_type == MovementType.IN,
                StockMovement.location_id.is_not(None),
            )
            .order_by(StockMovement.id),
        ),
        (
            "LotRepository.count_by_status (GROUP BY enum)",
            select(Lot.status, func.count()).group_by(Lot.status),
        ),
        (
            "LotRepository.list_filtered (join + lower LIKE + eager load)",
            select(Lot)
            .options(joinedload(Lot.part), joinedload(Lot.supplier), joinedload(Lot.location))
            .where(Lot.status.in_([LotStatus.STORED, LotStatus.APPROVED]))
            .join(Part)
            .where(
                or_(
                    func.lower(Lot.lot_number).like("%br%"),
                    func.lower(Part.reference).like("%br%"),
                )
            )
            .order_by(Lot.id.desc())
            .limit(200),
        ),
        (
            "WarehouseRepository.total_occupancy (SUM + COALESCE)",
            select(
                func.coalesce(func.sum(WarehouseLocation.occupied), 0),
                func.coalesce(func.sum(WarehouseLocation.capacity), 0),
            ).where(WarehouseLocation.is_active.is_(True)),
        ),
        (
            "ProductionRepository.demand_for_part (SUM of expression)",
            select(
                func.coalesce(
                    func.sum(
                        ProductionRequest.quantity_requested - ProductionRequest.quantity_issued
                    ),
                    0,
                )
            ).where(
                ProductionRequest.part_id == 1,
                ProductionRequest.status.in_(
                    [ProductionRequestStatus.SUBMITTED, ProductionRequestStatus.APPROVED]
                ),
            ),
        ),
        (
            "dashboard_service.build_kpis (COUNT over DISTINCT subquery)",
            select(func.count()).select_from(select(Lot.part_id).distinct().subquery()),
        ),
        (
            "analytics.stock_by_category (OUTER JOIN + GROUP BY + COALESCE)",
            select(
                func.coalesce(Category.name, "Uncategorised"),
                func.sum(Stock.quantity_available),
            )
            .select_from(Stock)
            .join(Part, Part.id == Stock.part_id)
            .outerjoin(Category, Category.id == Part.category_id)
            .group_by(Category.name)
            .order_by(func.sum(Stock.quantity_available).desc()),
        ),
        (
            "analytics.stock_by_part (ORDER BY + LIMIT)",
            select(Part.reference, Stock.quantity_available)
            .select_from(Stock)
            .join(Part, Part.id == Stock.part_id)
            .order_by(Stock.quantity_available.desc())
            .limit(15),
        ),
        (
            "analytics.stock_evolution (window filter)",
            select(StockMovement.occurred_at, StockMovement.movement_type, StockMovement.quantity)
            .where(StockMovement.occurred_at >= now)
            .order_by(StockMovement.occurred_at),
        ),
        (
            "analytics.stage_durations (IN on enum column)",
            select(AuditLog.lot_id, AuditLog.action, AuditLog.occurred_at)
            .where(
                AuditLog.lot_id.is_not(None),
                AuditLog.action.in_(["LOT_RECEIVED", "STORAGE_CONFIRMED"]),
            )
            .order_by(AuditLog.occurred_at),
        ),
        (
            "analytics.quality defects_by_part (GROUP BY + HAVING)",
            select(Part.reference, func.sum(Inspection.defects_found))
            .select_from(Inspection)
            .join(Lot, Lot.id == Inspection.lot_id)
            .join(Part, Part.id == Lot.part_id)
            .group_by(Part.reference)
            .having(func.sum(Inspection.defects_found) > 0)
            .order_by(func.sum(Inspection.defects_found).desc()),
        ),
        (
            "analytics.defects_by_supplier (3 joins + HAVING)",
            select(Supplier.name, func.sum(Inspection.defects_found))
            .select_from(Inspection)
            .join(Lot, Lot.id == Inspection.lot_id)
            .join(Supplier, Supplier.id == Lot.supplier_id)
            .group_by(Supplier.name)
            .having(func.sum(Inspection.defects_found) > 0),
        ),
        (
            "analytics.requests_by_station (COUNT + GROUP BY)",
            select(ProductionStation.code, func.count(ProductionRequest.id))
            .select_from(ProductionRequest)
            .join(ProductionStation, ProductionStation.id == ProductionRequest.station_id)
            .group_by(ProductionStation.code)
            .order_by(func.count(ProductionRequest.id).desc()),
        ),
        (
            "analytics.consumption_by_part (filter on enum + GROUP BY)",
            select(Part.reference, func.sum(StockMovement.quantity))
            .select_from(StockMovement)
            .join(Part, Part.id == StockMovement.part_id)
            .where(StockMovement.movement_type == MovementType.OUT)
            .group_by(Part.reference),
        ),
        (
            "analytics.powerbi fact_lots (4-way join with OUTER)",
            select(Lot, Part, Supplier, WarehouseLocation)
            .join(Part, Part.id == Lot.part_id)
            .join(Supplier, Supplier.id == Lot.supplier_id)
            .outerjoin(WarehouseLocation, WarehouseLocation.id == Lot.location_id),
        ),
        (
            "analytics.powerbi fact_quality (4-way join)",
            select(Inspection, Lot, Part, Supplier)
            .join(Lot, Lot.id == Inspection.lot_id)
            .join(Part, Part.id == Lot.part_id)
            .join(Supplier, Supplier.id == Lot.supplier_id),
        ),
        (
            "ai_service._incoming_quantity (SUM + IN)",
            select(func.coalesce(func.sum(Lot.quantity_received), 0)).where(
                Lot.part_id == 1,
                Lot.status.in_([LotStatus.PENDING_INSPECTION, LotStatus.APPROVED]),
            ),
        ),
        (
            "AuditRepository.timeline (OR over lowered nullable columns)",
            select(AuditLog)
            .options(joinedload(AuditLog.lot), joinedload(AuditLog.part))
            .where(
                or_(
                    func.lower(AuditLog.entity_reference).like("%lot%"),
                    func.lower(AuditLog.reason).like("%lot%"),
                    func.lower(AuditLog.actor_name).like("%lot%"),
                )
            )
            .order_by(AuditLog.id.desc())
            .limit(200),
        ),
        (
            "RecommendationRepository.active (boolean is_ + eager load)",
            select(AIRecommendation)
            .where(AIRecommendation.is_active.is_(True))
            .options(joinedload(AIRecommendation.part), joinedload(AIRecommendation.lot))
            .order_by(AIRecommendation.priority, AIRecommendation.id.desc())
            .limit(50),
        ),
        (
            "WarehouseRepository.part_links (eager load + order by enum)",
            select(PartLocation)
            .where(PartLocation.part_id == 1)
            .options(joinedload(PartLocation.location))
            .order_by(PartLocation.role),
        ),
        (
            "ReceptionRepository.recent (nested eager loads)",
            select(Reception)
            .options(
                joinedload(Reception.lot).joinedload(Lot.part),
                joinedload(Reception.lot).joinedload(Lot.supplier),
                joinedload(Reception.received_by),
            )
            .order_by(Reception.id.desc())
            .limit(100),
        ),
        (
            "QualityRepository.recent (nested eager loads)",
            select(QualityValidation)
            .options(
                joinedload(QualityValidation.lot).joinedload(Lot.part),
                joinedload(QualityValidation.decided_by),
            )
            .order_by(QualityValidation.id.desc())
            .limit(100),
        ),
        (
            "reference_service._next (COUNT with LIKE on reference)",
            select(func.count()).select_from(Lot).where(Lot.lot_number.like("LOT-2026-%")),
        ),
        (
            "InspectionRepository.latest_for_lot (ORDER BY DESC + LIMIT 1)",
            select(Inspection)
            .where(Inspection.lot_id == 1)
            .order_by(Inspection.id.desc())
            .limit(1),
        ),
        (
            "inspection filter on result enum",
            select(func.count())
            .select_from(Inspection)
            .where(Inspection.result == InspectionResult.CONFORM),
        ),
    ]


def main() -> int:
    print("PostgreSQL compatibility check")
    print("=" * 72)

    # 1. Schema
    ddl_failures = []
    for table in Base.metadata.sorted_tables:
        try:
            CreateTable(table).compile(dialect=DIALECT)
        except Exception as exc:  # noqa: BLE001
            ddl_failures.append((table.name, str(exc)))

    print(f"\nSchema: {len(Base.metadata.sorted_tables)} tables")
    if ddl_failures:
        for name, error in ddl_failures:
            print(f"  FAIL  {name}: {error}")
    else:
        print("  all tables render as valid PostgreSQL DDL")

    # 2. Queries
    statements = build_statements()
    results = [compile_statement(label, statement) for label, statement in statements]
    failures = [row for row in results if not row[1]]

    print(f"\nQueries: {len(results)} compiled")
    for label, ok, error in results:
        print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
        if not ok:
            print(f"        {error}")

    print("\n" + "=" * 72)
    if ddl_failures or failures:
        print(f"RESULT: {len(ddl_failures)} schema failure(s), {len(failures)} query failure(s)")
        return 1

    print("RESULT: schema and queries are PostgreSQL compatible")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
