/**
 * Typed access to every SLCC endpoint.
 *
 * The UI never builds a URL by hand: each business action is a named function
 * here, so a rename on the backend breaks compilation instead of production.
 */

import { API_BASE_URL, apiClient } from './apiClient'
import type { Overview, PeriodKey } from '@/types/overview'
import type { Alert } from '@/types/domain'
import type {
  ExcelHistoryEntry,
  ExcelHistoryQuery,
  ExcelWorkbookStatus,
  SyncResult,
} from '@/types/excel'
import type {
  AiAnalysis,
  DataImport,
  DataImportDetail,
  ImportStatus,
  ImportType,
  ImportTypeInfo,
  OperatorRef,
  ReportKind,
  ReportOut,
  ReportPeriod,
  WorkbookStatus,
  ZoneTable,
  Analytics,
  AuditEntry,
  Category,
  CopilotAnswer,
  Dashboard,
  Inspection,
  Lot,
  LotStatus,
  LotTrace,
  LocationDetail,
  Part,
  PowerBiCatalog,
  ProductionRequestRow,
  ProductionRequest,
  QualityValidation,
  Recommendation,
  Reception,
  SampleSuggestion,
  Setting,
  ShortageRisk,
  Station,
  StockMovement,
  StockRow,
  StoragePlan,
  Supplier,
  TolerancePreview,
  User,
  WarehouseGrid,
  WarehouseLocation,
} from '@/types/domain'

async function get<T>(url: string, params?: object): Promise<T> {
  const { data } = await apiClient.get<T>(url, { params })
  return data
}

async function post<T>(url: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.post<T>(url, body ?? {})
  return data
}

async function put<T>(url: string, body?: unknown): Promise<T> {
  const { data } = await apiClient.put<T>(url, body ?? {})
  return data
}

// ------------------------------------------------------------------ catalogue
export const catalogApi = {
  //: The reference pickers list the whole catalogue. The server defaults to a
  //: hundred rows, which silently hid every reference past the hundredth once
  //: the catalogue grew to 2 239.
  parts: (search?: string) =>
    get<Part[]>('/parts', search ? { search, limit: 5000 } : { limit: 5000 }),
  part: (id: number) => get<Part>(`/parts/${id}`),
  suppliers: () => get<Supplier[]>('/suppliers'),
  categories: () => get<Category[]>('/categories'),
  stations: () => get<Station[]>('/stations'),
  users: () => get<User[]>('/users'),
  settings: () => get<Setting[]>('/settings'),
  updateSetting: (key: string, value: string) => put<Setting>(`/settings/${key}`, { value }),
}

// ------------------------------------------------------------------ receiving
export interface ReceptionPayload {
  part_id: number
  supplier_id: number
  quantity_expected: number
  quantity_received: number
  delivery_note?: string | null
  notes?: string | null
  actor_id?: number | null
}

export const receivingApi = {
  list: (limit = 100) => get<Reception[]>('/receptions', { limit }),
  create: (payload: ReceptionPayload) => post<Reception>('/receptions', payload),
  tolerancePreview: (partId: number, quantityExpected: number) =>
    get<TolerancePreview>('/receptions/tolerance-preview', {
      part_id: partId,
      quantity_expected: quantityExpected,
    }),
}

// ----------------------------------------- imports & Maker-Checker validation
export const importsApi = {
  types: () => get<ImportTypeInfo[]>('/imports/types'),

  list: (status?: ImportStatus) =>
    get<DataImport[]>('/imports', status ? { status } : undefined),

  get: (id: number) => get<DataImportDetail>(`/imports/${id}`),

  checkers: (id: number) => get<OperatorRef[]>(`/imports/${id}/checkers`),

  /** Upload a spreadsheet as the MAKER. Creates no business record. */
  upload: async (payload: {
    import_type: ImportType
    maker_id: number
    file: File
    notes?: string | null
  }) => {
    const form = new FormData()
    form.append('import_type', payload.import_type)
    form.append('maker_id', String(payload.maker_id))
    form.append('file', payload.file)
    if (payload.notes) form.append('notes', payload.notes)

    const { data } = await apiClient.post<DataImportDetail>('/imports', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 30000,
    })
    return data
  },

  /** Validate as the CHECKER. Only now is the data applied. */
  approve: (id: number, checkerId: number, comment?: string | null) =>
    post<DataImportDetail>(`/imports/${id}/approve`, {
      checker_id: checkerId,
      comment: comment ?? null,
    }),

  /** Reject as the CHECKER. Comment mandatory, nothing applied. */
  reject: (id: number, checkerId: number, comment: string) =>
    post<DataImportDetail>(`/imports/${id}/reject`, { checker_id: checkerId, comment }),

  /** URL of the .xlsx template for an import type. */
  templateUrl: (importType: ImportType) =>
    `${API_BASE_URL}/imports/template?import_type=${importType}`,
}

// ------------------------------------------------ echanges de donnees Excel
export const dataApi = {
  status: () => get<WorkbookStatus>('/data/status'),

  /** The zone content, read in SLCC instead of opening the spreadsheet. */
  zone: (zone: string, limit = 500) => get<ZoneTable>(`/data/zones/${zone}`, { limit }),

  zoneExportUrl: (zone: string) => `${API_BASE_URL}/data/zones/${zone}/export`,
  //: Same workbook with an empty SAISIE grid, for an operator starting a batch.
  zoneTemplateUrl: (zone: string) =>
    `${API_BASE_URL}/data/zones/${zone}/export?template=true`,
  workbookUrl: () => `${API_BASE_URL}/data/workbook`,
}

// --------------------------------------------------------------- rapports
export interface ReportQuery {
  period: ReportPeriod
  date_from?: string
  date_to?: string
}

function reportParams(query: ReportQuery): Record<string, string> {
  const params: Record<string, string> = { period: query.period }
  if (query.period === 'custom') {
    if (query.date_from) params.date_from = query.date_from
    if (query.date_to) params.date_to = query.date_to
  }
  return params
}

export const reportsApi = {
  kinds: () => get<ReportKind[]>('/reports/kinds'),
  get: (kind: string, query: ReportQuery) => get<ReportOut>(`/reports/${kind}`, reportParams(query)),
  exportUrl: (kind: string, query: ReportQuery, format: 'xlsx' | 'pdf') => {
    const search = new URLSearchParams(reportParams(query)).toString()
    return `${API_BASE_URL}/reports/${kind}/export.${format}?${search}`
  },
}

// ----------------------------------------------------------------------- lots
export interface LotFilters {
  status?: LotStatus[]
  part_id?: number
  supplier_id?: number
  search?: string
  limit?: number
}

export const lotsApi = {
  list: (filters: LotFilters = {}) => get<Lot[]>('/lots', filters),
  get: (id: number) => get<Lot>(`/lots/${id}`),
}

// ----------------------------------------------------------------- inspection
export const inspectionApi = {
  list: (limit = 100) => get<Inspection[]>('/inspections', { limit }),
  sampleSuggestion: (lotId: number) =>
    get<SampleSuggestion>(`/lots/${lotId}/sample-suggestion`),
  start: async (lotId: number, actorId?: number | null) => {
    // The backend takes the actor as a query parameter on this endpoint.
    const { data } = await apiClient.post<Lot>(
      `/lots/${lotId}/inspection/start`,
      {},
      { params: actorId ? { actor_id: actorId } : undefined },
    )
    return data
  },
  record: (
    lotId: number,
    payload: {
      sample_size: number
      defects_found: number
      observations?: string | null
      actor_id?: number | null
    },
  ) => post<Inspection>(`/lots/${lotId}/inspect`, payload),
}

// -------------------------------------------------------------------- quality
export interface QualityPayload {
  justification: string
  quantity_approved?: number | null
  actor_id?: number | null
}

export const qualityApi = {
  pending: () => get<Lot[]>('/quality/pending'),
  redCage: () => get<Lot[]>('/quality/red-cage'),
  history: (limit = 100) => get<QualityValidation[]>('/quality/validations', { limit }),
  approve: (lotId: number, payload: QualityPayload) =>
    post<QualityValidation>(`/lots/${lotId}/quality/approve`, payload),
  reject: (lotId: number, payload: QualityPayload) =>
    post<QualityValidation>(`/lots/${lotId}/quality/reject`, payload),
  sendToRedCage: (lotId: number, payload: QualityPayload) =>
    post<QualityValidation>(`/lots/${lotId}/quality/red-cage`, payload),
  scrap: (lotId: number, payload: QualityPayload) =>
    post<QualityValidation>(`/lots/${lotId}/quality/scrap`, payload),
}

// ------------------------------------------------------------------ warehouse
export const warehouseApi = {
  grid: () => get<WarehouseGrid>('/warehouse/grid'),
  locations: () => get<WarehouseLocation[]>('/warehouse/locations'),
  location: (id: number) => get<LocationDetail>(`/warehouse/locations/${id}`),
  storagePlan: (lotId: number) => get<StoragePlan>(`/lots/${lotId}/storage-plan`),
  confirmStorage: (
    lotId: number,
    payload: {
      allocations: { location_id: number; quantity: number }[]
      actor_id?: number | null
      notes?: string | null
    },
  ) => post<StockMovement[]>(`/lots/${lotId}/storage/confirm`, payload),
}

export const stockApi = {
  list: () => get<StockRow[]>('/stock'),
  forPart: (partId: number) => get<StockRow>(`/stock/${partId}`),
  movements: (params: { part_id?: number; lot_id?: number; limit?: number } = {}) =>
    get<StockMovement[]>('/stock-movements', params),
}

// ----------------------------------------------------------------- production
export interface RequestPayload {
  station_id: number
  part_id: number
  quantity: number
  priority?: number
  needed_at?: string | null
  notes?: string | null
  actor_id?: number | null
  submit_immediately?: boolean
}

export const productionApi = {
  list: (params: { status?: string[]; station_id?: number; part_id?: number } = {}) =>
    get<ProductionRequestRow[]>('/production/requests', params),
  get: (id: number) => get<ProductionRequestRow>(`/production/requests/${id}`),
  create: (payload: RequestPayload) =>
    post<ProductionRequest>('/production/requests', payload),
  submit: (id: number, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/submit`, { actor_id: actorId ?? null }),
  approve: (id: number, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/approve`, { actor_id: actorId ?? null }),
  reject: (id: number, reason: string, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/reject`, {
      reason,
      actor_id: actorId ?? null,
    }),
  prepare: (id: number, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/prepare`, { actor_id: actorId ?? null }),
  ready: (id: number, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/ready`, { actor_id: actorId ?? null }),
  issue: (id: number, payload: { quantity?: number | null; actor_id?: number | null } = {}) =>
    post<StockMovement>(`/production/requests/${id}/issue`, payload),
  cancel: (id: number, reason: string, actorId?: number | null) =>
    post<ProductionRequest>(`/production/requests/${id}/cancel`, {
      reason,
      actor_id: actorId ?? null,
    }),
}

// ------------------------------------------------------- dashboard & insights
export const dashboardApi = {
  get: () => get<Dashboard>('/dashboard'),
}

//: Supervision decisions on alerts. None of these change a business state:
//: releasing a lot or covering a request stays in the workbook, signed by the
//: zone chief. These record who is watching.
export interface AlertFeed {
  alerts: Alert[]
  standing: Record<string, number>
  kinds: string[]
}

export const alertsApi = {
  //: Every alert, unlike the dashboard's shortlist of eight.
  list: (params?: { severity?: string; kind?: string }) => get<AlertFeed>('/alerts', params),
  acknowledge: (body: AlertDecision) => post<unknown>('/alerts/acknowledge', body),
  snooze: (body: AlertDecision) => post<unknown>('/alerts/snooze', body),
  close: (body: AlertDecision) => post<unknown>('/alerts/close', body),
}

export interface AlertDecision {
  alert_key: string
  actor_reference: string
  reason?: string
  snooze_hours?: number
}

export interface TeamMember extends User {
  can_validate: boolean
  has_code: boolean
}

export interface MemberWithCode {
  member: TeamMember
  /** Returned once, on creation or reissue. Never stored, never returned again. */
  code: string | null
}

//: Who signs in the workbook. Administration, not production: granting the
//: right to validate changes nothing the plant did.
export const teamApi = {
  list: () => get<TeamMember[]>('/team'),
  create: (body: {
    employee_number: string
    first_name: string
    last_name: string
    role_name: string
    zone?: string
    service?: string
  }) => post<MemberWithCode>('/team', body),
  deactivate: (matricule: string) =>
    post<TeamMember>(`/team/${encodeURIComponent(matricule)}/deactivate`),
  activate: (matricule: string) =>
    post<TeamMember>(`/team/${encodeURIComponent(matricule)}/activate`),
  reissueCode: (matricule: string) =>
    post<MemberWithCode>(`/team/${encodeURIComponent(matricule)}/reissue-code`),
  //: Rewrites the shared workbook from the current roster. Not automatic: it
  //: fails while an operator has the file open, and silently rewriting a file
  //: somebody is typing in would be worse than asking.
  regenerateWorkbook: () =>
    post<{ path: string; size_bytes: number; sheet_count: number }>(
      '/team/workbook/regenerate',
    ),
}

export const traceabilityApi = {
  lot: (lotId: number) => get<LotTrace>(`/traceability/lots/${lotId}`),
  byLotNumber: (lotNumber: string) =>
    get<LotTrace>(`/traceability/lot-number/${encodeURIComponent(lotNumber)}`),
  audit: (params: { search?: string; entity_type?: string; part_id?: number; limit?: number }) =>
    get<AuditEntry[]>('/traceability/audit', params),
  partMovements: (partId: number, limit = 200) =>
    get<StockMovement[]>(`/traceability/parts/${partId}/movements`, { limit }),
}

export interface OverviewQuery {
  period: PeriodKey
  date_from?: string
  date_to?: string
}

export const analyticsApi = {
  get: () => get<Analytics>('/analytics'),
  powerbi: () => get<PowerBiCatalog>('/analytics/powerbi'),
  //: One request per screen: every block shares the same window, so the KPI and
  //: the charts can never disagree with each other.
  overview: (query: OverviewQuery) => get<Overview>('/analytics/overview', query),
}

/**
 * The shared workbook.
 *
 * The site supervises what Excel produces; it never re-implements the
 * Maker-Checker rules, which live on the server.
 */
export const excelApi = {
  status: () => get<ExcelWorkbookStatus>('/excel/status'),
  history: (query: ExcelHistoryQuery = {}) =>
    get<ExcelHistoryEntry[]>('/excel/history', query),
  //: Re-posts the rows the workbook already validated. The same endpoint the
  //: Excel macro calls - there is only one synchronisation path.
  sync: (sheet: string, file: string, rows: Record<string, unknown>[]) =>
    post<SyncResult>('/excel/sync', { sheet, file, rows }),
  verifyCode: (matricule: string, code: string) =>
    post<{ matricule: string; valid: boolean }>('/excel/verify-code', { matricule, code }),
  downloadUrl: () => `${API_BASE_URL}/excel/workbook`,
}

export const aiApi = {
  analysis: (refresh = true) => get<AiAnalysis>('/ai/analysis', { refresh }),
  recommendations: () => get<Recommendation[]>('/ai/recommendations'),
  shortageRisk: (onlyAtRisk = false) =>
    get<ShortageRisk[]>('/ai/shortage-risk', { only_at_risk: onlyAtRisk }),
  copilot: (question: string) => post<CopilotAnswer>('/ai/copilot', { question }),
  suggestions: () => get<string[]>('/ai/copilot/suggestions'),
}

//: `simulationApi` was here. It POSTed to /insights/simulation/run,
//: which creates lots, inspections and quality decisions through the
//: real services and commits them - production manufactured from the
//: supervision screen. The endpoint remains for terminal use, the way
//: the seed script is used; the site no longer has a way to call it.
