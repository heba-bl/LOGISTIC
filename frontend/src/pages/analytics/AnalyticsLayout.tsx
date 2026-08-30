import { useCallback, useMemo, useState } from 'react'
import { NavLink, Outlet, useOutletContext } from 'react-router-dom'
import { Database, RefreshCw } from 'lucide-react'

import { Button, ErrorPanel, LoadingPanel } from '@/components/ui'
import { PowerBiDialog } from '@/features/analytics/PowerBiDialog'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { analyticsApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import type { MessageKey } from '@/i18n/messages'
import type { Overview, PeriodKey } from '@/types/overview'

/**
 * The four Analytics tabs share one window and one request.
 *
 * Fetching per tab would let two screens disagree about the same day, which is
 * the fastest way to lose a manager's trust in a dashboard. The period lives
 * here, the payload is fetched once, and the tabs read it through the outlet.
 */

export interface AnalyticsContext {
  overview: Overview
  refresh: () => void
}

export function useOverview(): AnalyticsContext {
  return useOutletContext<AnalyticsContext>()
}

const PERIODS: PeriodKey[] = ['today', '7d', '30d', 'custom']

const TABS: { path: string; labelKey: MessageKey; end?: boolean }[] = [
  { path: '/analytics', labelKey: 'analytics.tab.overview', end: true },
  { path: '/analytics/stock', labelKey: 'analytics.tab.stock' },
  { path: '/analytics/qualite', labelKey: 'analytics.tab.quality' },
  { path: '/analytics/production', labelKey: 'analytics.tab.production' },
]

function isoDaysAgo(days: number): string {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

export default function AnalyticsLayout() {
  const { t, formatTime, formatDay } = useI18n()

  const [period, setPeriod] = useState<PeriodKey>('30d')
  const [from, setFrom] = useState(() => isoDaysAgo(14))
  const [to, setTo] = useState(() => new Date().toISOString().slice(0, 10))
  const [powerbiOpen, setPowerbiOpen] = useState(false)

  const query = useMemo(
    () =>
      period === 'custom'
        ? { period, date_from: from, date_to: to }
        : { period },
    [period, from, to],
  )

  const resource = useApiResource(() => analyticsApi.overview(query), [query])
  const refresh = useCallback(() => void resource.refresh(), [resource])

  const overview = resource.data

  return (
    <div className="space-y-5">
      {/* ------------------------------------------------------------ header */}
      <header className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="eyebrow">{t('app.name')}</p>
          <h1 className="mt-1 text-xl font-semibold tracking-tight text-ink">
            {t('analytics.title')}
          </h1>
          <p className="mt-1 text-2xs text-ink-3">{t('analytics.subtitle')}</p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Period selector: one row, above the charts. */}
          <div
            className="inline-flex rounded-lg border border-line bg-panel p-0.5"
            role="group"
            aria-label={t('reports.period')}
          >
            {PERIODS.map((key) => (
              <button
                key={key}
                type="button"
                onClick={() => setPeriod(key)}
                aria-pressed={period === key}
                className={cn(
                  'rounded-md px-3 py-1.5 text-2xs font-medium transition-colors',
                  period === key
                    ? 'bg-accent text-panel'
                    : 'text-ink-2 hover:bg-elevated hover:text-ink',
                )}
              >
                {t(`period.${key}` as MessageKey)}
              </button>
            ))}
          </div>

          {period === 'custom' && (
            <div className="flex items-center gap-1.5">
              <input
                type="date"
                value={from}
                max={to}
                onChange={(event) => setFrom(event.target.value)}
                className="numeric rounded-md border border-line bg-panel px-2 py-1.5 text-2xs text-ink focus:border-accent/60 focus:outline-none"
              />
              <span className="text-2xs text-ink-3">→</span>
              <input
                type="date"
                value={to}
                min={from}
                onChange={(event) => setTo(event.target.value)}
                className="numeric rounded-md border border-line bg-panel px-2 py-1.5 text-2xs text-ink focus:border-accent/60 focus:outline-none"
              />
            </div>
          )}

          <Button
            variant="secondary"
            icon={<Database className="h-3.5 w-3.5" />}
            onClick={() => setPowerbiOpen(true)}
          >
            {t('analytics.powerbi')}
          </Button>

          <Button
            variant="secondary"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            loading={resource.loading && !resource.initialLoading}
            onClick={refresh}
          >
            {t('common.refresh')}
          </Button>
        </div>
      </header>

      {/* -------------------------------------------------------------- tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line">
        <nav className="-mb-px flex gap-1 overflow-x-auto" aria-label={t('analytics.title')}>
          {TABS.map((tab) => (
            <NavLink
              key={tab.path}
              to={tab.path}
              end={tab.end}
              className={({ isActive }) =>
                cn(
                  'whitespace-nowrap border-b-2 px-3 py-2.5 text-xs font-medium transition-colors',
                  isActive
                    ? 'border-accent text-ink'
                    : 'border-transparent text-ink-3 hover:border-line-strong hover:text-ink-2',
                )
              }
            >
              {t(tab.labelKey)}
            </NavLink>
          ))}
        </nav>

        {overview && (
          <p className="numeric pb-2 text-2xs text-ink-3">
            {t('analytics.periodRange', {
              from: formatDay(overview.period.start_date),
              to: formatDay(overview.period.end_date),
            })}
            {' · '}
            {t('analytics.lastSync')} {formatTime(overview.generated_at)}
          </p>
        )}
      </div>

      {/* ------------------------------------------------------------ content */}
      {resource.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={8} />
        </div>
      ) : resource.error ? (
        <div className="panel">
          <ErrorPanel message={resource.error} onRetry={refresh} />
        </div>
      ) : overview ? (
        <Outlet context={{ overview, refresh } satisfies AnalyticsContext} />
      ) : null}

      <PowerBiDialog open={powerbiOpen} onClose={() => setPowerbiOpen(false)} />
    </div>
  )
}
