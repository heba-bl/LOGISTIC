/** Payload of `GET /api/analytics/overview`. */

export type Severity4 = 'OK' | 'WARNING' | 'CRITICAL' | 'INFO'
export type PeriodKey = 'today' | '7d' | '30d' | 'custom'

export interface OverviewPeriod {
  key: PeriodKey
  start_date: string
  end_date: string
  days: number
}

export interface TrendPoint {
  date: string
  value: number | null
}

export interface OverviewKpi {
  id: string
  value: number | null
  unit: string | null
  decimals: number
  delta_percent: number | null
  severity: Severity4
  trend: TrendPoint[]
  context_key: string | null
  context_value: number | null
}

export interface StockPoint {
  date: string
  stock: number
  received: number
  consumed: number
}

export interface WaterfallStep {
  key: string
  value: number
  kind: 'START' | 'IN' | 'OUT' | 'END'
}

export interface StockTotals {
  available: number
  reserved: number
  free: number
  references: number
}

export interface CategoryShare {
  label: string
  value: number
  references: number
  share_percent: number
}

export interface StockDemandRow {
  part_id: number
  reference: string
  designation: string
  category: string | null
  available: number
  reserved: number
  demand: number
  safety_stock: number | null
  coverage_days: number | null
  gap: number
  daily_consumption: number | null
  risk: Severity4
  action_key: string
}

export interface ScatterPoint {
  part_id: number
  reference: string
  daily_consumption: number
  available: number
  demand: number
  coverage_days: number | null
  risk: Severity4
}

export interface DefectRow {
  reference: string
  designation: string
  defects: number
  inspected: number
  inspections: number
  rate_percent: number
}

export interface QualityBlock {
  conform: number
  non_conform: number
  red_cage: number
  conformity_percent: number | null
  inspections: number
  trend: { date: string; value: number; sample: number }[]
  top_defects: DefectRow[]
}

export interface ZoneRow {
  zone: string
  capacity: number
  occupied: number
  free: number
  locations: number
  references: number
  saturated_locations: number
  occupancy_percent: number
  severity: Severity4
}

export interface HeatCell {
  zone: string
  position: number
  code: string
  capacity: number
  occupied: number
  occupancy_percent: number
  references: number
  severity: Severity4
}

export interface WarehouseBlock {
  zones: ZoneRow[]
  heatmap: HeatCell[]
  total_capacity: number
  total_occupied: number
  occupancy_percent: number
  warning_threshold: number
  critical_threshold: number
}

export interface HistogramBucket {
  from_hours: number
  to_hours: number | null
  count: number
}

export interface LeadTimeDistribution {
  buckets: HistogramBucket[]
  sample_size: number
  median_hours: number | null
}

export interface MatrixRow {
  reference: string
  designation: string
  total: number
  risk: Severity4
  cells: { zone: string; quantity: number }[]
}

export interface PartZoneMatrix {
  zones: string[]
  rows: MatrixRow[]
}

export interface ZoneDwellPoint {
  zone: string
  occupancy_percent: number
  average_days: number
  lots: number
  quantity: number
  severity: Severity4
}

export interface FlowStageRow {
  id: string
  lot_count: number
  quantity: number
  severity: Severity4
  anomalies: number
}

export interface FlowTransition {
  key: string
  stage: string
  average_hours: number
  sample_size: number
  is_bottleneck: boolean
}

export interface FlowBlock {
  stages: FlowStageRow[]
  transitions: FlowTransition[]
  bottleneck: string | null
  bottleneck_hours: number | null
}

export interface UncoveredRequest {
  reference: string
  part_reference: string
  station: string
  requested: number
  available: number
  shortfall: number
  priority: number
}

export interface ProductionBlock {
  requested: number
  issued: number
  service_rate_percent: number | null
  by_status: { status: string; count: number }[]
  open_count: number
  uncovered: UncoveredRequest[]
  consumption: { reference: string; value: number }[]
}

export interface DecisionMetric {
  key: string
  value: number | string | null
  unit: string | null
}

export interface Decision {
  rank: number
  kind: string
  severity: Severity4
  subject: string
  subject_id: number | null
  target: string
  metrics: DecisionMetric[]
  reason: string | null
  reason_key: string | null
  reason_values: Record<string, number | string>
  action_key: string
}

export interface Overview {
  generated_at: string
  period: OverviewPeriod
  kpis: OverviewKpi[]
  stock_trend: StockPoint[]
  stock_waterfall: WaterfallStep[]
  stock_totals: StockTotals
  stock_by_category: CategoryShare[]
  stock_vs_demand: StockDemandRow[]
  risk_scatter: ScatterPoint[]
  quality: QualityBlock
  warehouse: WarehouseBlock
  lead_time_distribution: LeadTimeDistribution
  part_zone_matrix: PartZoneMatrix
  zone_dwell: ZoneDwellPoint[]
  flow: FlowBlock
  production: ProductionBlock
  decisions: Decision[]
}
