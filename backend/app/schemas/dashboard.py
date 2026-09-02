"""Mission Control, traceability, analytics and AI schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.enums import RecommendationKind, RiskLevel, Severity
from app.schemas.common import UtcDatetime, ORMModel
from app.schemas.flow import LotOut


# ------------------------------------------------------------------ mission control
class KpiOut(BaseModel):
    id: str
    label: str
    value: float
    unit: str | None = None
    #: English wording, kept so a client that does not know the key still shows
    #: a sentence rather than an empty line.
    hint: str
    #: The same sentence as a translation key and its values, so the interface
    #: can word it in the language the user is actually reading.
    hint_key: str | None = None
    hint_values: dict[str, str | int | float] = {}
    severity: str
    ratio: float | None = None


class FlowStageOut(BaseModel):
    id: str
    label: str
    caption: str
    lot_count: int
    quantity: int
    severity: str
    lots: list[LotOut] = Field(default_factory=list)


class AlertOut(BaseModel):
    id: str
    kind: str | None = None
    severity: str
    title: str
    message: str
    #: Set when the reason was composed by the services; the UI words it.
    message_key: str | None = None
    message_values: dict = Field(default_factory=dict)
    source: str
    timestamp: UtcDatetime
    lot_number: str | None = None
    part_reference: str | None = None
    location_code: str | None = None
    #: Present only once somebody has taken the alert on.
    acknowledged_by: str | None = None
    acknowledged_by_name: str | None = None
    acknowledged_at: UtcDatetime | None = None
    acknowledged_reason: str | None = None



class ActivityOut(BaseModel):
    id: int
    time: str
    action: str
    label: str
    detail: str
    severity: str
    actor_name: str
    occurred_at: UtcDatetime
    lot_number: str | None = None


class DashboardOut(BaseModel):
    """Everything Mission Control needs, in one round trip."""

    generated_at: UtcDatetime
    system_status: str
    kpis: list[KpiOut]
    stages: list[FlowStageOut]
    lots_in_flow: list[LotOut]
    alerts: list[AlertOut]
    #: total / owned / snoozed / unowned - the last is the one to read.
    alert_standing: dict[str, int] = {}
    activity: list[ActivityOut]


# -------------------------------------------------------------------- traceability
class TraceEventOut(BaseModel):
    id: int
    action: str
    label: str
    detail: str
    actor_name: str
    occurred_at: UtcDatetime
    quantity: int | None = None
    location_code: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    severity: str

    # --- Identification and Maker-Checker ---------------------------------
    actor_reference: str | None = None
    actor_role: str | None = None
    maker_reference: str | None = None
    maker_role: str | None = None
    checker_reference: str | None = None
    checker_role: str | None = None
    decision: str | None = None
    source_file: str | None = None
    source_hash: str | None = None


class LotTraceOut(BaseModel):
    """Complete life of a lot: who, what, when, how much, where, why."""

    lot: LotOut
    reception_reference: str | None = None
    inspection_count: int
    quality_decisions: int
    total_in: int
    total_out: int
    events: list[TraceEventOut]


class AuditEntryOut(ORMModel):
    id: int
    action: str
    entity_type: str
    entity_reference: str | None = None
    quantity: int | None = None
    location_code: str | None = None
    status_before: str | None = None
    status_after: str | None = None
    reason: str | None = None
    actor_name: str
    actor_reference: str | None = None
    actor_role: str | None = None
    maker_reference: str | None = None
    maker_role: str | None = None
    checker_reference: str | None = None
    checker_role: str | None = None
    decision: str | None = None
    source_file: str | None = None
    occurred_at: UtcDatetime


# ------------------------------------------------------------------------ analytics
class SeriesPoint(BaseModel):
    label: str
    value: float


class NamedSeries(BaseModel):
    name: str
    points: list[SeriesPoint]


class StageDurationOut(BaseModel):
    stage: str
    average_hours: float
    sample_size: int
    is_bottleneck: bool


class AnalyticsOut(BaseModel):
    """Analytical model backing the Analytics screen and the Power BI datasets."""

    generated_at: UtcDatetime
    stock_by_category: list[SeriesPoint]
    stock_by_part: list[SeriesPoint]
    stock_by_location: list[SeriesPoint]
    stock_evolution: list[SeriesPoint]
    flow_counts: list[SeriesPoint]
    stage_durations: list[StageDurationOut]
    quality_conformity_percent: float
    quality_non_conformity_percent: float
    red_cage_count: int
    defects_by_part: list[SeriesPoint]
    defects_by_supplier: list[SeriesPoint]
    requests_by_station: list[SeriesPoint]
    quantity_requested: int
    quantity_issued: int
    pending_requests: int
    consumption_by_part: list[SeriesPoint]
    bottleneck: str | None = None


class PowerBiDataset(BaseModel):
    """One flat, Power BI friendly table."""

    name: str
    description: str
    columns: list[str]
    rows: list[dict]


class PowerBiCatalog(BaseModel):
    generated_at: UtcDatetime
    datasets: list[PowerBiDataset]
    measures: list[dict]


# ------------------------------------------------------------------------------ AI
class RecommendationOut(ORMModel):
    id: int
    kind: RecommendationKind
    severity: Severity
    risk_level: RiskLevel | None = None
    priority: int
    #: Names the detected situation so the interface can word it in the reader's
    #: language. The three sentences below stay as the fallback.
    text_key: str | None = None
    title: str
    message: str
    rationale: str
    recommended_action: str | None = None
    location_code: str | None = None
    generated_at: UtcDatetime
    part_reference: str | None = None
    lot_number: str | None = None
    metrics: dict = Field(default_factory=dict)


class ShortageRiskOut(BaseModel):
    part_id: int
    part_reference: str
    #: Names the branch the rating rests on; the interface words it.
    text_key: str | None = None
    designation: str
    stock_available: int
    open_demand: int
    safety_stock: int
    incoming_quantity: int
    projected_balance: int
    days_of_cover: float | None = None
    risk_level: RiskLevel
    rationale: str


class AiAnalysisOut(BaseModel):
    generated_at: UtcDatetime
    headline: str
    #: The headline as a key plus its figures, so the screen can word it.
    headline_key: str | None = None
    headline_values: dict = Field(default_factory=dict)
    shortage_risks: list[ShortageRiskOut]
    recommendations: list[RecommendationOut]
    priority_count: dict[str, int]


class CopilotQuery(BaseModel):
    question: str = Field(min_length=2, max_length=500)


class CopilotSource(BaseModel):
    label: str
    value: str


class CopilotAnswer(BaseModel):
    """A grounded answer: every figure comes from the database, with its source."""

    question: str
    intent: str
    answer: str
    confidence: str
    sources: list[CopilotSource]
    suggestions: list[str]
    generated_at: UtcDatetime


# ----------------------------------------------------------------------- simulation
class SimulationStepOut(BaseModel):
    order: int
    key: str
    title: str
    detail: str
    entity_reference: str | None = None
    stock_before: int | None = None
    stock_after: int | None = None
    occurred_at: UtcDatetime


class SimulationRunOut(BaseModel):
    scenario: str
    lot_number: str
    part_reference: str
    steps: list[SimulationStepOut]
    stock_before: int
    stock_after: int
    message: str


class SimulationRequest(BaseModel):
    part_id: int | None = None
    supplier_id: int | None = None
    station_id: int | None = None
    quantity: int = Field(default=120, gt=0)
    production_quantity: int = Field(default=20, gt=0)
    #: Stop after this step to drive the demo manually (None = run everything).
    stop_after: str | None = None
