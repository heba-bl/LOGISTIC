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
import { aiApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatNumber } from '@/utils/format'
import { prioritySeverity, riskSeverity, toSeverity } from '@/utils/status'
import type { RecommendationKind } from '@/types/domain'

const KIND_ICON: Record<RecommendationKind, typeof Brain> = {
  SHORTAGE_RISK: TrendingDown,
  PRIORITY: AlertTriangle,
  BLOCKED_LOT: ShieldAlert,
  WAREHOUSE_SATURATION: AlertTriangle,
  OPTIMIZATION: Lightbulb,
}

const KIND_LABEL: Record<RecommendationKind, string> = {
  SHORTAGE_RISK: 'Shortage risk',
  PRIORITY: 'Priority',
  BLOCKED_LOT: 'Blocked lot',
  WAREHOUSE_SATURATION: 'Saturation',
  OPTIMIZATION: 'Optimisation',
}

/**
 * AI Assistant.
 *
 * Three functions, all computed from live data and all explained: shortage risk,
 * prioritisation and optimisation. No recommendation is ever shown without the
 * reasoning and the figures that produced it.
 */
export default function AiAssistant() {
  const analysis = useApiResource(() => aiApi.analysis(true), [])

  const data = analysis.data
  const highRisks = data?.shortage_risks.filter((risk) => risk.risk_level === 'HIGH') ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        title="AI Assistant"
        description="Decision support built on the operational data — every conclusion is justified."
        actions={
          <Button
            variant="primary"
            icon={<RefreshCw className="h-3.5 w-3.5" />}
            loading={analysis.loading && !analysis.initialLoading}
            onClick={analysis.refresh}
          >
            Re-run the analysis
          </Button>
        }
      />

      {analysis.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={6} />
        </Panel>
      ) : analysis.error ? (
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
                <p className="eyebrow">Situation assessment</p>
                <p className="mt-1.5 text-sm leading-relaxed text-ink">{data.headline}</p>
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
              label="References at high risk"
              value={formatNumber(highRisks.length)}
              hint={highRisks.length ? highRisks.map((r) => r.part_reference).join(', ') : 'None'}
              severity={highRisks.length ? 'crit' : 'ok'}
            />
            <StatTile
              label="References under watch"
              value={formatNumber(data.shortage_risks.length - highRisks.length)}
              hint="Medium risk"
              severity={data.shortage_risks.length - highRisks.length ? 'warn' : 'ok'}
            />
            <StatTile
              label="Active recommendations"
              value={formatNumber(data.recommendations.length)}
              hint="Ordered by priority"
              severity="info"
            />
            <StatTile
              label="Priority 1"
              value={formatNumber(data.priority_count['1'] ?? 0)}
              hint="Production at risk — handle first"
              severity={data.priority_count['1'] ? 'crit' : 'ok'}
            />
          </div>

          <div className="grid gap-4 xl:grid-cols-3">
            {/* Recommendations */}
            <Panel
              className="xl:col-span-2"
              title="Recommendations"
              subtitle="Ordered by priority — each one states why it was produced"
              delay={0.06}
              bodyClassName=""
            >
              {data.recommendations.length === 0 ? (
                <EmptyState
                  title="No recommendation"
                  description="No risk or optimisation opportunity detected."
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
                                {recommendation.title}
                              </p>
                              <Badge
                                severity={prioritySeverity[recommendation.priority] ?? 'info'}
                              >
                                P{recommendation.priority}
                              </Badge>
                              <Badge severity="info">{KIND_LABEL[recommendation.kind]}</Badge>
                              {recommendation.risk_level && (
                                <Badge severity={riskSeverity[recommendation.risk_level]}>
                                  {recommendation.risk_level}
                                </Badge>
                              )}
                            </div>

                            <p className="mt-1.5 text-xs leading-relaxed text-ink-2">
                              {recommendation.message}
                            </p>

                            {/* Mandatory justification */}
                            <div className="mt-2 rounded-md border border-line bg-elevated/60 px-3 py-2">
                              <p className="text-[10px] font-semibold uppercase tracking-wider text-ink-3">
                                Why
                              </p>
                              <p className="mt-1 text-2xs leading-relaxed text-ink-2">
                                {recommendation.rationale}
                              </p>
                            </div>

                            {recommendation.recommended_action && (
                              <p className="mt-2 flex items-start gap-1.5 text-2xs text-accent/90">
                                <Lightbulb className="mt-0.5 h-3 w-3 shrink-0" />
                                {recommendation.recommended_action}
                              </p>
                            )}

                            {Object.keys(recommendation.metrics).length > 0 && (
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                {Object.entries(recommendation.metrics).map(([key, value]) => (
                                  <span
                                    key={key}
                                    className="rounded border border-line bg-panel px-2 py-0.5 text-[10px] text-ink-3"
                                  >
                                    {key.replace(/_/g, ' ')}:{' '}
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
              title="Shortage risk"
              subtitle="Stock versus confirmed demand"
              delay={0.1}
              bodyClassName=""
            >
              {data.shortage_risks.length === 0 ? (
                <EmptyState
                  title="No risk"
                  description="Every reference covers its confirmed demand."
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
                          {risk.risk_level}
                        </Badge>
                      </div>

                      <div className="mt-2 grid grid-cols-3 gap-2">
                        <Figure label="Stock" value={formatNumber(risk.stock_available)} />
                        <Figure label="Demand" value={formatNumber(risk.open_demand)} />
                        <Figure
                          label="Cover"
                          value={risk.days_of_cover !== null ? `${risk.days_of_cover} d` : '—'}
                        />
                      </div>

                      <p className="mt-2 text-2xs leading-relaxed text-ink-3">{risk.rationale}</p>

                      {risk.incoming_quantity > 0 && (
                        <p className="mt-1.5 text-2xs text-info-soft">
                          {formatNumber(risk.incoming_quantity)} units received but not yet stock.
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
            title="Logistics Copilot"
            subtitle="Ask a question — answers come from the live database"
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
      <p className="text-[10px] text-ink-3">{label}</p>
      <p className="numeric mt-0.5 text-2xs font-semibold text-ink">{value}</p>
    </div>
  )
}
