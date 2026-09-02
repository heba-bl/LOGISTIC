import { useMemo, useState } from 'react'
import { Boxes, Truck } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import {
  FilterBar,
  KpiRow,
  ReportTable,
  matches,
  useFilterState,
  type SupervisionKpi,
} from '@/features/supervision/shell'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { catalogApi } from '@/services/slcc.service'

/**
 * The reference tables: what the plant handles, and who supplies it.
 *
 * These lived in Settings, which was wrong twice over. They are not settings -
 * nothing here is configured, it is consulted - and a 2 239 row table with no
 * search box is a table nobody uses: finding WHAP-0446 meant scrolling past two
 * thousand rows, so people opened the workbook instead.
 */
export default function Referentiel() {
  const { t, formatNumber } = useI18n()
  const [tab, setTab] = useState<'parts' | 'suppliers'>('parts')

  const parts = useApiResource(() => catalogApi.parts(), [])
  const suppliers = useApiResource(() => catalogApi.suppliers(), [])

  const filters = useFilterState(['category', 'size'])

  const categories = useMemo(
    () =>
      [...new Set((parts.data ?? []).map((part) => part.category?.name).filter(Boolean))]
        .sort() as string[],
    [parts.data],
  )

  const visibleParts = useMemo(
    () =>
      (parts.data ?? []).filter(
        (part) =>
          matches(
            [part.reference, part.designation, part.description, part.category?.name],
            filters.search,
          ) &&
          (!filters.values.category || part.category?.name === filters.values.category) &&
          (!filters.values.size || part.size_class === filters.values.size),
      ),
    [parts.data, filters.search, filters.values.category, filters.values.size],
  )

  const visibleSuppliers = useMemo(
    () =>
      (suppliers.data ?? []).filter((supplier) =>
        matches([supplier.code, supplier.name, supplier.country], filters.search),
      ),
    [suppliers.data, filters.search],
  )

  const kpis: SupervisionKpi[] = [
    {
      key: 'parts',
      label: t('ref.kpi.parts'),
      value: formatNumber(parts.data?.length ?? 0),
      hint: t('ref.kpi.partsHint'),
      severity: 'INFO',
    },
    {
      key: 'categories',
      label: t('ref.kpi.categories'),
      value: formatNumber(categories.length),
      hint: t('ref.kpi.categoriesHint'),
      severity: 'INFO',
    },
    {
      key: 'suppliers',
      label: t('ref.kpi.suppliers'),
      value: formatNumber(suppliers.data?.length ?? 0),
      hint: t('ref.kpi.suppliersHint'),
      severity: 'INFO',
    },
  ]

  const loading = tab === 'parts' ? parts : suppliers
  const shown = tab === 'parts' ? visibleParts.length : visibleSuppliers.length
  const total = tab === 'parts' ? (parts.data?.length ?? 0) : (suppliers.data?.length ?? 0)

  return (
    <div className="space-y-4">
      <PageHeader title={t('ref.title')} description={t('ref.subtitle')} />

      {loading.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : loading.error && !loading.data ? (
        <div className="panel">
          <ErrorPanel message={loading.error} onRetry={loading.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          {/* Two tables, one at a time: side by side they would each get half a
              screen, and the catalogue is the one that needs the room. */}
          <div className="flex gap-2">
            {(
              [
                ['parts', t('ref.parts'), Boxes],
                ['suppliers', t('ref.suppliers'), Truck],
              ] as const
            ).map(([value, label, Icon]) => (
              <button
                key={value}
                type="button"
                onClick={() => setTab(value)}
                className={
                  tab === value
                    ? 'btn-primary h-9 px-4'
                    : 'btn-secondary h-9 px-4'
                }
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" />
                {label}
              </button>
            ))}
          </div>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={tab === 'parts' ? t('ref.searchParts') : t('ref.searchSuppliers')}
            count={t('common.rowsShown', {
              shown: formatNumber(shown),
              total: formatNumber(total),
            })}
            onReset={filters.reset}
            selects={
              tab === 'parts'
                ? [
                    {
                      key: 'category',
                      label: t('ref.category'),
                      value: filters.values.category,
                      onChange: (value) => filters.set('category', value),
                      options: categories.map((value) => ({ value, label: value })),
                    },
                    {
                      key: 'size',
                      label: t('ref.size'),
                      value: filters.values.size,
                      onChange: (value) => filters.set('size', value),
                      options: ['SMALL', 'LARGE'].map((value) => ({ value, label: value })),
                    },
                  ]
                : []
            }
          />

          {tab === 'parts' ? (
            <ChartCard
              title={t('ref.parts')}
              question={t('ref.partsQuestion')}
              bodyClassName="px-0 pb-0"
            >
              <ReportTable
                minWidth={980}
                columns={[
                  { key: 'reference', label: t('common.reference') },
                  { key: 'designation', label: t('recv.col.part') },
                  { key: 'category', label: t('ref.category') },
                  { key: 'size', label: t('ref.size') },
                  { key: 'tolerance', label: t('ref.tolerance'), align: 'right' },
                  { key: 'stock', label: t('chart.stock'), align: 'right' },
                  { key: 'safety', label: t('ref.minimum'), align: 'right' },
                ]}
                empty={
                  visibleParts.length === 0 ? (
                    <div className="px-5 pb-5">
                      <EmptyState
                        icon={<Boxes className="h-5 w-5" />}
                        title={t('ref.noMatch')}
                        description={t('recv.emptyFiltered')}
                      />
                    </div>
                  ) : undefined
                }
              >
                {/* Capped: past a few hundred rows the browser spends its time
                    laying out cells nobody scrolls to. The filters are how you
                    reach the rest, which is the point of having them. */}
                {visibleParts.slice(0, 300).map((part) => (
                  <tr key={part.id}>
                    <td className="numeric font-medium text-ink">{part.reference}</td>
                    <td className="truncate">{part.designation}</td>
                    <td className="text-2xs">{part.category?.name ?? '—'}</td>
                    <td>
                      <Badge severity={part.size_class === 'LARGE' ? 'warn' : 'info'}>
                        {part.size_class}
                      </Badge>
                    </td>
                    <td className="numeric text-right text-2xs">
                      {part.reception_tolerance_percent ?? 0} %
                    </td>
                    <td className="numeric text-right font-medium text-ink">
                      {formatNumber(part.stock?.quantity_available ?? 0)}
                    </td>
                    <td className="numeric text-right text-ink-3">
                      {formatNumber(part.safety_stock ?? 0)}
                    </td>
                  </tr>
                ))}
              </ReportTable>
            </ChartCard>
          ) : (
            <ChartCard
              title={t('ref.suppliers')}
              question={t('ref.suppliersQuestion')}
              bodyClassName="px-0 pb-0"
            >
              <ReportTable
                minWidth={620}
                columns={[
                  { key: 'code', label: t('common.reference') },
                  { key: 'name', label: t('recv.col.supplier') },
                  { key: 'country', label: t('ref.country') },
                  { key: 'lead', label: t('ref.leadTime'), align: 'right' },
                ]}
                empty={
                  visibleSuppliers.length === 0 ? (
                    <div className="px-5 pb-5">
                      <EmptyState
                        icon={<Truck className="h-5 w-5" />}
                        title={t('ref.noMatch')}
                        description={t('recv.emptyFiltered')}
                      />
                    </div>
                  ) : undefined
                }
              >
                {visibleSuppliers.map((supplier) => (
                  <tr key={supplier.id}>
                    <td className="numeric font-medium text-ink">{supplier.code}</td>
                    <td>{supplier.name}</td>
                    <td className="text-2xs">{supplier.country}</td>
                    <td className="numeric text-right">
                      {t('ref.days', { count: supplier.lead_time_days ?? 0 })}
                    </td>
                  </tr>
                ))}
              </ReportTable>
            </ChartCard>
          )}
        </>
      )}
    </div>
  )
}
