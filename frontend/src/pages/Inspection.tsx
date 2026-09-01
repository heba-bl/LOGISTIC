import { useMemo, useState } from 'react'
import { ClipboardCheck } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import { Gauge } from '@/features/analytics/circular'
import { HBarChart, StackedBar } from '@/features/analytics/bars'
import { RadarChart, type RadarSeries } from '@/features/analytics/radar'
import {
  FilterBar,
  KpiRow,
  ReportTable,
  SourceNote,
  matches,
  useFilterState,
  type SupervisionKpi,
} from '@/features/supervision/shell'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { inspectionApi, lotsApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatTimestamp } from '@/utils/format'
import { inspectionResultSeverity } from '@/utils/status'

/**
 * Inspection, as the logistics manager sees it.
 *
 * The sampling happened on the floor and was recorded in the workbook. What
 * matters here is the verdict: how much of what arrived is usable, which
 * references keep failing, and how many lots are still waiting to be checked.
 */
export default function Inspection() {
  const { t, ts, formatNumber } = useI18n()
  const history = useApiResource(() => inspectionApi.list(300), [], { pollMs: 60_000 })
  const queue = useApiResource(
    () => lotsApi.list({ status: ['PENDING_INSPECTION', 'INSPECTION_IN_PROGRESS'] }),
    [],
    { pollMs: 60_000 },
  )
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  const filters = useFilterState(['result'])
  const rows = history.data ?? []

  const visible = useMemo(
    () =>
      rows.filter(
        (row) =>
          matches(
            [
              row.reference,
              row.lot.lot_number,
              row.lot.part.reference,
              row.lot.part.designation,
              row.lot.supplier.name,
              row.inspector?.full_name,
            ],
            filters.search,
          ) && (!filters.values.result || row.result === filters.values.result),
      ),
    [rows, filters.search, filters.values.result],
  )

  const summary = useMemo(() => {
    const conform = visible.filter((row) => row.result === 'CONFORM').length
    const defects = visible.reduce((sum, row) => sum + row.defects_found, 0)
    const checked = visible.reduce((sum, row) => sum + row.sample_size, 0)
    return {
      conform,
      nonConform: visible.length - conform,
      defects,
      checked,
      rate: visible.length ? (conform / visible.length) * 100 : 100,
    }
  }, [visible])

  const kpis: SupervisionKpi[] = [
    {
      key: 'count',
      label: t('insp.history'),
      value: formatNumber(visible.length),
      hint: t('recv.kpi.ofTotal', { total: formatNumber(rows.length) }),
      severity: 'INFO',
    },
    {
      key: 'rate',
      label: t('kpi.conformity'),
      value: summary.rate.toFixed(1).replace('.', ','),
      unit: '%',
      hint: t('insp.kpi.checked', { value: formatNumber(summary.checked) }),
      severity: summary.rate >= 95 ? 'OK' : summary.rate >= 90 ? 'WARNING' : 'CRITICAL',
    },
    {
      key: 'defects',
      label: t('table.defects'),
      value: formatNumber(summary.defects),
      hint: t('insp.kpi.nonConform', { count: summary.nonConform }),
      severity: summary.nonConform ? 'WARNING' : 'OK',
    },
    {
      key: 'queue',
      label: t('insp.queue'),
      value: formatNumber(queue.data?.length ?? 0),
      hint: t('insp.kpi.waiting'),
      severity: (queue.data?.length ?? 0) > 10 ? 'WARNING' : 'INFO',
    },
  ]

  // Which references keep failing - a supplier conversation, not a lot decision.
  const worstParts = useMemo(() => {
    const totals = new Map<string, number>()
    for (const row of visible) {
      if (row.defects_found <= 0) continue
      const key = row.lot.part.reference
      totals.set(key, (totals.get(key) ?? 0) + row.defects_found)
    }
    return [...totals.entries()]
      .map(([label, value]) => ({ key: label, label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8)
  }, [visible])

  /**
   * The two most-inspected suppliers, scored on four criteria.
   *
   * Every axis is oriented so that further from the centre is better, and each
   * is normalised to 0-100 - a radar cannot mix a percentage with a count and
   * still mean anything. The real figures ride along in `raw` for the tooltip,
   * because "82" on an axis is not an answer to give a supplier.
   */
  const supplierRadar = useMemo<RadarSeries[]>(() => {
    const bySupplier = new Map<string, typeof visible>()
    for (const row of visible) {
      const name = row.lot.supplier?.name
      if (!name) continue
      bySupplier.set(name, [...(bySupplier.get(name) ?? []), row])
    }

    return [...bySupplier.entries()]
      .filter(([, rows]) => rows.length >= 3)
      .sort((a, b) => b[1].length - a[1].length)
      .slice(0, 2)
      .map(([name, rows]) => {
        const conform = rows.filter((row) => row.result === 'CONFORM').length
        const rates = rows.map((row) => row.defect_rate_percent)
        const mean = rates.reduce((sum, rate) => sum + rate, 0) / rates.length
        const spread = Math.sqrt(
          rates.reduce((sum, rate) => sum + (rate - mean) ** 2, 0) / rates.length,
        )
        const threshold =
          rows.reduce((sum, row) => sum + row.defect_threshold_percent, 0) / rows.length
        // How much of the allowed defect budget is left unused. A supplier
        // sitting just under the threshold passes every lot and is one bad
        // batch from stopping the line - which is the thing worth seeing.
        const margin = threshold > 0 ? ((threshold - mean) / threshold) * 100 : 100

        return {
          key: name,
          label: name,
          scores: {
            conformity: (conform / rows.length) * 100,
            defects: Math.max(0, 100 - mean * 10),
            regularity: Math.max(0, 100 - spread * 10),
            margin: Math.max(0, Math.min(100, margin)),
          },
          raw: {
            conformity: (conform / rows.length) * 100,
            defects: mean,
            regularity: spread,
            margin: threshold - mean,
          },
        }
      })
  }, [visible])

  return (
    <div className="space-y-4">
      <PageHeader title={t('insp.title')} description={t('insp.supervisionSubtitle')} />
      <SourceNote zone="nav.inspection" />

      {history.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : history.error ? (
        <div className="panel">
          <ErrorPanel message={history.error} onRetry={history.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <div className="grid gap-4 xl:grid-cols-3">
            {/* A gauge, not a donut: conformity has a target to be read against. */}
            <ChartCard
              title={t('insp.chart.result')}
              question={t('insp.chart.resultQuestion')}
              bodyClassName="px-5 pb-5 pt-2"
            >
              <div className="flex flex-col items-center gap-4">
                <Gauge
                  value={summary.rate}
                  label={t('kpi.conformity')}
                  target={95}
                  warning={95}
                  critical={90}
                  targetLabel={t('gauge.target', { value: 95 })}
                />
                <StackedBar
                  segments={[
                    {
                      key: 'conform',
                      label: t('status.CONFORM'),
                      value: summary.conform,
                      className: 'bg-chart-2',
                    },
                    {
                      key: 'non',
                      label: t('status.NON_CONFORM'),
                      value: summary.nonConform,
                      className: 'bg-chart-4',
                    },
                  ]}
                  emptyMessage={t('insp.noHistory')}
                />
              </div>
            </ChartCard>

            <ChartCard
              title={t('insp.chart.defects')}
              question={t('insp.chart.defectsQuestion')}
              delay={0.05}
            >
              <HBarChart
                points={worstParts}
                unit={` ${t('table.defects').toLowerCase()}`}
                emptyMessage={t('card.defects.empty')}
              />
            </ChartCard>

            {/* A shape, not a bar: the question is where a supplier is weak,
                not how big they are. */}
            <ChartCard
              title={t('insp.chart.supplier')}
              question={t('insp.chart.supplierQuestion')}
              delay={0.08}
              bodyClassName="px-5 pb-5 pt-1"
            >
              <RadarChart
                axes={[
                  {
                    key: 'conformity',
                    label: t('insp.axis.conformity'),
                    format: (value) => `${value.toFixed(0)} %`,
                  },
                  {
                    key: 'defects',
                    label: t('insp.axis.defects'),
                    format: (value) => `${value.toFixed(1)} %`,
                  },
                  {
                    key: 'regularity',
                    label: t('insp.axis.regularity'),
                    format: (value) => `± ${value.toFixed(1)} %`,
                  },
                  {
                    key: 'margin',
                    label: t('insp.axis.margin'),
                    format: (value) => `${value.toFixed(1)} pts`,
                  },
                ]}
                series={supplierRadar}
                emptyMessage={t('insp.chart.supplierEmpty')}
              />
            </ChartCard>
          </div>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('insp.searchPlaceholder')}
            count={t('common.rowsShown', {
              shown: formatNumber(visible.length),
              total: formatNumber(rows.length),
            })}
            onReset={filters.reset}
            selects={[
              {
                key: 'result',
                label: t('common.status'),
                value: filters.values.result,
                onChange: (value) => filters.set('result', value),
                options: ['CONFORM', 'NON_CONFORM'].map((value) => ({
                  value,
                  label: ts(value),
                })),
              },
            ]}
          />

          <ChartCard
            title={t('insp.report')}
            question={t('insp.reportQuestion')}
            bodyClassName="px-0 pb-0"
            delay={0.08}
          >
            <ReportTable
              minWidth={980}
              columns={[
                { key: 'reference', label: t('common.reference') },
                { key: 'lot', label: t('recv.col.lot') },
                { key: 'part', label: t('recv.col.part') },
                { key: 'sample', label: t('insp.field.sample'), align: 'right' },
                { key: 'defects', label: t('table.defects'), align: 'right' },
                { key: 'rate', label: t('table.defectRate'), align: 'right' },
                { key: 'result', label: t('common.status') },
                { key: 'inspector', label: t('common.operator') },
                { key: 'date', label: t('common.date'), align: 'right' },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<ClipboardCheck className="h-5 w-5" />}
                      title={t('insp.noHistory')}
                      description={t('recv.emptyFiltered')}
                    />
                  </div>
                ) : undefined
              }
            >
              {visible.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelectedLotId(row.lot.id)}
                  className="cursor-pointer"
                >
                  <td className="numeric">{row.reference}</td>
                  <td className="numeric font-medium text-ink">{row.lot.lot_number}</td>
                  <td>
                    <span className="numeric">{row.lot.part.reference}</span>
                    <span className="block truncate text-2xs text-ink-3">
                      {row.lot.supplier.name}
                    </span>
                  </td>
                  <td className="numeric text-right">{formatNumber(row.sample_size)}</td>
                  <td className="numeric text-right">{formatNumber(row.defects_found)}</td>
                  <td
                    className={cn(
                      'numeric text-right font-medium',
                      row.defect_rate_percent > row.defect_threshold_percent
                        ? 'text-crit-soft'
                        : 'text-ok-soft',
                    )}
                  >
                    {row.defect_rate_percent} %
                  </td>
                  <td>
                    <Badge severity={inspectionResultSeverity[row.result]}>{ts(row.result)}</Badge>
                  </td>
                  <td className="text-2xs">{row.inspector?.full_name ?? '—'}</td>
                  <td className="numeric text-right text-2xs text-ink-3">
                    {formatTimestamp(row.inspected_at)}
                  </td>
                </tr>
              ))}
            </ReportTable>
          </ChartCard>
        </>
      )}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}
