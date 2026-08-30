import { useNavigate } from 'react-router-dom'

import { ChartCard, ChartEmpty, RiskChip } from '@/features/analytics/primitives'
import { Gauge } from '@/features/analytics/circular'
import { HBarChart, StackedBar } from '@/features/analytics/bars'
import { DecisionList, PriorityTable } from '@/features/analytics/decision'
import { ScatterPlot } from '@/features/analytics/series'
import { useI18n } from '@/i18n/I18nProvider'
import { useOverview } from './AnalyticsLayout'
import type { Decision } from '@/types/overview'

/**
 * Colour by what the status means, not by the order it arrived in.
 *
 * These are not unrelated categories - they are the stages of one request. A
 * served request is green, a request still moving wears the blue family, and a
 * request that was closed without being served is neutral: nothing went wrong,
 * but nothing was delivered either. Purple stays reserved for the assistant.
 */
const STATUS_FILL: Record<string, string> = {
  ISSUED: 'bg-ok',
  READY: 'bg-seq-3',
  PREPARING: 'bg-seq-4',
  APPROVED: 'bg-chart-1',
  SUBMITTED: 'bg-seq-5',
  DRAFT: 'bg-line-strong',
  CANCELLED: 'bg-ink-3/50',
  REJECTED: 'bg-crit',
}
const STATUS_FALLBACK = 'bg-line-strong'

/**
 * Page 4 - demand, what it consumed, and what it may not get.
 *
 * The scatter is the centrepiece: a reference that is used fast and held thin
 * is the one that stops a line, and no bar chart puts those two dimensions on
 * the same picture.
 */
export default function ProductionRisques() {
  const { t, ts, formatNumber } = useI18n()
  const { overview } = useOverview()
  const navigate = useNavigate()

  const { production, risk_scatter, stock_vs_demand, decisions } = overview

  function openDecision(decision: Decision) {
    const routes: Record<string, string> = {
      stock: '/warehouse',
      warehouse: '/warehouse',
      quality: '/quality',
    }
    navigate(routes[decision.target] ?? '/mission-control')
  }

  //: Statuses beyond the four categorical slots are grouped rather than given a
  //: generated colour.
  const statusSegments = production.by_status.slice(0, 4).map((row) => ({
    key: row.status,
    label: ts(row.status),
    value: row.count,
    className: STATUS_FILL[row.status] ?? STATUS_FALLBACK,
  }))
  const others = production.by_status.slice(4)
  if (others.length > 0) {
    statusSegments.push({
      key: 'other',
      label: t('common.other'),
      value: others.reduce((sum, row) => sum + row.count, 0),
      className: 'bg-line-strong',
    })
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 xl:grid-cols-3">
        <ChartCard
          title={t('card.serviceRate.title')}
          question={t('card.serviceRate.question')}
          bodyClassName="px-5 pb-5 pt-2"
        >
          {production.service_rate_percent === null ? (
            <ChartEmpty message={t('card.serviceRate.empty')} />
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Gauge
                value={production.service_rate_percent}
                label={t('card.serviceRate.title')}
                target={90}
                warning={90}
                critical={70}
                targetLabel={t('gauge.target', { value: 90 })}
              />
              <p className="numeric text-center text-2xs text-ink-3">
                {t('production.servedOf', {
                  issued: formatNumber(production.issued),
                  requested: formatNumber(production.requested),
                })}
              </p>
            </div>
          )}
        </ChartCard>

        <ChartCard
          title={t('card.requestStatus.title')}
          question={t('card.requestStatus.question')}
          delay={0.05}
        >
          <StackedBar
            segments={statusSegments}
            emptyMessage={t('card.requestStatus.empty')}
          />
        </ChartCard>

        <ChartCard
          title={t('card.consumption.title')}
          question={t('card.consumption.question')}
          delay={0.08}
        >
          <HBarChart
            points={production.consumption.map((row) => ({
              key: row.reference,
              label: row.reference,
              value: row.value,
            }))}
            unit={` ${t('unit.pcs')}`}
            emptyMessage={t('card.consumption.empty')}
          />
        </ChartCard>
      </div>

      <ChartCard
        title={t('card.scatter.title')}
        question={t('card.scatter.question')}
        delay={0.11}
      >
        <ScatterPlot
          points={risk_scatter}
          emptyMessage={t('card.scatter.empty')}
          axisLabels={{ x: t('scatter.x'), y: t('scatter.y') }}
          sizeLabel={t('scatter.size')}
          riskZoneLabel={t('scatter.riskZone')}
          coverageLabel={(days) => t('scatter.coverageUnder', { days })}
          coverageTitle={t('chart.coverage')}
          onSelect={() => navigate('/warehouse')}
        />
      </ChartCard>

      <ChartCard
        title={t('card.uncovered.title')}
        question={t('card.uncovered.question')}
        delay={0.14}
        bodyClassName="px-0 pb-0"
      >
        {production.uncovered.length === 0 ? (
          <div className="px-5 pb-5">
            <ChartEmpty message={t('card.uncovered.empty')} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[680px]">
              <thead>
                <tr>
                  <th>{t('table.request')}</th>
                  <th>{t('table.station')}</th>
                  <th>{t('common.reference')}</th>
                  <th className="text-right">{t('table.requested')}</th>
                  <th className="text-right">{t('table.available')}</th>
                  <th className="text-right">{t('table.shortfall')}</th>
                  <th>{t('table.priority')}</th>
                </tr>
              </thead>
              <tbody>
                {production.uncovered.map((row) => (
                  <tr
                    key={row.reference}
                    onClick={() => navigate('/production')}
                    className="cursor-pointer"
                  >
                    <td className="numeric text-xs font-medium text-ink">{row.reference}</td>
                    <td className="numeric">{row.station}</td>
                    <td className="numeric">{row.part_reference}</td>
                    <td className="numeric text-right">{formatNumber(row.requested)}</td>
                    <td className="numeric text-right">{formatNumber(row.available)}</td>
                    <td className="numeric text-right font-semibold text-crit-soft">
                      -{formatNumber(row.shortfall)}
                    </td>
                    <td>
                      <RiskChip
                        risk={row.priority === 1 ? 'CRITICAL' : row.priority === 2 ? 'WARNING' : 'INFO'}
                        label={`P${row.priority}`}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>

      <ChartCard
        title={t('card.priorities.title')}
        question={t('card.priorities.question')}
        delay={0.17}
        bodyClassName="px-0 pb-0"
      >
        <PriorityTable
          rows={stock_vs_demand}
          emptyMessage={t('card.priorities.empty')}
          onSelect={() => navigate('/warehouse')}
        />
      </ChartCard>

      <ChartCard
        title={t('card.decisions.title')}
        question={t('card.decisions.question')}
        delay={0.2}
      >
        <DecisionList
          decisions={decisions}
          emptyMessage={t('card.decisions.empty')}
          onOpen={openDecision}
        />
      </ChartCard>
    </div>
  )
}
