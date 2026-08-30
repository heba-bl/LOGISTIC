"""Response models for the Logistics Overview screen."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.common import UtcDatetime


class PeriodOut(BaseModel):
    key: str
    start_date: date
    end_date: date
    days: int


class TrendPoint(BaseModel):
    date: str
    value: float | None = None


class KpiOut(BaseModel):
    id: str
    value: float | None
    unit: str | None = None
    decimals: int = 0
    delta_percent: float | None = None
    severity: str
    trend: list[TrendPoint] = []
    context_key: str | None = None
    context_value: float | None = None


class StockPoint(BaseModel):
    date: str
    stock: int
    received: int
    consumed: int


class WaterfallStep(BaseModel):
    key: str
    value: int
    kind: str


class StockTotals(BaseModel):
    available: int
    reserved: int
    free: int
    references: int


class CategoryShare(BaseModel):
    label: str
    value: int
    references: int
    share_percent: float


class StockDemandRow(BaseModel):
    part_id: int
    reference: str
    designation: str
    category: str | None = None
    available: int
    reserved: int
    demand: int
    safety_stock: int | None = None
    coverage_days: float | None = None
    gap: int
    daily_consumption: float | None = None
    risk: str
    action_key: str


class ScatterPoint(BaseModel):
    part_id: int
    reference: str
    daily_consumption: float
    available: int
    demand: int
    coverage_days: float | None = None
    risk: str


class DefectRow(BaseModel):
    reference: str
    designation: str
    defects: int
    inspected: int
    inspections: int
    rate_percent: float


class QualityTrendPoint(BaseModel):
    date: str
    value: float
    sample: int


class QualityBlock(BaseModel):
    conform: int
    non_conform: int
    red_cage: int
    conformity_percent: float | None = None
    inspections: int
    trend: list[QualityTrendPoint] = []
    top_defects: list[DefectRow] = []


class ZoneRow(BaseModel):
    zone: str
    capacity: int
    occupied: int
    free: int
    locations: int
    references: int
    saturated_locations: int
    occupancy_percent: float
    severity: str


class HeatCell(BaseModel):
    zone: str
    position: int
    code: str
    capacity: int
    occupied: int
    occupancy_percent: float
    references: int
    severity: str


class WarehouseBlock(BaseModel):
    zones: list[ZoneRow] = []
    heatmap: list[HeatCell] = []
    total_capacity: int
    total_occupied: int
    occupancy_percent: float
    warning_threshold: float
    critical_threshold: float


class HistogramBucket(BaseModel):
    from_hours: float
    to_hours: float | None = None
    count: int


class LeadTimeDistribution(BaseModel):
    buckets: list[HistogramBucket] = []
    sample_size: int
    median_hours: float | None = None


class MatrixCell(BaseModel):
    zone: str
    quantity: int


class MatrixRow(BaseModel):
    reference: str
    designation: str
    total: int
    risk: str
    cells: list[MatrixCell] = []


class PartZoneMatrix(BaseModel):
    zones: list[str] = []
    rows: list[MatrixRow] = []


class ZoneDwellPoint(BaseModel):
    zone: str
    occupancy_percent: float
    average_days: float
    lots: int
    quantity: int
    severity: str


class FlowStage(BaseModel):
    id: str
    lot_count: int
    quantity: int
    severity: str
    anomalies: int


class FlowTransition(BaseModel):
    key: str
    stage: str
    average_hours: float
    sample_size: int
    is_bottleneck: bool


class FlowBlock(BaseModel):
    stages: list[FlowStage] = []
    transitions: list[FlowTransition] = []
    bottleneck: str | None = None
    bottleneck_hours: float | None = None


class StatusCount(BaseModel):
    status: str
    count: int


class UncoveredRequest(BaseModel):
    reference: str
    part_reference: str
    station: str
    requested: int
    available: int
    shortfall: int
    priority: int


class ConsumptionRow(BaseModel):
    reference: str
    value: int


class ProductionBlock(BaseModel):
    requested: int
    issued: int
    service_rate_percent: float | None = None
    by_status: list[StatusCount] = []
    open_count: int
    uncovered: list[UncoveredRequest] = []
    consumption: list[ConsumptionRow] = []


class DecisionMetric(BaseModel):
    key: str
    value: float | str | None = None
    unit: str | None = None


class DecisionOut(BaseModel):
    rank: int = 0
    kind: str
    severity: str
    subject: str
    subject_id: int | None = None
    target: str
    metrics: list[DecisionMetric] = []
    #: Either a sentence built by the backend, or a key the UI translates.
    reason: str | None = None
    reason_key: str | None = None
    reason_values: dict[str, float | str] = {}
    action_key: str


class OverviewOut(BaseModel):
    generated_at: UtcDatetime
    period: PeriodOut
    kpis: list[KpiOut] = []
    stock_trend: list[StockPoint] = []
    stock_waterfall: list[WaterfallStep] = []
    stock_totals: StockTotals
    stock_by_category: list[CategoryShare] = []
    stock_vs_demand: list[StockDemandRow] = []
    risk_scatter: list[ScatterPoint] = []
    quality: QualityBlock
    warehouse: WarehouseBlock
    lead_time_distribution: LeadTimeDistribution
    part_zone_matrix: PartZoneMatrix
    zone_dwell: list[ZoneDwellPoint] = []
    flow: FlowBlock
    production: ProductionBlock
    decisions: list[DecisionOut] = []
