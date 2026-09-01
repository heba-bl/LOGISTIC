import { motion } from 'framer-motion'

import { Meter, StatusDot } from '@/components/ui'
import { cn } from '@/utils/cn'
import { formatDecimal, formatNumber } from '@/utils/format'
import { useCountUp } from '@/hooks/useCountUp'
import { useI18n } from '@/i18n/I18nProvider'
import { severityStyles, toSeverity } from '@/utils/status'
import type { MessageKey } from '@/i18n/messages'
import type { Kpi } from '@/types/domain'

interface KpiGridProps {
  kpis: Kpi[]
}

/**
 * KPI row, fed by `GET /api/dashboard`.
 *
 * Each tile is a hero number: label above, value in mono figures, one line of
 * context below. Colour marks state; the text carries the meaning.
 */
//: The backend returns a stable id per KPI; the label is translated here.
const KPI_KEYS: Record<string, MessageKey> = {
  'active-lots': 'kpi.activeLots',
  'pending-inspections': 'kpi.pendingInspections',
  'uncovered-requests': 'kpi.uncoveredRequests',
  'warehouse-occupancy': 'kpi.warehouseOccupancy',
  'critical-alerts': 'kpi.criticalAlerts',
  'excel-sync': 'kpi.excelSync',
}

/**
 * One tile's figure, counting to its value.
 *
 * Its own component because the hook has to run per tile: called in the map
 * body it would be a conditional hook, and React would be right to complain.
 */
function Figure({ value, isRatio }: { value: number; isRatio: boolean }) {
  const shown = useCountUp(value)
  return (
    <span className="figure text-2xl leading-none">
      {isRatio ? formatDecimal(shown) : formatNumber(Math.round(shown))}
    </span>
  )
}

export function KpiGrid({ kpis }: KpiGridProps) {
  const { t } = useI18n()

  /**
   * The sub-line, in the interface language.
   *
   * Falls back to the backend's English wording rather than to nothing: a tile
   * missing its context line reads as a bug, while an untranslated one reads
   * as a translation still to do - which is what it is.
   */
  const worded = (kpi: Kpi) => {
    if (!kpi.hint_key) return kpi.hint
    const text = t(kpi.hint_key as MessageKey, kpi.hint_values)
    return text === kpi.hint_key ? kpi.hint : text
  }
  return (
    <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      {kpis.map((kpi, index) => {
        const severity = toSeverity(kpi.severity)
        const styles = severityStyles[severity]
        const isRatio = kpi.unit === '%'

        return (
          <motion.article
            key={kpi.id}
            initial={{ opacity: 0, y: 14 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
            className="panel group overflow-hidden p-4 transition-colors duration-200 hover:border-line-strong"
          >
            <span
              className={cn('absolute inset-x-0 top-0 h-px opacity-60', styles.bar)}
              aria-hidden="true"
            />

            <div className="flex items-start justify-between gap-2">
              <p className="eyebrow min-h-[2rem] leading-tight">
                {KPI_KEYS[kpi.id] ? t(KPI_KEYS[kpi.id]) : kpi.label}
              </p>
              <StatusDot severity={severity} pulse={severity === 'crit'} />
            </div>

            <p className="mt-3 flex items-baseline gap-1">
              <Figure value={kpi.value} isRatio={isRatio} />
              {kpi.unit && <span className="text-xs font-medium text-ink-3">{kpi.unit}</span>}
            </p>

            {typeof kpi.ratio === 'number' && (
              <Meter value={kpi.ratio} severity={severity} label={kpi.label} className="mt-3" />
            )}

            <p className="mt-2.5 text-2xs leading-relaxed text-ink-3">{worded(kpi)}</p>
          </motion.article>
        )
      })}
    </div>
  )
}
