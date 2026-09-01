import { useMemo, useState } from 'react'

import { cn } from '@/utils/cn'
import { ChartEmpty, ChartTooltip, SERIES_STROKE, SERIES_FILL } from './primitives'

export interface RadarAxis {
  key: string
  label: string
  /** How the raw figure should read in the tooltip, already worded. */
  format?: (value: number) => string
}

export interface RadarSeries {
  key: string
  label: string
  /** One score per axis, each already normalised to 0-100. */
  scores: Record<string, number>
  /** The unnormalised figures, shown on hover: a score of 82 means nothing. */
  raw?: Record<string, number>
}

interface RadarChartProps {
  axes: RadarAxis[]
  series: RadarSeries[]
  emptyMessage: string
  /** Rings drawn behind the shapes. Four is legible; more becomes a target. */
  rings?: number
}

const SIZE = 260
const CENTER = SIZE / 2
const RADIUS = SIZE / 2 - 34

/** Where an axis sits on the circle. Starts at twelve o'clock and turns right. */
function point(index: number, total: number, distance: number) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  return {
    x: CENTER + Math.cos(angle) * distance,
    y: CENTER + Math.sin(angle) * distance,
  }
}

function polygon(values: number[], total: number) {
  return values
    .map((value, index) => {
      const { x, y } = point(index, total, (Math.max(0, Math.min(100, value)) / 100) * RADIUS)
      return `${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

/**
 * Several subjects compared across the same handful of criteria.
 *
 * A radar is the right form for exactly one question: *is this one weak
 * somewhere the others are not*. It answers that better than four bar charts
 * side by side, because the shape itself carries the answer - a dented outline
 * is visible before any number is read.
 *
 * It is the wrong form for magnitude. The area a polygon covers grows with the
 * square of its values and changes with the order of the axes, so a shape that
 * looks "twice as big" is not twice anything. Every axis is therefore
 * normalised to 0-100 by the caller and the real figures live in the tooltip.
 *
 * Two subjects at a time is the practical limit: a third outline turns the
 * plot into a scribble. Callers filter before they get here.
 */
export function RadarChart({ axes, series, emptyMessage, rings = 4 }: RadarChartProps) {
  const [hovered, setHovered] = useState<number | null>(null)

  const shapes = useMemo(
    () =>
      series.map((entry) => ({
        entry,
        points: polygon(
          axes.map((axis) => entry.scores[axis.key] ?? 0),
          axes.length,
        ),
      })),
    [series, axes],
  )

  // Three axes is the minimum that encloses an area; below that the shape is a
  // line and the form is lying about being a comparison.
  if (axes.length < 3 || series.length === 0) {
    return <ChartEmpty message={emptyMessage} />
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="mx-auto block h-auto w-full max-w-[280px] overflow-visible"
        role="img"
        aria-label={`${series.map((entry) => entry.label).join(', ')} — ${axes
          .map((axis) => axis.label)
          .join(', ')}`}
      >
        {/* The grid: rings first, then spokes, both recessive. */}
        {Array.from({ length: rings }, (_, ring) => (
          <polygon
            key={ring}
            points={polygon(
              axes.map(() => ((ring + 1) / rings) * 100),
              axes.length,
            )}
            className="fill-none stroke-line"
            strokeWidth={1}
          />
        ))}

        {axes.map((axis, index) => {
          const outer = point(index, axes.length, RADIUS)
          return (
            <line
              key={axis.key}
              x1={CENTER}
              y1={CENTER}
              x2={outer.x}
              y2={outer.y}
              className="stroke-line"
              strokeWidth={1}
            />
          )
        })}

        {/* The shapes. Fills stay light so an overlap reads as an overlap and
            not as a fifth colour; the outline carries the identity. */}
        {shapes.map(({ entry, points }, index) => (
          <g
            key={entry.key}
            className={cn(
              'transition-opacity duration-200',
              hovered !== null && hovered !== index && 'opacity-30',
            )}
          >
            <polygon
              points={points}
              className={cn(SERIES_FILL[index % SERIES_FILL.length], SERIES_STROKE[index % SERIES_STROKE.length])}
              fillOpacity={0.18}
              strokeWidth={2}
              strokeLinejoin="round"
            />
            {axes.map((axis, axisIndex) => {
              const { x, y } = point(
                axisIndex,
                axes.length,
                (Math.max(0, Math.min(100, entry.scores[axis.key] ?? 0)) / 100) * RADIUS,
              )
              return (
                <circle
                  key={axis.key}
                  cx={x}
                  cy={y}
                  r={3.5}
                  className={cn(
                    SERIES_FILL[index % SERIES_FILL.length],
                    // A 2px ring in the surface colour, so two points that land
                    // on top of each other still read as two.
                    'stroke-panel',
                  )}
                  strokeWidth={2}
                />
              )
            })}
          </g>
        ))}

        {/* Axis labels, outside the outermost ring. */}
        {axes.map((axis, index) => {
          const { x, y } = point(index, axes.length, RADIUS + 18)
          return (
            <text
              key={axis.key}
              x={x}
              y={y}
              textAnchor={x > CENTER + 4 ? 'start' : x < CENTER - 4 ? 'end' : 'middle'}
              dominantBaseline="middle"
              className="fill-ink-3 text-[11px]"
            >
              {axis.label}
            </text>
          )
        })}
      </svg>

      {/* Identity is never colour alone: the legend names every shape, and
          hovering one dims the others rather than relying on hue memory. */}
      <ul className="mt-3 flex flex-wrap items-center justify-center gap-x-4 gap-y-1">
        {series.map((entry, index) => (
          <li key={entry.key}>
            <button
              type="button"
              onMouseEnter={() => setHovered(index)}
              onMouseLeave={() => setHovered(null)}
              onFocus={() => setHovered(index)}
              onBlur={() => setHovered(null)}
              className="flex min-h-[32px] cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-2xs text-ink-2 transition-colors hover:bg-elevated hover:text-ink"
            >
              <span
                className={cn(
                  'h-2 w-2 shrink-0 rounded-sm',
                  SERIES_FILL[index % SERIES_FILL.length].replace('fill-', 'bg-'),
                )}
                aria-hidden="true"
              />
              {entry.label}
            </button>
          </li>
        ))}
      </ul>

      {hovered !== null && series[hovered]?.raw && (
        <ChartTooltip
          x={50}
          y={0}
          title={series[hovered].label}
          rows={axes.map((axis) => {
            const raw = series[hovered].raw?.[axis.key]
            return {
              label: axis.label,
              value:
                raw === undefined
                  ? `${Math.round(series[hovered].scores[axis.key] ?? 0)}`
                  : (axis.format ?? String)(raw),
            }
          })}
        />
      )}
    </div>
  )
}
