/**
 * The top row: five figures, read in under a second.
 *
 * A KPI tile carries four things and nothing else - the value, how it moved,
 * the shape of that movement, and one line of context. The status colour is a
 * 2px rule at the top rather than a coloured card: five coloured boxes compete
 * with each other and stop ranking anything.
 */

import { motion } from 'framer-motion'
import { ArrowDownRight, ArrowRight, ArrowUpRight } from 'lucide-react'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { STATE_BG, useUnitLabel } from './primitives'
import type { MessageKey } from '@/i18n/messages'
import type { OverviewKpi } from '@/types/overview'

/** A sparkline is a shape, not a chart: no axis, no labels, no tooltip. */
function Sparkline({ points, severity }: { points: number[]; severity: string }) {
  if (points.length < 2) return null

  const width = 100
  const height = 24
  const max = Math.max(...points)
  const min = Math.min(...points)
  const span = max - min || 1

  const x = (index: number) => (index / (points.length - 1)) * width
  const y = (value: number) => height - ((value - min) / span) * (height - 3) - 1.5

  const line = points.map((value, index) => `${x(index)},${y(value)}`).join(' ')
  const area = `0,${height} ${line} ${width},${height}`

  const stroke =
    severity === 'CRITICAL'
      ? 'stroke-crit'
      : severity === 'WARNING'
        ? 'stroke-warn'
        : 'stroke-chart-2'
  //: /10 and not /12: Tailwind's opacity scale steps by 5, and an off-scale
  //: modifier generates no class at all - the fill would fall back to black.
  const fill =
    severity === 'CRITICAL'
      ? 'fill-crit/10'
      : severity === 'WARNING'
        ? 'fill-warn/10'
        : 'fill-chart-2/10'

  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="h-6 w-full"
      aria-hidden="true"
    >
      <polygon points={area} className={fill} />
      <motion.polyline
        points={line}
        fill="none"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
        vectorEffect="non-scaling-stroke"
        className={stroke}
        initial={{ pathLength: 0 }}
        animate={{ pathLength: 1 }}
        transition={{ duration: 0.8, ease: [0.22, 1, 0.36, 1] }}
      />
    </svg>
  )
}

interface KpiCardProps {
  kpi: OverviewKpi
  index: number
  /** Whether a rise is good news. Blocked lots going up is not an improvement. */
  riseIsGood?: boolean
  onClick?: () => void
}

export function KpiCard({ kpi, index, riseIsGood = true, onClick }: KpiCardProps) {
  const { t, formatDecimal, formatNumber } = useI18n()

  const unitLabel = useUnitLabel()

  const label = t(`kpi.${kpi.id}` as MessageKey)
  const value =
    kpi.value === null
      ? '—'
      : kpi.decimals > 0
        ? formatDecimal(kpi.value, kpi.decimals)
        : formatNumber(kpi.value)

  const delta = kpi.delta_percent
  const rising = delta !== null && delta > 0
  const flat = delta === null || Math.abs(delta) < 0.05
  const DeltaIcon = flat ? ArrowRight : rising ? ArrowUpRight : ArrowDownRight
  const deltaIsGood = flat ? null : rising === riseIsGood

  const Element = onClick ? motion.button : motion.div

  return (
    <Element
      type={onClick ? 'button' : undefined}
      onClick={onClick}
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
      className={cn(
        'panel group relative overflow-hidden px-4 pb-3 pt-4 text-left',
        onClick && 'transition-colors hover:border-line-strong',
      )}
    >
      {/* Status reads as a rule, not as a filled card. */}
      <span
        className={cn('absolute inset-x-0 top-0 h-0.5', STATE_BG[kpi.severity])}
        aria-hidden="true"
      />

      <p className="eyebrow truncate">{label}</p>

      <div className="mt-2.5 flex items-baseline gap-1.5">
        <span className="numeric text-2xl font-semibold leading-none tracking-tight text-ink">
          {value}
        </span>
        {kpi.unit && (
          <span className="text-xs font-medium text-ink-3">{unitLabel(kpi.unit)}</span>
        )}
      </div>

      <div className="mt-2 flex items-center justify-between gap-2">
        {/* No trend line where there is no comparable previous period. Saying so
            in words would cost a line of type on every tile that has one, so the
            slot simply stays empty and the context claims the width. */}
        {delta !== null && (
          <span
            className={cn(
              'inline-flex shrink-0 items-center gap-0.5 rounded px-1 py-0.5 text-2xs font-semibold',
              flat
                ? 'text-ink-3'
                : deltaIsGood
                  ? 'bg-ok/12 text-ok-soft'
                  : 'bg-crit/12 text-crit-soft',
            )}
          >
            <DeltaIcon className="h-3 w-3" strokeWidth={2.4} />
            <span className="numeric">
              {rising ? '+' : ''}
              {formatDecimal(delta, 1)} %
            </span>
          </span>
        )}

        {kpi.context_key && kpi.context_value !== null && (
          <span className="ml-auto truncate text-2xs text-ink-3">
            {t(kpi.context_key as MessageKey, { value: formatNumber(kpi.context_value) })}
          </span>
        )}
      </div>

      {kpi.trend.length > 1 && (
        <div className="mt-2.5">
          <Sparkline
            points={kpi.trend.map((point) => point.value ?? 0)}
            severity={kpi.severity}
          />
        </div>
      )}

      {kpi.trend.length <= 1 && (
        /* No honest series exists for this measure, so the tile keeps its height
           without drawing a plausible line. */
        <p className="mt-2.5 h-6 text-[11px] leading-6 text-ink-3/70">{t('kpi.snapshot')}</p>
      )}
    </Element>
  )
}
