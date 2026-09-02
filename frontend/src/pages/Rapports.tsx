import { useState } from 'react'
import { Download, FileText } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  EmptyState,
  ErrorPanel,
  Input,
  LoadingPanel,
  Panel,
} from '@/components/ui'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { reportsApi, type ReportQuery } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { toSeverity } from '@/utils/status'
import type { MessageKey } from '@/i18n/messages'
import type { ReportPeriod } from '@/types/domain'

const PERIODS: { value: ReportPeriod; key: MessageKey }[] = [
  { value: 'today', key: 'reports.period.today' },
  { value: 'week', key: 'reports.period.week' },
  { value: 'month', key: 'reports.period.month' },
  { value: 'year', key: 'reports.period.year' },
  { value: 'custom', key: 'reports.period.custom' },
]

/**
 * Reports.
 *
 * A period, a subject, headline figures, then the detail - and two exports. The
 * manager reads the conclusion first; the table is there if they need it.
 */
export default function Rapports() {
  const { t, formatNumber, formatDate } = useI18n()

  const kinds = useApiResource(() => reportsApi.kinds(), [])
  const [kind, setKind] = useState('receptions')
  const [period, setPeriod] = useState<ReportPeriod>('month')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')

  const query: ReportQuery = {
    period,
    date_from: from || undefined,
    date_to: to || undefined,
  }
  const ready = period !== 'custom' || (Boolean(from) && Boolean(to))

  const report = useApiResource(
    () => reportsApi.get(kind, query),
    [kind, period, from, to],
    { enabled: ready },
  )

  return (
    <div className="space-y-4">
      <PageHeader title={t('reports.title')} description={t('reports.subtitle')} />

      {/* Filters: one row, above the content */}
      <Panel>
        <div className="flex flex-wrap items-end gap-4">
          <div className="min-w-0">
            <p className="eyebrow mb-1.5">{t('reports.period')}</p>
            <div className="flex flex-wrap gap-1">
              {PERIODS.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => setPeriod(option.value)}
                  className={cn(
                    'rounded-md border px-3 py-1.5 text-xs font-medium transition-colors',
                    period === option.value
                      ? 'border-accent/40 bg-accent/10 text-accent'
                      : 'border-line text-ink-2 hover:bg-elevated hover:text-ink',
                  )}
                >
                  {t(option.key)}
                </button>
              ))}
            </div>
          </div>

          {period === 'custom' && (
            <div className="flex items-end gap-2">
              <label className="block">
                <span className="eyebrow">{t('reports.from')}</span>
                <Input
                  type="date"
                  value={from}
                  onChange={(event) => setFrom(event.target.value)}
                  className="mt-1.5 w-40"
                />
              </label>
              <label className="block">
                <span className="eyebrow">{t('reports.to')}</span>
                <Input
                  type="date"
                  value={to}
                  onChange={(event) => setTo(event.target.value)}
                  className="mt-1.5 w-40"
                />
              </label>
            </div>
          )}

          <div className="ml-auto flex items-center gap-2">
            <a
              href={reportsApi.exportUrl(kind, query, 'xlsx')}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-2 text-xs font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink',
                !ready && 'pointer-events-none opacity-50',
              )}
            >
              <Download className="h-3.5 w-3.5" />
              {t('reports.exportExcel')}
            </a>
            <a
              href={reportsApi.exportUrl(kind, query, 'pdf')}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-2 text-xs font-medium text-ink-2 transition-colors hover:border-line-strong hover:text-ink',
                !ready && 'pointer-events-none opacity-50',
              )}
            >
              <FileText className="h-3.5 w-3.5" />
              {t('reports.exportPdf')}
            </a>
          </div>
        </div>

        {/* Subjects */}
        <div className="mt-4 flex flex-wrap gap-1 border-t border-line pt-3">
          {(kinds.data ?? []).map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setKind(item.key)}
              title={item.description}
              className={cn(
                'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
                kind === item.key
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-2 hover:bg-elevated hover:text-ink',
              )}
            >
              {t(`reports.kind.${item.key}` as MessageKey)}
            </button>
          ))}
        </div>
      </Panel>

      {!ready ? (
        <Panel bodyClassName="">
          <EmptyState title={t('reports.period.custom')} description={`${t('reports.from')} / ${t('reports.to')}`} />
        </Panel>
      ) : report.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={5} />
        </Panel>
      ) : report.error && !report.data ? (
        <Panel bodyClassName="">
          <ErrorPanel message={report.error} onRetry={report.refresh} />
        </Panel>
      ) : report.data ? (
        <>
          {/* Headline figures first */}
          {report.data.summary.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
              {report.data.summary.map((item) => {
                const severity = toSeverity(item.severity)
                return (
                  <div
                    key={item.label}
                    className="rounded-lg border border-line bg-panel p-4 shadow-panel"
                  >
                    <p className="eyebrow">{item.label}</p>
                    <p className="mt-2 flex items-baseline gap-1">
                      <span
                        className={cn(
                          'numeric text-xl font-semibold leading-none',
                          severity === 'crit'
                            ? 'text-crit'
                            : severity === 'warn'
                              ? 'text-warn'
                              : 'text-ink',
                        )}
                      >
                        {typeof item.value === 'number'
                          ? formatNumber(item.value)
                          : item.value}
                      </span>
                      {item.unit && (
                        <span className="text-2xs text-ink-3">{item.unit}</span>
                      )}
                    </p>
                  </div>
                )
              })}
            </div>
          )}

          <Panel
            title={report.data.title}
            subtitle={`${report.data.period_label} · ${t('reports.rowCount', {
              count: formatNumber(report.data.row_count),
            })} · ${formatDate(report.data.generated_at)}`}
            bodyClassName=""
          >
            {report.data.rows.length === 0 ? (
              <EmptyState title={t('reports.noData')} />
            ) : (
              <div className="max-h-[60vh] overflow-auto">
                <table className="data-table">
                  <thead className="sticky top-0 bg-panel">
                    <tr>
                      {report.data.columns.map((column) => (
                        <th key={column} className="whitespace-nowrap">
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {report.data.rows.map((row, index) => (
                      <tr key={index}>
                        {row.map((value, cell) => {
                          const column = report.data!.columns[cell]
                          const text = value === null ? '' : String(value)
                          const isStatus = ['STATUT', 'RESULTAT', 'NIVEAU'].includes(column)
                          return (
                            <td key={cell} className="whitespace-nowrap">
                              {isStatus && text ? (
                                <Badge severity={toSeverity(normalise(text))}>{text}</Badge>
                              ) : (
                                <span className={cn(/^[\d\s.,%-]+$/.test(text) && 'numeric')}>
                                  {text.length > 60 ? `${text.slice(0, 60)}…` : text}
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
            )}
          </Panel>
        </>
      ) : null}
    </div>
  )
}

function normalise(value: string): string {
  const upper = value.toUpperCase()
  if (['OK', 'ACCEPTED', 'CONFORM', 'APPROVED', 'ISSUED'].includes(upper)) return 'OK'
  if (
    ['CRIT', 'CRITICAL', 'REJECTED', 'NON_CONFORM', 'RED_CAGE', 'SOUS SEUIL'].includes(upper)
  )
    return 'CRITICAL'
  if (['WARN', 'WARNING', 'ACCEPTED_WITH_TOLERANCE', 'SUBMITTED'].includes(upper))
    return 'WARNING'
  return 'INFO'
}
