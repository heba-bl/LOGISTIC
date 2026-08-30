"""Data-access layer: repositories isolate SQLAlchemy queries from services."""

from app.repositories.base import BaseRepository
from app.repositories.repositories import (
    AuditRepository,
    CategoryRepository,
    InspectionRepository,
    LotRepository,
    PartRepository,
    ProductionRepository,
    QualityRepository,
    ReceptionRepository,
    RecommendationRepository,
    StockRepository,
    SupplierRepository,
    UserRepository,
    WarehouseRepository,
)

__all__ = [
    "BaseRepository",
    "AuditRepository",
    "CategoryRepository",
    "InspectionRepository",
    "LotRepository",
    "PartRepository",
    "ProductionRepository",
    "QualityRepository",
    "ReceptionRepository",
    "RecommendationRepository",
    "StockRepository",
    "SupplierRepository",
    "UserRepository",
    "WarehouseRepository",
]
