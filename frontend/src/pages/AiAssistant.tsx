import { AlertTriangle, Brain, Lightbulb, RefreshCw, ShieldAlert, TrendingDown } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Panel,
  StatusDot,
} from '@/components/ui'
import { LogisticsCopilot } from '@/features/mission-control'
import { StatTile } from '@/features/analytics/charts'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { aiApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { prioritySeverity, riskSeverity, toSeverity } from '@/utils/status'
import type { MessageKey } from '@/i18n/messages'
import type { Recommendation, RecommendationKind } from '@/types/domain'

const KIND_ICON: Record<RecommendationKind, typeof Brain> = {
  SHORTAGE_RISK: TrendingDown,
  PRIORITY: AlertTriangle,
  BLOCKED_LOT: ShieldAlert,
  WAREHOUSE_SATURATION: AlertTriangle,
  OPTIMIZATION: Lightbulb,
}

//: The backend sends a kind; the wording is the interface's business.
const KIND_KEY: Record<RecommendationKind, MessageKey> = {
  SHORTAGE_RISK: 'ai.kind.SHORTAGE_RISK',
  PRIORITY: 'ai.kind.PRIORITY',
  BLOCKED_LOT: 'ai.kind.BLOCKED_LOT',
  WAREHOUSE_SATURATION: 'ai.kind.WAREHOUSE_SATURATION',
  OPTIMIZATION: 'ai.kind.OPTIMIZATION',
}

/**
 * Word a recommendation in the reader's language.
 *
 * The engine ships a `text_key` naming the situation it detected plus the
 * figures behind it; the sentence is assembled here. When a key has no
 * translation - an older row, or a case added before its wording - the English
 * the backend already composed is shown instead of a raw key.
 */
function useRecommendationText() {
  const { t, locale } = useI18n()
  void locale

  return (
    recommendation: Recommendation,
    part: 'title' | 'message' | 'why' | 'action',
    fallback: string,
  ) => {
    if (!recommendation.text_key) return fallback
    const key = `reco.${recommendation.text_key}.${part}` as MessageKey
    const values: Record<string, string | number> = {
      ...(recommendation.metrics as Record<string, string | number>),
      part_reference: recommendation.part_reference ?? '',
      lot_number: recommendation.lot_number ?? '',
      location_code: recommendation.location_code ?? '',
    }
    const rendered = t(key, values)
    return rendered === key ? fallback : rendered
  }
}

/**
 * AI Assistant.
 *
 * Three functions, all computed from live data and all explained: shortage risk,
 * prioritisation and optimisation. No recommendation is ever shown without the
 * reasoning and the figures that produced it.
 */
export default function AiAssistant() {
  const { t, ts, formatNumber } = useI18n()
  const say = useRecommendationText()
  const analysis = useApiResource(() => aiApi.analysis(true), [])

  const data = analysis.data
  const highRisks = data?.shortage_risks.filter((risk) => risk.risk_level === 'HIGH') ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('ai.title')}
        description={t('ai.subtitle')}
        actions={
          <Button
            variant="primary"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            loading={analysis.loading && !analysis.initialLoading}
            onClick={analysis.refresh}
          >
            {t('ai.rerun')}
          </Button>
        }
      />

      {analysis.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={6} />
        </Panel>
      ) : analysis.error && !analysis.data ? (
        <Panel bodyClassName="">
          <ErrorPanel message={analysis.error} onRetry={analysis.refresh} />
        </Panel>
      ) : data ? (
        <>
          {/* Headline */}
          <Panel delay={0.02}>
            <div className="flex items-start gap-4">
              <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-accent/30 bg-accent-dim">
                <Brain className="h-5 w-5 text-accent" strokeWidth={1.8} />
              </span>
              <div className="min-w-0 flex-1">
                <p className="eyebrow">{t('ai.assessment')}</p>
                <p className="mt-1.5 text-sm leading-relaxed text-ink">
                  {data.headline_key
                    ? t(data.headline_key as MessageKey, data.headline_values)
                    : data.headline}
                </p>
                <div className="mt-3 flex flex-wrap gap-2">
                  <Badge severity="crit">P1 · {data.priority_count['1'] ?? 0}</Badge>
                  <Badge severity="warn">P2 · {data.priority_count['2'] ?? 0}</Badge>
                  <Badge severity="info">P3 · {data.priority_count['3'] ?? 0}</Badge>
                </div>
              </div>
            </div>
          </Panel>

          {/* Shortage risk */}
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label={t('ai.highRisk')}
              value={formatNumber(highRisks.length)}
              hint={
                highRisks.length
                  ? highRisks.map((r) => r.part_reference).join(', ')
                  : t('common.none')
              }
              severity={highRisks.length ? 'crit' : 'ok'}
            />
            <StatTile
              label={t('ai.underWatch')}
              value={formatNumber(data.shortage_risks.length - highRisks.length)}
              hint={t('ai.mediumRisk')}
              severity={data.shortage_risks.length - highRisks.length ? 'warn' : 'ok'}
            />
            <StatTile
              label={t('ai.activeRecommendations')}
              value={formatNumber(data.recommendations.length)}
              hint={t('ai.byPriority')}
              severity="info"
            />
            <StatTile
              label={t('ai.priorityOne')}
              value={formatNumber(data.priority_count['1'] ?? 0)}
              hint={t('ai.priorityOneHint')}
              severity={data.priority_count['1'] ? 'crit' : 'ok'}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            {/* Recommendations */}
            <Panel
              className="xl:col-span-2"
              title={t('ai.recommendations')}
              subtitle={t('ai.recommendationsSubtitle')}
              delay={0.06}
              bodyClassName=""
            >
              {data.recommendations.length === 0 ? (
                <EmptyState
                  title={t('ai.noRecommendation')}
                  description={t('ai.noRecommendationHint')}
                />
              ) : (
                <ul className="divide-y divide-line">
                  {data.recommendations.map((recommendation) => {
                    const severity = toSeverity(recommendation.severity)
                    const Icon = KIND_ICON[recommendation.kind]
                    return (
                      <li key={recommendation.id} className="px-5 py-4">
                        <div className="flex items-start gap-3">
                          <span
                            className={cn(
                              'mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border',
                              severity === 'crit'
                                ? 'border-crit/40 bg-crit/10'
                                : severity === 'warn'
                                  ? 'border-warn/40 bg-warn/10'
                                  : 'border-line bg-elevated',
                            )}
                          >
                            <Icon
                              className={cn(
                                'h-4 w-4',
                                severity === 'crit'
                                  ? 'text-crit-soft'
                                  : severity === 'warn'
                                    ? 'text-warn-soft'
                                    : 'text-ink-2',
                              )}
                              strokeWidth={1.9}
                            />
                          </span>

                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <p className="text-xs font-semibold text-ink">
                                {say(recommendation, 'title', recommendation.title)}
                              </p>
                              <Badge
                                severity={prioritySeverity[recommendation.priority] ?? 'info'}
                              >
                                P{recommendation.priority}
                              </Badge>
                              <Badge severity="info">{t(KIND_KEY[recommendation.kind])}</Badge>
                              {recommendation.risk_level && (
                                <Badge severity={riskSeverity[recommendation.risk_level]}>
                                  {ts(recommendation.risk_level)}
                                </Badge>
                              )}
                            </div>

                            <p className="mt-1.5 text-xs leading-relaxed text-ink-2">
                              {say(recommendation, 'message', recommendation.message)}
                            </p>

                            {/* Mandatory justification */}
                            <div className="mt-2 rounded-md border border-line bg-elevated/60 px-3 py-2">
                              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                                {t('ai.why')}
                              </p>
                              <p className="mt-1 text-2xs leading-relaxed text-ink-2">
                                {say(recommendation, 'why', recommendation.rationale)}
                              </p>
                            </div>

                            {recommendation.recommended_action && (
                              <p className="mt-2 flex items-start gap-1.5 text-2xs text-accent/90">
                                <Lightbulb className="mt-0.5 h-3 w-3 shrink-0" />
                                {say(
                                  recommendation,
                                  'action',
                                  recommendation.recommended_action,
                                )}
                              </p>
                            )}

                            {Object.keys(recommendation.metrics).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {Object.entries(recommendation.metrics).map(([key, value]) => (
                                  <span
                                    key={key}
                                    className="rounded border border-line bg-panel px-2 py-0.5 text-[11px] text-ink-3"
                                  >
                                    {t(`metric.${key}` as MessageKey) === `metric.${key}`
                                      ? key.replace(/_/g, ' ')
                                      : t(`metric.${key}` as MessageKey)}
                                    :{' '}
                                    <span className="numeric text-ink-2">
                                      {Array.isArray(value)
                                        ? value.join(', ')
                                        : String(value ?? '—')}
                                    </span>
                                  </span>
                                ))}
                              </div>
                            )}
                          </div>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </Panel>

            {/* Shortage risk detail */}
            <Panel
              title={t('ai.shortageTitle')}
              subtitle={t('ai.shortageSubtitle')}
              delay={0.1}
              bodyClassName=""
            >
              {data.shortage_risks.length === 0 ? (
                <EmptyState
                  title={t('ai.noRisk')}
                  description={t('ai.noRiskHint')}
                />
              ) : (
                <ul className="divide-y divide-line">
                  {data.shortage_risks.map((risk) => (
                    <li key={risk.part_id} className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        <StatusDot severity={riskSeverity[risk.risk_level]} />
                        <span className="numeric text-xs font-medium text-ink">
                          {risk.part_reference}
                        </span>
                        <Badge severity={riskSeverity[risk.risk_level]} className="ml-auto">
                          {ts(risk.risk_level)}
                        </Badge>
                      </div>

                      <div className="mt-2 grid grid-cols-3 gap-2">
                        <Figure label={t('chart.stock')} value={formatNumber(risk.stock_available)} />
                        <Figure label={t('chart.demand')} value={formatNumber(risk.open_demand)} />
                        <Figure
                          label={t('chart.coverage')}
                          value={risk.days_of_cover !== null ? `${risk.days_of_cover} d` : '—'}
                        />
                      </div>

                      <p className="mt-2 text-2xs leading-relaxed text-ink-3">
                        {risk.text_key
                          ? t(`reco.${risk.text_key}.why` as MessageKey, {
                              stock_available: risk.stock_available,
                              open_demand: risk.open_demand,
                              safety_stock: risk.safety_stock,
                              projected_balance: risk.projected_balance,
                              days_of_cover: risk.days_of_cover ?? '—',
                              part_reference: risk.part_reference,
                            })
                          : risk.rationale}
                      </p>

                      {risk.incoming_quantity > 0 && (
                        <p className="mt-1.5 text-2xs text-info-soft">
                          {t('ai.incoming', {
                            value: formatNumber(risk.incoming_quantity),
                          })}
                        </p>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          {/* Copilot */}
          <Panel
            title={t('copilot.title')}
            subtitle={t('copilot.subtitle')}
            delay={0.14}
            bodyClassName=""
          >
            <LogisticsCopilot />
          </Panel>
        </>
      ) : null}
    </div>
  )
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded border border-line bg-elevated/60 px-2 py-1.5">
      <p className="text-[11px] text-ink-3">{label}</p>
      <p className="numeric mt-0.5 text-2xs font-semibold text-ink">{value}</p>
    </div>
  )
}
