"""Analytical model: indicators for the Analytics screen and Power BI.

Nothing here blocks the application: if Power BI is never connected, these
endpoints simply stay unused. The datasets are deliberately flat and denormalised
so they can be consumed directly by a BI tool.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.catalog import Category, Part, Supplier
from app.models.enums import (
    InspectionResult,
    LotStatus,
    MovementType,
    ProductionRequestStatus,
)
from app.models.flow import Inspection, Lot
from app.models.production import ProductionRequest, ProductionStation
from app.models.system import AuditLog
from app.models.warehouse import Stock, StockMovement, WarehouseLocation
from app.repositories import LotRepository

#: Flow stages measured for lead time, in process order.
STAGE_PAIRS = (
    ("Reception to inspection", "LOT_RECEIVED", "INSPECTION_RECORDED"),
    ("Inspection to quality", "INSPECTION_RECORDED", "QUALITY_APPROVED"),
    ("Quality to storage", "QUALITY_APPROVED", "STORAGE_CONFIRMED"),
    ("Storage to issue", "STORAGE_CONFIRMED", "REQUEST_ISSUED"),
)


def _points(rows) -> list[dict]:
    return [{"label": str(label), "value": float(value or 0)} for label, value in rows]


def stock_by_category(db: Session) -> list[dict]:
    rows = db.execute(
        select(func.coalesce(Category.name, "Uncategorised"), func.sum(Stock.quantity_available))
        .select_from(Stock)
        .join(Part, Part.id == Stock.part_id)
        .outerjoin(Category, Category.id == Part.category_id)
        .group_by(Category.name)
        .order_by(func.sum(Stock.quantity_available).desc())
    ).all()
    return _points(rows)


def stock_by_part(db: Session, limit: int = 15) -> list[dict]:
    rows = db.execute(
        select(Part.reference, Stock.quantity_available)
        .select_from(Stock)
        .join(Part, Part.id == Stock.part_id)
        .order_by(Stock.quantity_available.desc())
        .limit(limit)
    ).all()
    return _points(rows)


def stock_by_location(db: Session) -> list[dict]:
    rows = db.execute(
        select(WarehouseLocation.code, WarehouseLocation.occupied)
        .where(WarehouseLocation.occupied > 0)
        .order_by(WarehouseLocation.occupied.desc())
    ).all()
    return _points(rows)


def stock_evolution(db: Session, days: int = 14) -> list[dict]:
    """Net stock movement per day over the recent window."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    movements = db.execute(
        select(StockMovement.occurred_at, StockMovement.movement_type, StockMovement.quantity)
        .where(StockMovement.occurred_at >= since)
        .order_by(StockMovement.occurred_at)
    ).all()

    buckets: dict[str, float] = {}
    for occurred_at, movement_type, quantity in movements:
        key = occurred_at.strftime("%d %b")
        delta = quantity if movement_type is MovementType.IN else -quantity
        buckets[key] = buckets.get(key, 0.0) + delta

    return [{"label": key, "value": value} for key, value in buckets.items()]


def flow_counts(db: Session) -> list[dict]:
    counts = LotRepository(db).count_by_status()
    ordered = (
        ("Received", LotStatus.PENDING_INSPECTION),
        ("In inspection", LotStatus.INSPECTION_IN_PROGRESS),
        ("Awaiting quality", LotStatus.QUALITY_PENDING),
        ("Approved", LotStatus.APPROVED),
        ("Stored", LotStatus.STORED),
        ("Red Cage", LotStatus.RED_CAGE),
        ("Rejected", LotStatus.REJECTED),
        ("Consumed", LotStatus.CONSUMED),
    )
    return [
        {"label": label, "value": float(counts.get(status.value, 0))} for label, status in ordered
    ]


def stage_durations(db: Session) -> list[dict]:
    """Average hours between milestones - reveals the bottleneck."""
    results: list[dict] = []

    for label, start_action, end_action in STAGE_PAIRS:
        rows = db.execute(
            select(AuditLog.lot_id, AuditLog.action, AuditLog.occurred_at)
            .where(
                AuditLog.lot_id.is_not(None),
                AuditLog.action.in_([start_action, end_action]),
            )
            .order_by(AuditLog.occurred_at)
        ).all()

        starts: dict[int, datetime] = {}
        durations: list[float] = []
        for lot_id, action, occurred_at in rows:
            action_value = action.value if hasattr(action, "value") else action
            if action_value == start_action:
                starts[lot_id] = occurred_at
            elif action_value == end_action and lot_id in starts:
                delta = (occurred_at - starts.pop(lot_id)).total_seconds() / 3600.0
                if delta >= 0:
                    durations.append(delta)

        average = round(sum(durations) / len(durations), 2) if durations else 0.0
        results.append(
            {
                "stage": label,
                "average_hours": average,
                "sample_size": len(durations),
                "is_bottleneck": False,
            }
        )

    measured = [row for row in results if row["sample_size"] > 0]
    if measured:
        slowest = max(measured, key=lambda row: row["average_hours"])
        slowest["is_bottleneck"] = True
    return results


def quality_metrics(db: Session) -> dict:
    total = db.execute(select(func.count()).select_from(Inspection)).scalar_one()
    conform = db.execute(
        select(func.count()).select_from(Inspection).where(
            Inspection.result == InspectionResult.CONFORM
        )
    ).scalar_one()
    red_cage = db.execute(
        select(func.count()).select_from(Lot).where(Lot.status == LotStatus.RED_CAGE)
    ).scalar_one()

    conformity = round(conform / total * 100, 1) if total else 100.0

    defects_by_part = _points(
        db.execute(
            select(Part.reference, func.sum(Inspection.defects_found))
            .select_from(Inspection)
            .join(Lot, Lot.id == Inspection.lot_id)
            .join(Part, Part.id == Lot.part_id)
            .group_by(Part.reference)
            .having(func.sum(Inspection.defects_found) > 0)
            .order_by(func.sum(Inspection.defects_found).desc())
        ).all()
    )

    defects_by_supplier = _points(
        db.execute(
            select(Supplier.name, func.sum(Inspection.defects_found))
            .select_from(Inspection)
            .join(Lot, Lot.id == Inspection.lot_id)
            .join(Supplier, Supplier.id == Lot.supplier_id)
            .group_by(Supplier.name)
            .having(func.sum(Inspection.defects_found) > 0)
            .order_by(func.sum(Inspection.defects_found).desc())
        ).all()
    )

    return {
        "conformity_percent": conformity,
        "non_conformity_percent": round(100 - conformity, 1),
        "red_cage_count": int(red_cage),
        "defects_by_part": defects_by_part,
        "defects_by_supplier": defects_by_supplier,
    }


def production_metrics(db: Session) -> dict:
    by_station = _points(
        db.execute(
            select(ProductionStation.code, func.count(ProductionRequest.id))
            .select_from(ProductionRequest)
            .join(ProductionStation, ProductionStation.id == ProductionRequest.station_id)
            .group_by(ProductionStation.code)
            .order_by(func.count(ProductionRequest.id).desc())
        ).all()
    )

    requested = db.execute(
        select(func.coalesce(func.sum(ProductionRequest.quantity_requested), 0))
    ).scalar_one()
    issued = db.execute(
        select(func.coalesce(func.sum(ProductionRequest.quantity_issued), 0))
    ).scalar_one()
    pending = db.execute(
        select(func.count())
        .select_from(ProductionRequest)
        .where(
            ProductionRequest.status.in_(
                [
                    ProductionRequestStatus.SUBMITTED,
                    ProductionRequestStatus.APPROVED,
                    ProductionRequestStatus.PREPARING,
                    ProductionRequestStatus.READY,
                ]
            )
        )
    ).scalar_one()

    consumption = _points(
        db.execute(
            select(Part.reference, func.sum(StockMovement.quantity))
            .select_from(StockMovement)
            .join(Part, Part.id == StockMovement.part_id)
            .where(StockMovement.movement_type == MovementType.OUT)
            .group_by(Part.reference)
            .order_by(func.sum(StockMovement.quantity).desc())
        ).all()
    )

    return {
        "requests_by_station": by_station,
        "quantity_requested": int(requested),
        "quantity_issued": int(issued),
        "pending_requests": int(pending),
        "consumption_by_part": consumption,
    }


def build_analytics(db: Session) -> dict:
    """The complete analytical payload."""
    quality = quality_metrics(db)
    production = production_metrics(db)
    durations = stage_durations(db)
    bottleneck = next((row["stage"] for row in durations if row["is_bottleneck"]), None)

    return {
        "generated_at": datetime.now(timezone.utc),
        "stock_by_category": stock_by_category(db),
        "stock_by_part": stock_by_part(db),
        "stock_by_location": stock_by_location(db),
        "stock_evolution": stock_evolution(db),
        "flow_counts": flow_counts(db),
        "stage_durations": durations,
        "quality_conformity_percent": quality["conformity_percent"],
        "quality_non_conformity_percent": quality["non_conformity_percent"],
        "red_cage_count": quality["red_cage_count"],
        "defects_by_part": quality["defects_by_part"],
        "defects_by_supplier": quality["defects_by_supplier"],
        "requests_by_station": production["requests_by_station"],
        "quantity_requested": production["quantity_requested"],
        "quantity_issued": production["quantity_issued"],
        "pending_requests": production["pending_requests"],
        "consumption_by_part": production["consumption_by_part"],
        "bottleneck": bottleneck,
    }


# --------------------------------------------------------------------- Power BI
def powerbi_datasets(db: Session) -> dict:
    """Flat tables ready to be imported by Power BI (or exported to CSV).

    Kept intentionally denormalised: one row per fact, every dimension resolved,
    so the BI model needs no join to be useful.
    """
    lots = db.execute(
        select(Lot, Part, Supplier, WarehouseLocation)
        .join(Part, Part.id == Lot.part_id)
        .join(Supplier, Supplier.id == Lot.supplier_id)
        .outerjoin(WarehouseLocation, WarehouseLocation.id == Lot.location_id)
    ).all()

    fact_lots = [
        {
            "lot_number": lot.lot_number,
            "part_reference": part.reference,
            "part_designation": part.designation,
            "supplier": supplier.name,
            "supplier_code": supplier.code,
            "status": lot.status.value,
            "quantity_expected": lot.quantity_expected,
            "quantity_received": lot.quantity_received,
            "quantity_approved": lot.quantity_approved,
            "quantity_available": lot.quantity_available,
            "location": location.code if location else None,
            "received_at": lot.received_at.isoformat() if lot.received_at else None,
            "stored_at": lot.stored_at.isoformat() if lot.stored_at else None,
        }
        for lot, part, supplier, location in lots
    ]

    movements = db.execute(
        select(StockMovement, Part)
        .join(Part, Part.id == StockMovement.part_id)
        .order_by(StockMovement.occurred_at)
    ).all()

    fact_movements = [
        {
            "movement_reference": movement.reference,
            "movement_type": movement.movement_type.value,
            "part_reference": part.reference,
            "quantity": movement.quantity,
            "quantity_before": movement.quantity_before,
            "quantity_after": movement.quantity_after,
            "actor": movement.actor_name,
            "occurred_at": movement.occurred_at.isoformat(),
            "reason": movement.reason,
        }
        for movement, part in movements
    ]

    inspections = db.execute(
        select(Inspection, Lot, Part, Supplier)
        .join(Lot, Lot.id == Inspection.lot_id)
        .join(Part, Part.id == Lot.part_id)
        .join(Supplier, Supplier.id == Lot.supplier_id)
    ).all()

    fact_quality = [
        {
            "inspection_reference": inspection.reference,
            "lot_number": lot.lot_number,
            "part_reference": part.reference,
            "supplier": supplier.name,
            "sample_size": inspection.sample_size,
            "defects_found": inspection.defects_found,
            "defect_rate_percent": inspection.defect_rate_percent,
            "result": inspection.result.value,
            "inspected_at": inspection.inspected_at.isoformat(),
        }
        for inspection, lot, part, supplier in inspections
    ]

    requests = db.execute(
        select(ProductionRequest, Part, ProductionStation)
        .join(Part, Part.id == ProductionRequest.part_id)
        .join(ProductionStation, ProductionStation.id == ProductionRequest.station_id)
    ).all()

    fact_requests = [
        {
            "request_reference": request.reference,
            "station": station.code,
            "production_line": station.production_line,
            "part_reference": part.reference,
            "quantity_requested": request.quantity_requested,
            "quantity_issued": request.quantity_issued,
            # What the line is still waiting for. The `Open Demand` measure sums
            # this over the open statuses, so it has to travel with the fact.
            "quantity_outstanding": max(
                request.quantity_requested - request.quantity_issued, 0
            ),
            "status": request.status.value,
            "priority": request.priority,
            "created_on": request.created_on.isoformat(),
            "issued_at": request.issued_at.isoformat() if request.issued_at else None,
        }
        for request, part, station in requests
    ]

    stock_rows = db.execute(
        select(Stock, Part, Category)
        .join(Part, Part.id == Stock.part_id)
        .outerjoin(Category, Category.id == Part.category_id)
    ).all()

    dim_stock = [
        {
            "part_reference": part.reference,
            "designation": part.designation,
            "category": category.name if category else "Uncategorised",
            "quantity_available": stock.quantity_available,
            "quantity_reserved": stock.quantity_reserved,
            "safety_stock": part.safety_stock,
            "average_daily_consumption": part.average_daily_consumption,
        }
        for stock, part, category in stock_rows
    ]

    # A date table, so Power BI can do time intelligence over the ledger. Built
    # from the real span of the movements rather than an arbitrary range.
    bounds = db.execute(
        select(func.min(StockMovement.occurred_at), func.max(StockMovement.occurred_at))
    ).one()
    dim_date: list[dict] = []
    if bounds[0] and bounds[1]:
        first, last = bounds[0].date(), bounds[1].date()
        for offset in range((last - first).days + 1):
            day = first + timedelta(days=offset)
            dim_date.append(
                {
                    "date": day.isoformat(),
                    "year": day.year,
                    "month": day.month,
                    "month_name": day.strftime("%B"),
                    "week": day.isocalendar().week,
                    "day_of_month": day.day,
                    "weekday": day.isoweekday(),
                    "is_weekend": day.isoweekday() >= 6,
                }
            )

    locations = db.execute(select(WarehouseLocation)).scalars().all()
    dim_locations = [
        {
            "location_code": location.code,
            "zone": location.zone,
            "capacity": location.capacity,
            "occupied": location.occupied,
            "occupancy_percent": location.occupancy_percent,
        }
        for location in locations
    ]

    #: The schema each dataset promises, empty day or not.
    SCHEMA = {
        "fact_lots": (
            "lot_number", "part_reference", "part_designation", "supplier",
            "supplier_code", "status", "quantity_expected", "quantity_received",
            "quantity_approved", "quantity_available", "location", "received_at",
            "stored_at",
        ),
        "fact_stock_movements": (
            "movement_reference", "movement_type", "part_reference", "quantity",
            "quantity_before", "quantity_after", "actor", "occurred_at", "reason",
        ),
        "fact_quality": (
            "inspection_reference", "lot_number", "part_reference", "supplier",
            "sample_size", "defects_found", "defect_rate_percent", "result",
            "inspected_at",
        ),
        "fact_production_requests": (
            "request_reference", "station", "production_line", "part_reference",
            "quantity_requested", "quantity_issued", "quantity_outstanding", "status",
            "priority", "created_on", "issued_at",
        ),
        "dim_stock": (
            "part_reference", "designation", "category", "quantity_available",
            "quantity_reserved", "safety_stock", "average_daily_consumption",
        ),
        "dim_locations": (
            "location_code", "zone", "capacity", "occupied", "occupancy_percent",
        ),
        "dim_date": (
            "date", "year", "month", "month_name", "week", "day_of_month", "weekday",
            "is_weekend",
        ),
    }

    def dataset(
        name: str, description: str, rows: list[dict], columns: tuple[str, ...]
    ) -> dict:
        """One flat table plus its declared schema.

        The columns are declared rather than sniffed from the first row: on a
        quiet day a dataset is empty, and a report bound to a schema that
        vanished breaks in someone else's tool with no clue why. Declaring them
        also makes a dropped column a test failure here instead of a support
        call there.
        """
        if rows:
            missing = set(columns) - set(rows[0])
            extra = set(rows[0]) - set(columns)
            assert not missing and not extra, f"{name}: {missing or ''} {extra or ''}"
        return {
            "name": name,
            "description": description,
            "columns": list(columns),
            "rows": rows,
        }

    return {
        "generated_at": datetime.now(timezone.utc),
        "datasets": [
            dataset("fact_lots", "One row per lot with its flow status", fact_lots, SCHEMA["fact_lots"]),
            dataset(
                "fact_stock_movements",
                "Stock ledger, one row per movement",
                fact_movements,
                SCHEMA["fact_stock_movements"],
            ),
            dataset("fact_quality", "Inspection results per lot", fact_quality, SCHEMA["fact_quality"]),
            dataset(
                "fact_production_requests",
                "Production demand and issues",
                fact_requests,
                SCHEMA["fact_production_requests"],
            ),
            dataset("dim_stock", "Current stock per part reference", dim_stock, SCHEMA["dim_stock"]),
            dataset("dim_locations", "Warehouse locations and occupancy", dim_locations, SCHEMA["dim_locations"]),
            dataset("dim_date", "Calendar covering the movement history", dim_date, SCHEMA["dim_date"]),
        ],
        "measures": [
            {
                "name": "Total Stock",
                "expression": "SUM(dim_stock[quantity_available])",
                "description": "Quantite disponible, toutes references confondues.",
            },
            {
                "name": "Stock Coverage",
                "expression": (
                    "DIVIDE([Total Stock], SUM(dim_stock[average_daily_consumption]))"
                ),
                "description": (
                    "Jours de couverture: stock disponible divise par la consommation "
                    "moyenne journaliere. C'est le KPI 'Couverture stock' de SLCC."
                ),
            },
            {
                "name": "Conformity Rate",
                "expression": (
                    "DIVIDE(CALCULATE(COUNTROWS(fact_quality), "
                    "fact_quality[result] = \"CONFORM\"), COUNTROWS(fact_quality))"
                ),
                "description": "Part des inspections declarees conformes.",
            },
            {
                "name": "Non-Conformity Rate",
                "expression": "1 - [Conformity Rate]",
                "description": "Complement de la conformite, pour les visuels en pourcentage.",
            },
            {
                "name": "Blocked Lots",
                "expression": (
                    "CALCULATE(COUNTROWS(fact_lots), fact_lots[status] = \"RED_CAGE\")"
                ),
                "description": "Lots immobilises en Red Cage, en attente d'une decision qualite.",
            },
            {
                "name": "Warehouse Occupancy",
                "expression": (
                    "DIVIDE(SUM(dim_locations[occupied]), SUM(dim_locations[capacity]))"
                ),
                "description": "Taux de remplissage global de l'entrepot.",
            },
            {
                "name": "Issued Quantity",
                "expression": "SUM(fact_production_requests[quantity_issued])",
                "description": "Quantite reellement livree a la production.",
            },
            {
                "name": "Service Rate",
                "expression": (
                    "VAR Servable = FILTER(fact_production_requests, "
                    "NOT fact_production_requests[status] IN "
                    "{\"CANCELLED\", \"REJECTED\"}) "
                    "RETURN DIVIDE("
                    "SUMX(Servable, fact_production_requests[quantity_issued]), "
                    "SUMX(Servable, fact_production_requests[quantity_requested]))"
                ),
                "description": (
                    "Quantite servie sur quantite demandee. Les demandes annulees ou "
                    "rejetees sont exclues du denominateur: elles n'avaient pas vocation "
                    "a etre servies, et les compter ferait plonger le taux sur une "
                    "decision volontaire. Meme regle que l'API."
                ),
            },
            {
                "name": "Open Demand",
                "expression": (
                    "CALCULATE(SUM(fact_production_requests[quantity_outstanding]), "
                    "fact_production_requests[status] IN "
                    "{\"SUBMITTED\", \"APPROVED\", \"PREPARING\", \"READY\"})"
                ),
                "description": (
                    "Besoin production confirme mais pas encore sorti. C'est la valeur "
                    "comparee au stock dans le visuel 'Stock vs besoin'."
                ),
            },
            {
                "name": "References At Risk",
                "expression": (
                    "COUNTROWS(FILTER(VALUES(dim_stock[part_reference]), "
                    "CALCULATE(SUM(dim_stock[quantity_available])) < [Open Demand]))"
                ),
                "description": (
                    "Nombre de references dont le stock ne couvre pas le besoin ouvert: "
                    "le KPI 'Risque production'."
                ),
            },
        ],
    }


# ------------------------------------------------------------- Power BI theme
#: The SLCC palette as a Power BI theme file.
#:
#: A report that reads the same figures but wears different colours is a second
#: product, not the same one. Exporting the theme is what keeps the two in step:
#: the hexes below are the light-mode tokens of `index.css`, in the same order,
#: so slot 1 is the same blue in both places.
#:
#: They drifted once: the site palette was reworked twice and this file was not,
#: so a report built from the export wore the old muted colours while the screen
#: beside it wore the new ones. When these change again, change them here in the
#: same commit - a theme that lags is worse than no theme, because it looks
#: deliberate.
POWERBI_THEME = {
    "name": "SLCC",
    "dataColors": [
        "#1D6FD0",  # Blue - information and flow, series 1
        "#17B26A",  # Green - sound, series 2
        "#E8930C",  # Amber - watch this, series 3
        "#7C3AED",  # Violet - series 4
        "#16549E",  # Deep blue - comparison
        "#7DB0F0",  # Pale blue - secondary information
    ],
    "background": "#F6F8FB",
    "foreground": "#0F172A",
    "tableAccent": "#1D6FD0",
    # The three state colours, exactly as the screens use them.
    "good": "#17B26A",
    "neutral": "#E8930C",
    "bad": "#B42318",
    # The sequential ramp, deep to pale: magnitude only, never identity.
    "maximum": "#12427C",
    "center": "#1D6FD0",
    "minimum": "#CDE2FA",
    "textClasses": {
        "title": {"color": "#0F172A", "fontSize": 14, "fontFace": "Segoe UI Semibold"},
        "header": {"color": "#0F172A", "fontSize": 11, "fontFace": "Segoe UI Semibold"},
        "label": {"color": "#5B6B7F", "fontSize": 10, "fontFace": "Segoe UI"},
        "callout": {"color": "#1D6FD0", "fontSize": 28, "fontFace": "Segoe UI Light"},
    },
    "visualStyles": {
        "*": {
            "*": {
                # Little chrome: no border, no shadow, one soft card surface.
                "background": [{"show": True, "color": {"solid": {"color": "#FFFFFF"}}}],
                "border": [{"show": False}],
                "dropShadow": [{"show": False}],
                "title": [
                    {
                        "show": True,
                        "fontColor": {"solid": {"color": "#172A35"}},
                        "fontSize": 12,
                        "alignment": "left",
                    }
                ],
                "labels": [{"color": {"solid": {"color": "#40606E"}}, "fontSize": 9}],
                # Recessive gridlines: the marks carry the reading, not the grid.
                "categoryAxis": [
                    {
                        "gridlineShow": False,
                        "labelColor": {"solid": {"color": "#5F7280"}},
                        "fontSize": 9,
                    }
                ],
                "valueAxis": [
                    {
                        "gridlineColor": {"solid": {"color": "#E3DED2"}},
                        "gridlineStyle": "dotted",
                        "labelColor": {"solid": {"color": "#5F7280"}},
                        "fontSize": 9,
                    }
                ],
                "legend": [{"show": True, "position": "TopLeft", "fontSize": 9}],
            }
        },
        "card": {
            "*": {
                "labels": [{"color": {"solid": {"color": "#173F4F"}}, "fontSize": 28}],
                "categoryLabels": [{"color": {"solid": {"color": "#5F7280"}}, "fontSize": 9}],
            }
        },
    },
}


def powerbi_theme() -> dict:
    """The report theme, so Power BI and the application look like one product."""
    return POWERBI_THEME
