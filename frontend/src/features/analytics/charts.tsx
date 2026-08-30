/**
 * The hero-number tile used by the AI assistant.
 *
 * The chart forms that used to live here moved to `primitives`, `bars`,
 * `circular` and `series` when Analytics was rebuilt. Only the stat tile is
 * left, because not every figure needs a chart.
 */

import { cn } from '@/utils/cn'
import { severityStyles } from '@/utils/status'
import type { Severity } from '@/types'

/** Hero number with an optional qualifier. Not every figure needs a chart. */
export function StatTile({
  label,
  value,
  unit,
  hint,
  severity = 'info',
}: {
  label: string
  value: string
  unit?: string
  hint?: string
  severity?: Severity
}) {
  const styles = severityStyles[severity]
  return (
    <div className="relative overflow-hidden rounded-lg border border-line bg-elevated/60 p-4">
      <span className={cn('absolute inset-x-0 top-0 h-px opacity-70', styles.bar)} />
      <p className="eyebrow">{label}</p>
      <p className="mt-2 flex items-baseline gap-1">
        <span className="numeric text-xl font-semibold leading-none text-ink">{value}</span>
        {unit && <span className="text-2xs text-ink-3">{unit}</span>}
      </p>
      {hint && <p className="mt-1.5 text-2xs leading-relaxed text-ink-3">{hint}</p>}
    </div>
  )
}
