import { useMemo, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

import {
  AnalyticsComboChart,
  AnalyticsGauge,
  AnalyticsHeatmap,
  AnalyticsMatrix,
  AnalyticsPie,
  AnalyticsScatterXY,
  AnalyticsStackedBar,
  AnalyticsStockDemand,
  AnalyticsTreemap,
  AnalyticsWaterfall,
  ChartCard,
  Legend,
  SelectionDetail,
  WarehouseMap,
} from '@/features/analytics'
import { useI18n } from '@/i18n/I18nProvider'
import { useOverview } from './AnalyticsLayout'
import type { DetailFigure } from '@/features/analytics/SelectionDetail'
import type { MessageKey } from '@/i18n/messages'

/**
 * Page 2 - the stock itself, then the racks holding it.
 *
 * Two halves, each answering its own question. The stock half asks how much
 * there is, what it is made of and why it moved; the warehouse half asks where
 * it sits and which zone is under pressure.
 *
 * The page cross-filters: pick a family and the reference list narrows to it;
 * pick a zone and the matrix, the plan and the reference list follow. One
 * subject is selected at a time, because two simultaneous filters produce a
 * screen nobody can read back.
 */
export default function StockEntrepot() {
  const { t, formatDecimal, formatNumber } = useI18n()
  const { overview } = useOverview()
  const navigate = useNavigate()

  const [category, setCategory] = useState<string | null>(null)
  const [zone, setZone] = useState<string | null>(null)
  const [cell, setCell] = useState<{ reference: string; zone: string } | null>(null)

  const {
    stock_by_category,
    stock_totals,
    stock_vs_demand,
    stock_trend,
    stock_waterfall,
    warehouse,
    part_zone_matrix,
    zone_dwell,
  } = overview

  function selectCategory(next: string | null) {
    setCategory(next)
    setZone(null)
    setCell(null)
  }
  function selectZone(next: string | null) {
    setZone(next)
    setCategory(null)
    setCell(null)
  }
  function clear() {
    setCategory(null)
    setZone(null)
    setCell(null)
  }

  const filteredRows = useMemo(() => {
    if (category) return stock_vs_demand.filter((row) => row.category === category)
    if (zone) {
      const inZone = new Set(
        part_zone_matrix.rows
          .filter((row) => row.cells.some((item) => item.zone === zone && item.quantity > 0))
          .map((row) => row.reference),
      )
      return stock_vs_demand.filter((row) => inZone.has(row.reference))
    }
    return stock_vs_demand
  }, [stock_vs_demand, part_zone_matrix.rows, category, zone])

  const matrixRows = useMemo(
    () =>
      zone
        ? part_zone_matrix.rows.filter((row) =>
            row.cells.some((item) => item.zone === zone && item.quantity > 0),
          )
        : part_zone_matrix.rows,
    [part_zone_matrix.rows, zone],
  )

  const selectedZone = warehouse.zones.find((row) => row.zone === zone) ?? null

  const detail = (() => {
    if (cell) {
      return {
        title: cell.reference,
        subtitle: t('detail.cellSelected', { reference: cell.reference, zone: cell.zone }),
        risk: undefined,
        figures: [
          {
            labelKey: 'common.quantity' as const,
            value: formatNumber(
              part_zone_matrix.rows
                .find((row) => row.reference === cell.reference)
                ?.cells.find((item) => item.zone === cell.zone)?.quantity ?? 0,
            ),
          },
        ] as DetailFigure[],
        actionLabel: t('detail.openWarehouse'),
        onAction: () => navigate('/warehouse'),
      }
    }
    if (selectedZone) {
      return {
        title: `${t('warehouse.zone')} ${selectedZone.zone}`,
        subtitle: undefined,
        risk: selectedZone.severity,
        figures: [
          {
            labelKey: 'metric.occupancy' as const,
            value: `${formatDecimal(selectedZone.occupancy_percent, 1)} %`,
          },
          { labelKey: 'metric.free' as const, value: formatNumber(selectedZone.free) },
          {
            labelKey: 'warehouse.capacity' as const,
            value: formatNumber(selectedZone.capacity),
          },
          {
            labelKey: 'metric.locations' as const,
            value: formatNumber(selectedZone.locations),
          },
        ] as DetailFigure[],
        actionLabel: t('detail.openWarehouse'),
        onAction: () => navigate('/warehouse'),
      }
    }
    return null
  })()

  return (
    <div className="space-y-5">
      <AnimatePresence initial={false}>
        {detail && (
          <SelectionDetail
            key={detail.title}
            title={detail.title}
            subtitle={detail.subtitle}
            risk={detail.risk}
            figures={detail.figures}
            actionLabel={detail.actionLabel}
            onAction={detail.onAction}
            onClear={clear}
          />
        )}
      </AnimatePresence>

      {/* --- What the stock is made of, and how full the racks are --------- */}
      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard
          className="xl:col-span-2"
          title={t('card.treemap.title')}
          question={t('card.treemap.question')}
          footer={category ? t('filter.active', { value: category }) : undefined}
        >
          <AnalyticsTreemap
            nodes={stock_by_category.map((row) => ({
              key: row.label,
              label: row.label,
              value: row.value,
            }))}
            unit={` ${t('unit.pcs')}`}
            otherLabel={t('common.other')}
            emptyMessage={t('card.treemap.empty')}
            selectedKey={category}
            onSelect={(key) => selectCategory(key === category ? null : key)}
          />
        </ChartCard>

        <ChartCard
          title={t('card.occupancy.title')}
          question={t('card.occupancy.question')}
          delay={0.05}
          bodyClassName="px-5 pb-5 pt-2"
        >
          <div className="flex flex-col items-center gap-4">
            <AnalyticsGauge
              value={warehouse.occupancy_percent}
              label={t('card.warehouse.title')}
              warning={warehouse.warning_threshold}
              critical={warehouse.critical_threshold}
              targetLabel={t('gauge.thresholds', {
                warning: warehouse.warning_threshold,
                critical: warehouse.critical_threshold,
              })}
              higherIsWorse
            />
            <dl className="grid w-full grid-cols-3 gap-2 border-t border-line pt-3 text-center">
              <div>
                <dt className="text-[10px] text-ink-3">{t('metric.occupancy')}</dt>
                <dd className="numeric mt-0.5 text-xs font-semibold text-ink">
                  {formatNumber(warehouse.total_occupied)}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] text-ink-3">{t('warehouse.capacity')}</dt>
                <dd className="numeric mt-0.5 text-xs font-semibold text-ink">
                  {formatNumber(warehouse.total_capacity)}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] text-ink-3">{t('metric.free')}</dt>
                <dd className="numeric mt-0.5 text-xs font-semibold text-ok-soft">
                  {formatNumber(warehouse.total_capacity - warehouse.total_occupied)}
                </dd>
              </div>
            </dl>
          </div>
        </ChartCard>
      </div>

      {/* --- The reference list, narrowed by whatever is selected ---------- */}
      <ChartCard
        title={t('card.stockVsDemand.title')}
        question={t('card.stockVsDemand.question')}
        action={
          <Legend
            items={[
              { label: t('chart.stock'), className: 'bg-chart-1' },
              { label: t('chart.demand'), className: 'bg-warn' },
              { label: t('chart.uncovered'), className: 'bg-crit' },
            ]}
          />
        }
        delay={0.08}
      >
        <AnalyticsStockDemand
          rows={filteredRows}
          emptyMessage={t('card.stockVsDemand.empty')}
          onSelect={() => navigate('/warehouse')}
        />
      </ChartCard>

      {/* --- How it moved, and why ---------------------------------------- */}
      <ChartCard
        title={t('card.stockTrend.title')}
        question={t('card.stockTrend.question')}
        action={
          <Legend
            items={[
              { label: t('chart.stock'), className: 'bg-chart-1' },
              { label: t('chart.received'), className: 'bg-chart-2' },
              { label: t('chart.consumed'), className: 'bg-crit' },
            ]}
          />
        }
        delay={0.11}
      >
        <AnalyticsComboChart
          points={stock_trend}
          emptyMessage={t('card.stockTrend.empty')}
          labels={{
            stock: t('chart.stock'),
            received: t('chart.received'),
            consumed: t('chart.consumed'),
          }}
        />
      </ChartCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title={t('card.waterfall.title')}
          question={t('card.waterfall.question')}
          delay={0.14}
        >
          <AnalyticsWaterfall
            steps={stock_waterfall}
            emptyMessage={t('card.waterfall.empty')}
            labelFor={(key) => t(`waterfall.${key}` as MessageKey)}
          />
        </ChartCard>

        <ChartCard
          title={t('card.stockComposition.title')}
          question={t('card.stockComposition.question')}
          delay={0.17}
        >
          <AnalyticsStackedBar
            segments={[
              {
                key: 'available',
                label: t('chart.available'),
                value: stock_totals.free,
                className: 'bg-chart-2',
              },
              {
                key: 'reserved',
                label: t('chart.reserved'),
                value: stock_totals.reserved,
                className: 'bg-chart-3',
              },
            ]}
            emptyMessage={t('card.stockComposition.empty')}
          />
        </ChartCard>
      </div>

      {/* --- Where it sits ------------------------------------------------- */}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard title={t('card.map.title')} question={t('card.map.question')} delay={0.2}>
          <WarehouseMap
            zones={warehouse.zones}
            emptyMessage={t('card.map.empty')}
            selectedZone={zone}
            onSelectZone={(next) => selectZone(next === zone ? null : next)}
          />
        </ChartCard>

        <ChartCard
          title={t('card.zoneShare.title')}
          question={t('card.zoneShare.question')}
          delay={0.23}
        >
          {/* Three identities, assigned in value order and never cycled.
              Measured, not guessed: a fourth slot would have to be purple,
              which is reserved for the assistant and sits at dE 12 from blue -
              indistinguishable in a pie where every pair is adjacent. The rest
              folds into one neutral wedge, and the plan above still names every
              zone. Green and yellow are close under protanopia, so the legend
              beside the disc doubles as the value table. */}
          <AnalyticsPie
            segments={[...warehouse.zones]
              .sort((a, b) => b.occupied - a.occupied)
              .map((row, index) => ({
                key: row.zone,
                label: `${t('warehouse.zone')} ${row.zone}`,
                value: row.occupied,
                className:
                  ['text-chart-1', 'text-chart-2', 'text-chart-3'][index] ?? 'text-ink-3',
              }))}
            maxSlices={4}
            otherLabel={t('common.other')}
            unit={` ${t('unit.pcs')}`}
            emptyMessage={t('card.zoneShare.empty')}
            selectedKey={zone}
            onSelect={(key) => selectZone(key === zone ? null : key)}
          />
        </ChartCard>
      </div>

      <ChartCard
        title={t('card.matrix.title')}
        question={t('card.matrix.question')}
        delay={0.26}
        footer={zone ? t('filter.active', { value: `${t('warehouse.zone')} ${zone}` }) : undefined}
      >
        <AnalyticsMatrix
          zones={part_zone_matrix.zones}
          rows={matrixRows}
          zoneLabel={t('warehouse.zone')}
          emptyMessage={t('card.matrix.empty')}
          selected={cell}
          onSelectCell={(row, selectedZoneKey) =>
            setCell((current) =>
              current?.reference === row.reference && current?.zone === selectedZoneKey
                ? null
                : { reference: row.reference, zone: selectedZoneKey },
            )
          }
        />
      </ChartCard>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title={t('card.heatmap.title')}
          question={t('card.heatmap.question')}
          delay={0.29}
        >
          <AnalyticsHeatmap
            cells={
              zone ? warehouse.heatmap.filter((item) => item.zone === zone) : warehouse.heatmap
            }
            emptyMessage={t('card.heatmap.empty')}
            legend={{ empty: t('heatmap.empty'), full: t('heatmap.full') }}
            onSelect={() => navigate('/warehouse')}
          />
        </ChartCard>

        <ChartCard title={t('card.dwell.title')} question={t('card.dwell.question')} delay={0.32}>
          <AnalyticsScatterXY
            points={zone_dwell.map((point) => ({
              key: point.zone,
              label: `${t('warehouse.zone')} ${point.zone}`,
              x: point.occupancy_percent,
              y: point.average_days,
              size: point.quantity,
              severity: point.severity,
            }))}
            emptyMessage={t('card.dwell.empty')}
            axisLabels={{
              x: t('chart.axis.occupancy'),
              y: t('chart.axis.dwellDays'),
            }}
            formatX={(value) => `${formatDecimal(value, 0)}`}
            formatY={(value) => `${formatDecimal(value, 0)}`}
            tooltipRows={(point) => {
              const row = zone_dwell.find((item) => item.zone === point.key)
              return [
                {
                  label: t('metric.occupancy'),
                  value: `${formatDecimal(row?.occupancy_percent ?? 0, 1)} %`,
                },
                {
                  label: t('chart.axis.dwellDays'),
                  value: formatDecimal(row?.average_days ?? 0, 1),
                },
                { label: t('flow.lots'), value: formatNumber(row?.lots ?? 0) },
              ]
            }}
            selectedKey={zone}
            onSelect={(key) => selectZone(key === zone ? null : key)}
          />
        </ChartCard>
      </div>
    </div>
  )
}
