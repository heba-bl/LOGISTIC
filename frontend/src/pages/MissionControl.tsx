import { useState } from 'react'
import { Activity, RadioTower, RefreshCw } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Button, ErrorPanel, LoadingPanel, Panel, StatusDot } from '@/components/ui'
import {
  KpiGrid,
  LogisticsCopilot,
  LogisticsFlow,
  RecentActivity,
  SmartAlerts,
} from '@/features/mission-control'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { dashboardApi } from '@/services/slcc.service'

/**
 * Mission Control - the plant right now.
 *
 * Every figure here is a snapshot, polled every 30 seconds. Nothing on this
 * screen covers a period: totals, rates and trends live on the Analyse screens,
 * and showing them in both places produced two different numbers for the same
 * question. What this screen owns is the present tense - where the lots are,
 * what is blocked, who did what a minute ago, and whether the workbook that
 * feeds all of it is still up to date.
 */
export default function MissionControl() {
  const { t, formatTime } = useI18n()
  const dashboard = useApiResource(() => dashboardApi.get(), [], { pollMs: 30000 })
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  const operational = dashboard.data?.system_status === 'OPERATIONAL'
  const severity = dashboard.error ? 'crit' : operational ? 'ok' : 'warn'
  const label = dashboard.error
    ? t('mission.backendUnreachable')
    : !dashboard.data
      ? t('mission.initialising')
      : operational
        ? t('mission.operational')
        : t('mission.degraded')

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('mission.title')}
        description={t('mission.subtitle')}
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              icon={<RefreshCw className="h-3.5 w-3.5" />}
              loading={dashboard.loading && !dashboard.initialLoading}
              onClick={dashboard.refresh}
            >
              {t('common.refresh')}
            </Button>
            <div className="flex items-center gap-2 rounded-lg border border-line bg-panel px-3 py-2">
              <StatusDot severity={severity} pulse />
              <span className="text-xs font-medium text-ink">{label}</span>
              {dashboard.data && (
                <span className="numeric ml-1 border-l border-line pl-2 text-2xs text-ink-3">
                  {formatTime(dashboard.data.generated_at)}
                </span>
              )}
            </div>
          </div>
        }
      />

      {dashboard.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={6} />
        </Panel>
      ) : dashboard.error && !dashboard.data ? (
        <Panel bodyClassName="">
          <ErrorPanel message={dashboard.error} onRetry={dashboard.refresh} />
        </Panel>
      ) : dashboard.data ? (
        <>
          <KpiGrid kpis={dashboard.data.kpis} />

          {/* Flow: full width so the six stages never clip */}
          <div className="grid gap-4">
            <Panel
              title={t('mission.flow')}
              subtitle={t('mission.flowSubtitle')}
              delay={0.1}
              action={
                <span className="flex items-center gap-1.5 text-2xs text-ink-3">
                  <RadioTower className="h-3 w-3 text-accent" />
                  live
                </span>
              }
            >
              <LogisticsFlow
                stages={dashboard.data.stages}
                onSelectLot={(lot) => setSelectedLotId(lot.id)}
              />
            </Panel>
          </div>

          {/* Alerts, full width. The lots that used to sit beside them are the
              same ones the flow already shows under their stage. */}
          <Panel
            title={t('mission.alerts')}
            // The count that matters is not how many alerts exist but how
            // many are in nobody's hands: the first only grows, the second is
            // the one a manager can act on.
            subtitle={t('alert.standing', dashboard.data.alert_standing ?? {
              total: dashboard.data.alerts.length,
              owned: 0,
              snoozed: 0,
              unowned: dashboard.data.alerts.length,
            })}
            delay={0.16}
            bodyClassName=""
            action={<Activity className="h-3.5 w-3.5 text-ink-3" />}
          >
            <SmartAlerts alerts={dashboard.data.alerts} onChanged={dashboard.refresh} />
          </Panel>

          {/* Activity + copilot */}
          <div className="grid gap-4 xl:grid-cols-3 xl:items-start">
            <Panel title={t('mission.activity')} subtitle={t('mission.activitySubtitle')} delay={0.24} bodyClassName="">
              <RecentActivity events={dashboard.data.activity} />
            </Panel>

            <Panel className="xl:col-span-2" delay={0.28} bodyClassName="">
              <LogisticsCopilot compact />
            </Panel>
          </div>
        </>
      ) : null}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}
