/**
 * Circular forms: a share of a whole, and a measure against a target.
 *
 * A donut is only used where the parts genuinely sum to one whole and there are
 * at most four of them; a gauge only where the indicator has a target to be
 * read against. Everywhere else a bar is more honest, and shorter to read.
 */

import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { ChartEmpty } from './primitives'

interface DonutSegment {
  key: string
  label: string
  value: number
  /** Tailwind text-* class: the arc is stroked with currentColor. */
  className: string
}

interface DonutChartProps {
  segments: DonutSegment[]
  /** The one figure the reader should leave with. */
  centreValue: string
  centreLabel: string
  emptyMessage: string
  size?: number
  /** Clicking a slice filters the rest of the screen on that state. */
  onSelect?: (key: string) => void
  selectedKey?: string | null
}

export function DonutChart({
  segments,
  centreValue,
  centreLabel,
  emptyMessage,
  size = 168,
  onSelect,
  selectedKey,
}: DonutChartProps) {
  const { formatDecimal, formatNumber } = useI18n()
  const total = segments.reduce((accumulator, item) => accumulator + item.value, 0)

  if (total <= 0) return <ChartEmpty message={emptyMessage} />

  const stroke = 18
  const radius = (size - stroke) / 2
  const circumference = 2 * Math.PI * radius
  //: A 2px gap between arcs, expressed on the circumference.
  const gap = 2

  let offset = 0

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:items-center sm:gap-6">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg
          viewBox={`0 0 ${size} ${size}`}
          width={size}
          height={size}
          role="img"
          aria-label={centreLabel}
        >
          <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
            {/* Track, so a thin slice still reads against something. */}
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              strokeWidth={stroke}
              className="stroke-line/70"
            />
            {segments
              .filter((segment) => segment.value > 0)
              .map((segment) => {
                const length = (segment.value / total) * circumference
                const dash = Math.max(length - gap, 1)
                const element = (
                  <motion.circle
                    key={segment.key}
                    cx={size / 2}
                    cy={size / 2}
                    r={radius}
                    fill="none"
                    strokeWidth={stroke}
                    strokeLinecap="butt"
                    stroke="currentColor"
                    className={cn(
                      segment.className,
                      onSelect && 'cursor-pointer',
                    )}
                    strokeDasharray={`${dash} ${circumference - dash}`}
                    initial={{ strokeDashoffset: -offset, opacity: 0 }}
                    animate={{
                      strokeDashoffset: -offset,
                      opacity:
                        selectedKey && selectedKey !== segment.key ? 0.25 : 1,
                    }}
                    transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
                    onClick={onSelect ? () => onSelect(segment.key) : undefined}
                  />
                )
                offset += length
                return element
              })}
          </g>
        </svg>

        <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
          <div>
            <p className="numeric text-2xl font-semibold leading-none tracking-tight text-ink">
              {centreValue}
            </p>
            <p className="mt-1 px-6 text-[10px] uppercase tracking-widest2 text-ink-3">
              {centreLabel}
            </p>
          </div>
        </div>
      </div>

      {/* The legend is also the value table: no reading colours off the arc. */}
      <ul className="w-full min-w-0 flex-1 space-y-2">
        {segments.map((segment) => {
          const active = selectedKey === segment.key
          const Item = onSelect ? 'button' : 'div'
          return (
            <li key={segment.key}>
              <Item
                type={onSelect ? 'button' : undefined}
                onClick={onSelect ? () => onSelect(segment.key) : undefined}
                aria-pressed={onSelect ? active : undefined}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg border px-2 py-1.5 text-2xs transition-colors',
                  active
                    ? 'border-accent/40 bg-accent/[0.06]'
                    : 'border-transparent hover:border-line hover:bg-elevated',
                  selectedKey && !active && 'opacity-50',
                  onSelect && 'cursor-pointer',
                )}
              >
                <span
                  className={cn(
                    'h-2.5 w-2.5 shrink-0 rounded-[3px] bg-current',
                    segment.className,
                  )}
                />
                <span className="truncate text-ink-2">{segment.label}</span>
                <span className="numeric ml-auto shrink-0 font-semibold text-ink">
                  {formatNumber(segment.value)}
                </span>
                <span className="numeric w-12 shrink-0 text-right text-ink-3">
                  {formatDecimal((segment.value / total) * 100, 1)} %
                </span>
              </Item>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

// ---------------------------------------------------------------------- gauge
interface GaugeProps {
  /** 0-100. */
  value: number
  label: string
  /** Where the needle should be. Drawn as a tick, not as a coloured zone. */
  target?: number
  warning?: number
  critical?: number
  display?: string
  /** Already translated by the caller - this file holds no copy. */
  targetLabel?: string
  /** True when a high value is the problem (occupancy), false when it is the goal. */
  higherIsWorse?: boolean
}

export function Gauge({
  value,
  label,
  target,
  warning,
  critical,
  display,
  targetLabel,
  higherIsWorse = false,
}: GaugeProps) {
  const { formatDecimal } = useI18n()
  const clamped = Math.max(0, Math.min(100, value))

  const severity = (() => {
    if (higherIsWorse) {
      if (critical !== undefined && clamped >= critical) return 'crit'
      if (warning !== undefined && clamped >= warning) return 'warn'
      return 'ok'
    }
    if (critical !== undefined && clamped < critical) return 'crit'
    if (warning !== undefined && clamped < warning) return 'warn'
    return 'ok'
  })()

  const arcClass =
    severity === 'crit' ? 'stroke-crit' : severity === 'warn' ? 'stroke-warn' : 'stroke-ok'

  // A 240-degree arc: open at the bottom so the figure sits in the mouth.
  const size = 160
  const stroke = 14
  const radius = (size - stroke) / 2
  const sweep = 240
  const start = 150
  const circumference = 2 * Math.PI * radius
  const arcLength = (sweep / 360) * circumference

  const tickAngle = target !== undefined ? start + (target / 100) * sweep : null
  const tickPoint = (angle: number, distance: number) => {
    const radians = ((angle - 90) * Math.PI) / 180
    return {
      x: size / 2 + Math.cos(radians) * distance,
      y: size / 2 + Math.sin(radians) * distance,
    }
  }

  return (
    <div className="flex flex-col items-center">
      <div className="relative" style={{ width: size, height: size * 0.78 }}>
        <svg viewBox={`0 0 ${size} ${size * 0.9}`} width={size} height={size * 0.78} role="img" aria-label={label}>
          <g transform={`rotate(${start} ${size / 2} ${size / 2})`}>
            <circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              strokeWidth={stroke}
              strokeLinecap="round"
              className="stroke-line/70"
              strokeDasharray={`${arcLength} ${circumference}`}
            />
            <motion.circle
              cx={size / 2}
              cy={size / 2}
              r={radius}
              fill="none"
              strokeWidth={stroke}
              strokeLinecap="round"
              className={arcClass}
              strokeDasharray={`${(clamped / 100) * arcLength} ${circumference}`}
              initial={{ strokeDasharray: `0 ${circumference}` }}
              animate={{ strokeDasharray: `${(clamped / 100) * arcLength} ${circumference}` }}
              transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
            />
          </g>

          {tickAngle !== null &&
            (() => {
              const outer = tickPoint(tickAngle, radius + stroke / 2 + 3)
              const inner = tickPoint(tickAngle, radius - stroke / 2 - 3)
              return (
                <line
                  x1={inner.x}
                  y1={inner.y}
                  x2={outer.x}
                  y2={outer.y}
                  strokeWidth={2}
                  className="stroke-ink-3"
                />
              )
            })()}
        </svg>

        <div className="pointer-events-none absolute inset-x-0 bottom-1 text-center">
          <p className="numeric text-xl font-semibold leading-none text-ink">
            {display ?? `${formatDecimal(clamped, 1)} %`}
          </p>
        </div>
      </div>
      <p className="mt-1 text-center text-2xs text-ink-2">{label}</p>
      {targetLabel && <p className="numeric mt-0.5 text-[10px] text-ink-3">{targetLabel}</p>}
    </div>
  )
}

// ------------------------------------------------------------------------ pie
interface PieChartProps {
  segments: DonutSegment[]
  emptyMessage: string
  /** Six is the ceiling: past that the eye cannot rank the wedges. */
  maxSlices?: number
  otherLabel: string
  unit?: string
  selectedKey?: string | null
  onSelect?: (key: string) => void
  size?: number
}

/**
 * A share of one whole, with no hole in the middle.
 *
 * Used only where the parts genuinely sum to something meaningful and there are
 * few of them; the donut is preferred whenever a headline figure belongs in the
 * centre. Everything past the sixth slice folds into one "other" wedge rather
 * than becoming a colour nobody can name.
 */
export function AnalyticsPie({
  segments,
  emptyMessage,
  maxSlices = 6,
  otherLabel,
  unit,
  selectedKey,
  onSelect,
  size = 190,
}: PieChartProps) {
  const { formatNumber, formatDecimal } = useI18n()

  const positive = segments.filter((segment) => segment.value > 0)
  if (positive.length === 0) return <ChartEmpty message={emptyMessage} />

  const sorted = [...positive].sort((a, b) => b.value - a.value)
  const head = sorted.slice(0, maxSlices - 1)
  const tail = sorted.slice(maxSlices - 1)
  const shown: DonutSegment[] =
    tail.length > 1
      ? [
          ...head,
          {
            key: 'other',
            label: otherLabel,
            value: tail.reduce((sum, item) => sum + item.value, 0),
            className: 'text-ink-3',
          },
        ]
      : sorted

  const total = shown.reduce((sum, segment) => sum + segment.value, 0)
  const radius = size / 2 - 4
  const centre = size / 2

  let angle = -Math.PI / 2
  const wedges = shown.map((segment) => {
    const sweep = (segment.value / total) * Math.PI * 2
    const start = angle
    const end = angle + sweep
    angle = end

    const x1 = centre + radius * Math.cos(start)
    const y1 = centre + radius * Math.sin(start)
    const x2 = centre + radius * Math.cos(end)
    const y2 = centre + radius * Math.sin(end)
    const large = sweep > Math.PI ? 1 : 0

    return {
      segment,
      path: `M ${centre} ${centre} L ${x1} ${y1} A ${radius} ${radius} 0 ${large} 1 ${x2} ${y2} Z`,
    }
  })

  return (
    <div className="flex flex-col items-center gap-4 sm:flex-row sm:gap-6">
      <svg
        viewBox={`0 0 ${size} ${size}`}
        width={size}
        height={size}
        className="shrink-0"
        role="img"
        aria-label={otherLabel}
      >
        {wedges.map(({ segment, path }, index) => {
          const active = selectedKey === segment.key
          return (
            <motion.path
              key={segment.key}
              d={path}
              fill="currentColor"
              className={cn(
                segment.className,
                onSelect && 'cursor-pointer',
                /* A 2px surface ring keeps adjacent wedges from merging. */
                'stroke-panel',
              )}
              strokeWidth={2}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{
                opacity: selectedKey && !active ? 0.3 : 1,
                scale: active ? 1.04 : 1,
              }}
              style={{ transformOrigin: `${centre}px ${centre}px` }}
              transition={{ duration: 0.35, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
              onClick={onSelect ? () => onSelect(segment.key) : undefined}
            />
          )
        })}
      </svg>

      {/* The legend is the value table: nobody reads a wedge to two decimals. */}
      <ul className="w-full min-w-0 flex-1 space-y-1.5">
        {shown.map((segment) => {
          const active = selectedKey === segment.key
          const Item = onSelect ? 'button' : 'div'
          return (
            <li key={segment.key}>
              <Item
                type={onSelect ? 'button' : undefined}
                onClick={onSelect ? () => onSelect(segment.key) : undefined}
                aria-pressed={onSelect ? active : undefined}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg border px-2 py-1.5 text-2xs transition-colors',
                  active
                    ? 'border-accent/40 bg-accent/[0.06]'
                    : 'border-transparent hover:border-line hover:bg-elevated',
                  selectedKey && !active && 'opacity-50',
                  onSelect && 'cursor-pointer',
                )}
              >
                <span
                  className={cn(
                    'h-2.5 w-2.5 shrink-0 rounded-[3px] bg-current',
                    segment.className,
                  )}
                />
                <span className="truncate text-ink-2">{segment.label}</span>
                <span className="numeric ml-auto shrink-0 font-semibold text-ink">
                  {formatNumber(segment.value)}
                  {unit && <span className="ml-0.5 font-normal text-ink-3">{unit}</span>}
                </span>
                <span className="numeric w-12 shrink-0 text-right text-ink-3">
                  {formatDecimal((segment.value / total) * 100, 1)} %
                </span>
              </Item>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
