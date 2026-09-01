import { motion } from 'framer-motion'

import { EmptyState } from '@/components/ui'
import { useI18n } from '@/i18n/I18nProvider'
import { cn } from '@/utils/cn'
import { formatTime } from '@/utils/format'
import { severityStyles, toSeverity } from '@/utils/status'
import type { ActivityEvent } from '@/types/domain'

interface RecentActivityProps {
  events: ActivityEvent[]
}

/** Chronological trace of operator actions, read straight from the audit trail. */
export function RecentActivity({ events }: RecentActivityProps) {
  const { t } = useI18n()
  if (events.length === 0) {
    return <EmptyState title={t('mission.noActivity')} description={t('mission.noActivityHint')} />
  }

  return (
    <ol className="relative px-5 py-4">
      <span className="absolute left-[38px] bottom-6 top-6 w-px bg-line" aria-hidden="true" />

      {events.map((event, index) => {
        const styles = severityStyles[toSeverity(event.severity)]
        return (
          <motion.li
            key={event.id}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: Math.min(index, 10) * 0.04 }}
            className="relative flex gap-4 pb-4 last:pb-0"
          >
            <span className="numeric w-9 shrink-0 pt-0.5 text-2xs text-ink-3">
              {formatTime(event.occurred_at)}
            </span>

            <span className="relative z-10 mt-1 flex h-2.5 w-2.5 shrink-0">
              <span className={cn('h-2.5 w-2.5 rounded-full ring-4 ring-panel', styles.bar)} />
            </span>

            <div className="min-w-0 flex-1 pb-1">
              <p className="text-xs font-medium text-ink">{event.label}</p>
              <p className="mt-0.5 line-clamp-2 text-2xs leading-relaxed text-ink-3">
                {event.detail}
              </p>
              <p className="mt-0.5 text-[11px] text-ink-3/80">{event.actor_name}</p>
            </div>
          </motion.li>
        )
      })}
    </ol>
  )
}
