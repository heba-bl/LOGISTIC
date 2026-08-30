import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, ShieldAlert, type LucideIcon } from 'lucide-react'

import { EmptyState } from '@/components/ui'
import { cn } from '@/utils/cn'
import { formatTime } from '@/utils/format'
import { severityStyles, toSeverity } from '@/utils/status'
import type { Alert } from '@/types/domain'
import type { Severity } from '@/types'

const ALERT_ICON: Record<Severity, LucideIcon> = {
  crit: ShieldAlert,
  warn: AlertTriangle,
  info: Info,
  ok: CheckCircle2,
}

const ALERT_LABEL: Record<Severity, string> = {
  crit: 'Critical',
  warn: 'Warning',
  info: 'Info',
  ok: 'Normal',
}

interface SmartAlertsProps {
  alerts: Alert[]
}

/**
 * Prioritised operational signals computed by the backend from live state:
 * blocked lots, uncovered production demand, safety-stock breaches, saturation.
 * Icon and label always accompany the colour.
 */
export function SmartAlerts({ alerts }: SmartAlertsProps) {
  if (alerts.length === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
        title="No active alert"
        description="Stock covers the confirmed demand and no lot is blocked."
      />
    )
  }

  return (
    <ul className="divide-y divide-line">
      {alerts.map((alert, index) => {
        const severity = toSeverity(alert.severity)
        const styles = severityStyles[severity]
        const Icon = ALERT_ICON[severity]

        return (
          <motion.li
            key={alert.id}
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.35, delay: Math.min(index, 6) * 0.06 }}
            className="flex gap-3 px-5 py-3.5 transition-colors hover:bg-elevated/40"
          >
            <span
              className={cn(
                'mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-md border',
                styles.border,
                styles.bg,
              )}
            >
              <Icon className={cn('h-3.5 w-3.5', styles.text)} strokeWidth={2} />
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={cn('text-2xs font-bold uppercase tracking-wider', styles.text)}
                >
                  {ALERT_LABEL[severity]}
                </span>
                <span className="numeric ml-auto shrink-0 text-2xs text-ink-3">
                  {formatTime(alert.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-ink">{alert.message}</p>
              <p className="mt-1 text-2xs text-ink-3">{alert.source}</p>
            </div>
          </motion.li>
        )
      })}
    </ul>
  )
}
