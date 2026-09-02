import { useMemo } from 'react'
import { Factory } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard, RiskChip } from '@/features/analytics/primitives'
import { Gauge } from '@/features/analytics/circular'
import { HBarChart, StackedBar } from '@/features/analytics/bars'
import {
  FilterBar,
  KpiRow,
  ReportTable,
  SourceNote,
  matches,
  useFilterState,
  type SupervisionKpi,
} from '@/features/supervision/shell'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { productionApi } from '@/services/slcc.service'
import { formatTimestamp } from '@/utils/format'
import { requestStatusSeverity } from '@/utils/status'

/** Colour by what the status means in the workflow, not by arrival order. */
const STATUS_FILL: Record<string, string> = {
  ISSUED: 'bg-ok',
  READY: 'bg-seq-3',
  PREPARING: 'bg-seq-4',
  APPROVED: 'bg-chart-1',
  SUBMITTED: 'bg-seq-5',
  DRAFT: 'bg-line-strong',
  CANCELLED: 'bg-ink-3/50',
  REJECTED: 'bg-crit',
}

/**
 * Production, as the logistics manager sees it.
 *
 * The lines raised their requests in the workbook and the magasin confirmed
 * the issues there. The question here is whether logistics is serving what
 * production asks for, and which requests it cannot.
 */
export default function Production() {
  const { t, ts, formatNumber } = useI18n()
  const requests = useApiResource(() => productionApi.list(), [], { pollMs: 60_000 })

  const filters = useFilterState(['status', 'station'])
  const rows = requests.data ?? []

  const stations = useMemo(
    () => [...new Set(rows.map((row) => row.request.station.code))].sort(),
    [rows],
  )

  const visible = useMemo(
    () =>
      rows.filter(
        (row) =>
          matches(
            [
              row.request.reference,
              row.request.station.code,
              row.request.station.name,
              row.request.part.reference,
              row.request.part.designation,
            ],
            filters.search,
          ) &&
          (!filters.values.status || row.request.status === filters.values.status) &&
          (!filters.values.station || row.request.station.code === filters.values.station),
      ),
    [rows, filters.search, filters.values.status, filters.values.station],
  )

  const summary = useMemo(() => {
    // A cancelled or rejected request was never meant to be served: counting it
    // would sink the service rate on a decision somebody took deliberately.
    const servable = rows.filter(
      (row) => !['CANCELLED', 'REJECTED'].includes(row.request.status),
    )
    const requested = servable.reduce((sum, row) => sum + row.request.quantity_requested, 0)
    const issued = servable.reduce((sum, row) => sum + row.request.quantity_issued, 0)
    const uncovered = rows.filter((row) => !row.is_coverable && row.request.status !== 'ISSUED')
    return {
      requested,
      issued,
      rate: requested ? (issued / requested) * 100 : 100,
      uncovered: uncovered.length,
      shortfall: uncovered.reduce((sum, row) => sum + row.shortfall, 0),
      open: rows.filter((row) =>
        ['SUBMITTED', 'APPROVED', 'PREPARING', 'READY'].includes(row.request.status),
      ).length,
    }
  }, [rows])

  const kpis: SupervisionKpi[] = [
    {
      key: 'requests',
      label: t('prod.title'),
      value: formatNumber(rows.length),
      hint: t('prod.kpi.open', { count: summary.open }),
      severity: 'INFO',
    },
    {
      key: 'issued',
      label: t('status.ISSUED'),
      value: formatNumber(summary.issued),
      unit: t('unit.pcs'),
      hint: t('production.servedOf', {
        issued: formatNumber(summary.issued),
        requested: formatNumber(summary.requested),
      }),
      severity: 'OK',
    },
    {
      key: 'uncovered',
      label: t('card.uncovered.title'),
      value: formatNumber(summary.uncovered),
      hint: t('prod.kpi.shortfall', { value: formatNumber(summary.shortfall) }),
      severity: summary.uncovered ? 'CRITICAL' : 'OK',
    },
    {
      key: 'stations',
      label: t('prod.kpi.stations'),
      value: formatNumber(stations.length),
      hint: t('prod.kpi.stationsHint'),
      severity: 'INFO',
    },
  ]

  const byStatus = useMemo(() => {
    const totals = new Map<string, number>()
    for (const row of rows) {
      totals.set(row.request.status, (totals.get(row.request.status) ?? 0) + 1)
    }
    return [...totals.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([status, count]) => ({
        key: status,
        label: ts(status),
        value: count,
        className: STATUS_FILL[status] ?? 'bg-line-strong',
      }))
  }, [rows, ts])

  const byStation = useMemo(() => {
    const totals = new Map<string, number>()
    for (const row of rows) {
      if (row.request.quantity_issued <= 0) continue
      const key = row.request.station.code
      totals.set(key, (totals.get(key) ?? 0) + row.request.quantity_issued)
    }
    return [...totals.entries()]
      .map(([label, value]) => ({ key: label, label, value }))
      .sort((a, b) => b.value - a.value)
  }, [rows])

  return (
    <div className="space-y-4">
      <PageHeader title={t('prod.title')} description={t('prod.supervisionSubtitle')} />
      <SourceNote zone="nav.production" />

      {requests.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : requests.error && !requests.data ? (
        <div className="panel">
          <ErrorPanel message={requests.error} onRetry={requests.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <div className="grid gap-4 xl:grid-cols-3">
            {/* Service rate has a target, so it is read on a gauge. */}
            <ChartCard
              title={t('card.serviceRate.title')}
              question={t('card.serviceRate.question')}
              bodyClassName="px-5 pb-5 pt-2"
            >
              <div className="flex flex-col items-center gap-3">
                <Gauge
                  value={summary.rate}
                  label={t('card.serviceRate.title')}
                  target={90}
                  warning={90}
                  critical={70}
                  targetLabel={t('gauge.target', { value: 90 })}
                />
              </div>
            </ChartCard>

            {/* Where the requests are in the workflow: one whole, split. */}
            <ChartCard
              title={t('card.requestStatus.title')}
              question={t('card.requestStatus.question')}
              delay={0.05}
            >
              <StackedBar segments={byStatus} emptyMessage={t('card.requestStatus.empty')} />
            </ChartCard>

            <ChartCard
              title={t('prod.chart.station')}
              question={t('prod.chart.stationQuestion')}
              delay={0.08}
            >
              <HBarChart
                points={byStation}
                unit={` ${t('unit.pcs')}`}
                emptyMessage={t('card.consumption.empty')}
              />
            </ChartCard>
          </div>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('prod.searchPlaceholder')}
            count={t('common.rowsShown', {
              shown: formatNumber(visible.length),
              total: formatNumber(rows.length),
            })}
            onReset={filters.reset}
            selects={[
              {
                key: 'status',
                label: t('common.status'),
                value: filters.values.status,
                onChange: (value) => filters.set('status', value),
                options: [
                  'SUBMITTED',
                  'APPROVED',
                  'PREPARING',
                  'READY',
                  'ISSUED',
                  'REJECTED',
                  'CANCELLED',
                ].map((value) => ({ value, label: ts(value) })),
              },
              {
                key: 'station',
                label: t('prod.field.station'),
                value: filters.values.station,
                onChange: (value) => filters.set('station', value),
                options: stations.map((code) => ({ value: code, label: code })),
              },
            ]}
          />

          <ChartCard
            title={t('prod.report')}
            question={t('prod.reportQuestion')}
            bodyClassName="px-0 pb-0"
            delay={0.11}
          >
            <ReportTable
              minWidth={1020}
              columns={[
                { key: 'reference', label: t('common.reference') },
                { key: 'station', label: t('prod.field.station') },
                { key: 'part', label: t('recv.col.part') },
                { key: 'requested', label: t('prod.col.requested'), align: 'right' },
                { key: 'issued', label: t('status.ISSUED'), align: 'right' },
                { key: 'stock', label: t('chart.stock'), align: 'right' },
                { key: 'coverage', label: t('prod.col.coverage') },
                { key: 'priority', label: t('prod.field.priority') },
                { key: 'status', label: t('common.status') },
                { key: 'date', label: t('common.date'), align: 'right' },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<Factory className="h-5 w-5" />}
                      title={t('prod.noOpen')}
                      description={t('recv.emptyFiltered')}
                    />
                  </div>
                ) : undefined
              }
            >
              {visible.map((row) => (
                <tr key={row.request.id}>
                  <td className="numeric font-medium text-ink">{row.request.reference}</td>
                  <td>
                    <span className="numeric">{row.request.station.code}</span>
                    <span className="block truncate text-2xs text-ink-3">
                      {row.request.station.name}
                    </span>
                  </td>
                  <td>
                    <span className="numeric">{row.request.part.reference}</span>
                    <span className="block truncate text-2xs text-ink-3">
                      {row.request.part.designation}
                    </span>
                  </td>
                  <td className="numeric text-right">
                    {formatNumber(row.request.quantity_requested)}
                  </td>
                  <td className="numeric text-right font-medium text-ink">
                    {formatNumber(row.request.quantity_issued)}
                  </td>
                  <td className="numeric text-right">{formatNumber(row.stock_available)}</td>
                  <td>
                    {row.request.status === 'ISSUED' ? (
                      <span className="text-2xs text-ink-3">—</span>
                    ) : row.is_coverable ? (
                      <Badge severity="ok">{t('prod.covered')}</Badge>
                    ) : (
                      <Badge severity="crit">
                        {t('prod.short', { value: formatNumber(row.shortfall) })}
                      </Badge>
                    )}
                  </td>
                  <td>
                    <RiskChip
                      risk={
                        row.request.priority === 1
                          ? 'CRITICAL'
                          : row.request.priority === 2
                            ? 'WARNING'
                            : 'INFO'
                      }
                      label={`P${row.request.priority}`}
                    />
                  </td>
                  <td>
                    <Badge severity={requestStatusSeverity[row.request.status]}>
                      {ts(row.request.status)}
                    </Badge>
                  </td>
                  <td className="numeric text-right text-2xs text-ink-3">
                    {formatTimestamp(row.request.created_on)}
                  </td>
                </tr>
              ))}
            </ReportTable>
          </ChartCard>
        </>
      )}
    </div>
  )
}
