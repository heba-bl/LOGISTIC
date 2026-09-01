import type { ReactNode } from 'react'

import { cn } from '@/utils/cn'
import { severityStyles } from '@/utils/status'
import type { Severity } from '@/types'

interface BadgeProps {
  severity?: Severity
  children: ReactNode
  icon?: ReactNode
  className?: string
}

/** Status pill. Colour is never the only carrier of meaning — the text is. */
export function Badge({ severity = 'info', children, icon, className }: BadgeProps) {
  const styles = severityStyles[severity]
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-2xs font-semibold uppercase tracking-wider',
        styles.border,
        styles.bg,
        styles.text,
        className,
      )}
    >
      {icon}
      {children}
    </span>
  )
}
