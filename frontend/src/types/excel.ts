/** Payloads of the `/api/excel/*` endpoints. */

export type WorkbookState = 'SYNCED' | 'PENDING' | 'NEVER_SYNCED'

export interface ActivityCounts {
  receptions: number
  inspections: number
  quality: number
  red_cage: number
  warehouse_articles: number
  stock_movements: number
  production_requests: number
  issues: number
}

export interface WarehousePressure {
  locations: number
  locations_used: number
  capacity: number
  occupied: number
  occupancy_percent: number
}

export interface BatchCounts {
  total: number
  pending: number
  approved: number
  rejected: number
}

export interface ProcessCounts {
  batches: number
  rows: number
  pending: number
  approved: number
  rejected: number
}

export interface ExcelWorkbookStatus {
  workbook: string
  state: WorkbookState
  local_path: string | null
  local_size_bytes: number | null
  local_modified_at: string | null
  last_sync_at: string | null
  last_actor: string | null
  last_maker: string | null
  last_reference: string | null
  rows_received: number
  rows_approved: number
  rows_rejected: number
  rows_applied: number
  batches: BatchCounts
  activity: ActivityCounts
  warehouse: WarehousePressure
  per_process: Record<string, ProcessCounts>
}

export interface ExcelHistoryEntry {
  reference: string
  import_type: string
  status: string
  decision: string | null
  maker_reference: string
  maker_role: string
  maker_service: string | null
  submitted_at: string
  checker_reference: string | null
  checker_role: string | null
  checker_service: string | null
  checked_at: string | null
  comment: string | null
  source_filename: string
  row_count: number
  valid_row_count: number
  invalid_row_count: number
  applied_row_count: number
  result_references: string[]
}

export interface ExcelHistoryQuery {
  matricule?: string
  role?: string
  zone?: string
  status?: string
  import_type?: string
  date_from?: string
  date_to?: string
  limit?: number
}

export interface SyncRowResult {
  sync_id: string
  source_row: number
  accepted: boolean
  reason: string | null
  result_reference: string | null
}

export interface SyncResult {
  sheet: string
  file: string
  received: number
  accepted: number
  rejected: number
  duplicates: number
  import_reference: string | null
  rows: SyncRowResult[]
}
