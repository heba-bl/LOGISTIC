"""Workflow state machines and controlled vocabularies.

Every enum is persisted as a VARCHAR with a CHECK constraint (``native_enum=False``)
so the schema is identical on PostgreSQL and on the SQLite development fallback.
"""

from __future__ import annotations

from enum import Enum


class Zone(str, Enum):
    """Physical work zones of the plant.

    Operators belong to a zone; the responsible of that zone is the one who may
    validate what its operators entered.
    """

    RECEPTION = "RECEPTION"
    INSPECTION = "INSPECTION"
    QUALITY = "QUALITY"
    WAREHOUSE = "WAREHOUSE"
    PRODUCTION = "PRODUCTION"
    LOGISTICS = "LOGISTICS"


#: Which zone each role works in.
ROLE_ZONE: dict[str, str] = {
    "RECEPTIONIST": Zone.RECEPTION.value,
    "RECEPTION_MANAGER": Zone.RECEPTION.value,
    "QUALITY_INSPECTOR": Zone.INSPECTION.value,
    "QUALITY_MANAGER": Zone.QUALITY.value,
    "WAREHOUSE_OPERATOR": Zone.WAREHOUSE.value,
    "STATION_LEADER": Zone.PRODUCTION.value,
    "PRODUCTION_MANAGER": Zone.PRODUCTION.value,
    "LOGISTICS_MANAGER": Zone.LOGISTICS.value,
}


class RoleName(str, Enum):
    """Simulated roles (PROJECT_SLCC section 12)."""

    RECEPTIONIST = "RECEPTIONIST"
    RECEPTION_MANAGER = "RECEPTION_MANAGER"
    QUALITY_INSPECTOR = "QUALITY_INSPECTOR"
    QUALITY_MANAGER = "QUALITY_MANAGER"
    WAREHOUSE_OPERATOR = "WAREHOUSE_OPERATOR"
    STATION_LEADER = "STATION_LEADER"
    PRODUCTION_MANAGER = "PRODUCTION_MANAGER"
    LOGISTICS_MANAGER = "LOGISTICS_MANAGER"


class PartSize(str, Enum):
    """Drives the reception tolerance rule.

    SMALL parts may be received within a configurable percentage tolerance;
    LARGE parts must match the expected quantity exactly.
    """

    SMALL = "SMALL"
    LARGE = "LARGE"


class LotStatus(str, Enum):
    """Lifecycle of a lot.

    The first six values are the states mandated by the specification. STORED and
    CONSUMED extend them so that "quality approved" can be distinguished from
    "physically stored" — the distinction the stock rule depends on.
    """

    PENDING_INSPECTION = "PENDING_INSPECTION"
    INSPECTION_IN_PROGRESS = "INSPECTION_IN_PROGRESS"
    QUALITY_PENDING = "QUALITY_PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RED_CAGE = "RED_CAGE"
    STORED = "STORED"
    CONSUMED = "CONSUMED"


#: Lot states that are allowed to be turned into available stock.
STORABLE_LOT_STATUSES = frozenset({LotStatus.APPROVED})

#: Lot states that block the lot from progressing without a human decision.
BLOCKED_LOT_STATUSES = frozenset({LotStatus.RED_CAGE, LotStatus.REJECTED})


class ReceptionStatus(str, Enum):
    """Outcome of the quantity check performed at reception."""

    ACCEPTED = "ACCEPTED"
    ACCEPTED_WITH_TOLERANCE = "ACCEPTED_WITH_TOLERANCE"
    QUANTITY_MISMATCH = "QUANTITY_MISMATCH"


class InspectionResult(str, Enum):
    CONFORM = "CONFORM"
    NON_CONFORM = "NON_CONFORM"


class QualityDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    RED_CAGE = "RED_CAGE"


class ProductionRequestStatus(str, Enum):
    """Lifecycle of a production parts request."""

    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    PREPARING = "PREPARING"
    READY = "READY"
    ISSUED = "ISSUED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


#: Statuses from which a request can still be cancelled.
CANCELLABLE_REQUEST_STATUSES = frozenset(
    {
        ProductionRequestStatus.DRAFT,
        ProductionRequestStatus.SUBMITTED,
        ProductionRequestStatus.APPROVED,
        ProductionRequestStatus.PREPARING,
        ProductionRequestStatus.READY,
    }
)


class MovementType(str, Enum):
    """Direction of a stock movement. Every movement is auditable."""

    IN = "IN"
    OUT = "OUT"
    TRANSFER = "TRANSFER"
    ADJUSTMENT = "ADJUSTMENT"


class LocationRole(str, Enum):
    """A part has one primary address and may have secondary addresses."""

    PRIMARY = "PRIMARY"
    SECONDARY = "SECONDARY"


class Severity(str, Enum):
    """Functional severity shared by alerts and recommendations."""

    OK = "OK"
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class RecommendationKind(str, Enum):
    """Categories of AI output (PROJECT_SLCC sections 21-23)."""

    SHORTAGE_RISK = "SHORTAGE_RISK"
    PRIORITY = "PRIORITY"
    BLOCKED_LOT = "BLOCKED_LOT"
    WAREHOUSE_SATURATION = "WAREHOUSE_SATURATION"
    OPTIMIZATION = "OPTIMIZATION"


class ImportType(str, Enum):
    """Which business flow an uploaded file feeds."""

    RECEPTION = "RECEPTION"
    INSPECTION = "INSPECTION"
    PRODUCTION_REQUEST = "PRODUCTION_REQUEST"


class ImportStatus(str, Enum):
    """Maker-Checker lifecycle of an imported file.

    Imported data is never authoritative until a habilitated checker - a
    different person from the maker - has confirmed it. No stock operation is
    executed before APPROVED.
    """

    IMPORTED = "IMPORTED"
    PENDING_REVIEW = "PENDING_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ImportRowStatus(str, Enum):
    """State of one line of an imported file."""

    #: Parsed and structurally valid, waiting for the checker.
    PENDING = "PENDING"
    #: Rejected by the parser (unknown reference, bad quantity...).
    INVALID = "INVALID"
    #: Applied to the business tables after approval.
    APPLIED = "APPLIED"
    #: Not applied because the checker rejected the file.
    REJECTED = "REJECTED"
    #: Approved but the business rule refused it (kept for traceability).
    FAILED = "FAILED"


class ValidationDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class AuditAction(str, Enum):
    """Every business event worth tracing."""

    LOT_RECEIVED = "LOT_RECEIVED"
    INSPECTION_STARTED = "INSPECTION_STARTED"
    INSPECTION_RECORDED = "INSPECTION_RECORDED"
    QUALITY_APPROVED = "QUALITY_APPROVED"
    QUALITY_REJECTED = "QUALITY_REJECTED"
    QUALITY_RED_CAGE = "QUALITY_RED_CAGE"
    RED_CAGE_RELEASED = "RED_CAGE_RELEASED"
    RED_CAGE_SCRAPPED = "RED_CAGE_SCRAPPED"
    STORAGE_CONFIRMED = "STORAGE_CONFIRMED"
    STOCK_INCREMENTED = "STOCK_INCREMENTED"
    STOCK_DECREMENTED = "STOCK_DECREMENTED"
    REQUEST_CREATED = "REQUEST_CREATED"
    REQUEST_SUBMITTED = "REQUEST_SUBMITTED"
    REQUEST_APPROVED = "REQUEST_APPROVED"
    REQUEST_REJECTED = "REQUEST_REJECTED"
    REQUEST_PREPARING = "REQUEST_PREPARING"
    REQUEST_READY = "REQUEST_READY"
    REQUEST_ISSUED = "REQUEST_ISSUED"
    REQUEST_CANCELLED = "REQUEST_CANCELLED"
    IMPORT_CREATED = "IMPORT_CREATED"
    IMPORT_SUBMITTED = "IMPORT_SUBMITTED"
    IMPORT_APPROVED = "IMPORT_APPROVED"
    IMPORT_REJECTED = "IMPORT_REJECTED"
    IMPORT_ROW_APPLIED = "IMPORT_ROW_APPLIED"
    SETTING_UPDATED = "SETTING_UPDATED"
    SIMULATION_RUN = "SIMULATION_RUN"
