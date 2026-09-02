import { AlertTriangle, Clock, WifiOff } from 'lucide-react'

import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { dashboardApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'

/** Past this, the screen is describing a shift that has already ended. */
const WARN_MINUTES = 120
const CRITICAL_MINUTES = 720

/**
 * Says, above everything else, when the figures stopped being true.
 *
 * This site is a mirror of the shared workbook, and a mirror that lags without
 * saying so is worse than a blank screen: a blank screen tells you that you do
 * not know, while a screen showing forty-four alerts from ten hours ago gets
 * decided on. That is the one serious objection to the whole architecture, and
 * this is the answer to it.
 *
 * It appears only past the threshold. A banner that is always there stops being
 * read within a week, and then it is decoration standing where a warning
 * belongs.
 *
 * The figure comes from the same `excel-sync` indicator Mission Control shows,
 * so the banner and the tile can never disagree.
 */
export function StalenessBanner() {
  const { t } = useI18n()
  const dashboard = useApiResource(() => dashboardApi.get(), [], { pollMs: 60_000 })

  // Two different ages, one banner. The API being unreachable is the more
  // serious of the two - the workbook may be perfectly up to date while this
  // screen has stopped hearing about it - so it wins when both apply.
  if (dashboard.stale) {
    const since = dashboard.lastSuccessAt
    return (
      <div
        role="status"
        className="rise mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-crit/40 bg-crit/10 px-4 py-3 text-crit-soft"
      >
        <WifiOff className="h-4 w-4 shrink-0" aria-hidden="true" />
        <p className="text-xs font-semibold">
          {t('frozen.title', {
            time: since ? since.toLocaleTimeString('fr-FR', { hour: '2-digit', minute: '2-digit' }) : '—',
          })}
        </p>
        <p className="text-2xs opacity-90">{t('frozen.detail')}</p>
      </div>
    )
  }

  const sync = dashboard.data?.kpis?.find((kpi) => kpi.id === 'excel-sync')
  if (!sync) return null

  const minutes = Math.round(sync.value)
  if (minutes < WARN_MINUTES) return null

  const critical = minutes >= CRITICAL_MINUTES
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  // Hours and minutes past the first hour: "9 h 33" is read at a glance,
  // "573 min" has to be divided before it means anything.
  const age = hours > 0 ? t('stale.age', { hours, minutes: rest }) : `${minutes} min`

  return (
    <div
      role="status"
      className={cn(
        'rise mb-5 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border px-4 py-3',
        critical
          ? 'border-crit/40 bg-crit/10 text-crit-soft'
          : 'border-warn/40 bg-warn/10 text-warn-soft',
      )}
    >
      {critical ? (
        <AlertTriangle className="h-4 w-4 shrink-0" aria-hidden="true" />
      ) : (
        <Clock className="h-4 w-4 shrink-0" aria-hidden="true" />
      )}
      <p className="text-xs font-semibold">{t('stale.title', { age })}</p>
      <p className="text-2xs opacity-90">{t('stale.detail')}</p>
    </div>
  )
}
