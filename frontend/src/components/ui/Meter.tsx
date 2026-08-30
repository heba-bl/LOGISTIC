import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { severityStyles } from '@/utils/status'
import type { Severity } from '@/types'

interface MeterProps {
  /** 0-100. */
  value: number
  severity?: Severity
  className?: string
  label?: string
}

/** Single-track magnitude meter (occupancy, load, coverage). */
export function Meter({ value, severity = 'info', className, label }: MeterProps) {
  const clamped = Math.max(0, Math.min(100, value))
  return (
    <div
      className={cn('w-full', className)}
      role="meter"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? 'progress'}
    >
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-line">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${clamped}%` }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          className={cn('h-full rounded-full', severityStyles[severity].bar)}
        />
      </div>
    </div>
  )
}
