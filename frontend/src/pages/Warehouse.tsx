import { useMemo, useState } from 'react'
import { Boxes } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel, Meter, StatusDot } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
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
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { stockApi, warehouseApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatDecimal } from '@/utils/format'
import { toSeverity } from '@/utils/status'
import type { WarehouseLocation } from '@/types/domain'

function occupancySeverity(location: WarehouseLocation, warning: number, critical: number) {
  if (location.occupancy_percent >= critical) return 'crit' as const
  if (location.occupancy_percent >= warning) return 'warn' as const
  if (location.occupied === 0) return 'info' as const
  return 'ok' as const
}

/**
 * Warehouse, as the logistics manager sees it.
 *
 * Storage was confirmed by a magasinier in the workbook - that confirmation is
 * what created the stock. This screen reads the consequence: how full the
 * racks are, what sits on them, and which references are thin.
 */
export default function Warehouse() {
  const { t, ts, formatNumber } = useI18n()
  const grid = useApiResource(() => warehouseApi.grid(), [], { pollMs: 60_000 })
  const stock = useApiResource(() => stockApi.list(), [], { pollMs: 60_000 })

  const filters = useFilterState(['severity', 'category'])
  const rows = stock.data ?? []
  const [zoneFilter, setZoneFilter] = useState<string | null>(null)

  const categories = useMemo(
    () => [...new Set(rows.map((row) => row.category).filter(Boolean) as string[])].sort(),
    [rows],
  )

  const visible = useMemo(
    () =>
      rows.filter(
        (row) =>
          matches(
            [row.reference, row.designation, row.category, row.locations.join(' ')],
            filters.search,
          ) &&
          (!filters.values.severity || row.severity === filters.values.severity) &&
          (!filters.values.category || row.category === filters.values.category) &&
          (!zoneFilter || row.locations.some((code) => code.startsWith(`WH-${zoneFilter}`))),
      ),
    [rows, filters.search, filters.values.severity, filters.values.category, zoneFilter],
  )

  const summary = useMemo(() => {
    const available = visible.reduce((sum, row) => sum + row.quantity_available, 0)
    const thin = visible.filter((row) => row.severity !== 'OK').length
    return { available, thin }
  }, [visible])

  const saturated = useMemo(
    () =>
      (grid.data?.locations ?? []).filter(
        (location) => location.occupancy_percent >= (grid.data?.critical_threshold ?? 100),
      ).length,
    [grid.data],
  )

  const kpis: SupervisionKpi[] = [
    {
      key: 'stock',
      label: t('wh.stock'),
      value: formatNumber(summary.available),
      unit: t('unit.pcs'),
      hint: t('wh.kpi.references', { count: visible.length }),
      severity: 'OK',
    },
    {
      key: 'occupancy',
      label: t('wh.globalOccupancy'),
      value: formatDecimal(grid.data?.occupancy_percent ?? 0),
      unit: '%',
      hint: t('wh.kpi.ofCapacity', {
        value: formatNumber(grid.data?.total_capacity ?? 0),
      }),
      severity:
        (grid.data?.occupancy_percent ?? 0) >= (grid.data?.critical_threshold ?? 90)
          ? 'CRITICAL'
          : (grid.data?.occupancy_percent ?? 0) >= (grid.data?.warning_threshold ?? 75)
            ? 'WARNING'
            : 'OK',
    },
    {
      key: 'saturated',
      label: t('wh.kpi.saturated'),
      value: formatNumber(saturated),
      hint: t('wh.kpi.ofLocations', { count: grid.data?.locations.length ?? 0 }),
      severity: saturated ? 'CRITICAL' : 'OK',
    },
    {
      key: 'thin',
      label: t('wh.kpi.thin'),
      value: formatNumber(summary.thin),
      hint: t('wh.kpi.thinHint'),
      severity: summary.thin ? 'WARNING' : 'OK',
    },
  ]

  // Occupancy per zone: the pressure a manager acts on, not per address.
  const byZone = useMemo(() => {
    const totals = new Map<string, { occupied: number; capacity: number }>()
    for (const location of grid.data?.locations ?? []) {
      const current = totals.get(location.zone) ?? { occupied: 0, capacity: 0 }
      current.occupied += location.occupied
      current.capacity += location.capacity
      totals.set(location.zone, current)
    }
    return [...totals.entries()]
      .map(([zone, value]) => ({
        key: zone,
        label: `${t('warehouse.zone')} ${zone}`,
        value: value.capacity ? Math.round((value.occupied / value.capacity) * 1000) / 10 : 0,
        caption: `${formatNumber(value.occupied)} / ${formatNumber(value.capacity)}`,
      }))
      .sort((a, b) => b.value - a.value)
  }, [grid.data, t, formatNumber])

  return (
    <div className="space-y-4">
      <PageHeader title={t('wh.title')} description={t('wh.supervisionSubtitle')} />
      <SourceNote zone="nav.warehouse" />

      {grid.initialLoading || stock.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : grid.error && !grid.data ? (
        <div className="panel">
          <ErrorPanel message={grid.error} onRetry={grid.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <div className="grid gap-4 xl:grid-cols-3">
            <ChartCard title={t('wh.chart.zone')} question={t('wh.chart.zoneQuestion')}>
              <HBarChart
                points={byZone}
                unit=" %"
                max={100}
                emptyMessage={t('card.warehouse.empty')}
                selected={zoneFilter}
                onSelect={(zone) => setZoneFilter((current) => (current === zone ? null : zone))}
              />
            </ChartCard>

            {/* The addresses themselves: where a pallet will and will not fit. */}
            <ChartCard
              className="xl:col-span-2"
              title={t('wh.map')}
              question={t('wh.mapQuestion')}
              delay={0.05}
            >
              {grid.data && (
                <div className="space-y-3">
                  {grid.data.zones.map((zone) => (
                    <div key={zone} className="flex items-start gap-3">
                      <span className="numeric w-8 shrink-0 pt-2 text-sm font-semibold text-ink-3">
                        {zone}
                      </span>
                      <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
                        {grid.data!.locations
                          .filter((location) => location.zone === zone)
                          .map((location) => {
                            const severity = occupancySeverity(
                              location,
                              grid.data!.warning_threshold,
                              grid.data!.critical_threshold,
                            )
                            return (
                              <div
                                key={location.id}
                                title={`${location.code} · ${formatNumber(location.occupied)}/${formatNumber(location.capacity)}`}
                                className={cn(
                                  'rounded-md border bg-elevated/60 p-2',
                                  severity === 'crit'
                                    ? 'border-crit/40'
                                    : severity === 'warn'
                                      ? 'border-warn/40'
                                      : severity === 'ok'
                                        ? 'border-ok/30'
                                        : 'border-line',
                                )}
                              >
                                <div className="flex items-center justify-between gap-1">
                                  <span className="numeric text-[11px] font-semibold text-ink">
                                    {location.code}
                                  </span>
                                  <StatusDot severity={severity} />
                                </div>
                                <Meter
                                  value={location.occupancy_percent}
                                  severity={severity}
                                  label={location.code}
                                  className="mt-1.5"
                                />
                                <p className="numeric mt-1 text-[11px] text-ink-3">
                                  {formatDecimal(location.occupancy_percent)} %
                                </p>
                              </div>
                            )
                          })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </ChartCard>
          </div>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('wh.searchPlaceholder')}
            count={t('common.rowsShown', {
              shown: formatNumber(visible.length),
              total: formatNumber(rows.length),
            })}
            onReset={() => {
              filters.reset()
              setZoneFilter(null)
            }}
            selects={[
              {
                key: 'severity',
                label: t('wh.col.state'),
                value: filters.values.severity,
                onChange: (value) => filters.set('severity', value),
                options: ['OK', 'WARNING', 'CRITICAL'].map((value) => ({
                  value,
                  label: ts(value),
                })),
              },
              {
                key: 'category',
                label: t('wh.col.category'),
                value: filters.values.category,
                onChange: (value) => filters.set('category', value),
                options: categories.map((name) => ({ value: name, label: name })),
              },
            ]}
          />

          <ChartCard
            title={t('wh.report')}
            question={t('wh.reportQuestion')}
            bodyClassName="px-0 pb-0"
            delay={0.08}
          >
            <ReportTable
              minWidth={980}
              columns={[
                { key: 'reference', label: t('common.reference') },
                { key: 'category', label: t('wh.col.category') },
                { key: 'available', label: t('wh.col.available'), align: 'right' },
                { key: 'reserved', label: t('wh.col.reserved'), align: 'right' },
                { key: 'safety', label: t('wh.col.safety'), align: 'right' },
                { key: 'demand', label: t('wh.col.demand'), align: 'right' },
                { key: 'cover', label: t('wh.col.cover'), align: 'right' },
                { key: 'addresses', label: t('wh.col.addresses') },
                { key: 'state', label: t('wh.col.state') },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<Boxes className="h-5 w-5" />}
                      title={t('wh.noStock')}
                      description={t('recv.emptyFiltered')}
                    />
                  </div>
                ) : undefined
              }
            >
              {visible.map((row) => (
                <tr key={row.part_id}>
                  <td>
                    <span className="numeric font-medium text-ink">{row.reference}</span>
                    <span className="block truncate text-2xs text-ink-3">{row.designation}</span>
                  </td>
                  <td className="text-2xs">{row.category ?? '—'}</td>
                  <td className="numeric text-right font-semibold text-ink">
                    {formatNumber(row.quantity_available)}
                  </td>
                  <td className="numeric text-right">{formatNumber(row.quantity_reserved)}</td>
                  <td className="numeric text-right text-ink-3">
                    {formatNumber(row.safety_stock)}
                  </td>
                  <td className="numeric text-right">{formatNumber(row.open_demand)}</td>
                  <td className="numeric text-right">
                    {row.days_of_cover !== null
                      ? t('chart.coverageDays', { days: row.days_of_cover })
                      : '—'}
                  </td>
                  <td className="numeric text-2xs">{row.locations.join(', ') || '—'}</td>
                  <td>
                    <Badge severity={toSeverity(row.severity)}>{ts(row.severity)}</Badge>
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
