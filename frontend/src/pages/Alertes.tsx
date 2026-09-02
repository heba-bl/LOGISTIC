import { useMemo, useState } from 'react'
import { CheckCircle2 } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import { SmartAlerts } from '@/features/mission-control'
import { FilterBar, KpiRow, useFilterState, type SupervisionKpi } from '@/features/supervision/shell'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { alertsApi } from '@/services/slcc.service'

/**
 * The whole backlog, not the shortlist.
 *
 * Mission Control keeps eight alerts, one per kind, so a single situation
 * cannot fill the panel - right for a dashboard, useless for working through
 * sixty-nine. Taking eight in charge only made the next eight appear, and
 * nothing let a manager say "show me every shortage".
 *
 * The four figures at the top are the point. "Sixty-nine alerts" only ever
 * grows; "sixty-seven in nobody's hands" is a number somebody can move.
 */
export default function Alertes() {
  const { t, ts, formatNumber } = useI18n()
  const filters = useFilterState(['severity', 'kind'])
  const [refreshKey, setRefreshKey] = useState(0)

  const query = useMemo(
    () => ({
      severity: filters.values.severity || undefined,
      kind: filters.values.kind || undefined,
    }),
    [filters.values.severity, filters.values.kind],
  )

  const feed = useApiResource(
    () => alertsApi.list(query),
    [query.severity, query.kind, refreshKey],
    { pollMs: 60_000 },
  )

  const standing = feed.data?.standing ?? { total: 0, owned: 0, snoozed: 0, unowned: 0 }

  const kpis: SupervisionKpi[] = [
    {
      key: 'unowned',
      label: t('alerts.kpi.unowned'),
      value: formatNumber(standing.unowned ?? 0),
      hint: t('alerts.kpi.unownedHint'),
      // The only figure here that can be acted on, so the only one that alarms.
      severity: (standing.unowned ?? 0) > 0 ? 'CRITICAL' : 'OK',
    },
    {
      key: 'owned',
      label: t('alerts.kpi.owned'),
      value: formatNumber(standing.owned ?? 0),
      hint: t('alerts.kpi.ownedHint'),
      severity: 'OK',
    },
    {
      key: 'snoozed',
      label: t('alerts.kpi.snoozed'),
      value: formatNumber(standing.snoozed ?? 0),
      hint: t('alerts.kpi.snoozedHint'),
      severity: 'INFO',
    },
    {
      key: 'total',
      label: t('alerts.kpi.total'),
      value: formatNumber(standing.total ?? 0),
      hint: t('alerts.kpi.totalHint'),
      severity: 'INFO',
    },
  ]

  const alerts = feed.data?.alerts ?? []

  return (
    <div className="space-y-4">
      <PageHeader title={t('alerts.title')} description={t('alerts.subtitle')} />

      {feed.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : feed.error && !feed.data ? (
        <div className="panel">
          <ErrorPanel message={feed.error} onRetry={feed.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <FilterBar
            search=""
            onSearch={() => {}}
            placeholder={t('alerts.title')}
            count={t('common.rowsShown', {
              shown: formatNumber(alerts.length),
              total: formatNumber(standing.total ?? 0),
            })}
            onReset={filters.reset}
            selects={[
              {
                key: 'severity',
                label: t('common.status'),
                value: filters.values.severity,
                onChange: (value) => filters.set('severity', value),
                options: ['CRITICAL', 'WARNING', 'INFO'].map((value) => ({
                  value,
                  label: ts(value),
                })),
              },
              {
                key: 'kind',
                label: t('alerts.kind'),
                value: filters.values.kind,
                onChange: (value) => filters.set('kind', value),
                options: (feed.data?.kinds ?? []).map((value) => ({
                  value,
                  label: ts(value),
                })),
              },
            ]}
          />

          <ChartCard
            title={t('alerts.list')}
            question={t('alerts.listQuestion')}
            bodyClassName="px-0 pb-0"
          >
            {alerts.length === 0 ? (
              <div className="px-5 pb-5">
                <EmptyState
                  icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
                  title={t('mission.noAlerts')}
                  description={t('alerts.noneMatching')}
                />
              </div>
            ) : (
              <SmartAlerts alerts={alerts} onChanged={() => setRefreshKey((n) => n + 1)} />
            )}
          </ChartCard>
        </>
      )}
    </div>
  )
}
