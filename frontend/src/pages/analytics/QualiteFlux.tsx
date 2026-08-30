import { useNavigate } from 'react-router-dom'

import { ChartCard, ChartEmpty } from '@/features/analytics/primitives'
import { DonutChart, Gauge } from '@/features/analytics/circular'
import { FlowFunnel } from '@/features/analytics/decision'
import { AnalyticsHistogram, AnalyticsLineChart } from '@/features/analytics'
import { useI18n } from '@/i18n/I18nProvider'
import { useOverview } from './AnalyticsLayout'

/**
 * Page 3 - what the plant receives, and how fast it moves through.
 *
 * Compliance answers "is what arrives usable"; the flow answers "and how long
 * does it take to become stock". Together they explain most of what the stock
 * page shows as a symptom.
 */
export default function QualiteFlux() {
  const { t, formatDay, formatDecimal, formatNumber } = useI18n()
  const { overview } = useOverview()
  const navigate = useNavigate()

  const { quality, flow, lead_time_distribution } = overview

  return (
    <div className="space-y-5">
      {/* Two equal columns: at three, the donut card was mostly empty space. */}
      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title={t('card.quality.title')}
          question={t('card.quality.question')}
        >
          <DonutChart
            segments={[
              {
                key: 'conform',
                label: t('status.CONFORM'),
                value: quality.conform,
                className: 'text-ok',
              },
              {
                key: 'non_conform',
                label: t('status.NON_CONFORM'),
                value: quality.non_conform,
                className: 'text-warn',
              },
              {
                key: 'red_cage',
                label: t('status.RED_CAGE'),
                value: quality.red_cage,
                className: 'text-crit',
              },
            ]}
            centreValue={
              quality.conformity_percent !== null
                ? `${formatDecimal(quality.conformity_percent, 1)} %`
                : '—'
            }
            centreLabel={t('kpi.conformity')}
            emptyMessage={t('card.quality.empty')}
          />
        </ChartCard>

        <ChartCard
          title={t('card.conformityTarget.title')}
          question={t('card.conformityTarget.question')}
          delay={0.05}
          bodyClassName="px-5 pb-5 pt-2"
        >
          {quality.conformity_percent === null ? (
            <ChartEmpty message={t('card.quality.empty')} />
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Gauge
                value={quality.conformity_percent}
                label={t('kpi.conformity')}
                target={95}
                warning={95}
                critical={90}
                targetLabel={t('gauge.target', { value: 95 })}
              />
              <p className="numeric text-center text-2xs text-ink-3">
                {t('kpi.context.inspections', { value: formatNumber(quality.inspections) })}
              </p>
            </div>
          )}
        </ChartCard>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <ChartCard
          title={t('card.qualityTrend.title')}
          question={t('card.qualityTrend.question')}
          delay={0.08}
        >
          <AnalyticsLineChart
            points={quality.trend.map((point) => ({
              label: formatDay(point.date),
              value: point.value,
            }))}
            seriesLabel={t('quality.rate')}
            unit="%"
            format={(value) => formatDecimal(value, 1)}
            emptyMessage={t('card.qualityTrend.empty')}
          />
        </ChartCard>

        <ChartCard
          title={t('card.leadTime.title')}
          question={t('card.leadTime.question')}
          delay={0.11}
          footer={
            lead_time_distribution.sample_size > 0
              ? t('histogram.sample', { count: lead_time_distribution.sample_size })
              : undefined
          }
        >
          <AnalyticsHistogram
            buckets={lead_time_distribution.buckets}
            medianHours={lead_time_distribution.median_hours}
            medianLabel={
              lead_time_distribution.median_hours !== null
                ? t('histogram.median', {
                    value: formatDecimal(lead_time_distribution.median_hours, 1),
                  })
                : undefined
            }
            countLabel={t('histogram.lots')}
            emptyMessage={t('card.leadTime.empty')}
          />
        </ChartCard>
      </div>

      <ChartCard
        title={t('card.defects.title')}
        question={t('card.defects.question')}
        delay={0.11}
        bodyClassName="px-0 pb-0"
      >
        {quality.top_defects.length === 0 ? (
          <div className="px-5 pb-5">
            <ChartEmpty message={t('card.defects.empty')} />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table min-w-[520px]">
              <thead>
                <tr>
                  <th>{t('common.reference')}</th>
                  <th className="text-right">{t('table.defects')}</th>
                  <th className="text-right">{t('table.inspected')}</th>
                  <th className="text-right">{t('table.defectRate')}</th>
                </tr>
              </thead>
              <tbody>
                {quality.top_defects.map((row) => (
                  <tr key={row.reference}>
                    <td>
                      <span className="numeric text-xs font-medium text-ink">
                        {row.reference}
                      </span>
                      <span className="block truncate text-2xs text-ink-3">
                        {row.designation}
                      </span>
                    </td>
                    <td className="numeric text-right font-medium text-ink">
                      {formatNumber(row.defects)}
                    </td>
                    <td className="numeric text-right">{formatNumber(row.inspected)}</td>
                    <td className="numeric text-right font-semibold text-crit-soft">
                      {formatDecimal(row.rate_percent, 2)} %
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </ChartCard>

      <ChartCard title={t('card.flow.title')} question={t('card.flow.question')} delay={0.14}>
        <FlowFunnel
          flow={flow}
          emptyMessage={t('card.flow.empty')}
          onSelectStage={(stage) => {
            const routes: Record<string, string> = {
              RECEIVING: '/receiving',
              INSPECTION: '/inspection',
              QUALITY: '/quality',
              WAREHOUSE: '/warehouse',
              PRODUCTION: '/production',
            }
            navigate(routes[stage] ?? '/mission-control')
          }}
        />
      </ChartCard>
    </div>
  )
}
