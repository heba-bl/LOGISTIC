import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { motion } from 'framer-motion'
import {
  ClipboardCheck,
  Copy,
  Download,
  FileSpreadsheet,
  Factory,
  History,
  Move3d,
  PackageSearch,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Truck,
  Warehouse as WarehouseIcon,
} from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, Button, ErrorPanel, Input, LoadingPanel, Panel, Select } from '@/components/ui'
import { useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { excelApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import type { MessageKey } from '@/i18n/messages'
import type { ExcelHistoryQuery, WorkbookState } from '@/types/excel'
import type { Severity } from '@/types'

/**
 * The shared workbook, seen from the office.
 *
 * The plant keeps working in Excel; this screen is where a logistics manager
 * finds out what that produced without opening a spreadsheet. It shows three
 * things and deliberately keeps them apart:
 *
 *   activity    what the plant actually holds - real records, whatever created them
 *   validation  the Maker-Checker state of the batches that came from the file
 *   traceability who entered each one, who signed it off, and when
 *
 * Every figure comes from `/api/excel/status`; nothing is computed here. The
 * site supervises, it does not re-implement the rules.
 */

const STATE_SEVERITY: Record<WorkbookState, Severity> = {
  SYNCED: 'ok',
  PENDING: 'warn',
  NEVER_SYNCED: 'info',
}

const ACTIVITY_ICONS = {
  receptions: Truck,
  inspections: ClipboardCheck,
  quality: ShieldCheck,
  red_cage: ShieldAlert,
  warehouse_articles: WarehouseIcon,
  stock_movements: Move3d,
  production_requests: Factory,
  issues: PackageSearch,
} as const

type ActivityKey = keyof typeof ACTIVITY_ICONS

//: The four that answer "is anything blocked", first.
const ACTIVITY_ORDER: ActivityKey[] = [
  'receptions',
  'inspections',
  'quality',
  'red_cage',
  'warehouse_articles',
  'stock_movements',
  'production_requests',
  'issues',
]

export default function FichierOperationnel() {
  const { t, formatDate, formatNumber } = useI18n()
  const toast = useToast()

  const status = useApiResource(() => excelApi.status(), [])
  const [filters, setFilters] = useState<ExcelHistoryQuery>({})
  const history = useApiResource(() => excelApi.history({ ...filters, limit: 50 }), [filters])

  const data = status.data

  const hasFilters = useMemo(
    () => Object.values(filters).some((value) => value !== undefined && value !== ''),
    [filters],
  )

  function setFilter(key: keyof ExcelHistoryQuery, value: string) {
    setFilters((current) => {
      const next = { ...current }
      if (value) next[key] = value as never
      else delete next[key]
      return next
    })
  }

  async function copyPath() {
    if (!data?.local_path) return
    try {
      await navigator.clipboard.writeText(data.local_path)
      toast.success(t('excel.pathCopied'), data.local_path)
    } catch {
      toast.error(t('excel.copyFailed'))
    }
  }

  function refreshAll() {
    void status.refresh()
    void history.refresh()
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('excel.title')}
        description={t('excel.subtitle')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              loading={status.loading && !status.initialLoading}
              onClick={refreshAll}
            >
              {t('excel.refresh')}
            </Button>
            <a
              href={excelApi.downloadUrl()}
              className="inline-flex items-center gap-1.5 rounded-lg border border-accent/30 bg-accent-dim px-3 py-2 text-xs font-medium text-accent transition-colors hover:border-accent/60"
            >
              <Download className="h-3.5 w-3.5" />
              {t('excel.download')}
            </a>
          </div>
        }
      />

      {status.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={6} />
        </Panel>
      ) : status.error ? (
        <Panel bodyClassName="">
          <ErrorPanel message={status.error} onRetry={status.refresh} />
        </Panel>
      ) : data ? (
        <>
          {/* --- The file itself ---------------------------------------- */}
          <motion.section
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
            className="panel p-5"
          >
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="flex min-w-0 items-start gap-3.5">
                <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-ok/30 bg-ok/10">
                  <FileSpreadsheet className="h-5 w-5 text-ok-soft" strokeWidth={1.8} />
                </span>
                <div className="min-w-0">
                  <p className="numeric truncate text-sm font-semibold text-ink">
                    {data.workbook}
                  </p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2">
                    <Badge severity={STATE_SEVERITY[data.state]}>
                      {t(`excel.state.${data.state}` as MessageKey)}
                    </Badge>
                    {data.last_sync_at ? (
                      <span className="text-2xs text-ink-3">
                        {t('excel.lastSync')} — {formatDate(data.last_sync_at)}
                      </span>
                    ) : (
                      <span className="text-2xs text-ink-3">{t('excel.lastSyncNever')}</span>
                    )}
                  </div>
                </div>
              </div>

              <dl className="grid grid-cols-2 gap-x-6 gap-y-1.5 sm:grid-cols-3">
                <Meta label={t('excel.lastMaker')} value={data.last_maker} />
                <Meta label={t('excel.lastActor')} value={data.last_actor} />
                <Meta label={t('excel.lastBatch')} value={data.last_reference} />
              </dl>
            </div>

            {/* A browser cannot start Excel; say so and hand over the path. */}
            <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-3.5">
              <span className="eyebrow shrink-0">{t('excel.localFile')}</span>
              {data.local_path ? (
                <>
                  <code className="numeric min-w-0 flex-1 truncate rounded border border-line bg-elevated px-2.5 py-1.5 text-2xs text-ink-2">
                    {data.local_path}
                  </code>
                  <Button
                    size="sm"
                    variant="secondary"
                    icon={<Copy className="h-3 w-3" />}
                    onClick={() => void copyPath()}
                  >
                    {t('excel.copyPath')}
                  </Button>
                </>
              ) : (
                <span className="text-2xs text-warn-soft">{t('excel.localMissing')}</span>
              )}
            </div>
            <p className="mt-1.5 text-2xs text-ink-3">{t('excel.openHint')}</p>
          </motion.section>

          {/* --- Activity ------------------------------------------------ */}
          <Panel title={t('excel.section.activity')} bodyClassName="p-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {ACTIVITY_ORDER.map((key, index) => {
                const Icon = ACTIVITY_ICONS[key]
                const value = data.activity[key]
                const alarming = key === 'red_cage' && value > 0
                return (
                  <motion.div
                    key={key}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3, delay: index * 0.04 }}
                    className="rounded-lg border border-line bg-elevated/60 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="eyebrow truncate">
                        {t(`excel.activity.${key}` as MessageKey)}
                      </span>
                      <Icon
                        className={cn('h-3.5 w-3.5 shrink-0', alarming ? 'text-crit' : 'text-ink-3')}
                        strokeWidth={1.9}
                      />
                    </div>
                    <p
                      className={cn(
                        'numeric mt-2 text-xl font-semibold leading-none',
                        alarming ? 'text-crit-soft' : 'text-ink',
                      )}
                    >
                      {formatNumber(value)}
                    </p>
                  </motion.div>
                )
              })}
            </div>
          </Panel>

          <div className="grid gap-4 xl:grid-cols-3">
            {/* --- Validation ------------------------------------------- */}
            <Panel
              title={t('excel.section.validation')}
              subtitle={t('excel.batches.total') + ` : ${formatNumber(data.batches.total)}`}
              bodyClassName="p-4"
            >
              <div className="space-y-2.5">
                <Tally
                  label={t('excel.batches.pending')}
                  value={data.batches.pending}
                  total={data.batches.total}
                  className="bg-warn"
                />
                <Tally
                  label={t('excel.batches.approved')}
                  value={data.batches.approved}
                  total={data.batches.total}
                  className="bg-ok"
                />
                <Tally
                  label={t('excel.batches.rejected')}
                  value={data.batches.rejected}
                  total={data.batches.total}
                  className="bg-crit"
                />
              </div>

              <dl className="mt-4 space-y-1.5 border-t border-line pt-3">
                <Line label={t('excel.rows.received')} value={formatNumber(data.rows_received)} />
                <Line label={t('excel.rows.approved')} value={formatNumber(data.rows_approved)} />
                <Line label={t('excel.rows.rejected')} value={formatNumber(data.rows_rejected)} />
                <Line label={t('excel.rows.applied')} value={formatNumber(data.rows_applied)} />
              </dl>
            </Panel>

            {/* --- Per process ------------------------------------------ */}
            <Panel
              className="xl:col-span-2"
              title={t('excel.section.process')}
              bodyClassName="p-4"
            >
              {Object.keys(data.per_process).length === 0 ? (
                <p className="px-1 py-6 text-center text-2xs text-ink-3">
                  {t('excel.process.none')}
                </p>
              ) : (
                <div className="grid gap-3 sm:grid-cols-2">
                  {Object.entries(data.per_process).map(([key, counts]) => (
                    <div key={key} className="rounded-lg border border-line bg-elevated/60 p-3.5">
                      <div className="flex items-baseline justify-between gap-2">
                        <p className="text-xs font-semibold text-ink">
                          {t(`excel.process.${key}` as MessageKey)}
                        </p>
                        <span className="numeric text-2xs text-ink-3">
                          {formatNumber(counts.batches)} {t('excel.process.batches')} ·{' '}
                          {formatNumber(counts.rows)} {t('common.rows')}
                        </span>
                      </div>
                      <div className="mt-2.5 grid grid-cols-3 gap-2 text-center">
                        <Chip label={t('excel.batches.pending')} value={counts.pending} tone="warn" />
                        <Chip label={t('excel.batches.approved')} value={counts.approved} tone="ok" />
                        <Chip label={t('excel.batches.rejected')} value={counts.rejected} tone="crit" />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* The warehouse card carries pressure, not batch counts. */}
              <div className="mt-3 rounded-lg border border-line bg-elevated/60 p-3.5">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="text-xs font-semibold text-ink">{t('stage.WAREHOUSE')}</p>
                  <span className="numeric text-2xs font-semibold text-ink">
                    {data.warehouse.occupancy_percent.toFixed(1).replace('.', ',')} %
                  </span>
                </div>
                <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-line/60">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.min(data.warehouse.occupancy_percent, 100)}%` }}
                    transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                    className="h-full rounded-full bg-chart-1"
                  />
                </div>
                <p className="mt-1.5 flex flex-wrap gap-x-4 text-[10px] text-ink-3">
                  <span>
                    {t('excel.warehouse.locations')} :{' '}
                    <span className="numeric">
                      {formatNumber(data.warehouse.locations_used)} /{' '}
                      {formatNumber(data.warehouse.locations)}
                    </span>
                  </span>
                  <span>
                    {t('excel.warehouse.occupancy')} :{' '}
                    <span className="numeric">
                      {formatNumber(data.warehouse.occupied)} /{' '}
                      {formatNumber(data.warehouse.capacity)}
                    </span>
                  </span>
                  <span>
                    {t('excel.warehouse.movements')} :{' '}
                    <span className="numeric">
                      {formatNumber(data.activity.stock_movements)}
                    </span>
                  </span>
                </p>
              </div>
            </Panel>
          </div>

          {/* --- Traceability ------------------------------------------- */}
          <Panel
            title={t('excel.section.history')}
            subtitle={t('excel.history.count', { count: history.data?.length ?? 0 })}
            action={<History className="h-3.5 w-3.5 text-ink-3" />}
            bodyClassName="p-4"
          >
            {/*
              The controls carry `w-full` in their base class, so a width put on
              the control itself loses to it depending on stylesheet order. The
              wrapper sets the width instead, and the control fills it.
            */}
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
              <Input
                value={filters.matricule ?? ''}
                onChange={(event) => setFilter('matricule', event.target.value)}
                placeholder={t('excel.history.filterMatricule')}
              />
              <Select
                value={filters.status ?? ''}
                onChange={(event) => setFilter('status', event.target.value)}
              >
                <option value="">{t('excel.history.filterStatus')}</option>
                <option value="PENDING_REVIEW">{t('status.PENDING_REVIEW')}</option>
                <option value="APPROVED">{t('status.APPROVED')}</option>
                <option value="REJECTED">{t('status.REJECTED')}</option>
              </Select>
              <Select
                value={filters.import_type ?? ''}
                onChange={(event) => setFilter('import_type', event.target.value)}
              >
                <option value="">{t('excel.history.filterType')}</option>
                <option value="RECEPTION">{t('excel.process.RECEPTION')}</option>
                <option value="INSPECTION">{t('excel.process.INSPECTION')}</option>
                <option value="PRODUCTION_REQUEST">{t('excel.process.PRODUCTION_REQUEST')}</option>
              </Select>
              <Input
                type="date"
                aria-label={t('excel.history.filterFrom')}
                value={filters.date_from ?? ''}
                onChange={(event) => setFilter('date_from', event.target.value)}
              />
              <Input
                type="date"
                aria-label={t('excel.history.filterTo')}
                value={filters.date_to ?? ''}
                onChange={(event) => setFilter('date_to', event.target.value)}
              />
              {hasFilters && (
                <Button variant="ghost" onClick={() => setFilters({})}>
                  {t('excel.history.clear')}
                </Button>
              )}
            </div>

            <div className="mt-4 space-y-2.5">
              {history.initialLoading ? (
                <LoadingPanel rows={3} />
              ) : (history.data?.length ?? 0) === 0 ? (
                <p className="px-1 py-8 text-center text-2xs text-ink-3">
                  {t('excel.history.empty')}
                </p>
              ) : (
                history.data?.map((entry) => (
                  <article
                    key={entry.reference}
                    className="rounded-lg border border-line bg-elevated/60 p-3.5"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="numeric text-xs font-semibold text-ink">
                        {entry.reference}
                      </span>
                      <Badge
                        severity={
                          entry.status === 'APPROVED'
                            ? 'ok'
                            : entry.status === 'REJECTED'
                              ? 'crit'
                              : 'warn'
                        }
                      >
                        {t(`status.${entry.status}` as MessageKey)}
                      </Badge>
                      <span className="text-2xs text-ink-3">
                        {t(`excel.process.${entry.import_type}` as MessageKey)}
                      </span>
                      <span className="numeric ml-auto text-2xs text-ink-3">
                        {formatNumber(entry.applied_row_count)} / {formatNumber(entry.row_count)}{' '}
                        {t('common.rows')}
                      </span>
                    </div>

                    {/* Both signatures, side by side: that is the whole point. */}
                    <div className="mt-2.5 grid gap-2.5 sm:grid-cols-2">
                      <Signature
                        label={t('excel.history.maker')}
                        matricule={entry.maker_reference}
                        role={entry.maker_role}
                        moment={entry.submitted_at ? formatDate(entry.submitted_at) : null}
                        tone="info"
                      />
                      <Signature
                        label={t('excel.history.checker')}
                        matricule={entry.checker_reference}
                        role={entry.checker_role}
                        moment={entry.checked_at ? formatDate(entry.checked_at) : null}
                        tone={entry.status === 'REJECTED' ? 'crit' : 'ok'}
                      />
                    </div>

                    <p className="mt-2 flex flex-wrap gap-x-4 text-[10px] text-ink-3">
                      <span className="numeric">
                        {t('excel.history.source')} : {entry.source_filename}
                      </span>
                      {entry.result_references.length > 0 && (
                        <span className="numeric">
                          {t('excel.history.created')} : {entry.result_references.join(', ')}
                        </span>
                      )}
                    </p>
                    {entry.comment && (
                      <p className="mt-1.5 rounded border border-line bg-panel px-2.5 py-1.5 text-2xs text-ink-2">
                        <span className="font-semibold text-ink-3">
                          {t('excel.history.reason')} :{' '}
                        </span>
                        {entry.comment}
                      </p>
                    )}
                  </article>
                ))
              )}
            </div>
          </Panel>

          {/* --- The chain, stated once --------------------------------- */}
          <Panel title={t('excel.chain.title')} bodyClassName="p-4">
            <p className="text-2xs leading-relaxed text-ink-3">{t('excel.chain.hint')}</p>
            <ol className="mt-3 flex flex-wrap items-center gap-1.5 text-2xs">
              {[
                'Excel',
                'Maker / Checker',
                'API SLCC',
                'PostgreSQL',
                t('nav.analytics'),
                'Power BI',
              ].map((step, index, all) => (
                <li key={step} className="flex items-center gap-1.5">
                  <span className="rounded border border-line bg-elevated px-2 py-1 text-ink-2">
                    {step}
                  </span>
                  {index < all.length - 1 && <span className="text-ink-3">→</span>}
                </li>
              ))}
            </ol>
            <Link
              to="/donnees/imports"
              className="mt-3 inline-flex items-center gap-1.5 text-2xs font-medium text-accent hover:underline"
            >
              {t('data.title')} →
            </Link>
          </Panel>
        </>
      ) : null}
    </div>
  )
}

// ------------------------------------------------------------------ pieces
function Meta({ label, value }: { label: string; value: string | null }) {
  return (
    <div>
      <dt className="text-[10px] uppercase tracking-widest2 text-ink-3">{label}</dt>
      <dd className="numeric mt-0.5 text-xs font-medium text-ink">{value ?? '—'}</dd>
    </div>
  )
}

function Line({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <dt className="text-2xs text-ink-3">{label}</dt>
      <dd className="numeric text-2xs font-semibold text-ink">{value}</dd>
    </div>
  )
}

function Tally({
  label,
  value,
  total,
  className,
}: {
  label: string
  value: number
  total: number
  className: string
}) {
  const ratio = total > 0 ? (value / total) * 100 : 0
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-2xs text-ink-2">{label}</span>
        <span className="numeric text-xs font-semibold text-ink">{value}</span>
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-line/60">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(ratio, value > 0 ? 3 : 0)}%` }}
          transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
          className={cn('h-full rounded-full', className)}
        />
      </div>
    </div>
  )
}

function Chip({ label, value, tone }: { label: string; value: number; tone: Severity }) {
  const tones: Record<string, string> = {
    ok: 'border-ok/30 text-ok-soft',
    warn: 'border-warn/30 text-warn-soft',
    crit: 'border-crit/30 text-crit-soft',
    info: 'border-info/30 text-info-soft',
  }
  return (
    <div className={cn('rounded border px-1.5 py-1', tones[tone] ?? tones.info)}>
      <p className="numeric text-xs font-semibold">{value}</p>
      <p className="truncate text-[9px] text-ink-3">{label}</p>
    </div>
  )
}

function Signature({
  label,
  matricule,
  role,
  moment,
  tone,
}: {
  label: string
  matricule: string | null
  role: string | null
  moment: string | null
  tone: Severity
}) {
  const border =
    tone === 'ok' ? 'border-ok/25' : tone === 'crit' ? 'border-crit/25' : 'border-info/25'
  return (
    <div className={cn('rounded border bg-panel px-2.5 py-2', border)}>
      <p className="text-[10px] uppercase tracking-widest2 text-ink-3">{label}</p>
      <p className="numeric mt-0.5 text-xs font-semibold text-ink">{matricule ?? '—'}</p>
      <p className="text-[10px] text-ink-3">
        {role ? role.replace(/_/g, ' ').toLowerCase() : '—'}
        {moment ? ` · ${moment}` : ''}
      </p>
    </div>
  )
}
