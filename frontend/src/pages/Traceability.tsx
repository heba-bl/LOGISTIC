import { useState, type FormEvent } from 'react'
import { History, Route, Search } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  Input,
  LoadingPanel,
  Panel,
  Select,
  StatusDot,
} from '@/components/ui'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { catalogApi, lotsApi, traceabilityApi } from '@/services/slcc.service'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { lotStatusSeverity } from '@/utils/status'

/**
 * Traceability.
 *
 * Answers the ten questions the specification requires — who, what, when, how
 * much, which lot, which reference, which location, status before, status after
 * and why — by searching the append-only audit trail.
 */
export default function Traceability() {
  const { t, ts } = useI18n()
  const [search, setSearch] = useState('')
  const [appliedSearch, setAppliedSearch] = useState('')
  const [entityType, setEntityType] = useState('')
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  const lots = useApiResource(
    () => lotsApi.list({ search: appliedSearch || undefined, limit: 50 }),
    [appliedSearch],
  )
  const audit = useApiResource(
    () =>
      traceabilityApi.audit({
        search: appliedSearch || undefined,
        entity_type: entityType || undefined,
        limit: 150,
      }),
    [appliedSearch, entityType],
  )
  const parts = useApiResource(() => catalogApi.parts(), [])

  function onSubmit(event: FormEvent) {
    event.preventDefault()
    setAppliedSearch(search.trim())
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t('trace.title')}
        description={t('trace.subtitle')}
        actions={
          <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('common.searchPlaceholder')}
                className="w-64 pl-9"
              />
            </div>
            <Select
              value={entityType}
              onChange={(event) => setEntityType(event.target.value)}
              className="w-40"
            >
              <option value="">{t('trace.allEvents')}</option>
              <option value="reception">{t('trace.event.reception')}</option>
              <option value="inspection">{t('trace.event.inspection')}</option>
              <option value="quality_validation">{t('trace.event.quality')}</option>
              <option value="lot">{t('trace.event.lot')}</option>
              <option value="stock">{t('trace.event.stock')}</option>
              <option value="production_request">{t('trace.event.production')}</option>
            </Select>
            <Button type="submit" variant="primary">
              {t('trace.searchButton')}
            </Button>
          </form>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel
          title={t('trace.lots')}
          subtitle={t('trace.lotsSubtitle', { count: lots.data?.length ?? 0 })}
          bodyClassName=""
          action={<Route className="h-3.5 w-3.5 text-ink-3" />}
        >
          {lots.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : lots.error ? (
            <ErrorPanel message={lots.error} onRetry={lots.refresh} />
          ) : (lots.data?.length ?? 0) === 0 ? (
            <EmptyState title={t('trace.noLot')} description={t('trace.noLotHint')} />
          ) : (
            <ul className="max-h-[520px] divide-y divide-line overflow-y-auto">
              {lots.data?.map((lot) => (
                <li key={lot.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedLotId(lot.id)}
                    className="w-full px-5 py-3 text-left transition-colors hover:bg-elevated/50"
                  >
                    <div className="flex items-center gap-2">
                      <span className="numeric text-xs font-medium text-ink">
                        {lot.lot_number}
                      </span>
                      <Badge severity={lotStatusSeverity[lot.status]} className="ml-auto">
                        {ts(lot.status)}
                      </Badge>
                    </div>
                    <p className="mt-1 text-2xs text-ink-3">
                      {lot.part.reference} · {formatNumber(lot.quantity_received)}{' '}
                      {lot.part.unit} · {lot.supplier.name}
                    </p>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel
          className="xl:col-span-2"
          title={t('trace.audit')}
          subtitle={t('trace.auditSubtitle', { count: audit.data?.length ?? 0 })}
          bodyClassName=""
          action={<History className="h-3.5 w-3.5 text-ink-3" />}
        >
          {audit.initialLoading ? (
            <LoadingPanel rows={6} />
          ) : audit.error ? (
            <ErrorPanel message={audit.error} onRetry={audit.refresh} />
          ) : (audit.data?.length ?? 0) === 0 ? (
            <EmptyState title={t('trace.noEvent')} description={t('trace.noEventHint')} />
          ) : (
            <div className="max-h-[520px] overflow-auto">
              <table className="w-full min-w-[980px] border-collapse text-left">
                <thead className="sticky top-0 z-10 bg-panel">
                  <tr className="border-b border-line">
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.when')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.action')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.target')}</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">{t('trace.col.qty')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.transition')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.whoEntered')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.whoValidated')}</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.why')}</th>
                  </tr>
                </thead>
                <tbody>
                  {audit.data?.map((entry) => (
                    <tr key={entry.id} className="border-b border-line/60 last:border-0">
                      <td className="numeric whitespace-nowrap px-5 py-2.5 text-2xs text-ink-3">
                        {formatTimestamp(entry.occurred_at)}
                      </td>
                      <td className="whitespace-nowrap px-5 py-2.5 text-2xs text-ink-2">
                        {ts(entry.action)}
                      </td>
                      <td className="numeric whitespace-nowrap px-5 py-2.5 text-2xs text-ink">
                        {entry.entity_reference ?? entry.entity_type}
                      </td>
                      <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-2">
                        {entry.quantity !== null ? formatNumber(entry.quantity) : '—'}
                      </td>
                      <td className="numeric whitespace-nowrap px-5 py-2.5 text-2xs text-ink-3">
                        {entry.status_before && entry.status_after
                          ? `${entry.status_before} → ${entry.status_after}`
                          : (entry.status_after ?? '—')}
                      </td>
                      <td className="whitespace-nowrap px-5 py-2.5">
                        <span className="numeric block text-2xs text-ink">
                          {entry.maker_reference ?? entry.actor_reference ?? '—'}
                        </span>
                        <span className="block text-[11px] text-ink-3">
                          {entry.maker_role
                            ? ts(entry.maker_role)
                            : entry.actor_name}
                        </span>
                      </td>
                      <td className="whitespace-nowrap px-5 py-2.5">
                        {entry.checker_reference ? (
                          <>
                            <span className="numeric block text-2xs text-ok-soft">
                              {entry.checker_reference}
                            </span>
                            <span className="block text-[11px] text-ink-3">
                              {ts(entry.checker_role ?? '')}
                              {entry.decision ? ` · ${ts(entry.decision)}` : ''}
                            </span>
                          </>
                        ) : (
                          <span className="text-2xs text-ink-3">—</span>
                        )}
                      </td>
                      <td className="max-w-md px-5 py-2.5 text-2xs text-ink-3">
                        {entry.reason ?? '—'}
                        {entry.source_file && (
                          <span className="numeric mt-0.5 block text-[11px] text-ink-3/70">
                            {t('trace.file', { value: entry.source_file })}
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <PartHistory parts={parts.data ?? []} />

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}

/** "Why is the stock of X dropping?" answered from the movement ledger. */
function PartHistory({ parts }: { parts: { id: number; reference: string; designation: string }[] }) {
  const { t } = useI18n()
  const [partId, setPartId] = useState('')
  const movements = useApiResource(
    () => traceabilityApi.partMovements(Number(partId)),
    [partId],
    { enabled: Boolean(partId) },
  )

  return (
    <Panel
      title={t('trace.partHistory')}
      subtitle={t('trace.partHistorySubtitle')}
      bodyClassName=""
      action={
        <Select
          value={partId}
          onChange={(event) => setPartId(event.target.value)}
          className="w-56"
        >
          <option value="">{t('recv.selectPart')}</option>
          {parts.map((part) => (
            <option key={part.id} value={part.id}>
              {part.reference} — {part.designation}
            </option>
          ))}
        </Select>
      }
    >
      {!partId ? (
        <EmptyState
          title={t('trace.selectReference')}
          description={t('trace.selectReferenceHint')}
        />
      ) : movements.initialLoading ? (
        <LoadingPanel rows={4} />
      ) : (movements.data?.length ?? 0) === 0 ? (
        <EmptyState title={t('trace.noMovement')} description={t('trace.noMovementHint')} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line">
                <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.movement')}</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">{t('trace.col.type')}</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">{t('common.quantity')}</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">{t('trace.col.before')}</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">{t('trace.col.after')}</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">{t('common.operator')}</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">{t('common.reason')}</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">{t('common.date')}</th>
              </tr>
            </thead>
            <tbody>
              {movements.data?.map((movement) => (
                <tr key={movement.id} className="border-b border-line/60 last:border-0">
                  <td className="numeric px-5 py-2.5 text-2xs text-ink-2">
                    {movement.reference}
                  </td>
                  <td className="px-5 py-2.5">
                    <span className="flex items-center gap-1.5 text-2xs text-ink-2">
                      <StatusDot severity={movement.movement_type === 'IN' ? 'ok' : 'info'} />
                      {movement.movement_type}
                    </span>
                  </td>
                  <td className="numeric px-5 py-2.5 text-right text-xs font-medium text-ink">
                    {movement.movement_type === 'IN' ? '+' : '-'}
                    {formatNumber(movement.quantity)}
                  </td>
                  <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-3">
                    {formatNumber(movement.quantity_before)}
                  </td>
                  <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-2">
                    {formatNumber(movement.quantity_after)}
                  </td>
                  <td className="px-5 py-2.5 text-2xs text-ink-2">{movement.actor_name}</td>
                  <td className="max-w-sm px-5 py-2.5 text-2xs text-ink-3">
                    {movement.reason ?? '—'}
                  </td>
                  <td className="numeric px-5 py-2.5 text-right text-2xs text-ink-3">
                    {formatTimestamp(movement.occurred_at)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
