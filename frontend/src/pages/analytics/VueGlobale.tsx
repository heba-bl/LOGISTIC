import { useMemo, useState } from 'react'
import { AnimatePresence } from 'framer-motion'
import { useNavigate } from 'react-router-dom'

import { HBarChart } from '@/features/analytics/bars'
import { AnalyticsColumnPairs } from '@/features/analytics/columns'
import { DonutChart } from '@/features/analytics/circular'
import { DecisionList, FlowFunnel } from '@/features/analytics/decision'
import { KpiCard } from '@/features/analytics/KpiCard'
import { ChartCard, Legend } from '@/features/analytics/primitives'
import { SelectionDetail, type DetailFigure } from '@/features/analytics/SelectionDetail'
import { useI18n } from '@/i18n/I18nProvider'
import { useOverview } from './AnalyticsLayout'
import type { Decision } from '@/types/overview'

/**
 * The page a logistics manager opens first.
 *
 * It answers five questions in order and stops: what is the situation, what is
 * about to run out, is the incoming quality holding, where is the flow jammed,
 * and what should be done in the next hour. Everything finer - the waterfall,
 * the scatter, the heatmap - lives on the three detail tabs, because a screen
 * that shows everything ranks nothing.
 *
 * Clicking any mark filters the page onto that subject. The selection strip
 * then carries its figures and the way out to the screen that can act on it.
 */

const STAGE_ROUTES: Record<string, string> = {
  RECEIVING: '/receiving',
  INSPECTION: '/inspection',
  QUALITY: '/quality',
  WAREHOUSE: '/warehouse',
  PRODUCTION: '/production',
}

const DECISION_ROUTES: Record<string, string> = {
  stock: '/warehouse',
  warehouse: '/warehouse',
  quality: '/quality',
}

export default function VueGlobale() {
  const { t, formatDecimal, formatNumber } = useI18n()
  const { overview } = useOverview()
  const navigate = useNavigate()

  const { kpis, quality, warehouse, flow, stock_vs_demand, decisions } = overview

  const [partId, setPartId] = useState<number | null>(null)
  const [qualityState, setQualityState] = useState<string | null>(null)
  const [zone, setZone] = useState<string | null>(null)

  //: One subject at a time - two active filters and nobody knows what they see.
  function selectPart(next: number | null) {
    setPartId(next)
    setQualityState(null)
    setZone(null)
  }
  function selectQuality(next: string | null) {
    setQualityState(next)
    setPartId(null)
    setZone(null)
  }
  function selectZone(next: string | null) {
    setZone(next)
    setPartId(null)
    setQualityState(null)
  }
  function clear() {
    setPartId(null)
    setQualityState(null)
    setZone(null)
  }

  const part = useMemo(
    () => stock_vs_demand.find((row) => row.part_id === partId) ?? null,
    [stock_vs_demand, partId],
  )
  const selectedZone = useMemo(
    () => warehouse.zones.find((row) => row.zone === zone) ?? null,
    [warehouse.zones, zone],
  )

  //: Blocked lots and stockout risk going up is not an improvement.
  const riseIsGood = (id: string) => !['blocked-lots', 'production-risk'].includes(id)

  const qualitySegments = [
    {
      key: 'conform',
      label: t('status.CONFORM'),
      value: quality.conform,
      className: 'text-ok',
    },
    {
      key: 'non_conform',
      label: t('status.NON_CONFORM'),
      value: quality.non_conform,
      className: 'text-warn',
    },
    {
      key: 'red_cage',
      label: t('status.RED_CAGE'),
      value: quality.red_cage,
      className: 'text-crit',
    },
  ]

  const detail = buildDetail()

  function buildDetail() {
    if (part) {
      const figures: DetailFigure[] = [
        { labelKey: 'chart.stock', value: formatNumber(part.available) },
        { labelKey: 'chart.demand', value: formatNumber(part.demand) },
        {
          labelKey: 'chart.gap',
          value: `${part.gap > 0 ? '+' : ''}${formatNumber(part.gap)}`,
          tone: part.gap < 0 ? 'crit' : 'ok',
        },
      ]
      if (part.coverage_days !== null) {
        figures.push({
          labelKey: 'chart.coverage',
          value: t('chart.coverageDays', { days: formatDecimal(part.coverage_days, 1) }),
          tone: part.coverage_days < 2 ? 'crit' : part.coverage_days < 5 ? 'warn' : 'ok',
        })
      }
      return {
        title: part.reference,
        subtitle: part.designation,
        risk: part.risk,
        figures,
        actionLabel: t('detail.openStock'),
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
            tone:
              selectedZone.severity === 'CRITICAL'
                ? ('crit' as const)
                : selectedZone.severity === 'WARNING'
                  ? ('warn' as const)
                  : ('ok' as const),
          },
          { labelKey: 'metric.free' as const, value: formatNumber(selectedZone.free) },
          {
            labelKey: 'warehouse.capacity' as const,
            value: formatNumber(selectedZone.capacity),
          },
        ],
        actionLabel: t('detail.openWarehouse'),
        onAction: () => navigate('/warehouse'),
      }
    }

    if (qualityState) {
      const segment = qualitySegments.find((item) => item.key === qualityState)
      if (!segment) return null
      const total = qualitySegments.reduce((sum, item) => sum + item.value, 0) || 1
      return {
        title: segment.label,
        subtitle: undefined,
        risk: undefined,
        figures: [
          { labelKey: 'common.quantity' as const, value: formatNumber(segment.value) },
          {
            labelKey: 'quality.share' as const,
            value: `${formatDecimal((segment.value / total) * 100, 1)} %`,
          },
        ],
        actionLabel: t('detail.openQuality'),
        onAction: () => navigate('/quality'),
      }
    }

    return null
  }

  function openDecision(decision: Decision) {
    navigate(DECISION_ROUTES[decision.target] ?? '/mission-control')
  }

  return (
    <div className="space-y-5">
      {/* --- 1. What is the situation? ----------------------------------- */}
      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        {kpis.map((kpi, index) => (
          <KpiCard key={kpi.id} kpi={kpi} index={index} riseIsGood={riseIsGood(kpi.id)} />
        ))}
      </section>

      {/* The answer to whatever was just clicked. */}
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

      {/* --- 2. What is about to run out? -------------------------------- */}
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
        delay={0.05}
      >
        <AnalyticsColumnPairs
          rows={stock_vs_demand.slice(0, 6)}
          emptyMessage={t('card.stockVsDemand.empty')}
          selectedId={partId}
          onSelect={(next) => selectPart(next === partId ? null : next)}
        />
      </ChartCard>

      {/* --- 3. Is what arrives good, and is there room for it? ---------- */}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title={t('card.quality.title')}
          question={t('card.quality.question')}
          delay={0.08}
        >
          <DonutChart
            segments={qualitySegments}
            centreValue={
              quality.conformity_percent !== null
                ? `${formatDecimal(quality.conformity_percent, 1)} %`
                : '—'
            }
            centreLabel={t('kpi.conformity')}
            emptyMessage={t('card.quality.empty')}
            selectedKey={qualityState}
            onSelect={(key) => selectQuality(key === qualityState ? null : key)}
          />
        </ChartCard>

        <ChartCard
          title={t('card.warehouse.title')}
          question={t('card.warehouse.question')}
          action={
            <span className="numeric text-2xs font-semibold text-ink-2">
              {formatDecimal(warehouse.occupancy_percent, 1)} %
            </span>
          }
          delay={0.11}
        >
          <HBarChart
            points={warehouse.zones.map((row) => ({
              key: row.zone,
              label: `${t('warehouse.zone')} ${row.zone}`,
              value: row.occupancy_percent,
              severity: row.severity,
              caption: t('warehouse.freeOf', {
                free: formatNumber(row.free),
                capacity: formatNumber(row.capacity),
              }),
            }))}
            unit=" %"
            max={100}
            colouring="state"
            emptyMessage={t('card.warehouse.empty')}
            selected={zone}
            onSelect={(next) => selectZone(next === zone ? null : next)}
          />
        </ChartCard>
      </div>

      {/* --- 4. Where is the flow jammed? -------------------------------- */}
      <ChartCard title={t('card.flow.title')} question={t('card.flow.question')} delay={0.14}>
        <FlowFunnel
          flow={flow}
          emptyMessage={t('card.flow.empty')}
          onSelectStage={(stage) => navigate(STAGE_ROUTES[stage] ?? '/mission-control')}
        />
      </ChartCard>

      {/* --- 5. What do I do now? ---------------------------------------- */}
      <ChartCard
        title={t('card.now.title')}
        question={t('card.now.question')}
        delay={0.17}
      >
        <DecisionList
          decisions={decisions.slice(0, 5)}
          emptyMessage={t('decision.none')}
          onOpen={openDecision}
          compact
        />
      </ChartCard>
    </div>
  )
}
