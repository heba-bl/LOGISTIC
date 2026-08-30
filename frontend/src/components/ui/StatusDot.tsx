import { cn } from '@/utils/cn'
import { severityStyles } from '@/utils/status'
import type { Severity } from '@/types'

interface StatusDotProps {
  severity: Severity
  /** Emit a radar-style pulse (live/active states only). */
  pulse?: boolean
  className?: string
}

/** Small functional indicator. Always accompanied by a text label in the UI. */
export function StatusDot({ severity, pulse = false, className }: StatusDotProps) {
  const styles = severityStyles[severity]
  return (
    <span className={cn('relative inline-flex h-2 w-2 shrink-0', className)}>
      {pulse && (
        <span
          className={cn('absolute inline-flex h-full w-full rounded-full animate-pulse-ring', styles.dot)}
          aria-hidden="true"
        />
      )}
      <span className={cn('relative inline-flex h-2 w-2 rounded-full', styles.dot)} />
    </span>
  )
}
