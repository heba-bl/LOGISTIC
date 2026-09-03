import { useState } from 'react'
import { CheckCircle2, Download, FileSpreadsheet, Table2 } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, Button, EmptyState, ErrorPanel, LoadingPanel, Modal, Panel } from '@/components/ui'
import { FilterBar, matches } from '@/features/supervision/shell'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { dataApi, importsApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { toSeverity } from '@/utils/status'
import type { DataImport, ImportStatus } from '@/types/domain'
import type { Severity } from '@/types'

const STATUS_SEVERITY: Record<ImportStatus, Severity> = {
  IMPORTED: 'info',
  PENDING_REVIEW: 'warn',
  APPROVED: 'ok',
  REJECTED: 'crit',
}

/**
 * Operational data.
 *
 * The plant works in the shared workbook: operators enter, zone chiefs
 * validate, and the file synchronises here. This screen watches that exchange -
 * which zone sent what, who entered it and who signed it off. Nothing is
 * uploaded or validated from here, because neither happens in this building.
 */
export default function DonneesOperationnelles() {
  const { t, ts, formatDate, formatNumber } = useI18n()

  const status = useApiResource(() => dataApi.status(), [])
  const [search, setSearch] = useState('')
  const imports = useApiResource(() => importsApi.list(), [])

  const [zone, setZone] = useState<string | null>(null)

  // A hundred batches with no way to narrow them: finding the one a supplier
  // is asking about meant reading every row. The search covers what somebody
  // actually knows when they come looking - a reference, a file name, or the
  // matricule of whoever entered or signed it.
  const matching = (imports.data ?? []).filter((item) =>
    matches(
      [
        item.reference,
        item.source_filename,
        item.maker_reference,
        item.checker_reference,
        item.import_type,
      ],
      search,
    ),
  )

  const pending = matching.filter((item) => item.status === 'PENDING_REVIEW')
  const decided = matching.filter((item) => item.status !== 'PENDING_REVIEW')

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
          </div>
        }
      />

      {/* Shared workbook */}
      <Panel>
        {status.initialLoading ? (
          <LoadingPanel rows={2} />
        ) : status.error && !status.data ? (
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
      <FilterBar
        search={search}
        onSearch={setSearch}
        placeholder={t('data.searchPlaceholder')}
        count={t('common.rowsShown', {
          shown: String(matching.length),
          total: String(imports.data?.length ?? 0),
        })}
        onReset={() => setSearch('')}
      />
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
        ) : imports.error && !imports.data ? (
          <ErrorPanel message={imports.error} onRetry={imports.refresh} />
        ) : pending.length === 0 ? (
          <EmptyState
            icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
            title={t('data.nothingPending')}
          />
        ) : (
          <ImportTable rows={pending} />
        )}
      </Panel>

      {decided.length > 0 && (
        <Panel title={t('data.history')} bodyClassName="">
          <ImportTable rows={decided} />
        </Panel>
      )}

      {zone && <ZoneDialog zone={zone} onClose={() => setZone(null)} />}

    </div>
  )

  function ImportTable({ rows }: { rows: DataImport[] }) {
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
                  <span className="numeric block text-[11px] text-ink-3">
                    sha256 {item.source_hash.slice(0, 10)}…
                  </span>
                </td>
                <td className="numeric text-right">
                  {item.valid_row_count}/{item.row_count}
                  {item.applied_row_count > 0 && (
                    <span className="block text-[11px] text-ok">
                      {item.applied_row_count} ✓
                    </span>
                  )}
                </td>
                <td>
                  <span className="numeric block text-2xs font-medium text-ink">
                    {item.maker_reference}
                  </span>
                  <span className="block text-[11px] text-ink-3">
                    {formatDate(item.submitted_at)}
                  </span>
                </td>
                <td>
                  {item.checker_reference ? (
                    <>
                      <span className="numeric block text-2xs font-medium text-ink">
                        {item.checker_reference}
                      </span>
                      <span className="block text-[11px] text-ink-3">
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
                  <Button size="sm" variant="secondary">
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
        {hint && <p className="numeric mt-0.5 text-[11px] text-ink-3">{hint}</p>}
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
        ) : table.error && !table.data ? (
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


