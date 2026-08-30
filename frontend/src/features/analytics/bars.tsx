/**
 * Bar forms: magnitude by category, and stock measured against demand.
 *
 * Horizontal, because the labels are words rather than dates, and because a
 * horizontal bar leaves room for the value to sit beside the mark - the direct
 * label that the muted palette requires.
 */

import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { ChartEmpty, RAMP_BG, RiskChip, STATE_BG, rampStep } from './primitives'
import type { Severity4 } from '@/types/overview'

interface HBarPoint {
  key: string
  label: string
  value: number
  /** Optional second line under the label. */
  caption?: string
  /** Only when the value genuinely encodes a state. */
  severity?: Severity4
  share?: number
}

interface HBarChartProps {
  points: HBarPoint[]
  unit?: string
  emptyMessage: string
  /** Highlighted key - the rest dims, so a click reads as a filter. */
  selected?: string | null
  onSelect?: (key: string) => void
  /** Magnitude uses the sequential ramp; identity would use the series slots. */
  colouring?: 'ramp' | 'state'
  max?: number
}

export function HBarChart({
  points,
  unit,
  emptyMessage,
  selected,
  onSelect,
  colouring = 'ramp',
  max,
}: HBarChartProps) {
  const { formatDecimal, formatNumber } = useI18n()

  if (points.length === 0) return <ChartEmpty message={emptyMessage} />

  const ceiling = max ?? Math.max(...points.map((point) => point.value), 1)

  return (
    <ul className="space-y-2.5">
      {points.map((point, index) => {
        const ratio = ceiling > 0 ? (point.value / ceiling) * 100 : 0
        const dimmed = selected != null && selected !== point.key
        const fill =
          colouring === 'state' && point.severity
            ? STATE_BG[point.severity]
            : RAMP_BG[rampStep(ratio)]

        const Row = onSelect ? 'button' : 'div'

        return (
          <li key={point.key}>
            <Row
              type={onSelect ? 'button' : undefined}
              onClick={onSelect ? () => onSelect(point.key) : undefined}
              className={cn(
                'group block w-full text-left transition-opacity',
                dimmed && 'opacity-35',
                onSelect && 'cursor-pointer',
              )}
              aria-pressed={onSelect ? selected === point.key : undefined}
            >
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-2xs font-medium text-ink-2" title={point.label}>
                  {point.label}
                </span>
                <span className="numeric shrink-0 text-2xs font-semibold text-ink">
                  {formatNumber(point.value)}
                  {unit && <span className="ml-0.5 font-normal text-ink-3">{unit}</span>}
                  {point.share !== undefined && (
                    <span className="ml-1.5 font-normal text-ink-3">
                      {formatDecimal(point.share, 1)} %
                    </span>
                  )}
                </span>
              </div>

              <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-line/60">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.max(ratio, point.value > 0 ? 1.5 : 0)}%` }}
                  transition={{ duration: 0.6, delay: index * 0.03, ease: [0.22, 1, 0.36, 1] }}
                  className={cn('h-full rounded-full', fill)}
                />
              </div>

              {point.caption && (
                <p className="mt-0.5 truncate text-[10px] text-ink-3">{point.caption}</p>
              )}
            </Row>
          </li>
        )
      })}
    </ul>
  )
}

// ------------------------------------------------------- stock versus demand
interface StockDemandBarsProps {
  rows: {
    part_id: number
    reference: string
    designation: string
    available: number
    demand: number
    gap: number
    coverage_days: number | null
    risk: Severity4
  }[]
  emptyMessage: string
  onSelect?: (partId: number) => void
  /** The reference the dashboard is currently filtered on. */
  selectedId?: number | null
}

/**
 * The chart the whole screen exists for: can this reference still feed the line?
 *
 * Blue is what is on the shelf, and the demand bar answers in its own colour -
 * amber while the stock still covers it, red the moment it does not. So the
 * verdict is legible before any number is read, and the number is there anyway.
 */
export function StockDemandBars({
  rows,
  emptyMessage,
  onSelect,
  selectedId,
}: StockDemandBarsProps) {
  const { t, formatDecimal, formatNumber } = useI18n()

  if (rows.length === 0) return <ChartEmpty message={emptyMessage} />

  // Each row is scaled to its own pair, not to the largest reference on screen.
  // A shared scale looks rigorous and reads terribly here: a fastener held by
  // the thousand flattens the suspension arm that has 0 against a demand of 12
  // into an invisible sliver - and that sliver is the line about to stop. The
  // question this chart answers is "does THIS reference cover ITS demand", so
  // that is the comparison the length encodes. Absolute magnitudes are printed
  // beside every bar and ranked in the priority table underneath.

  return (
    <ul className="space-y-3.5">
      {rows.map((row, index) => {
        const ceiling = Math.max(row.available, row.demand, 1)
        const uncovered = row.available < row.demand
        const selected = selectedId === row.part_id
        const dimmed = selectedId != null && !selected
        const Row = onSelect ? 'button' : 'div'
        return (
          <li key={row.part_id}>
            <Row
              type={onSelect ? 'button' : undefined}
              onClick={onSelect ? () => onSelect(row.part_id) : undefined}
              aria-pressed={onSelect ? selected : undefined}
              className={cn(
                'block w-full rounded-lg border px-2.5 py-2 text-left transition-all duration-200',
                selected
                  ? 'border-accent/45 bg-accent/[0.06]'
                  : 'border-transparent hover:border-line hover:bg-elevated',
                dimmed && 'opacity-45',
                onSelect && 'cursor-pointer',
              )}
            >
              <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                <div className="min-w-0">
                  <span className="numeric text-xs font-semibold text-ink">{row.reference}</span>
                  <span className="ml-2 truncate text-2xs text-ink-3">{row.designation}</span>
                </div>
                <div className="flex items-center gap-2">
                  {row.coverage_days !== null && (
                    <span className="numeric text-2xs text-ink-3">
                      {t('chart.coverageDays', {
                        days: formatDecimal(row.coverage_days, 1),
                      })}
                    </span>
                  )}
                  <RiskChip risk={row.risk} />
                </div>
              </div>

              <div className="mt-1.5 space-y-1">
                <BarLine
                  label={t('chart.stock')}
                  value={row.available}
                  ceiling={ceiling}
                  className="bg-chart-1"
                  delay={index * 0.03}
                  formatValue={formatNumber}
                />
                <BarLine
                  label={t('chart.demand')}
                  value={row.demand}
                  ceiling={ceiling}
                  className={uncovered ? 'bg-crit' : 'bg-warn'}
                  delay={index * 0.03 + 0.05}
                  formatValue={formatNumber}
                />
              </div>

              <p className="mt-1.5 flex items-center gap-1.5">
                <span
                  className={cn(
                    'numeric rounded px-1.5 py-0.5 text-[10px] font-semibold',
                    uncovered ? 'bg-crit/12 text-crit-soft' : 'bg-ok/12 text-ok-soft',
                  )}
                >
                  {row.gap > 0 ? '+' : ''}
                  {formatNumber(row.gap)}
                </span>
                <span className="text-[10px] text-ink-3">{t('chart.gap')}</span>
              </p>
            </Row>
          </li>
        )
      })}
    </ul>
  )
}

function BarLine({
  label,
  value,
  ceiling,
  className,
  delay,
  formatValue,
}: {
  label: string
  value: number
  ceiling: number
  className: string
  delay: number
  formatValue: (value: number) => string
}) {
  const ratio = ceiling > 0 ? (value / ceiling) * 100 : 0
  return (
    <div className="flex items-center gap-2">
      <span className="w-16 shrink-0 text-[10px] uppercase tracking-wider text-ink-3">
        {label}
      </span>
      <div className="h-2 flex-1 overflow-hidden rounded-full bg-line/60">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${Math.max(ratio, value > 0 ? 1.5 : 0)}%` }}
          transition={{ duration: 0.6, delay, ease: [0.22, 1, 0.36, 1] }}
          className={cn('h-full rounded-full', className)}
        />
      </div>
      <span className="numeric w-14 shrink-0 text-right text-2xs font-medium text-ink">
        {formatValue(value)}
      </span>
    </div>
  )
}

// -------------------------------------------------------------- stacked bar
interface StackedBarProps {
  segments: { key: string; label: string; value: number; className: string }[]
  total?: number
  emptyMessage: string
}

/** Composition of a single whole - one bar, segments separated by a 2px gap. */
export function StackedBar({ segments, total, emptyMessage }: StackedBarProps) {
  const { formatDecimal, formatNumber } = useI18n()
  const sum = total ?? segments.reduce((accumulator, item) => accumulator + item.value, 0)

  if (sum <= 0) return <ChartEmpty message={emptyMessage} />

  return (
    <div>
      <div className="flex h-3 w-full gap-0.5 overflow-hidden rounded-full">
        {segments
          .filter((segment) => segment.value > 0)
          .map((segment) => (
            <motion.div
              key={segment.key}
              initial={{ width: 0 }}
              animate={{ width: `${(segment.value / sum) * 100}%` }}
              transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
              className={cn('h-full first:rounded-l-full last:rounded-r-full', segment.className)}
              title={`${segment.label}: ${formatNumber(segment.value)}`}
            />
          ))}
      </div>
      <ul className="mt-3 space-y-1.5">
        {segments.map((segment) => (
          <li key={segment.key} className="flex items-center gap-2 text-2xs">
            <span className={cn('h-2 w-2 shrink-0 rounded-[2px]', segment.className)} />
            <span className="text-ink-2">{segment.label}</span>
            <span className="numeric ml-auto font-medium text-ink">
              {formatNumber(segment.value)}
            </span>
            <span className="numeric w-12 text-right text-ink-3">
              {formatDecimal((segment.value / sum) * 100, 1)} %
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
