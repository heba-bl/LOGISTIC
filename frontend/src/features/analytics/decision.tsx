/**
 * The bottom of the reading order: where does the flow jam, what is at risk,
 * and what should be done first.
 *
 * These three components are the point of the whole screen. Everything above
 * them describes a situation; these say what to do about it.
 */

import { Fragment } from 'react'
import { motion } from 'framer-motion'
import {
  ArrowRight,
  Boxes,
  Sparkles,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Factory,
  PackageSearch,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import {
  ChartEmpty,
  RiskChip,
  STATE_BG,
  STATE_BORDER,
  STATE_TEXT,
  useUnitLabel,
} from './primitives'
import type { MessageKey } from '@/i18n/messages'
import type {
  Decision,
  FlowBlock,
  Severity4,
  StockDemandRow,
} from '@/types/overview'

const STAGE_ICONS: Record<string, LucideIcon> = {
  RECEIVING: PackageSearch,
  INSPECTION: ClipboardCheck,
  QUALITY: ShieldCheck,
  WAREHOUSE: Boxes,
  PRODUCTION: Factory,
}

// ------------------------------------------------------------------- funnel
/**
 * Five blocks and four arrows: where the parts are, and where they are waiting.
 *
 * Each block is a plain card - stage, volume, lot count - so it is read, not
 * decoded. The arrow between two blocks carries the measured hand-over time,
 * and the slowest one wears the warning colour, so the jam is visible without
 * comparing four numbers by eye.
 */
export function FlowFunnel({
  flow,
  emptyMessage,
  onSelectStage,
}: {
  flow: FlowBlock
  emptyMessage: string
  onSelectStage?: (stageId: string) => void
}) {
  const { t, formatDecimal, formatNumber } = useI18n()

  if (flow.stages.length === 0) return <ChartEmpty message={emptyMessage} />

  return (
    <div className="space-y-3">
      <div className="flex flex-col items-stretch gap-1.5 xl:flex-row xl:items-center">
        {flow.stages.map((stage, index) => {
          const Icon = STAGE_ICONS[stage.id] ?? Boxes
          const transition = flow.transitions[index]
          const Element = onSelectStage ? 'button' : 'div'

          return (
            <Fragment key={stage.id}>
              <motion.div
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: index * 0.07, ease: [0.22, 1, 0.36, 1] }}
                className="flex-1"
              >
                <Element
                  type={onSelectStage ? 'button' : undefined}
                  onClick={onSelectStage ? () => onSelectStage(stage.id) : undefined}
                  className={cn(
                    'w-full rounded-xl border bg-panel p-3.5 text-left transition-all duration-200',
                    stage.anomalies > 0 ? 'border-warn/40' : 'border-line',
                    onSelectStage &&
                      'cursor-pointer hover:-translate-y-px hover:border-accent/45 hover:shadow-lift',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span className="grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-accent/10">
                      <Icon className="h-3.5 w-3.5 text-accent" strokeWidth={2} />
                    </span>
                    <span className="truncate text-2xs font-semibold uppercase tracking-wider text-ink-2">
                      {t(`stage.${stage.id}` as MessageKey)}
                    </span>
                  </div>

                  <p className="mt-2.5 flex items-baseline gap-1">
                    <span className="numeric text-lg font-semibold leading-none text-ink">
                      {formatNumber(stage.lot_count)}
                    </span>
                    <span className="text-[11px] text-ink-3">{t('flow.lots')}</span>
                  </p>

                  <p className="numeric mt-1 text-[11px] text-ink-3">
                    {formatNumber(stage.quantity)} {t('unit.pcs')}
                  </p>

                  {stage.anomalies > 0 && (
                    <p className="mt-2 flex items-center gap-1.5 text-[11px] font-medium text-warn-soft">
                      <span className="h-1.5 w-1.5 rounded-full bg-warn" />
                      {t('flow.waiting', { count: stage.anomalies })}
                    </p>
                  )}
                </Element>
              </motion.div>

              {transition && index < flow.stages.length - 1 && (
                <div className="flex shrink-0 flex-row items-center justify-center gap-1.5 py-0.5 xl:w-16 xl:flex-col xl:gap-0.5 xl:py-0">
                  <ChevronDown
                    className={cn(
                      'h-4 w-4 xl:hidden',
                      transition.is_bottleneck ? 'text-warn' : 'text-ink-3',
                    )}
                    strokeWidth={2.2}
                  />
                  <ChevronRight
                    className={cn(
                      'hidden h-4 w-4 xl:block',
                      transition.is_bottleneck ? 'text-warn' : 'text-ink-3',
                    )}
                    strokeWidth={2.2}
                  />
                  <span
                    className={cn(
                      'numeric whitespace-nowrap text-[11px] font-medium',
                      transition.is_bottleneck ? 'text-warn-soft' : 'text-ink-3',
                    )}
                  >
                    {transition.sample_size > 0
                      ? `${formatDecimal(transition.average_hours, 1)} h`
                      : '—'}
                  </span>
                </div>
              )}
            </Fragment>
          )
        })}
      </div>

      {flow.bottleneck && (
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg bg-warn/10 px-3 py-2 text-2xs text-ink-2">
          <span className="font-semibold text-warn-soft">{t('flow.bottleneck')}</span>
          <span className="font-medium text-ink">
            {t(`flow.transition.${flow.bottleneck}` as MessageKey)}
          </span>
          <span className="numeric font-semibold text-warn-soft">
            {flow.bottleneck_hours !== null ? formatDecimal(flow.bottleneck_hours, 1) : '—'} h
          </span>
        </p>
      )}
    </div>
  )
}


// ----------------------------------------------------------- priority matrix
export function PriorityTable({
  rows,
  emptyMessage,
  onSelect,
}: {
  rows: StockDemandRow[]
  emptyMessage: string
  onSelect?: (partId: number) => void
}) {
  const { t, formatDecimal, formatNumber } = useI18n()

  if (rows.length === 0) return <ChartEmpty message={emptyMessage} />

  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-[720px]">
        <thead>
          <tr>
            <th>{t('common.reference')}</th>
            <th className="text-right">{t('chart.stock')}</th>
            <th className="text-right">{t('chart.demand')}</th>
            <th className="text-right">{t('chart.coverage')}</th>
            <th>{t('table.risk')}</th>
            <th>{t('table.action')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr
              key={row.part_id}
              onClick={onSelect ? () => onSelect(row.part_id) : undefined}
              className={onSelect ? 'cursor-pointer' : undefined}
            >
              <td>
                <span className="numeric text-xs font-medium text-ink">{row.reference}</span>
                <span className="block truncate text-2xs text-ink-3">{row.designation}</span>
              </td>
              <td className="numeric text-right font-medium text-ink">
                {formatNumber(row.available)}
              </td>
              <td className="numeric text-right">{formatNumber(row.demand)}</td>
              <td className="numeric text-right">
                {row.coverage_days !== null
                  ? t('chart.coverageDays', {
                      days: formatDecimal(row.coverage_days, 1),
                    })
                  : '—'}
              </td>
              <td>
                <RiskChip risk={row.risk} />
              </td>
              <td className="text-2xs">{t(row.action_key as MessageKey)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

//: Which entries come from the assistant's reasoning rather than from a plain
//: fact on the table. Purple is reserved for exactly this, so a suggestion is
//: never mistaken for a measurement.
const AI_KINDS = new Set(['SHORTAGE_RISK', 'OPTIMIZATION', 'PRIORITY'])

// ----------------------------------------------------------------- decisions
export function DecisionList({
  decisions,
  emptyMessage,
  onOpen,
  compact = false,
}: {
  decisions: Decision[]
  emptyMessage: string
  onOpen?: (decision: Decision) => void
  /**
   * Drop the reasoning sentence.
   *
   * On the overview this list has to be scannable in a couple of seconds, and a
   * paragraph per row defeats that. The figures stay - they are what makes the
   * item credible - and the full reasoning waits on the detail tab, where the
   * reader has already decided to dig.
   */
  compact?: boolean
}) {
  const { t, formatNumber } = useI18n()
  const unitLabel = useUnitLabel()

  if (decisions.length === 0) return <ChartEmpty message={emptyMessage} />

  return (
    <ol className="divide-y divide-line">
      {decisions.map((decision, index) => (
        <motion.li
          key={`${decision.kind}-${decision.subject}`}
          initial={{ opacity: 0, x: -6 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.3, delay: index * 0.05 }}
          className="py-3.5 first:pt-0 last:pb-0"
        >
          <div className="flex items-start gap-3.5">
            {/* The rank, so the list reads as an order rather than a pile. */}
            <span
              className={cn(
                'numeric mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border text-2xs font-semibold',
                STATE_BORDER[decision.severity],
                STATE_TEXT[decision.severity],
              )}
            >
              {String(decision.rank).padStart(2, '0')}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="numeric text-xs font-semibold text-ink">{decision.subject}</span>
                <span className="inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[11px] font-medium text-ink-2">
                  <span className={cn('h-1.5 w-1.5 rounded-full', STATE_BG[decision.severity])} />
                  {t(`decision.kind.${decision.kind}` as MessageKey)}
                </span>
                {AI_KINDS.has(decision.kind) && (
                  <span
                    className="inline-flex items-center gap-1 rounded bg-ai/12 px-1.5 py-0.5 text-[11px] font-medium text-ai-soft"
                    title={t('decision.fromAi')}
                  >
                    <Sparkles className="h-3 w-3" strokeWidth={2.2} />
                    {t('decision.ai')}
                  </span>
                )}
              </div>

              {/* Figures first: a recommendation without them is an opinion. */}
              {decision.metrics.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-x-4 gap-y-1">
                  {decision.metrics.map((metric) => (
                    <span key={metric.key} className="text-[11px] text-ink-3">
                      {t(metric.key as MessageKey)}{' '}
                      <span className="numeric font-semibold text-ink-2">
                        {typeof metric.value === 'number'
                          ? formatNumber(metric.value)
                          : (metric.value ?? '—')}
                        {metric.unit ? ` ${unitLabel(metric.unit)}` : ''}
                      </span>
                    </span>
                  ))}
                </div>
              )}

              {!compact && (
                <p className="mt-1.5 text-2xs leading-relaxed text-ink-2">
                  <span className="font-semibold text-ink-3">{t('decision.why')} </span>
                  {decision.reason_key
                    ? t(decision.reason_key as MessageKey, decision.reason_values)
                    : (decision.reason ?? '—')}
                </p>
              )}

              <button
                type="button"
                onClick={onOpen ? () => onOpen(decision) : undefined}
                title={
                  compact
                    ? (decision.reason_key
                        ? t(decision.reason_key as MessageKey, decision.reason_values)
                        : (decision.reason ?? undefined))
                    : undefined
                }
                className={cn(
                  'inline-flex min-h-[34px] cursor-pointer items-center gap-1.5 rounded-lg px-3 text-[11px] font-medium transition-colors',
                  compact
                    ? 'mt-1.5 text-accent hover:bg-accent/10'
                    : 'mt-2 border border-accent/30 bg-accent-dim text-accent hover:border-accent/60',
                )}
              >
                {t(decision.action_key as MessageKey)}
                <ArrowRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </motion.li>
      ))}
    </ol>
  )
}

// --------------------------------------------------------------- zone bars
export function ZoneOccupancy({
  zones,
  emptyMessage,
  saturationLabel,
  onSelect,
}: {
  zones: {
    zone: string
    capacity: number
    occupied: number
    free: number
    locations: number
    references: number
    occupancy_percent: number
    severity: Severity4
  }[]
  emptyMessage: string
  saturationLabel: string
  onSelect?: (zone: string) => void
}) {
  const { t, formatDecimal, formatNumber } = useI18n()

  if (zones.length === 0) return <ChartEmpty message={emptyMessage} />

  return (
    <ul className="space-y-3">
      {zones.map((zone) => {
        const Element = onSelect ? 'button' : 'div'
        return (
          <li key={zone.zone}>
            <Element
              type={onSelect ? 'button' : undefined}
              onClick={onSelect ? () => onSelect(zone.zone) : undefined}
              className={cn(
                'block w-full rounded-md px-1.5 py-1 text-left transition-colors',
                onSelect && 'cursor-pointer hover:bg-elevated',
              )}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="numeric text-xs font-semibold text-ink">
                  {t('warehouse.zone')} {zone.zone}
                </span>
                <span className="numeric text-xs font-semibold text-ink">
                  {formatDecimal(zone.occupancy_percent, 1)} %
                </span>
              </div>

              <div className="mt-1 h-2.5 w-full overflow-hidden rounded-full bg-line/60">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(zone.occupancy_percent, 100)}%` }}
                  transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                  className={cn('h-full rounded-full', STATE_BG[zone.severity])}
                />
              </div>

              <p className="mt-1 flex flex-wrap gap-x-3 text-[11px] text-ink-3">
                <span className="numeric">
                  {formatNumber(zone.occupied)} / {formatNumber(zone.capacity)}
                </span>
                <span>{t('warehouse.free', { value: formatNumber(zone.free) })}</span>
                <span>{t('warehouse.locations', { count: zone.locations })}</span>
                <span>{t('warehouse.references', { count: zone.references })}</span>
              </p>

              {zone.severity === 'CRITICAL' && (
                <p className="mt-1 text-[11px] font-medium text-crit-soft">{saturationLabel}</p>
              )}
            </Element>
          </li>
        )
      })}
    </ul>
  )
}
