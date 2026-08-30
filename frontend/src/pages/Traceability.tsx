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
  const { ts } = useI18n()
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
        title="Traceability"
        description="Complete history of every lot and every audited action."
        actions={
          <form onSubmit={onSubmit} className="flex flex-wrap items-center gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-ink-3" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Lot, reference, operator…"
                className="w-64 pl-9"
              />
            </div>
            <Select
              value={entityType}
              onChange={(event) => setEntityType(event.target.value)}
              className="w-40"
            >
              <option value="">All events</option>
              <option value="reception">Receptions</option>
              <option value="inspection">Inspections</option>
              <option value="quality_validation">Quality</option>
              <option value="lot">Lots</option>
              <option value="stock">Stock</option>
              <option value="production_request">Production</option>
            </Select>
            <Button type="submit" variant="primary">
              Search
            </Button>
          </form>
        }
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel
          title="Lots"
          subtitle={`${lots.data?.length ?? 0} lots — click to open the full history`}
          bodyClassName=""
          action={<Route className="h-3.5 w-3.5 text-ink-3" />}
        >
          {lots.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : lots.error ? (
            <ErrorPanel message={lots.error} onRetry={lots.refresh} />
          ) : (lots.data?.length ?? 0) === 0 ? (
            <EmptyState title="No lot found" description="Try another search term." />
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
          title="Audit trail"
          subtitle={`${audit.data?.length ?? 0} recorded events`}
          bodyClassName=""
          action={<History className="h-3.5 w-3.5 text-ink-3" />}
        >
          {audit.initialLoading ? (
            <LoadingPanel rows={6} />
          ) : audit.error ? (
            <ErrorPanel message={audit.error} onRetry={audit.refresh} />
          ) : (audit.data?.length ?? 0) === 0 ? (
            <EmptyState title="No event" description="No action matches this filter." />
          ) : (
            <div className="max-h-[520px] overflow-auto">
              <table className="w-full min-w-[980px] border-collapse text-left">
                <thead className="sticky top-0 z-10 bg-panel">
                  <tr className="border-b border-line">
                    <th className="eyebrow px-5 py-2.5 font-semibold">When</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Action</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Target</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Qty</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Transition</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Who entered</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Who validated</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Why</th>
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
                        <span className="block text-[10px] text-ink-3">
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
                            <span className="block text-[10px] text-ink-3">
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
                          <span className="numeric mt-0.5 block text-[10px] text-ink-3/70">
                            file: {entry.source_file}
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
  const [partId, setPartId] = useState('')
  const movements = useApiResource(
    () => traceabilityApi.partMovements(Number(partId)),
    [partId],
    { enabled: Boolean(partId) },
  )

  return (
    <Panel
      title="Stock history of a reference"
      subtitle="Every movement in and out, with its justification"
      bodyClassName=""
      action={
        <Select
          value={partId}
          onChange={(event) => setPartId(event.target.value)}
          className="w-56"
        >
          <option value="">Select a reference…</option>
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
          title="Select a reference"
          description="The ledger shows every increment and decrement, in order."
        />
      ) : movements.initialLoading ? (
        <LoadingPanel rows={4} />
      ) : (movements.data?.length ?? 0) === 0 ? (
        <EmptyState title="No movement" description="This reference has never moved." />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line">
                <th className="eyebrow px-5 py-2.5 font-semibold">Movement</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">Type</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">Quantity</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">Before</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">After</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">Operator</th>
                <th className="eyebrow px-5 py-2.5 font-semibold">Reason</th>
                <th className="eyebrow px-5 py-2.5 text-right font-semibold">Date</th>
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
