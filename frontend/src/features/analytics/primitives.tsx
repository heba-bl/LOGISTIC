/**
 * Chart shell, hero figures and the small pieces every visualisation reuses.
 *
 * The whole library is hand-drawn SVG rather than a charting dependency: the
 * shapes here are simple, and owning them is what lets every mark carry a
 * direct label and inherit the theme tokens in both light and dark mode.
 *
 * One rule governs colour throughout: `chart-1..4` are identity (fixed order,
 * never cycled), `seq-1..5` are magnitude, and `ok/warn/crit/info` are reserved
 * for state. A mark never wears a status colour unless the value *is* a state.
 */

import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import type { MessageKey } from '@/i18n/messages'
import type { Severity4 } from '@/types/overview'

// --------------------------------------------------------------------- shell
interface ChartCardProps {
  /** Short title. The question it answers goes in `question`, not here. */
  title: string
  /** The business question this visualisation exists to answer. */
  question?: string
  action?: ReactNode
  footer?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
  delay?: number
}

export function ChartCard({
  title,
  question,
  action,
  footer,
  className,
  bodyClassName,
  children,
  delay = 0,
}: ChartCardProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      className={cn('panel flex flex-col', className)}
    >
      <header className="flex items-start justify-between gap-3 px-5 pb-3 pt-4">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold tracking-tight text-ink">{title}</h2>
          {question && <p className="mt-0.5 text-2xs text-ink-3">{question}</p>}
        </div>
        {action && <div className="shrink-0">{action}</div>}
      </header>
      <div className={cn('flex-1 px-5 pb-5', bodyClassName)}>{children}</div>
      {footer && (
        <footer className="border-t border-line px-5 py-2.5 text-2xs text-ink-3">{footer}</footer>
      )}
    </motion.section>
  )
}

export function ChartEmpty({ message }: { message: string }) {
  return (
    <div className="grid h-full min-h-[120px] place-items-center px-4 py-8 text-center">
      <p className="text-2xs leading-relaxed text-ink-3">{message}</p>
    </div>
  )
}

// -------------------------------------------------------------------- colours
/** Categorical slots, in assignment order. A fifth series folds into "Other". */
export const SERIES_FILL = ['fill-chart-1', 'fill-chart-2', 'fill-chart-3', 'fill-chart-4']
export const SERIES_BG = ['bg-chart-1', 'bg-chart-2', 'bg-chart-3', 'bg-chart-4']
export const SERIES_STROKE = [
  'stroke-chart-1',
  'stroke-chart-2',
  'stroke-chart-3',
  'stroke-chart-4',
]

/** Sequential ramp for magnitude. Index 0 is the deepest step. */
export const RAMP_BG = ['bg-seq-1', 'bg-seq-2', 'bg-seq-3', 'bg-seq-4', 'bg-seq-5']

/**
 * Type colour for a label sitting on each ramp step.
 *
 * Measured, not guessed, and the crossover is not in the same place in the two
 * modes: the light ramp runs deep-to-pale while the dark one runs pale-to-deep,
 * so the middle steps need opposite ink. Hence the `dark:` overrides rather
 * than one threshold for both.
 */
export const RAMP_TEXT = [
  'text-panel',
  'text-panel',
  'text-ink dark:text-panel',
  'text-ink dark:text-panel',
  'text-ink',
]
export const RAMP_FILL = ['fill-seq-1', 'fill-seq-2', 'fill-seq-3', 'fill-seq-4', 'fill-seq-5']

/** Reserved state colours. Used only when the value is genuinely a state. */
export const STATE_BG: Record<Severity4, string> = {
  OK: 'bg-ok',
  WARNING: 'bg-warn',
  CRITICAL: 'bg-crit',
  INFO: 'bg-info',
}
export const STATE_FILL: Record<Severity4, string> = {
  OK: 'fill-ok',
  WARNING: 'fill-warn',
  CRITICAL: 'fill-crit',
  INFO: 'fill-info',
}
export const STATE_TEXT: Record<Severity4, string> = {
  OK: 'text-ok-soft',
  WARNING: 'text-warn-soft',
  CRITICAL: 'text-crit-soft',
  INFO: 'text-info-soft',
}
export const STATE_BORDER: Record<Severity4, string> = {
  OK: 'border-ok/35',
  WARNING: 'border-warn/35',
  CRITICAL: 'border-crit/35',
  INFO: 'border-info/35',
}

/** Pick a ramp step for a 0-100 ratio. Deepest step = fullest. */
export function rampStep(percent: number): number {
  if (percent >= 90) return 0
  if (percent >= 70) return 1
  if (percent >= 45) return 2
  if (percent >= 20) return 3
  return 4
}

// ------------------------------------------------------------------- legend
export function Legend({
  items,
}: {
  items: { label: string; className: string; value?: string }[]
}) {
  return (
    <ul className="flex flex-wrap items-center gap-x-4 gap-y-1.5">
      {items.map((item) => (
        <li key={item.label} className="flex items-center gap-1.5 text-2xs text-ink-2">
          <span className={cn('h-2 w-2 shrink-0 rounded-[2px]', item.className)} />
          {item.label}
          {item.value && <span className="numeric text-ink-3">{item.value}</span>}
        </li>
      ))}
    </ul>
  )
}

// -------------------------------------------------------------------- units
/**
 * Resolve a unit token to a word in the current language.
 *
 * The API sends `pcs` / `days` / `%`: deciding whether the screen reads "j" or
 * "d" is the interface's job, not the backend's. Anything unrecognised is
 * passed through, so a literal like "%" still works.
 */
export function useUnitLabel(): (unit: string | null | undefined) => string {
  const { t } = useI18n()
  return (unit) => {
    if (!unit) return ''
    return unit === 'pcs' || unit === 'days' ? t(`unit.${unit}` as MessageKey) : unit
  }
}

// ------------------------------------------------------------------ risk chip
export function RiskChip({ risk, label }: { risk: Severity4; label?: string }) {
  const { t } = useI18n()
  const text = label ?? t(`risk.${risk}` as MessageKey)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[10px] font-medium',
        STATE_BORDER[risk],
        STATE_TEXT[risk],
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', STATE_BG[risk])} />
      {text}
    </span>
  )
}

// ------------------------------------------------------------------- tooltip
export function ChartTooltip({
  x,
  y,
  title,
  rows,
}: {
  x: number
  y: number
  title: string
  rows: { label: string; value: string; className?: string }[]
}) {
  return (
    <div
      className="pointer-events-none absolute z-20 min-w-[9rem] -translate-x-1/2 -translate-y-full rounded-md border border-line bg-panel px-2.5 py-2 shadow-panel"
      style={{ left: `${x}%`, top: `${y}%` }}
    >
      <p className="text-2xs font-semibold text-ink">{title}</p>
      <ul className="mt-1 space-y-0.5">
        {rows.map((row) => (
          <li key={row.label} className="flex items-baseline justify-between gap-3 text-[10px]">
            <span className="text-ink-3">{row.label}</span>
            <span className={cn('numeric font-medium text-ink-2', row.className)}>
              {row.value}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
