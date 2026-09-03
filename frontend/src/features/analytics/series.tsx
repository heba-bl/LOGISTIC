/**
 * Time and structure: the combo chart, the waterfall, the heatmap, the scatter.
 *
 * Each of these exists to answer one question that a bar chart cannot:
 *   combo     - is consumption rising while the stock falls?
 *   waterfall - why did the stock end where it did?
 *   heatmap   - which corner of the warehouse is under pressure?
 *   scatter   - which references combine heavy use with a thin balance?
 */

import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import {
  ChartEmpty,
  ChartTooltip,
  RAMP_BG,
  RAMP_TEXT,
  STATE_FILL,
  rampStep,
} from './primitives'
import type { HeatCell, ScatterPoint, StockPoint, WaterfallStep } from '@/types/overview'

// ----------------------------------------------------------------- combo
interface ComboChartProps {
  points: StockPoint[]
  emptyMessage: string
  labels: { stock: string; received: string; consumed: string }
}

/**
 * Daily flows as bars, the resulting balance as a line.
 *
 * Both measures share one axis on purpose. They are the same unit - pieces -
 * so a second scale would be a lie: the point is precisely to see the balance
 * fall while the outbound bars grow.
 */
export function ComboChart({ points, emptyMessage, labels }: ComboChartProps) {
  const { formatDay, formatNumber } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (points.length === 0) return <ChartEmpty message={emptyMessage} />

  const width = 720
  const height = 220
  const padding = { top: 16, right: 8, bottom: 26, left: 8 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const ceiling = Math.max(
    ...points.map((point) => Math.max(point.stock, point.received, point.consumed)),
    1,
  )

  const slot = innerWidth / points.length
  const barWidth = Math.max(Math.min(slot * 0.28, 14), 2)

  const x = (index: number) => padding.left + slot * index + slot / 2
  const y = (value: number) => padding.top + innerHeight - (value / ceiling) * innerHeight

  const line = points.map((point, index) => `${x(index)},${y(point.stock)}`).join(' ')

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={labels.stock}>
        {/* Three recessive gridlines - enough to read a level, not a grid. */}
        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1={padding.left}
            x2={width - padding.right}
            y1={padding.top + innerHeight * fraction}
            y2={padding.top + innerHeight * fraction}
            className="stroke-line"
            strokeWidth={1}
            strokeDasharray="2 4"
          />
        ))}

        {points.map((point, index) => (
          <g key={point.date}>
            <rect
              x={x(index) - barWidth - 1}
              y={y(point.received)}
              width={barWidth}
              height={Math.max(padding.top + innerHeight - y(point.received), 0)}
              rx={2}
              className="fill-chart-2"
            />
            <rect
              x={x(index) + 1}
              y={y(point.consumed)}
              width={barWidth}
              height={Math.max(padding.top + innerHeight - y(point.consumed), 0)}
              rx={2}
              className="fill-crit"
            />
          </g>
        ))}

        <motion.polyline
          points={line}
          fill="none"
          strokeWidth={2}
          strokeLinecap="round"
          strokeLinejoin="round"
          vectorEffect="non-scaling-stroke"
          className="stroke-chart-1"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        />

        {points.map((point, index) => (
          <g key={`hit-${point.date}`}>
            <rect
              x={padding.left + slot * index}
              y={padding.top}
              width={slot}
              height={innerHeight}
              fill="transparent"
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            />
            {hover === index && (
              <circle
                cx={x(index)}
                cy={y(point.stock)}
                r={4}
                className="fill-chart-1 stroke-panel"
                strokeWidth={2}
              />
            )}
          </g>
        ))}

        {/* Only the two ends are labelled; the tooltip carries the rest. */}
        {[0, points.length - 1].map((index) => (
          <text
            key={`tick-${index}`}
            x={x(index)}
            y={height - 8}
            textAnchor={index === 0 ? 'start' : 'end'}
            className="fill-current text-ink-3"
            style={{ fontSize: 11 }}
          >
            {formatDay(points[index].date)}
          </text>
        ))}
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={((hover + 0.5) / points.length) * 100}
          y={4}
          title={formatDay(points[hover].date)}
          rows={[
            { label: labels.stock, value: formatNumber(points[hover].stock) },
            { label: labels.received, value: `+${formatNumber(points[hover].received)}` },
            { label: labels.consumed, value: `-${formatNumber(points[hover].consumed)}` },
          ]}
        />
      )}
    </div>
  )
}

// ------------------------------------------------------------------ waterfall
interface WaterfallProps {
  steps: WaterfallStep[]
  emptyMessage: string
  labelFor: (key: string) => string
}

/** Opening balance, what came in, what went out, closing balance. */
export function Waterfall({ steps, emptyMessage, labelFor }: WaterfallProps) {
  const { formatNumber } = useI18n()

  if (steps.length === 0) return <ChartEmpty message={emptyMessage} />

  // Running totals give each floating bar its base.
  let running = 0
  const bars = steps.map((step) => {
    if (step.kind === 'START' || step.kind === 'END') {
      running = step.value
      return { ...step, from: 0, to: step.value }
    }
    const from = running
    running += step.value
    return { ...step, from, to: running }
  })

  const ceiling = Math.max(...bars.map((bar) => Math.max(bar.from, bar.to)), 1)

  return (
    <ul className="space-y-2.5">
      {bars.map((bar, index) => {
        const low = Math.min(bar.from, bar.to)
        const high = Math.max(bar.from, bar.to)
        const left = (low / ceiling) * 100
        const span = Math.max(((high - low) / ceiling) * 100, 0.8)

        const fill =
          bar.kind === 'START' || bar.kind === 'END'
            ? 'bg-chart-1'
            : bar.kind === 'IN'
              ? 'bg-chart-2'
              : 'bg-crit'

        return (
          <li key={bar.key}>
            <div className="flex items-baseline justify-between gap-3">
              <span className="text-2xs font-medium text-ink-2">{labelFor(bar.key)}</span>
              <span
                className={cn(
                  'numeric text-2xs font-semibold',
                  bar.kind === 'IN'
                    ? 'text-ok-soft'
                    : bar.kind === 'OUT'
                      ? 'text-crit-soft'
                      : 'text-ink',
                )}
              >
                {bar.kind === 'IN' || bar.kind === 'OUT'
                  ? `${bar.value > 0 ? '+' : ''}${formatNumber(bar.value)}`
                  : formatNumber(bar.value)}
              </span>
            </div>
            <div className="relative mt-1 h-3 w-full rounded bg-line/40">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: `${span}%` }}
                transition={{ duration: 0.5, delay: index * 0.06, ease: [0.22, 1, 0.36, 1] }}
                style={{ left: `${left}%` }}
                className={cn('absolute inset-y-0 rounded', fill)}
              />
            </div>
            {bar.kind !== 'START' && bar.kind !== 'END' && (
              <p className="numeric mt-0.5 text-[11px] text-ink-3">
                {formatNumber(bar.from)} → {formatNumber(bar.to)}
              </p>
            )}
          </li>
        )
      })}
    </ul>
  )
}

// -------------------------------------------------------------------- heatmap
interface HeatmapProps {
  cells: HeatCell[]
  emptyMessage: string
  onSelect?: (cell: HeatCell) => void
  legend: { empty: string; full: string }
}

/** Warehouse grid: zone by row, position by column, occupancy by depth. */
export function Heatmap({ cells, emptyMessage, onSelect, legend }: HeatmapProps) {
  const { formatNumber } = useI18n()

  if (cells.length === 0) return <ChartEmpty message={emptyMessage} />

  const zones = [...new Set(cells.map((cell) => cell.zone))].sort()
  const positions = [...new Set(cells.map((cell) => cell.position))].sort((a, b) => a - b)

  return (
    <div className="overflow-x-auto">
      <div className="min-w-[420px]">
        <div
          className="grid gap-1"
          style={{ gridTemplateColumns: `1.5rem repeat(${positions.length}, minmax(0, 1fr))` }}
        >
          <span />
          {positions.map((position) => (
            <span
              key={position}
              className="numeric text-center text-[11px] text-ink-3"
            >
              {String(position).padStart(2, '0')}
            </span>
          ))}

          {zones.map((zone) => (
            <Row
              key={zone}
              zone={zone}
              positions={positions}
              cells={cells}
              onSelect={onSelect}
              formatNumber={formatNumber}
            />
          ))}
        </div>

        <div className="mt-3 flex items-center gap-2 text-[11px] text-ink-3">
          <span>{legend.empty}</span>
          {[...RAMP_BG].reverse().map((className) => (
            <span key={className} className={cn('h-2.5 w-7 rounded-sm', className)} />
          ))}
          <span>{legend.full}</span>
        </div>
      </div>
    </div>
  )
}

function Row({
  zone,
  positions,
  cells,
  onSelect,
  formatNumber,
}: {
  zone: string
  positions: number[]
  cells: HeatCell[]
  onSelect?: (cell: HeatCell) => void
  formatNumber: (value: number) => string
}) {
  return (
    <>
      <span className="numeric flex items-center text-2xs font-semibold text-ink-2">{zone}</span>
      {positions.map((position) => {
        const cell = cells.find((item) => item.zone === zone && item.position === position)
        if (!cell) return <span key={position} className="h-9 rounded bg-line/30" />

        const step = rampStep(cell.occupancy_percent)
        const Element = onSelect ? 'button' : 'div'
        return (
          <Element
            key={position}
            type={onSelect ? 'button' : undefined}
            onClick={onSelect ? () => onSelect(cell) : undefined}
            title={`${cell.code} · ${formatNumber(cell.occupied)}/${formatNumber(cell.capacity)}`}
            className={cn(
              'group relative grid h-9 place-items-center rounded transition-transform',
              RAMP_BG[step],
              cell.occupied === 0 && 'bg-line/40',
              onSelect && 'cursor-pointer hover:scale-[1.06]',
            )}
          >
            {/* The number is on the cell: colour alone never carries a value.
                `RAMP_TEXT` carries the measured ink for each step. */}
            <span
              className={cn(
                'numeric text-[11px] font-semibold',
                RAMP_TEXT[step],
                cell.occupied === 0 && 'text-ink-3 dark:text-ink-3',
              )}
            >
              {Math.round(cell.occupancy_percent)}
            </span>
          </Element>
        )
      })}
    </>
  )
}

// -------------------------------------------------------------------- scatter
interface ScatterProps {
  points: ScatterPoint[]
  emptyMessage: string
  axisLabels: { x: string; y: string }
  /** What the bubble area encodes. Translated by the caller. */
  sizeLabel: string
  riskZoneLabel: string
  /** Band caption, e.g. "cover under 3 days". Translated by the caller. */
  coverageLabel: (days: number) => string
  /** Row title for the coverage figure in the tooltip. */
  coverageTitle: string
  /** Coverage under this many days is the danger band. */
  riskDays?: number
  onSelect?: (partId: number) => void
}

/** Powers of ten inside a range, so a log axis can be read rather than guessed. */
function decadeTicks(low: number, high: number): number[] {
  const ticks: number[] = []
  for (let exponent = Math.floor(Math.log10(low)); exponent <= Math.ceil(Math.log10(high)); exponent += 1) {
    const value = 10 ** exponent
    if (value >= low / 1.5 && value <= high * 1.5) ticks.push(value)
  }
  return ticks
}

/**
 * Consumption against balance, on logarithmic axes.
 *
 * Linear axes were unreadable here: consumption spans 3 to 520 pieces a day and
 * the balance 0 to 3 700, so nine references out of ten collapsed into the
 * bottom-left corner. Log axes spread them out - and they buy something better
 * than room. Coverage is stock divided by consumption, so a constant coverage
 * becomes a straight 45-degree line: the shaded band below "three days of
 * cover" is an exact statement, not a rectangle drawn by eye.
 *
 * A reference at zero stock cannot be placed on a log axis. Rather than drop
 * the most critical case, those sit on the floor line, which is labelled 0.
 */
export function ScatterPlot({
  points,
  emptyMessage,
  axisLabels,
  sizeLabel,
  riskZoneLabel,
  coverageLabel,
  coverageTitle,
  riskDays = 3,
  onSelect,
}: ScatterProps) {
  const { formatDecimal, formatNumber } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (points.length === 0) return <ChartEmpty message={emptyMessage} />

  const width = 720
  const height = 360
  const padding = { top: 18, right: 20, bottom: 42, left: 64 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const consumptions = points.map((point) => point.daily_consumption).filter((value) => value > 0)
  const stocks = points.map((point) => point.available).filter((value) => value > 0)

  const xMin = Math.min(...consumptions, 1)
  const xMax = Math.max(...consumptions, 10)
  //: The floor sits one decade under the smallest real balance, and carries the
  //: zero-stock references.
  const yMin = Math.max(Math.min(...stocks, 10) / 4, 1)
  const yMax = Math.max(...stocks, 10)

  const logX = (value: number) =>
    padding.left +
    ((Math.log10(Math.max(value, xMin)) - Math.log10(xMin)) /
      (Math.log10(xMax) - Math.log10(xMin) || 1)) *
      innerWidth
  const logY = (value: number) =>
    padding.top +
    innerHeight -
    ((Math.log10(Math.max(value, yMin)) - Math.log10(yMin)) /
      (Math.log10(yMax) - Math.log10(yMin) || 1)) *
      innerHeight

  const floorY = padding.top + innerHeight
  const y = (value: number) => (value <= 0 ? floorY - 3 : logY(value))

  const maxDemand = Math.max(...points.map((point) => point.demand), 1)
  //: Area, not radius, encodes the demand - a doubled radius reads as four times.
  const r = (demand: number) => 4 + Math.sqrt(demand / maxDemand) * 10

  // Coverage = stock / consumption, so stock = coverage x consumption is a line.
  const coverageLine = (days: number) => {
    const x1 = xMin
    const x2 = xMax
    return { x1: logX(x1), y1: y(days * x1), x2: logX(x2), y2: y(days * x2) }
  }
  const risk = coverageLine(riskDays)

  /**
   * Where each critical label can sit without landing on another.
   *
   * The plot names only the references at risk, and on this data they all have
   * zero stock - identical y, so the default position stacked them. Each label
   * is nudged upwards until it clears the ones already placed; one that still
   * has nowhere to go is dropped rather than printed over its neighbour, and
   * the tooltip continues to name every point on hover.
   */
  const labelAt = useMemo(() => {
    const placed: { x: number; y: number }[] = []
    const chosen = new Map<number, number>()
    const HALF_WIDTH = 34
    const LINE = 13

    points.forEach((point, index) => {
      if (point.risk !== 'CRITICAL') return
      const x = logX(point.daily_consumption)
      const base = y(point.available) - r(point.demand) - 4

      for (let step = 0; step < 6; step += 1) {
        const candidate = base - step * LINE
        if (candidate < 10) break
        const clashes = placed.some(
          (other) =>
            Math.abs(other.x - x) < HALF_WIDTH * 2 &&
            Math.abs(other.y - candidate) < LINE,
        )
        if (!clashes) {
          placed.push({ x, y: candidate })
          chosen.set(index, candidate)
          return
        }
      }
    })
    return chosen
  }, [points, logX, y, r])

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={riskZoneLabel}>
        {/* Everything under the coverage line is a reference that runs out first. */}
        <polygon
          points={`${risk.x1},${risk.y1} ${risk.x2},${risk.y2} ${risk.x2},${floorY} ${risk.x1},${floorY}`}
          className="fill-crit/10"
        />
        <line
          x1={risk.x1}
          y1={risk.y1}
          x2={risk.x2}
          y2={risk.y2}
          strokeWidth={1.5}
          strokeDasharray="4 3"
          className="stroke-crit/40"
        />
        <text
          x={risk.x2 - 6}
          y={Math.min(risk.y2 + 14, floorY - 6)}
          textAnchor="end"
          className="fill-current text-crit-soft"
          style={{ fontSize: 11 }}
        >
          {riskZoneLabel} · {coverageLabel(riskDays)}
        </text>

        {/* Decade gridlines: a log axis is unreadable without them. */}
        {decadeTicks(xMin, xMax).map((tick) => (
          <g key={`x-${tick}`}>
            <line
              x1={logX(tick)}
              x2={logX(tick)}
              y1={padding.top}
              y2={floorY}
              className="stroke-line"
              strokeDasharray="2 4"
            />
            <text
              x={logX(tick)}
              y={floorY + 14}
              textAnchor="middle"
              className="fill-current text-ink-3"
              style={{ fontSize: 11 }}
            >
              {formatNumber(tick)}
            </text>
          </g>
        ))}
        {decadeTicks(yMin, yMax).map((tick) => (
          <g key={`y-${tick}`}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={logY(tick)}
              y2={logY(tick)}
              className="stroke-line"
              strokeDasharray="2 4"
            />
            <text
              x={padding.left - 8}
              y={logY(tick) + 3}
              textAnchor="end"
              className="fill-current text-ink-3"
              style={{ fontSize: 11 }}
            >
              {formatNumber(tick)}
            </text>
          </g>
        ))}

        <line
          x1={padding.left}
          x2={padding.left}
          y1={padding.top}
          y2={floorY}
          className="stroke-line-strong"
        />
        <line
          x1={padding.left}
          x2={width - padding.right}
          y1={floorY}
          y2={floorY}
          className="stroke-line-strong"
        />
        <text
          x={padding.left - 8}
          y={floorY + 3}
          textAnchor="end"
          className="fill-current text-ink-3"
          style={{ fontSize: 11 }}
        >
          0
        </text>

        {points.map((point, index) => (
          <g key={point.part_id}>
            <circle
              cx={logX(point.daily_consumption)}
              cy={y(point.available)}
              r={r(point.demand)}
              className={cn(STATE_FILL[point.risk], 'opacity-70')}
              stroke="currentColor"
              strokeWidth={2}
              style={{ color: 'rgb(var(--c-panel))' }}
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
              onClick={onSelect ? () => onSelect(point.part_id) : undefined}
              cursor={onSelect ? 'pointer' : undefined}
            />
            {/* Only the at-risk references are named, and only where the name
                has room. Every critical part here sits at zero stock, so they
                share a y and their labels were printing on top of each other -
                two references overlapping is worse than one of them hidden,
                because the reader cannot tell which is which. */}
            {labelAt.get(index) !== undefined && (
              <text
                x={logX(point.daily_consumption)}
                y={labelAt.get(index)}
                textAnchor="middle"
                className="fill-current text-ink-2"
                style={{ fontSize: 11 }}
              >
                {point.reference}
              </text>
            )}
          </g>
        ))}

        <text
          x={padding.left + innerWidth / 2}
          y={height - 8}
          textAnchor="middle"
          className="fill-current text-ink-3"
          style={{ fontSize: 11 }}
        >
          {axisLabels.x}
        </text>
        {/* Rotated about its own anchor, so the label can never fall outside. */}
        <text
          x={14}
          y={padding.top + innerHeight / 2}
          transform={`rotate(-90 14 ${padding.top + innerHeight / 2})`}
          textAnchor="middle"
          className="fill-current text-ink-3"
          style={{ fontSize: 11 }}
        >
          {axisLabels.y}
        </text>
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={(logX(points[hover].daily_consumption) / width) * 100}
          y={(y(points[hover].available) / height) * 100}
          title={points[hover].reference}
          rows={[
            { label: axisLabels.y, value: formatNumber(points[hover].available) },
            {
              label: axisLabels.x,
              value: formatDecimal(points[hover].daily_consumption, 1),
            },
            { label: sizeLabel, value: formatNumber(points[hover].demand) },
            {
              label: coverageTitle,
              value:
                points[hover].coverage_days !== null
                  ? formatDecimal(points[hover].coverage_days!, 1)
                  : '\u2014',
            },
          ]}
        />
      )}
    </div>
  )
}
