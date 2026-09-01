import { useMemo, useState } from 'react'
import { ShieldAlert, ShieldCheck } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import { Badge, EmptyState, ErrorPanel, LoadingPanel } from '@/components/ui'
import { ChartCard } from '@/features/analytics/primitives'
import { HBarChart } from '@/features/analytics/bars'
import { Waterfall } from '@/features/analytics/series'
import {
  FilterBar,
  KpiRow,
  ReportTable,
  SourceNote,
  matches,
  useFilterState,
  type SupervisionKpi,
} from '@/features/supervision/shell'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { qualityApi } from '@/services/slcc.service'
import { blockingReason } from '@/utils/blocking'
import { formatTimestamp } from '@/utils/format'

/**
 * Quality and Red Cage, as the logistics manager sees it.
 *
 * The decisions were taken by the quality chief in the workbook. What this
 * screen answers is what those decisions cost: how much is immobilised, for
 * how long, and on which references it keeps happening.
 */
export default function Quality() {
  const { t, ts, formatNumber } = useI18n()
  const redCage = useApiResource(() => qualityApi.redCage(), [], { pollMs: 60_000 })
  const pending = useApiResource(() => qualityApi.pending(), [], { pollMs: 60_000 })
  const history = useApiResource(() => qualityApi.history(300), [], { pollMs: 60_000 })
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  const filters = useFilterState(['decision'])
  const rows = history.data ?? []
  const blocked = redCage.data ?? []

  const visible = useMemo(
    () =>
      rows.filter(
        (row) =>
          matches(
            [row.justification, row.decided_by?.full_name, String(row.lot_id)],
            filters.search,
          ) && (!filters.values.decision || row.decision === filters.values.decision),
      ),
    [rows, filters.search, filters.values.decision],
  )

  const summary = useMemo(() => {
    const count = (decision: string) => rows.filter((row) => row.decision === decision).length
    return {
      approved: count('APPROVED'),
      rejected: count('REJECTED'),
      redCage: count('RED_CAGE'),
      scrapped: count('SCRAPPED'),
      blockedUnits: blocked.reduce((sum, lot) => sum + lot.quantity_received, 0),
    }
  }, [rows, blocked])

  const kpis: SupervisionKpi[] = [
    {
      key: 'decisions',
      label: t('qual.history'),
      value: formatNumber(rows.length),
      hint: t('qual.kpi.approvedShare', {
        percent: rows.length ? Math.round((summary.approved / rows.length) * 100) : 0,
      }),
      severity: 'INFO',
    },
    {
      key: 'redcage',
      label: t('qual.redCage'),
      value: formatNumber(blocked.length),
      hint: t('qual.kpi.blockedUnits', { value: formatNumber(summary.blockedUnits) }),
      severity: blocked.length ? 'CRITICAL' : 'OK',
    },
    {
      key: 'pending',
      label: t('qual.pending'),
      value: formatNumber(pending.data?.length ?? 0),
      hint: t('qual.kpi.awaiting'),
      severity: (pending.data?.length ?? 0) > 5 ? 'WARNING' : 'INFO',
    },
    {
      key: 'scrapped',
      label: t('status.REJECTED'),
      value: formatNumber(summary.rejected + summary.scrapped),
      hint: t('qual.kpi.neverStock'),
      severity: summary.rejected + summary.scrapped ? 'WARNING' : 'OK',
    },
  ]

  /**
   * How long the blocked lots have been waiting.
   *
   * The count of blocked lots says there is a problem; the age says how badly.
   * A lot stuck three days is a decision nobody took, and that is the line a
   * manager chases.
   */
  const ageing = useMemo(() => {
    const buckets = [
      { key: 'lt24', label: t('qual.age.lt24'), max: 24, severity: 'OK' as const },
      { key: 'd1to3', label: t('qual.age.d1to3'), max: 72, severity: 'WARNING' as const },
      { key: 'gt3', label: t('qual.age.gt3'), max: Infinity, severity: 'CRITICAL' as const },
    ]
    const now = Date.now()
    const counts = new Map(buckets.map((bucket) => [bucket.key, 0]))
    for (const lot of blocked) {
      const stamp = lot.updated_at ?? lot.received_at
      const hours = (now - new Date(stamp).getTime()) / 3_600_000
      const bucket = buckets.find((item) => hours < item.max) ?? buckets[buckets.length - 1]
      counts.set(bucket.key, (counts.get(bucket.key) ?? 0) + 1)
    }
    return buckets.map((bucket) => ({
      key: bucket.key,
      label: bucket.label,
      value: counts.get(bucket.key) ?? 0,
      severity: bucket.severity,
    }))
  }, [blocked, t])

  return (
    <div className="space-y-4">
      <PageHeader title={t('qual.title')} description={t('qual.supervisionSubtitle')} />
      <SourceNote zone="nav.quality" />

      {history.initialLoading ? (
        <div className="panel">
          <LoadingPanel rows={6} />
        </div>
      ) : history.error ? (
        <div className="panel">
          <ErrorPanel message={history.error} onRetry={history.refresh} />
        </div>
      ) : (
        <>
          <KpiRow items={kpis} />

          <div className="grid gap-4 xl:grid-cols-2">
            {/* A waterfall, not a pie. What leaves the quality gate is a flow:
                the lots inspected go in, the blocked and the rejected are
                subtracted, and what remains is what will become stock. Drawing
                the approvals as a subtraction - which is what a plain
                decomposition would do - would paint the good outcome as a
                loss. */}
            <ChartCard
              title={t('qual.chart.decisions')}
              question={t('qual.chart.decisionsQuestion')}
            >
              <Waterfall
                steps={[
                  { key: 'inspected', value: rows.length, kind: 'START' },
                  { key: 'redCageStep', value: -summary.redCage, kind: 'OUT' },
                  {
                    key: 'rejectedStep',
                    value: -(summary.rejected + summary.scrapped),
                    kind: 'OUT',
                  },
                  { key: 'approvedStep', value: summary.approved, kind: 'END' },
                ]}
                emptyMessage={t('qual.noHistory')}
                labelFor={(key) => t(`qual.step.${key}` as never) as string}
              />
            </ChartCard>

            {/* How long a lot has been stuck: the question a manager acts on. */}
            <ChartCard
              title={t('qual.chart.ageing')}
              question={t('qual.chart.ageingQuestion')}
              delay={0.05}
            >
              <HBarChart
                points={ageing}
                unit={` ${t('recv.col.lot').toLowerCase()}`}
                colouring="state"
                emptyMessage={t('qual.redCageEmptyHint')}
              />
            </ChartCard>
          </div>

          {/* What is immobilised right now, and why. */}
          <ChartCard
            title={t('qual.redCage')}
            question={t('qual.redCageQuestion')}
            action={<ShieldAlert className="h-3.5 w-3.5 text-crit" />}
            bodyClassName="px-0 pb-0"
            delay={0.08}
          >
            <ReportTable
              minWidth={860}
              columns={[
                { key: 'lot', label: t('recv.col.lot') },
                { key: 'part', label: t('recv.col.part') },
                { key: 'supplier', label: t('recv.col.supplier') },
                { key: 'quantity', label: t('common.quantity'), align: 'right' },
                { key: 'reason', label: t('qual.blockingReason') },
              ]}
              empty={
                blocked.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      icon={<ShieldCheck className="h-5 w-5 text-ok" />}
                      title={t('qual.redCageEmpty')}
                      description={t('qual.redCageEmptyHint')}
                    />
                  </div>
                ) : undefined
              }
            >
              {blocked.map((lot) => (
                <tr key={lot.id} onClick={() => setSelectedLotId(lot.id)} className="cursor-pointer">
                  <td className="numeric font-medium text-ink">{lot.lot_number}</td>
                  <td>
                    <span className="numeric">{lot.part.reference}</span>
                    <span className="block truncate text-2xs text-ink-3">
                      {lot.part.designation}
                    </span>
                  </td>
                  <td>{lot.supplier.name}</td>
                  <td className="numeric text-right">{formatNumber(lot.quantity_received)}</td>
                  <td className="max-w-md text-2xs">{blockingReason(lot, t)}</td>
                </tr>
              ))}
            </ReportTable>
          </ChartCard>

          <FilterBar
            search={filters.search}
            onSearch={filters.setSearch}
            placeholder={t('qual.searchPlaceholder')}
            count={t('common.rowsShown', {
              shown: formatNumber(visible.length),
              total: formatNumber(rows.length),
            })}
            onReset={filters.reset}
            selects={[
              {
                key: 'decision',
                label: t('qual.col.decision'),
                value: filters.values.decision,
                onChange: (value) => filters.set('decision', value),
                options: ['APPROVED', 'RED_CAGE', 'REJECTED', 'SCRAPPED'].map((value) => ({
                  value,
                  label: ts(value),
                })),
              },
            ]}
          />

          <ChartCard
            title={t('qual.history')}
            question={t('qual.historyQuestion')}
            bodyClassName="px-0 pb-0"
            delay={0.11}
          >
            <ReportTable
              minWidth={860}
              columns={[
                { key: 'lot', label: t('recv.col.lot') },
                { key: 'decision', label: t('qual.col.decision') },
                { key: 'approved', label: t('qual.col.approved'), align: 'right' },
                { key: 'justification', label: t('qual.col.justification') },
                { key: 'by', label: t('qual.col.by') },
                { key: 'date', label: t('common.date'), align: 'right' },
              ]}
              empty={
                visible.length === 0 ? (
                  <div className="px-5 pb-5">
                    <EmptyState
                      title={t('qual.noHistory')}
                      description={t('recv.emptyFiltered')}
                    />
                  </div>
                ) : undefined
              }
            >
              {visible.map((row) => (
                <tr
                  key={row.id}
                  onClick={() => setSelectedLotId(row.lot_id)}
                  className="cursor-pointer"
                >
                  <td className="numeric">#{row.lot_id}</td>
                  <td>
                    <Badge
                      severity={
                        row.decision === 'APPROVED'
                          ? 'ok'
                          : row.decision === 'RED_CAGE'
                            ? 'warn'
                            : 'crit'
                      }
                    >
                      {ts(row.decision)}
                    </Badge>
                  </td>
                  <td className="numeric text-right">{formatNumber(row.quantity_approved)}</td>
                  <td className="max-w-sm text-2xs">{row.justification}</td>
                  <td className="text-2xs">{row.decided_by?.full_name ?? '—'}</td>
                  <td className="numeric text-right text-2xs text-ink-3">
                    {formatTimestamp(row.decided_at)}
                  </td>
                </tr>
              ))}
            </ReportTable>
          </ChartCard>
        </>
      )}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}
