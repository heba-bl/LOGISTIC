import { motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, ShieldAlert, type LucideIcon } from 'lucide-react'

import { EmptyState } from '@/components/ui'
import { useI18n } from '@/i18n/I18nProvider'
import { cn } from '@/utils/cn'
import { formatTime } from '@/utils/format'
import { severityStyles, toSeverity } from '@/utils/status'
import type { MessageKey } from '@/i18n/messages'
import type { Alert } from '@/types/domain'
import type { Severity } from '@/types'

const ALERT_ICON: Record<Severity, LucideIcon> = {
  crit: ShieldAlert,
  warn: AlertTriangle,
  info: Info,
  ok: CheckCircle2,
}

//: The severity word is read by an operator, so it is translated like the rest
//: of the interface - a French screen reading "CRITICAL" is the last thing left
//: in English on this page.
const ALERT_LABEL: Record<Severity, MessageKey> = {
  crit: 'severity.crit',
  warn: 'severity.warn',
  info: 'severity.info',
  ok: 'severity.ok',
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
  const { t } = useI18n()
  if (alerts.length === 0) {
    return (
      <EmptyState
        icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
        title={t('mission.noAlerts')}
        description={t('mission.noAlertsHint')}
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
                  {t(ALERT_LABEL[severity])}
                </span>
                <span className="numeric ml-auto shrink-0 text-2xs text-ink-3">
                  {formatTime(alert.timestamp)}
                </span>
              </div>
              <p className="mt-1 text-xs leading-relaxed text-ink">{alert.message_key
                  ? t(alert.message_key as MessageKey, alert.message_values)
                  : alert.message}</p>
              <p className="mt-1 text-2xs text-ink-3">{alert.source}</p>
            </div>
          </motion.li>
        )
      })}
    </ul>
  )
}
