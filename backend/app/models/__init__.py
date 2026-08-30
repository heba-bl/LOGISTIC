"""SQLAlchemy ORM models.

Every model module is imported here so that ``Base.metadata`` is complete when
Alembic runs autogenerate and when the test suite creates the schema.
"""

from app.db.base import Base
from app.models.catalog import Category, Part, Supplier
from app.models.enums import (
    AuditAction,
    ImportRowStatus,
    ImportStatus,
    ImportType,
    InspectionResult,
    LocationRole,
    LotStatus,
    MovementType,
    PartSize,
    ProductionRequestStatus,
    QualityDecision,
    ReceptionStatus,
    RecommendationKind,
    RiskLevel,
    RoleName,
    Severity,
    ValidationDecision,
    Zone,
)
from app.models.flow import Inspection, Lot, QualityValidation, Reception
from app.models.imports import DataImport, ImportRow
from app.models.organization import Role, User
from app.models.production import ProductionRequest, ProductionStation
from app.models.system import AIRecommendation, AuditLog, SystemSetting
from app.models.vehicle import Vehicle, VehicleBomLine
from app.models.warehouse import (
    PartLocation,
    Stock,
    StockMovement,
    Warehouse,
    WarehouseLocation,
)

__all__ = [
    "Base",
    # organization
    "Role",
    "User",
    # catalog
    "Category",
    "Part",
    "Supplier",
    # imports / maker-checker
    "DataImport",
    "ImportRow",
    # flow
    "Inspection",
    "Lot",
    "QualityValidation",
    "Reception",
    # warehouse
    "PartLocation",
    "Stock",
    "StockMovement",
    "Warehouse",
    "WarehouseLocation",
    # production
    "ProductionRequest",
    "ProductionStation",
    # system
    "AIRecommendation",
    "AuditLog",
    "SystemSetting",
    # vehicle nomenclature
    "Vehicle",
    "VehicleBomLine",
    # enums
    "AuditAction",
    "ImportRowStatus",
    "ImportStatus",
    "ImportType",
    "InspectionResult",
    "LocationRole",
    "LotStatus",
    "MovementType",
    "PartSize",
    "ProductionRequestStatus",
    "QualityDecision",
    "ReceptionStatus",
    "RecommendationKind",
    "RiskLevel",
    "RoleName",
    "Severity",
    "ValidationDecision",
    "Zone",
]
