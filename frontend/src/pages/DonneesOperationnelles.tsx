import { useMemo, useRef, useState } from 'react'
import {
  CheckCircle2,
  Download,
  FileSpreadsheet,
  FileUp,
  Table2,
  XCircle,
} from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  Field,
  LoadingPanel,
  Modal,
  Panel,
  Select,
  Textarea,
} from '@/components/ui'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import { catalogApi, dataApi, importsApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { toSeverity } from '@/utils/status'
import type {
  DataImport,
  DataImportDetail,
  ImportRowStatus,
  ImportStatus,
  ImportType,
  User,
} from '@/types/domain'
import type { Severity } from '@/types'

const STATUS_SEVERITY: Record<ImportStatus, Severity> = {
  IMPORTED: 'info',
  PENDING_REVIEW: 'warn',
  APPROVED: 'ok',
  REJECTED: 'crit',
}

const ROW_SEVERITY: Record<ImportRowStatus, Severity> = {
  PENDING: 'warn',
  INVALID: 'crit',
  APPLIED: 'ok',
  REJECTED: 'crit',
  FAILED: 'crit',
}

/**
 * Operational data.
 *
 * The plant keeps working with spreadsheets. This screen is where they meet
 * SLCC: download the zone workbook, read its content without opening Excel,
 * upload an update, and let the zone responsible validate it.
 */
export default function DonneesOperationnelles() {
  const { t, ts, formatDate, formatNumber } = useI18n()

  const status = useApiResource(() => dataApi.status(), [])
  const imports = useApiResource(() => importsApi.list(), [])
  const types = useApiResource(() => importsApi.types(), [])
  const users = useApiResource(() => catalogApi.users(), [])

  const [zone, setZone] = useState<string | null>(null)
  const [uploadOpen, setUploadOpen] = useState(false)
  const [reviewId, setReviewId] = useState<number | null>(null)

  const pending = imports.data?.filter((item) => item.status === 'PENDING_REVIEW') ?? []
  const decided = imports.data?.filter((item) => item.status !== 'PENDING_REVIEW') ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('data.title')}
        description={t('data.subtitle')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <a
              href={dataApi.workbookUrl()}
              className="inline-flex items-center gap-2 rounded-md border border-line bg-panel px-3 py-2 text-xs font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              <Download className="h-3.5 w-3.5" />
              {t('data.downloadGlobal')}
            </a>
            <Button
              variant="primary"
              icon={<FileUp className="h-3.5 w-3.5" />}
              onClick={() => setUploadOpen(true)}
            >
              {t('data.importUpdate')}
            </Button>
          </div>
        }
      />

      {/* Shared workbook */}
      <Panel>
        {status.initialLoading ? (
          <LoadingPanel rows={2} />
        ) : status.error ? (
          <ErrorPanel message={status.error} onRetry={status.refresh} />
        ) : status.data ? (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="flex items-start gap-3">
              <span className="grid h-9 w-9 shrink-0 place-items-center rounded-md bg-accent/10 text-accent">
                <FileSpreadsheet className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="eyebrow">{t('data.sharedFile')}</p>
                <p className="numeric mt-1 truncate text-xs font-medium text-ink">
                  {status.data.workbook}
                </p>
              </div>
            </div>
            <Metric
              label={t('data.syncStatus')}
              value={t('data.synchronised')}
              dot="ok"
            />
            <Metric label={t('data.sheetCount')} value={String(status.data.sheet_count)} />
            <Metric
              label={t('data.rowCount')}
              value={formatNumber(status.data.row_count)}
              hint={formatDate(status.data.generated_at)}
            />
          </div>
        ) : null}
      </Panel>

      {/* Zones */}
      <Panel title={t('data.zones')} bodyClassName="">
        {status.data ? (
          <ul className="divide-y divide-line">
            {status.data.zones.map((item) => (
              <li
                key={item.zone}
                className="flex flex-wrap items-center gap-3 px-4 py-3"
              >
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-ink">{item.label}</p>
                  <p className="text-2xs text-ink-3">{item.description}</p>
                </div>
                <span className="numeric text-2xs text-ink-3">
                  {formatNumber(item.rows)} {t('common.rows')}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  icon={<Table2 className="h-3 w-3" />}
                  onClick={() => setZone(item.zone)}
                >
                  {t('data.viewData')}
                </Button>
                <a
                  href={dataApi.zoneExportUrl(item.zone)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-2xs font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
                >
                  <Download className="h-3 w-3" />
                  {t('data.downloadExcel')}
                </a>
                {/* The blank grid, for an operator starting a new batch. */}
                <a
                  href={dataApi.zoneTemplateUrl(item.zone)}
                  className="inline-flex items-center gap-1.5 rounded-md border border-dashed border-line px-2.5 py-1.5 text-2xs font-medium text-ink-3 transition-colors hover:border-line-strong hover:text-ink-2"
                >
                  <FileSpreadsheet className="h-3 w-3" />
                  {t('data.downloadTemplate')}
                </a>
              </li>
            ))}
          </ul>
        ) : (
          <LoadingPanel rows={3} />
        )}
      </Panel>

      {/* Maker / Checker */}
      <Panel
        title={t('data.pending')}
        subtitle={t('data.pendingSubtitle', { count: pending.length })}
        bodyClassName=""
      >
        <p className="border-b border-line px-4 py-2 text-2xs text-ink-3">
          {t('data.workflowHint')}
        </p>
        {imports.initialLoading ? (
          <LoadingPanel rows={2} />
        ) : imports.error ? (
          <ErrorPanel message={imports.error} onRetry={imports.refresh} />
        ) : pending.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
            title={t('data.nothingPending')}
          />
        ) : (
          <ImportTable rows={pending} onOpen={setReviewId} />
        )}
      </Panel>

      {decided.length > 0 && (
        <Panel title={t('data.history')} bodyClassName="">
          <ImportTable rows={decided} onOpen={setReviewId} />
        </Panel>
      )}

      {zone && <ZoneDialog zone={zone} onClose={() => setZone(null)} />}

      <UploadDialog
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        types={types.data ?? []}
        users={users.data ?? []}
        onUploaded={(batch) => {
          setUploadOpen(false)
          void imports.refresh()
          setReviewId(batch.id)
        }}
      />

      {reviewId !== null && (
        <ReviewDialog
          importId={reviewId}
          onClose={() => setReviewId(null)}
          onDecided={() => {
            void imports.refresh()
            void status.refresh()
          }}
        />
      )}
    </div>
  )

  function ImportTable({
    rows,
    onOpen,
  }: {
    rows: DataImport[]
    onOpen: (id: number) => void
  }) {
    return (
      <div className="overflow-x-auto">
        <table className="data-table min-w-[880px]">
          <thead>
            <tr>
              <th>{t('common.reference')}</th>
              <th>{t('data.sourceFile')}</th>
              <th className="text-right">{t('common.rows')}</th>
              <th>{t('data.maker')}</th>
              <th>{t('data.checker')}</th>
              <th>{t('common.status')}</th>
              <th className="text-right">{t('common.actions')}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((item) => (
              <tr key={item.id}>
                <td className="numeric font-medium text-ink">{item.reference}</td>
                <td>
                  <span className="block max-w-[180px] truncate">
                    {item.source_filename}
                  </span>
                  <span className="numeric block text-[10px] text-ink-3">
                    sha256 {item.source_hash.slice(0, 10)}…
                  </span>
                </td>
                <td className="numeric text-right">
                  {item.valid_row_count}/{item.row_count}
                  {item.applied_row_count > 0 && (
                    <span className="block text-[10px] text-ok">
                      {item.applied_row_count} ✓
                    </span>
                  )}
                </td>
                <td>
                  <span className="numeric block text-2xs font-medium text-ink">
                    {item.maker_reference}
                  </span>
                  <span className="block text-[10px] text-ink-3">
                    {formatDate(item.submitted_at)}
                  </span>
                </td>
                <td>
                  {item.checker_reference ? (
                    <>
                      <span className="numeric block text-2xs font-medium text-ink">
                        {item.checker_reference}
                      </span>
                      <span className="block text-[10px] text-ink-3">
                        {item.checked_at ? formatDate(item.checked_at) : ''}
                      </span>
                    </>
                  ) : (
                    <span className="text-ink-3">—</span>
                  )}
                </td>
                <td>
                  <Badge severity={STATUS_SEVERITY[item.status]}>{ts(item.status)}</Badge>
                </td>
                <td className="text-right">
                  <Button size="sm" variant="secondary" onClick={() => onOpen(item.id)}>
                    {item.status === 'PENDING_REVIEW' ? t('common.review') : t('common.detail')}
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  function Metric({
    label,
    value,
    hint,
    dot,
  }: {
    label: string
    value: string
    hint?: string
    dot?: Severity
  }) {
    return (
      <div className="min-w-0">
        <p className="eyebrow">{label}</p>
        <p className="mt-1 flex items-center gap-1.5 text-xs font-medium text-ink">
          {dot && <span className="h-1.5 w-1.5 rounded-full bg-ok" />}
          {value}
        </p>
        {hint && <p className="numeric mt-0.5 text-[10px] text-ink-3">{hint}</p>}
      </div>
    )
  }

  /** The zone content, rendered from the same data the spreadsheet carries. */
  function ZoneDialog({ zone, onClose }: { zone: string; onClose: () => void }) {
    const table = useApiResource(() => dataApi.zone(zone, 300), [zone])
    const label =
      status.data?.zones.find((item) => item.zone === zone)?.label ?? zone

    return (
      <Modal
        open
        onClose={onClose}
        title={t('data.zoneContent', { zone: label })}
        subtitle={
          table.data
            ? t('data.showingRows', {
                shown: table.data.returned_rows,
                total: table.data.total_rows,
              })
            : ''
        }
        width="lg"
        footer={
          <>
            <a
              href={dataApi.zoneExportUrl(zone)}
              className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-2 text-xs font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink"
            >
              <Download className="h-3.5 w-3.5" />
              {t('data.downloadExcel')}
            </a>
            <Button variant="ghost" onClick={onClose}>
              {t('common.close')}
            </Button>
          </>
        }
      >
        {table.initialLoading ? (
          <LoadingPanel rows={5} />
        ) : table.error ? (
          <ErrorPanel message={table.error} onRetry={table.refresh} />
        ) : table.data && table.data.rows.length > 0 ? (
          <div className="max-h-[55vh] overflow-auto rounded-md border border-line">
            <table className="data-table">
              <thead className="sticky top-0 bg-panel">
                <tr>
                  {table.data.columns.map((column) => (
                    <th key={column} className="whitespace-nowrap">
                      {column}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {table.data.rows.map((row, index) => (
                  <tr key={index}>
                    {row.map((value, cell) => {
                      const column = table.data!.columns[cell]
                      const isStatus = column === table.data!.status_column
                      const text =
                        value === null || value === undefined ? '' : String(value)
                      return (
                        <td key={cell} className="whitespace-nowrap">
                          {isStatus && text ? (
                            <Badge severity={toSeverity(statusToSeverity(text))}>
                              {ts(text)}
                            </Badge>
                          ) : (
                            <span className={cn(/\d/.test(text) && 'numeric')}>
                              {text.length > 48 ? `${text.slice(0, 48)}…` : text}
                            </span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title={t('reports.noData')} />
        )}
      </Modal>
    )
  }
}

/** Map a backend status string onto the API severity vocabulary. */
function statusToSeverity(value: string): string {
  const upper = value.toUpperCase()
  if (['ACCEPTED', 'APPROVED', 'CONFORM', 'STORED', 'ISSUED', 'OK'].includes(upper)) return 'OK'
  if (
    [
      'QUANTITY_MISMATCH',
      'RED_CAGE',
      'REJECTED',
      'NON_CONFORM',
      'CANCELLED',
      'SATURE',
    ].includes(upper)
  )
    return 'CRITICAL'
  if (
    [
      'ACCEPTED_WITH_TOLERANCE',
      'QUALITY_PENDING',
      'PENDING_INSPECTION',
      'SUBMITTED',
      'PREPARING',
      'READY',
      'A VERIFIER',
    ].includes(upper)
  )
    return 'WARNING'
  return 'INFO'
}

function UploadDialog({
  open,
  onClose,
  types,
  users,
  onUploaded,
}: {
  open: boolean
  onClose: () => void
  types: {
    value: ImportType
    label: string
    description: string
    columns: { name: string; required: boolean }[]
    maker_roles: string[]
  }[]
  users: User[]
  onUploaded: (batch: DataImportDetail) => void
}) {
  const { t } = useI18n()
  const { actorId } = useActor()
  const toast = useToast()
  const fileRef = useRef<HTMLInputElement>(null)

  const [importType, setImportType] = useState<ImportType>('RECEPTION')
  const [makerId, setMakerId] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const selected = types.find((type) => type.value === importType)
  const eligibleMakers = useMemo(() => {
    if (!selected) return users
    return users.filter(
      (user) => user.is_active && user.role && selected.maker_roles.includes(user.role.name),
    )
  }, [users, selected])

  async function submit() {
    const maker = makerId || (eligibleMakers.some((u) => u.id === actorId) ? String(actorId) : '')
    if (!maker || !file) {
      toast.error(t('common.required'), t('operator.selectOperator'))
      return
    }
    setSaving(true)
    try {
      const batch = await importsApi.upload({
        import_type: importType,
        maker_id: Number(maker),
        file,
        notes: notes || null,
      })
      toast.success(
        `${batch.reference} — ${t('status.PENDING_REVIEW')}`,
        `${batch.valid_row_count}/${batch.row_count} ${t('common.rows')}`,
      )
      setFile(null)
      setNotes('')
      if (fileRef.current) fileRef.current.value = ''
      onUploaded(batch)
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={t('data.importUpdate')}
      subtitle={t('data.workflowHint')}
      width="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t('common.cancel')}
          </Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            {t('common.import')}
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('common.zone')} required>
          <Select
            value={importType}
            onChange={(event) => {
              setImportType(event.target.value as ImportType)
              setMakerId('')
            }}
          >
            {types.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </Select>
        </Field>

        <Field label={t('data.maker')} required>
          <Select value={makerId} onChange={(event) => setMakerId(event.target.value)}>
            <option value="">{t('operator.selectOperator')}</option>
            {eligibleMakers.map((user) => (
              <option key={user.id} value={user.id}>
                {user.employee_number} — {user.full_name}
              </option>
            ))}
          </Select>
        </Field>
      </div>

      {selected && (
        <div className="mt-4 rounded-md border border-line bg-elevated p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <p className="flex-1 text-2xs leading-relaxed text-ink-3">
              {selected.description}
            </p>
            <a
              href={importsApi.templateUrl(importType)}
              className="inline-flex items-center gap-1.5 rounded border border-line bg-panel px-2 py-1 text-2xs text-ink-2 hover:text-accent"
            >
              <Download className="h-3 w-3" />
              Template
            </a>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {selected.columns.map((column) => (
              <span
                key={column.name}
                className={cn(
                  'numeric rounded border px-1.5 py-0.5 text-[10px]',
                  column.required
                    ? 'border-accent/30 text-accent'
                    : 'border-line text-ink-3',
                )}
              >
                {column.name}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="mt-4 grid gap-4">
        <Field label="Fichier Excel / CSV" required>
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xlsm,.csv"
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            className="w-full cursor-pointer rounded-md border border-line bg-elevated px-3 py-2 text-xs text-ink-2 file:mr-3 file:rounded file:border-0 file:bg-accent/10 file:px-3 file:py-1.5 file:text-xs file:text-accent"
          />
        </Field>
        <Field label={t('common.comment')}>
          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={2}
          />
        </Field>
      </div>
    </Modal>
  )
}

function ReviewDialog({
  importId,
  onClose,
  onDecided,
}: {
  importId: number
  onClose: () => void
  onDecided: () => void
}) {
  const { t, ts, formatDate } = useI18n()
  const detail = useApiResource(() => importsApi.get(importId), [importId])
  const toast = useToast()

  const [checkerId, setCheckerId] = useState('')
  const [comment, setComment] = useState('')
  const [saving, setSaving] = useState(false)

  const batch = detail.data
  const pending = batch?.status === 'PENDING_REVIEW'

  async function decide(decision: 'approve' | 'reject') {
    if (!batch || !checkerId) {
      toast.error(t('common.required'), t('data.checker'))
      return
    }
    if (decision === 'reject' && comment.trim().length < 3) {
      toast.error(t('common.required'), t('common.comment'))
      return
    }
    setSaving(true)
    try {
      if (decision === 'approve') {
        const result = await importsApi.approve(batch.id, Number(checkerId), comment || null)
        toast.success(
          `${result.reference} — ${ts('APPROVED')}`,
          `${result.applied_row_count} ${t('common.rows')} · ${result.checker_reference}`,
        )
      } else {
        const result = await importsApi.reject(batch.id, Number(checkerId), comment)
        toast.info(`${result.reference} — ${ts('REJECTED')}`, result.checker_reference ?? '')
      }
      onDecided()
      onClose()
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={batch ? batch.reference : t('common.review')}
      subtitle={pending ? t('data.workflowHint') : ''}
      width="lg"
      footer={
        pending ? (
          <>
            <Button variant="ghost" onClick={onClose}>
              {t('common.close')}
            </Button>
            <Button
              variant="danger"
              loading={saving}
              icon={<XCircle className="h-3.5 w-3.5" />}
              onClick={() => void decide('reject')}
            >
              {t('common.reject')}
            </Button>
            <Button
              variant="success"
              loading={saving}
              icon={<CheckCircle2 className="h-3.5 w-3.5" />}
              onClick={() => void decide('approve')}
            >
              {t('common.approve')}
            </Button>
          </>
        ) : (
          <Button variant="ghost" onClick={onClose}>
            {t('common.close')}
          </Button>
        )
      }
    >
      {detail.initialLoading ? (
        <LoadingPanel rows={4} />
      ) : batch ? (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-md border border-line bg-elevated p-3">
              <p className="eyebrow">{t('data.maker')}</p>
              <p className="numeric mt-1 text-xs font-semibold text-ink">
                {batch.maker_reference}
              </p>
              <p className="text-2xs text-ink-2">{batch.maker_name}</p>
              <p className="numeric text-[10px] text-ink-3">
                {formatDate(batch.submitted_at)}
              </p>
            </div>
            <div
              className={cn(
                'rounded-md border p-3',
                batch.checker_reference ? 'border-ok/30' : 'border-dashed border-line',
              )}
            >
              <p className="eyebrow">{t('data.checker')}</p>
              {batch.checker_reference ? (
                <>
                  <p className="numeric mt-1 text-xs font-semibold text-ink">
                    {batch.checker_reference}
                  </p>
                  <p className="text-2xs text-ink-2">{batch.checker_name}</p>
                  <p className="numeric text-[10px] text-ink-3">
                    {batch.checked_at ? formatDate(batch.checked_at) : ''}
                  </p>
                </>
              ) : (
                <p className="mt-1 text-2xs text-ink-3">—</p>
              )}
            </div>
          </div>

          <div className="rounded-md border border-line bg-elevated p-3">
            <p className="eyebrow">{t('data.sourceFile')}</p>
            <p className="mt-1 text-2xs text-ink-2">{batch.source_filename}</p>
            <p className="numeric mt-0.5 break-all text-[10px] text-ink-3">
              sha256: {batch.source_hash}
            </p>
          </div>

          {batch.decision_comment && (
            <div className="rounded-md border border-line bg-elevated p-3">
              <p className="eyebrow">{t('common.comment')}</p>
              <p className="mt-1 text-xs text-ink-2">{batch.decision_comment}</p>
            </div>
          )}

          <div className="max-h-56 overflow-auto rounded-md border border-line">
            <table className="data-table">
              <thead className="sticky top-0 bg-panel">
                <tr>
                  <th>#</th>
                  <th>{t('common.reference')}</th>
                  <th>{t('common.status')}</th>
                </tr>
              </thead>
              <tbody>
                {batch.rows.map((row) => (
                  <tr key={row.id}>
                    <td className="numeric">{row.row_number}</td>
                    <td>
                      <span className="numeric block break-all text-[10px]">
                        {Object.entries(row.payload)
                          .filter(([key]) => !key.endsWith('_id'))
                          .map(([key, value]) => `${key}=${String(value ?? '')}`)
                          .join('  ')}
                      </span>
                      {row.error_message && (
                        <span className="block text-[10px] text-crit">{row.error_message}</span>
                      )}
                      {row.result_reference && (
                        <span className="numeric block text-[10px] text-ok">
                          → {row.result_reference}
                        </span>
                      )}
                    </td>
                    <td>
                      <Badge severity={ROW_SEVERITY[row.status]}>{ts(row.status)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pending && (
            <div className="grid gap-3 rounded-md border border-accent/25 bg-accent/5 p-3">
              <Field label={t('data.checker')} required>
                <Select value={checkerId} onChange={(event) => setCheckerId(event.target.value)}>
                  <option value="">{t('operator.selectOperator')}</option>
                  {batch.eligible_checkers.map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.employee_number} — {user.full_name} ({user.role})
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label={t('common.comment')}>
                <Textarea
                  value={comment}
                  onChange={(event) => setComment(event.target.value)}
                  rows={2}
                />
              </Field>
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  )
}
