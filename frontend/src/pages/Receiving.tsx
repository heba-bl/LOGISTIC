import { useMemo } from 'react'
import { PackageSearch } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import { DonutChart } from '@/features/analytics/circular'
import { HBarChart } from '@/features/analytics/bars'
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
import { receivingApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatTimestamp } from '@/utils/format'
import { receptionStatusSeverity } from '@/utils/status'
import { useState } from 'react'

/**
 * Receiving, as the logistics manager sees it.
 *
 * Nothing is entered here. The deliveries were booked in by a receptionist in
 * the shared workbook and validated by their zone chief; this screen reads the
 * result - how much arrived, how much matched, and which deliveries did not.
 */
export default function Receiving() {
  const { t, ts, formatNumber } = useI18n()
  const receptions = useApiResource(() => receivingApi.list(), [], { pollMs: 60_000 })
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  const filters = useFilterState(['status', 'supplier'])
  const rows = receptions.data ?? []

  const suppliers = useMemo(
    () => [...new Set(rows.map((row) => row.lot.supplier.name))].sort(),
    [rows],
  )

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
              row.delivery_note,
            ],
            filters.search,
          ) &&
          (!filters.values.status || row.status === filters.values.status) &&
          (!filters.values.supplier || row.lot.supplier.name === filters.values.supplier),
      ),
    [rows, filters.search, filters.values.status, filters.values.supplier],
  )

  // --- What happened ------------------------------------------------------
  const summary = useMemo(() => {
    const count = (status: string) => visible.filter((row) => row.status === status).length
    const received = visible.reduce((sum, row) => sum + row.quantity_received, 0)
    const gaps = visible.filter((row) => row.quantity_gap !== 0)
    return {
      accepted: count('ACCEPTED'),
      tolerance: count('ACCEPTED_WITH_TOLERANCE'),
      mismatch: count('QUANTITY_MISMATCH'),
      received,
      gaps: gaps.length,
      gapUnits: gaps.reduce((sum, row) => sum + Math.abs(row.quantity_gap), 0),
    }
  }, [visible])

  const kpis: SupervisionKpi[] = [
    {
      key: 'count',
      label: t('recv.list'),
      value: formatNumber(visible.length),
      hint: t('recv.kpi.ofTotal', { total: formatNumber(rows.length) }),
      severity: 'INFO',
    },
    {
      key: 'quantity',
      label: t('recv.col.received'),
      value: formatNumber(summary.received),
      unit: t('unit.pcs'),
      severity: 'OK',
    },
    {
      key: 'conform',
      label: t('status.ACCEPTED'),
      value: formatNumber(summary.accepted),
      hint: t('recv.kpi.conformShare', {
        percent: visible.length
          ? Math.round((summary.accepted / visible.length) * 100)
          : 100,
      }),
      severity: 'OK',
    },
    {
      key: 'gaps',
      label: t('recv.kpi.gaps'),
      value: formatNumber(summary.gaps),
      hint: t('recv.kpi.gapUnits', { value: formatNumber(summary.gapUnits) }),
      severity: summary.mismatch ? 'CRITICAL' : summary.tolerance ? 'WARNING' : 'OK',
    },
  ]

  // --- How it splits ------------------------------------------------------
  const bySupplier = useMemo(() => {
    const totals = new Map<string, number>()
    for (const row of visible) {
      const name = row.lot.supplier.name
      totals.set(name, (totals.get(name) ?? 0) + row.quantity_received)
    }
    return [...totals.entries()]
      .map(([label, value]) => ({ key: label, label, value }))
      .sort((a, b) => b.value - a.value)
      .slice(0, 8)
  }, [visible])

  return (
    <div className="space-y-4">
      <PageHeader title={t('recv.title')} description={t('recv.supervisionSubtitle')} />
      <SourceNote zone="nav.receiving" />

      {receptions.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : receptions.error ? (
        <div className="panel">
          <ErrorPanel message={receptions.error} onRetry={receptions.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <div className="grid gap-4 xl:grid-cols-2">
            <ChartCard
              title={t('recv.chart.quality')}
              question={t('recv.chart.qualityQuestion')}
            >
              <DonutChart
                segments={[
                  {
                    key: 'accepted',
                    label: t('status.ACCEPTED'),
                    value: summary.accepted,
                    className: 'text-chart-2',
                  },
                  {
                    key: 'tolerance',
                    label: t('status.ACCEPTED_WITH_TOLERANCE'),
                    value: summary.tolerance,
                    className: 'text-chart-3',
                  },
                  {
                    key: 'mismatch',
                    label: t('status.QUANTITY_MISMATCH'),
                    value: summary.mismatch,
                    className: 'text-chart-4',
                  },
                ]}
                centreValue={formatNumber(visible.length)}
                centreLabel={t('recv.list')}
                emptyMessage={t('recv.empty')}
              />
            </ChartCard>

            <ChartCard
              title={t('recv.chart.supplier')}
              question={t('recv.chart.supplierQuestion')}
              delay={0.05}
            >
              <HBarChart
                points={bySupplier}
                unit={` ${t('unit.pcs')}`}
                emptyMessage={t('recv.empty')}
              />
            </ChartCard>
          </div>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('recv.searchPlaceholder')}
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
                  'ACCEPTED',
                  'ACCEPTED_WITH_TOLERANCE',
                  'QUANTITY_MISMATCH',
                ].map((value) => ({ value, label: ts(value) })),
              },
              {
                key: 'supplier',
                label: t('recv.col.supplier'),
                value: filters.values.supplier,
                onChange: (value) => filters.set('supplier', value),
                options: suppliers.map((name) => ({ value: name, label: name })),
              },
            ]}
          />

          <ChartCard
            title={t('recv.report')}
            question={t('recv.reportQuestion')}
            bodyClassName="px-0 pb-0"
            delay={0.08}
          >
            <ReportTable
              columns={[
                { key: 'reference', label: t('common.reference') },
                { key: 'lot', label: t('recv.col.lot') },
                { key: 'part', label: t('recv.col.part') },
                { key: 'supplier', label: t('recv.col.supplier') },
                { key: 'expected', label: t('recv.col.expected'), align: 'right' },
                { key: 'received', label: t('recv.col.received'), align: 'right' },
                { key: 'gap', label: t('recv.col.gap'), align: 'right' },
                { key: 'check', label: t('recv.col.check') },
                { key: 'date', label: t('common.date'), align: 'right' },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<PackageSearch className="h-5 w-5" />}
                      title={t('recv.empty')}
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
                      {row.lot.part.designation}
                    </span>
                  </td>
                  <td>{row.lot.supplier.name}</td>
                  <td className="numeric text-right">{formatNumber(row.quantity_expected)}</td>
                  <td className="numeric text-right font-medium text-ink">
                    {formatNumber(row.quantity_received)}
                  </td>
                  <td
                    className={cn(
                      'numeric text-right',
                      row.quantity_gap === 0
                        ? 'text-ink-3'
                        : row.status === 'QUANTITY_MISMATCH'
                          ? 'text-crit-soft'
                          : 'text-warn-soft',
                    )}
                  >
                    {row.quantity_gap > 0 ? '+' : ''}
                    {row.quantity_gap}
                  </td>
                  <td>
                    <Badge severity={receptionStatusSeverity[row.status]}>{ts(row.status)}</Badge>
                  </td>
                  <td className="numeric text-right text-2xs text-ink-3">
                    {formatTimestamp(row.received_at)}
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
