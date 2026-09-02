/**
 * Domain types mirroring the FastAPI schemas.
 *
 * These are the contract between backend and UI. Keeping them in one place means
 * a backend change surfaces as a TypeScript error rather than a runtime surprise.
 */

// --------------------------------------------------------------------- enums
export type LotStatus =
  | 'PENDING_INSPECTION'
  | 'INSPECTION_IN_PROGRESS'
  | 'QUALITY_PENDING'
  | 'APPROVED'
  | 'REJECTED'
  | 'RED_CAGE'
  | 'STORED'
  | 'CONSUMED'

export type ReceptionStatus = 'ACCEPTED' | 'ACCEPTED_WITH_TOLERANCE' | 'QUANTITY_MISMATCH'

export type InspectionResult = 'CONFORM' | 'NON_CONFORM'

export type QualityDecision = 'APPROVED' | 'REJECTED' | 'RED_CAGE'

export type ProductionRequestStatus =
  | 'DRAFT'
  | 'SUBMITTED'
  | 'APPROVED'
  | 'PREPARING'
  | 'READY'
  | 'ISSUED'
  | 'REJECTED'
  | 'CANCELLED'

export type MovementType = 'IN' | 'OUT' | 'TRANSFER' | 'ADJUSTMENT'

export type PartSize = 'SMALL' | 'LARGE'

export type LocationRole = 'PRIMARY' | 'SECONDARY'

export type ApiSeverity = 'OK' | 'INFO' | 'WARNING' | 'CRITICAL'

export type RiskLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export type RecommendationKind =
  | 'SHORTAGE_RISK'
  | 'PRIORITY'
  | 'BLOCKED_LOT'
  | 'WAREHOUSE_SATURATION'
  | 'OPTIMIZATION'

export type FlowStageId =
  | 'SUPPLIER'
  | 'RECEIVING'
  | 'INSPECTION'
  | 'QUALITY'
  | 'WAREHOUSE'
  | 'PRODUCTION'

// ------------------------------------------------------------------ catalogue
export interface Category {
  id: number
  code: string
  name: string
}

export interface Supplier {
  id: number
  code: string
  name: string
  country: string | null
  lead_time_days: number
  is_active: boolean
}

export interface StockSummary {
  quantity_available: number
  quantity_reserved: number
  quantity_free: number
}

export interface Part {
  id: number
  reference: string
  designation: string
  description: string | null
  unit: string
  size_class: PartSize
  reception_tolerance_percent: number | null
  safety_stock: number
  average_daily_consumption: number
  is_active: boolean
  category: Category | null
  stock: StockSummary | null
}

export interface Station {
  id: number
  code: string
  name: string
  production_line: string | null
  is_active: boolean
}

export interface Role {
  id: number
  name: string
  label: string
  description: string | null
  can_validate: boolean
}

export type Zone =
  | 'RECEPTION'
  | 'INSPECTION'
  | 'QUALITY'
  | 'WAREHOUSE'
  | 'PRODUCTION'
  | 'LOGISTICS'

export interface User {
  id: number
  employee_number: string
  username: string
  full_name: string
  first_name: string | null
  last_name: string | null
  service: string | null
  zone: Zone | null
  is_active: boolean
  role: Role | null
}

export interface Setting {
  id: number
  key: string
  value: string
  value_type: string
  label: string
  description: string | null
  group: string
}

// ------------------------------------------------------------------ core refs
export interface PartRef {
  id: number
  reference: string
  designation: string
  unit: string
}

export interface SupplierRef {
  id: number
  code: string
  name: string
}

export interface LocationRef {
  id: number
  code: string
  zone: string
}

export interface StationRef {
  id: number
  code: string
  name: string
}

export interface ActorRef {
  id: number
  full_name: string
  username: string
}

// ----------------------------------------------------------------------- flow
export interface Lot {
  id: number
  lot_number: string
  status: LotStatus
  quantity_expected: number
  quantity_received: number
  quantity_approved: number
  quantity_available: number
  blocked_reason: string | null
  /** Set when the services composed the reason; the UI words it. */
  blocked_reason_key: string | null
  blocked_reason_values: Record<string, string | number>
  received_at: string
  stored_at: string | null
  /** Last movement on the lot - what the block ageing is measured from. */
  updated_at?: string | null
  part: PartRef
  supplier: SupplierRef
  location: LocationRef | null
}

export interface Reception {
  id: number
  reference: string
  status: ReceptionStatus
  quantity_expected: number
  quantity_received: number
  quantity_gap: number
  tolerance_percent_applied: number
  delivery_note: string | null
  notes: string | null
  received_at: string
  lot: Lot
  received_by: ActorRef | null
}

export interface TolerancePreview {
  part_reference: string
  size_class: string
  tolerance_percent: number
  tolerance_source: string
  allowed_units: number
  quantity_expected: number
  minimum_accepted: number
  maximum_accepted: number
}

export interface Inspection {
  id: number
  reference: string
  lot_id: number
  sample_size: number
  defects_found: number
  defect_rate_percent: number
  defect_threshold_percent: number
  result: InspectionResult
  observations: string | null
  inspected_at: string
  inspector: ActorRef | null
  /** Enough of the lot to name the part and the supplier on a report row. */
  lot: {
    id: number
    lot_number: string
    part: { id: number; reference: string; designation: string; unit: string }
    supplier: { id: number; code: string; name: string }
  }
}

export interface SampleSuggestion {
  lot_number: string
  quantity_received: number
  suggested_sample_size: number
  sample_percent: number
  minimum_sample: number
  defect_threshold_percent: number
}

export interface QualityValidation {
  id: number
  lot_id: number
  decision: QualityDecision
  quantity_approved: number
  justification: string
  decided_at: string
  decided_by: ActorRef | null
}

// ------------------------------------------------------------------ warehouse
export interface WarehouseLocation {
  id: number
  code: string
  zone: string
  position: number
  capacity: number
  occupied: number
  occupancy_percent: number
  free_capacity: number
  is_active: boolean
}

export interface LocationDetail extends WarehouseLocation {
  severity: ApiSeverity
  lots: Lot[]
  references: string[]
}

export interface WarehouseGrid {
  warehouse_code: string
  warehouse_name: string
  zones: string[]
  locations: WarehouseLocation[]
  total_capacity: number
  total_occupied: number
  occupancy_percent: number
  warning_threshold: number
  critical_threshold: number
}

export interface AllocationSuggestion {
  location_id: number
  location_code: string
  role: LocationRole
  quantity: number
  free_capacity: number
  occupancy_percent: number
  rationale: string
}

export interface StoragePlan {
  lot_number: string
  part_reference: string
  quantity_to_store: number
  fully_allocatable: boolean
  suggestions: AllocationSuggestion[]
}

export interface StockRow {
  part_id: number
  reference: string
  designation: string
  category: string | null
  unit: string
  quantity_available: number
  quantity_reserved: number
  quantity_free: number
  safety_stock: number
  average_daily_consumption: number
  days_of_cover: number | null
  open_demand: number
  locations: string[]
  severity: ApiSeverity
}

export interface StockMovement {
  id: number
  reference: string
  movement_type: MovementType
  quantity: number
  quantity_before: number
  quantity_after: number
  actor_name: string
  reason: string | null
  occurred_at: string
  part: PartRef
  lot: Lot | null
}

// ----------------------------------------------------------------- production
export interface ProductionRequest {
  id: number
  reference: string
  status: ProductionRequestStatus
  quantity_requested: number
  quantity_issued: number
  priority: number
  needed_at: string | null
  notes: string | null
  rejection_reason: string | null
  created_on: string
  submitted_at: string | null
  approved_at: string | null
  ready_at: string | null
  issued_at: string | null
  part: PartRef
  station: StationRef
  requested_by: ActorRef | null
  approved_by: ActorRef | null
}

export interface ProductionRequestRow {
  request: ProductionRequest
  stock_available: number
  is_coverable: boolean
  shortfall: number
}

// ------------------------------------------------------------- mission control
export interface Kpi {
  id: string
  label: string
  value: number
  unit: string | null
  /** English wording, kept as the fallback when `hint_key` is unknown. */
  hint: string
  /** Translation key for the same sentence; preferred when present. */
  hint_key?: string
  hint_values?: Record<string, string | number>
  severity: ApiSeverity
  ratio: number | null
}

export interface FlowStage {
  id: FlowStageId
  label: string
  caption: string
  lot_count: number
  quantity: number
  severity: ApiSeverity
  lots: Lot[]
}

export interface Alert {
  id: string
  severity: ApiSeverity
  title: string
  message: string
  /** Set when the services composed the reason; the UI words it. */
  message_key: string | null
  message_values: Record<string, string | number>
  source: string
  timestamp: string
  lot_number: string | null
  part_reference: string | null
  location_code: string | null
  /** Present once somebody has taken the alert on. */
  acknowledged_by?: string | null
  acknowledged_by_name?: string | null
  acknowledged_at?: string | null
  acknowledged_reason?: string | null
}

export interface ActivityEvent {
  id: number
  time: string
  action: string
  label: string
  detail: string
  severity: ApiSeverity
  actor_name: string
  occurred_at: string
  lot_number: string | null
}

export interface Dashboard {
  generated_at: string
  system_status: 'OPERATIONAL' | 'DEGRADED'
  kpis: Kpi[]
  stages: FlowStage[]
  lots_in_flow: Lot[]
  alerts: Alert[]
  /** total / owned / snoozed / unowned. */
  alert_standing: Record<string, number>
  activity: ActivityEvent[]
}

// ---------------------------------------------------------------- traceability
export interface TraceEvent {
  id: number
  action: string
  label: string
  detail: string
  actor_name: string
  occurred_at: string
  quantity: number | null
  location_code: string | null
  status_before: string | null
  status_after: string | null
  severity: ApiSeverity
  actor_reference: string | null
  actor_role: string | null
  maker_reference: string | null
  maker_role: string | null
  checker_reference: string | null
  checker_role: string | null
  decision: string | null
  source_file: string | null
  source_hash: string | null
}

export interface LotTrace {
  lot: Lot
  reception_reference: string | null
  inspection_count: number
  quality_decisions: number
  total_in: number
  total_out: number
  events: TraceEvent[]
}

export interface AuditEntry {
  id: number
  action: string
  entity_type: string
  entity_reference: string | null
  quantity: number | null
  location_code: string | null
  status_before: string | null
  status_after: string | null
  reason: string | null
  actor_name: string
  actor_reference: string | null
  actor_role: string | null
  maker_reference: string | null
  maker_role: string | null
  checker_reference: string | null
  checker_role: string | null
  decision: string | null
  source_file: string | null
  occurred_at: string
}

// ------------------------------------------------------------------- analytics
export interface SeriesPoint {
  label: string
  value: number
}

export interface StageDuration {
  stage: string
  average_hours: number
  sample_size: number
  is_bottleneck: boolean
}

export interface Analytics {
  generated_at: string
  stock_by_category: SeriesPoint[]
  stock_by_part: SeriesPoint[]
  stock_by_location: SeriesPoint[]
  stock_evolution: SeriesPoint[]
  flow_counts: SeriesPoint[]
  stage_durations: StageDuration[]
  quality_conformity_percent: number
  quality_non_conformity_percent: number
  red_cage_count: number
  defects_by_part: SeriesPoint[]
  defects_by_supplier: SeriesPoint[]
  requests_by_station: SeriesPoint[]
  quantity_requested: number
  quantity_issued: number
  pending_requests: number
  consumption_by_part: SeriesPoint[]
  bottleneck: string | null
}

export interface PowerBiDataset {
  name: string
  description: string
  columns: string[]
  rows: Record<string, unknown>[]
}

export interface PowerBiCatalog {
  generated_at: string
  datasets: PowerBiDataset[]
  measures: { name: string; expression: string; description: string }[]
}

// -------------------------------------------------------------------------- AI
export interface Recommendation {
  id: number
  /** Names the situation the engine detected; the UI words it. */
  text_key: string | null
  kind: RecommendationKind
  severity: ApiSeverity
  risk_level: RiskLevel | null
  priority: number
  title: string
  message: string
  rationale: string
  recommended_action: string | null
  location_code: string | null
  generated_at: string
  part_reference: string | null
  lot_number: string | null
  metrics: Record<string, unknown>
}

export interface ShortageRisk {
  part_id: number
  part_reference: string
  /** Names the branch the rating rests on; the UI words it. */
  text_key: string | null
  designation: string
  stock_available: number
  open_demand: number
  safety_stock: number
  incoming_quantity: number
  projected_balance: number
  days_of_cover: number | null
  risk_level: RiskLevel
  rationale: string
}

export interface AiAnalysis {
  generated_at: string
  headline: string
  /** The headline as a key plus its figures, so the UI words it. */
  headline_key: string | null
  headline_values: Record<string, string | number>
  shortage_risks: ShortageRisk[]
  recommendations: Recommendation[]
  priority_count: Record<string, number>
}

export interface CopilotAnswer {
  question: string
  intent: string
  answer: string
  confidence: string
  sources: { label: string; value: string }[]
  suggestions: string[]
  generated_at: string
}

// ------------------------------------------------------------------ simulation
export interface SimulationStep {
  order: number
  key: string
  title: string
  detail: string
  entity_reference: string | null
  stock_before: number | null
  stock_after: number | null
  occurred_at: string
}

export interface SimulationRun {
  scenario: string
  lot_number: string
  part_reference: string
  steps: SimulationStep[]
  stock_before: number
  stock_after: number
  message: string
}

// -------------------------------------------- imports & Maker-Checker
export type ImportType = 'RECEPTION' | 'INSPECTION' | 'PRODUCTION_REQUEST'

export type ImportStatus = 'IMPORTED' | 'PENDING_REVIEW' | 'APPROVED' | 'REJECTED'

export type ImportRowStatus = 'PENDING' | 'INVALID' | 'APPLIED' | 'REJECTED' | 'FAILED'

export type ValidationDecision = 'APPROVED' | 'REJECTED'

export interface OperatorRef {
  id: number
  employee_number: string
  full_name: string
  role: string
  service: string | null
  is_active: boolean
}

export interface ImportRow {
  id: number
  row_number: number
  status: ImportRowStatus
  payload: Record<string, unknown>
  error_message: string | null
  result_reference: string | null
}

export interface DataImport {
  id: number
  reference: string
  import_type: ImportType
  status: ImportStatus

  source_filename: string
  source_hash: string
  source_size_bytes: number

  row_count: number
  valid_row_count: number
  invalid_row_count: number
  applied_row_count: number

  /** MAKER — the operator who entered the data. */
  maker_reference: string
  maker_role: string
  maker_service: string | null
  maker_name: string | null
  submitted_at: string

  /** CHECKER — the responsible who validated it. */
  checker_reference: string | null
  checker_role: string | null
  checker_service: string | null
  checker_name: string | null
  checked_at: string | null

  decision: ValidationDecision | null
  decision_comment: string | null
  notes: string | null
}

export interface DataImportDetail extends DataImport {
  rows: ImportRow[]
  eligible_checkers: OperatorRef[]
}

export interface ImportTypeInfo {
  value: ImportType
  label: string
  description: string
  columns: { name: string; required: boolean }[]
  maker_roles: string[]
  checker_roles: string[]
}

// ------------------------------------------ echanges de donnees (Excel)
export interface SheetInfo {
  name: string
  rows: number
}

export interface ZoneInfo {
  zone: string
  label: string
  description: string
  filename: string
  rows: number
}

export interface WorkbookStatus {
  workbook: string
  status: string
  generated_at: string
  sheet_count: number
  row_count: number
  sheets: SheetInfo[]
  zones: ZoneInfo[]
}

export interface ZoneTable {
  zone: string
  columns: string[]
  rows: (string | number | null)[][]
  total_rows: number
  returned_rows: number
  status_column: string | null
}

// ------------------------------------------------------------- rapports
export type ReportPeriod = 'today' | 'week' | 'month' | 'year' | 'custom'

export interface ReportKind {
  key: string
  label: string
  description: string
}

export interface ReportSummaryItem {
  label: string
  value: number | string
  unit: string | null
  severity: ApiSeverity
}

export interface ReportOut {
  key: string
  title: string
  period: string
  period_label: string
  generated_at: string
  columns: string[]
  rows: (string | number | null)[][]
  summary: ReportSummaryItem[]
  row_count: number
}
