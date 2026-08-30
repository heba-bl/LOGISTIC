/**
 * Distribution, time series and share-of-whole.
 *
 * Three forms that the bar/donut/scatter set could not cover:
 *   histogram  where does the tail sit, not just the average
 *   line/area  how a level moved, day by day
 *   treemap    which families hold the volume, at a glance
 *
 * All hand-drawn SVG, like the rest of the library: that is what lets every
 * mark inherit the theme tokens and carry a direct label in both modes.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { ChartEmpty, ChartTooltip, RAMP_BG, RAMP_TEXT, STATE_FILL, rampStep } from './primitives'
import type { Severity4 } from '@/types/overview'

// ---------------------------------------------------------------- histogram
export interface HistogramBucket {
  from_hours: number
  to_hours: number | null
  count: number
}

interface HistogramProps {
  buckets: HistogramBucket[]
  emptyMessage: string
  /** Already-formatted marker line, e.g. "médiane 3,6 h". */
  medianLabel?: string
  medianHours?: number | null
  countLabel: string
}

/**
 * How many lots fall in each duration band.
 *
 * The median is drawn as a line rather than printed alone: an average tells you
 * where the middle is, the shape tells you whether there is a tail worth acting
 * on, and the two together are what a manager actually reads.
 */
export function AnalyticsHistogram({
  buckets,
  emptyMessage,
  medianLabel,
  medianHours,
  countLabel,
}: HistogramProps) {
  const { formatNumber, formatDecimal } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (buckets.length === 0) return <ChartEmpty message={emptyMessage} />

  const width = 680
  const height = 220
  const padding = { top: 18, right: 12, bottom: 34, left: 40 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const ceiling = Math.max(...buckets.map((bucket) => bucket.count), 1)
  const slot = innerWidth / buckets.length
  const barWidth = slot * 0.72

  const x = (index: number) => padding.left + slot * index + (slot - barWidth) / 2
  const barHeight = (count: number) => (count / ceiling) * innerHeight

  // The median sits on the value axis, so it needs the bucket bounds to place.
  const lastBound = buckets[buckets.length - 1].from_hours || 1
  const medianX =
    medianHours != null
      ? padding.left + Math.min(medianHours / (lastBound * 1.2), 1) * innerWidth
      : null

  const label = (bucket: HistogramBucket) =>
    bucket.to_hours === null
      ? `${formatDecimal(bucket.from_hours, 0)}+`
      : `${formatDecimal(bucket.from_hours, 0)}–${formatDecimal(bucket.to_hours, 0)}`

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={countLabel}>
        {[0.25, 0.5, 0.75, 1].map((fraction) => (
          <g key={fraction}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerHeight * (1 - fraction)}
              y2={padding.top + innerHeight * (1 - fraction)}
              className="stroke-line"
              strokeDasharray="2 4"
            />
            <text
              x={padding.left - 6}
              y={padding.top + innerHeight * (1 - fraction) + 3}
              textAnchor="end"
              className="fill-current text-ink-3"
              style={{ fontSize: 9 }}
            >
              {formatNumber(Math.round(ceiling * fraction))}
            </text>
          </g>
        ))}

        {buckets.map((bucket, index) => (
          <g
            key={`${bucket.from_hours}-${index}`}
            onMouseEnter={() => setHover(index)}
            onMouseLeave={() => setHover(null)}
          >
            <rect
              x={padding.left + slot * index}
              y={padding.top}
              width={slot}
              height={innerHeight}
              fill="transparent"
            />
            <motion.rect
              x={x(index)}
              width={barWidth}
              rx={4}
              initial={{ y: padding.top + innerHeight, height: 0 }}
              animate={{
                y: padding.top + innerHeight - barHeight(bucket.count),
                height: barHeight(bucket.count),
              }}
              transition={{ duration: 0.5, delay: index * 0.04, ease: [0.22, 1, 0.36, 1] }}
              className={cn('fill-chart-1', hover === index && 'fill-accent-soft')}
            />
            {/* The count sits on the bar: no counting gridlines by eye. */}
            {bucket.count > 0 && (
              <text
                x={x(index) + barWidth / 2}
                y={padding.top + innerHeight - barHeight(bucket.count) - 5}
                textAnchor="middle"
                className="fill-current text-ink-2"
                style={{ fontSize: 10, fontWeight: 600 }}
              >
                {formatNumber(bucket.count)}
              </text>
            )}
            <text
              x={x(index) + barWidth / 2}
              y={height - 12}
              textAnchor="middle"
              className="fill-current text-ink-3"
              style={{ fontSize: 9 }}
            >
              {label(bucket)}
            </text>
          </g>
        ))}

        {medianX !== null && medianLabel && (
          <g>
            <line
              x1={medianX}
              x2={medianX}
              y1={padding.top - 4}
              y2={padding.top + innerHeight}
              className="stroke-ai"
              strokeWidth={1.5}
              strokeDasharray="4 3"
            />
            <text
              x={medianX + 4}
              y={padding.top + 6}
              className="fill-current text-ai-soft"
              style={{ fontSize: 9, fontWeight: 600 }}
            >
              {medianLabel}
            </text>
          </g>
        )}
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={((hover + 0.5) / buckets.length) * 100}
          y={6}
          title={`${label(buckets[hover])} h`}
          rows={[{ label: countLabel, value: formatNumber(buckets[hover].count) }]}
        />
      )}
    </div>
  )
}

// -------------------------------------------------------------- line & area
export interface SeriesPoint {
  label: string
  value: number
}

interface LineChartProps {
  points: SeriesPoint[]
  emptyMessage: string
  seriesLabel: string
  /** Fill under the curve. Use when the volume matters, not just the shape. */
  area?: boolean
  unit?: string
  /** Formats the value in the tooltip and on the axis. */
  format?: (value: number) => string
}

/**
 * One measure over time, with a crosshair.
 *
 * A single series on a single axis: two measures of different scale would need
 * a second axis, and a second axis is the fastest way to make a chart lie.
 */
export function AnalyticsLineChart({
  points,
  emptyMessage,
  seriesLabel,
  area = false,
  unit,
  format,
}: LineChartProps) {
  const { formatNumber } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (points.length < 2) return <ChartEmpty message={emptyMessage} />

  const show = format ?? formatNumber

  const width = 720
  const height = 240
  const padding = { top: 16, right: 16, bottom: 28, left: 52 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const values = points.map((point) => point.value)
  const max = Math.max(...values)
  const min = Math.min(...values)
  //: A ribbon that never touches the floor reads as "nothing happened".
  const low = min - (max - min) * 0.15
  const span = max - low || 1

  const x = (index: number) => padding.left + (index / (points.length - 1)) * innerWidth
  const y = (value: number) => padding.top + innerHeight - ((value - low) / span) * innerHeight

  const line = points.map((point, index) => `${x(index)},${y(point.value)}`).join(' ')
  const fill = `${padding.left},${padding.top + innerHeight} ${line} ${width - padding.right},${
    padding.top + innerHeight
  }`

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={seriesLabel}
      >
        {[0, 0.5, 1].map((fraction) => (
          <g key={fraction}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerHeight * fraction}
              y2={padding.top + innerHeight * fraction}
              className="stroke-line"
              strokeDasharray="2 4"
            />
            <text
              x={padding.left - 8}
              y={padding.top + innerHeight * fraction + 3}
              textAnchor="end"
              className="fill-current text-ink-3"
              style={{ fontSize: 9 }}
            >
              {show(low + span * (1 - fraction))}
            </text>
          </g>
        ))}

        {area && (
          <motion.polygon
            points={fill}
            className="fill-chart-1/15"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
          />
        )}

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
          <g key={`${point.label}-${index}`}>
            <rect
              x={padding.left + (index - 0.5) * (innerWidth / (points.length - 1))}
              y={padding.top}
              width={innerWidth / (points.length - 1)}
              height={innerHeight}
              fill="transparent"
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
            />
            {hover === index && (
              <>
                <line
                  x1={x(index)}
                  x2={x(index)}
                  y1={padding.top}
                  y2={padding.top + innerHeight}
                  className="stroke-line-strong"
                />
                <circle
                  cx={x(index)}
                  cy={y(point.value)}
                  r={4.5}
                  className="fill-chart-1 stroke-panel"
                  strokeWidth={2}
                />
              </>
            )}
          </g>
        ))}

        {[0, points.length - 1].map((index) => (
          <text
            key={`tick-${index}`}
            x={x(index)}
            y={height - 8}
            textAnchor={index === 0 ? 'start' : 'end'}
            className="fill-current text-ink-3"
            style={{ fontSize: 10 }}
          >
            {points[index].label}
          </text>
        ))}
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={(x(hover) / width) * 100}
          y={Math.max((y(points[hover].value) / height) * 100 - 4, 8)}
          title={points[hover].label}
          rows={[
            {
              label: seriesLabel,
              value: `${show(points[hover].value)}${unit ? ` ${unit}` : ''}`,
            },
          ]}
        />
      )}
    </div>
  )
}

/** The same chart with the ribbon filled. Kept separate so intent is explicit. */
export function AnalyticsAreaChart(props: Omit<LineChartProps, 'area'>) {
  return <AnalyticsLineChart {...props} area />
}

// ------------------------------------------------------------------ treemap
export interface TreemapNode {
  key: string
  label: string
  value: number
  caption?: string
}

interface TreemapProps {
  nodes: TreemapNode[]
  emptyMessage: string
  selectedKey?: string | null
  onSelect?: (key: string) => void
  unit?: string
  /** Label for the tile the tail is folded into. */
  otherLabel?: string
}

//: Below this share a tile is a few pixels wide - unreadable, and it makes the
//: chart look broken. The tail folds into one block instead.
const TREEMAP_MIN_SHARE = 2.5

/**
 * Volume by family, as area.
 *
 * A treemap earns its place over a bar chart when the question is "what is the
 * bulk made of" rather than "which is biggest": the eye reads the two or three
 * blocks that own the surface immediately, and the long tail stops competing
 * for attention.
 */
export function AnalyticsTreemap({
  nodes,
  emptyMessage,
  selectedKey,
  onSelect,
  unit,
  otherLabel,
}: TreemapProps) {
  const { formatNumber, formatDecimal } = useI18n()

  const positive = nodes.filter((node) => node.value > 0)
  if (positive.length === 0) return <ChartEmpty message={emptyMessage} />

  const total = positive.reduce((sum, node) => sum + node.value, 0)
  const ranked = [...positive].sort((a, b) => b.value - a.value)

  const big = ranked.filter((node) => (node.value / total) * 100 >= TREEMAP_MIN_SHARE)
  const tail = ranked.filter((node) => (node.value / total) * 100 < TREEMAP_MIN_SHARE)
  const sorted =
    otherLabel && tail.length > 1
      ? [
          ...big,
          {
            key: '__other__',
            label: otherLabel,
            value: tail.reduce((sum, node) => sum + node.value, 0),
          },
        ]
      : ranked

  // Squarified-ish slice-and-dice: alternate the cut direction so blocks stay
  // close to square, which is what keeps areas comparable by eye.
  type Rect = { x: number; y: number; width: number; height: number }
  const tiles: (TreemapNode & Rect)[] = []

  function layout(items: TreemapNode[], rect: Rect, horizontal: boolean) {
    if (items.length === 0) return
    if (items.length === 1) {
      tiles.push({ ...items[0], ...rect })
      return
    }
    const sum = items.reduce((accumulator, item) => accumulator + item.value, 0)
    let running = 0
    let cut = 1
    for (let index = 0; index < items.length; index += 1) {
      running += items[index].value
      if (running >= sum / 2) {
        cut = index + 1
        break
      }
    }
    const head = items.slice(0, cut)
    const tail = items.slice(cut)
    const share = head.reduce((accumulator, item) => accumulator + item.value, 0) / sum

    if (horizontal) {
      const splitWidth = rect.width * share
      layout(head, { ...rect, width: splitWidth }, !horizontal)
      layout(tail, { ...rect, x: rect.x + splitWidth, width: rect.width - splitWidth }, !horizontal)
    } else {
      const splitHeight = rect.height * share
      layout(head, { ...rect, height: splitHeight }, !horizontal)
      layout(
        tail,
        { ...rect, y: rect.y + splitHeight, height: rect.height - splitHeight },
        !horizontal,
      )
    }
  }

  layout(sorted, { x: 0, y: 0, width: 100, height: 100 }, true)

  return (
    <div className="relative h-[260px] w-full">
      {tiles.map((tile, index) => {
        const share = (tile.value / total) * 100
        const step = rampStep(share * 3)
        const active = selectedKey === tile.key
        const dimmed = selectedKey != null && !active
        const Element = onSelect ? 'button' : 'div'
        //: Two thresholds, because a block can be too short for its value and
        //: still wide enough for its name. Anything smaller keeps only the
        //: tooltip - a clipped label reads as a rendering fault.
        const showLabel = tile.width > 9 && tile.height > 9
        const showValue = tile.width > 12 && tile.height > 17

        return (
          <motion.div
            key={tile.key}
            initial={{ opacity: 0, scale: 0.94 }}
            animate={{ opacity: dimmed ? 0.4 : 1, scale: 1 }}
            transition={{ duration: 0.35, delay: index * 0.03, ease: [0.22, 1, 0.36, 1] }}
            className="absolute p-[2px]"
            style={{
              left: `${tile.x}%`,
              top: `${tile.y}%`,
              width: `${tile.width}%`,
              height: `${tile.height}%`,
            }}
          >
            <Element
              type={onSelect ? 'button' : undefined}
              onClick={onSelect ? () => onSelect(tile.key) : undefined}
              aria-pressed={onSelect ? active : undefined}
              title={`${tile.label} · ${formatNumber(tile.value)}${unit ?? ''} · ${formatDecimal(
                share,
                1,
              )} %`}
              className={cn(
                'flex h-full w-full flex-col justify-between overflow-hidden rounded-lg p-2 text-left transition-all',
                RAMP_BG[step],
                active && 'ring-2 ring-accent ring-offset-1 ring-offset-panel',
                onSelect && 'cursor-pointer hover:brightness-110',
              )}
            >
              {showLabel && (
                <span className={cn('truncate text-[11px] font-semibold', RAMP_TEXT[step])}>
                  {tile.label}
                </span>
              )}
              {showValue && (
                <span className={cn('numeric text-[11px] font-semibold', RAMP_TEXT[step])}>
                  {formatNumber(tile.value)}
                  <span className="ml-1 font-normal opacity-80">
                    {formatDecimal(share, 1)} %
                  </span>
                </span>
              )}
            </Element>
          </motion.div>
        )
      })}
    </div>
  )
}

// -------------------------------------------------------------- generic xy
export interface XYPoint {
  key: string
  label: string
  x: number
  y: number
  /** Bubble area, not radius: a doubled radius reads as four times the value. */
  size?: number
  severity?: Severity4
}

interface ScatterXYProps {
  points: XYPoint[]
  emptyMessage: string
  axisLabels: { x: string; y: string }
  formatX?: (value: number) => string
  formatY?: (value: number) => string
  tooltipRows?: (point: XYPoint) => { label: string; value: string }[]
  onSelect?: (key: string) => void
  selectedKey?: string | null
}

/**
 * Two measures against each other, labelled.
 *
 * Kept separate from the reference scatter because the question is different:
 * this one compares a handful of named things, so every point carries its name
 * rather than only the alarming ones.
 */
export function AnalyticsScatterXY({
  points,
  emptyMessage,
  axisLabels,
  formatX,
  formatY,
  tooltipRows,
  onSelect,
  selectedKey,
}: ScatterXYProps) {
  const { formatNumber } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (points.length === 0) return <ChartEmpty message={emptyMessage} />

  const showX = formatX ?? formatNumber
  const showY = formatY ?? formatNumber

  const width = 680
  const height = 300
  const padding = { top: 20, right: 24, bottom: 40, left: 56 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  const maxX = Math.max(...points.map((point) => point.x), 1) * 1.1
  const maxY = Math.max(...points.map((point) => point.y), 1) * 1.15
  const maxSize = Math.max(...points.map((point) => point.size ?? 1), 1)

  const x = (value: number) => padding.left + (value / maxX) * innerWidth
  const y = (value: number) => padding.top + innerHeight - (value / maxY) * innerHeight
  const r = (size?: number) => 6 + Math.sqrt((size ?? maxSize) / maxSize) * 10

  return (
    <div className="relative">
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label={axisLabels.y}>
        {[0.25, 0.5, 0.75, 1].map((fraction) => (
          <g key={fraction}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={padding.top + innerHeight * (1 - fraction)}
              y2={padding.top + innerHeight * (1 - fraction)}
              className="stroke-line"
              strokeDasharray="2 4"
            />
            <text
              x={padding.left - 8}
              y={padding.top + innerHeight * (1 - fraction) + 3}
              textAnchor="end"
              className="fill-current text-ink-3"
              style={{ fontSize: 9 }}
            >
              {showY(maxY * fraction)}
            </text>
          </g>
        ))}

        <line
          x1={padding.left}
          x2={padding.left}
          y1={padding.top}
          y2={padding.top + innerHeight}
          className="stroke-line-strong"
        />
        <line
          x1={padding.left}
          x2={width - padding.right}
          y1={padding.top + innerHeight}
          y2={padding.top + innerHeight}
          className="stroke-line-strong"
        />

        {points.map((point, index) => {
          const active = selectedKey === point.key
          const dimmed = selectedKey != null && !active
          return (
            <g
              key={point.key}
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
              onClick={onSelect ? () => onSelect(point.key) : undefined}
              className={cn(onSelect && 'cursor-pointer', dimmed && 'opacity-35')}
            >
              <circle
                cx={x(point.x)}
                cy={y(point.y)}
                r={r(point.size)}
                className={cn(
                  point.severity ? STATE_FILL[point.severity] : 'fill-chart-1',
                  'opacity-75',
                )}
                stroke="currentColor"
                strokeWidth={active ? 3 : 2}
                style={{ color: 'rgb(var(--c-panel))' }}
              />
              <text
                x={x(point.x)}
                y={y(point.y) - r(point.size) - 5}
                textAnchor="middle"
                className="fill-current text-ink-2"
                style={{ fontSize: 10, fontWeight: 600 }}
              >
                {point.label}
              </text>
            </g>
          )
        })}

        <text
          x={padding.left + innerWidth / 2}
          y={height - 8}
          textAnchor="middle"
          className="fill-current text-ink-3"
          style={{ fontSize: 10 }}
        >
          {axisLabels.x}
        </text>
        <text
          x={-(padding.top + innerHeight / 2)}
          y={13}
          transform="rotate(-90)"
          textAnchor="middle"
          className="fill-current text-ink-3"
          style={{ fontSize: 10 }}
        >
          {axisLabels.y}
        </text>
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={(x(points[hover].x) / width) * 100}
          y={Math.max((y(points[hover].y) / height) * 100 - 6, 6)}
          title={points[hover].label}
          rows={
            tooltipRows?.(points[hover]) ?? [
              { label: axisLabels.x, value: showX(points[hover].x) },
              { label: axisLabels.y, value: showY(points[hover].y) },
            ]
          }
        />
      )}
    </div>
  )
}
