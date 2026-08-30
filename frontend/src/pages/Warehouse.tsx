import { useMemo, useState } from 'react'
import { motion } from 'framer-motion'
import { Boxes, PackageCheck, Warehouse as WarehouseIcon } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  LoadingPanel,
  Meter,
  Modal,
  Panel,
  StatusDot,
  Textarea,
} from '@/components/ui'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import { lotsApi, stockApi, warehouseApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatDecimal, formatNumber } from '@/utils/format'
import { toSeverity } from '@/utils/status'
import type { Lot, StoragePlan, WarehouseLocation } from '@/types/domain'
import type { Severity } from '@/types'

function occupancySeverity(
  location: WarehouseLocation,
  warning: number,
  critical: number,
): Severity {
  if (location.occupancy_percent >= critical) return 'crit'
  if (location.occupancy_percent >= warning) return 'warn'
  if (location.occupied === 0) return 'info'
  return 'ok'
}

/**
 * Warehouse.
 *
 * Interactive map of the addresses, storage confirmation for approved lots (the
 * only operation that increments stock) and the live stock table.
 */
export default function Warehouse() {
  const { ts } = useI18n()
  const grid = useApiResource(() => warehouseApi.grid(), [])
  const stock = useApiResource(() => stockApi.list(), [])
  const toStore = useApiResource(() => lotsApi.list({ status: ['APPROVED'] }), [])

  const [locationId, setLocationId] = useState<number | null>(null)
  const [storing, setStoring] = useState<Lot | null>(null)
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  function refreshAll() {
    void grid.refresh()
    void stock.refresh()
    void toStore.refresh()
  }

  const zones = grid.data?.zones ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        title="Warehouse"
        description="Addressing, storage confirmation and available stock."
        actions={
          grid.data && (
            <div className="flex items-center gap-3 rounded-lg border border-line bg-panel px-3 py-2">
              <div>
                <p className="eyebrow">Global occupancy</p>
                <p className="numeric mt-0.5 text-sm font-semibold text-ink">
                  {formatDecimal(grid.data.occupancy_percent)}%
                </p>
              </div>
              <div className="border-l border-line pl-3 text-right">
                <p className="numeric text-xs text-ink-2">
                  {formatNumber(grid.data.total_occupied)}
                </p>
                <p className="text-2xs text-ink-3">
                  of {formatNumber(grid.data.total_capacity)}
                </p>
              </div>
            </div>
          )
        }
      />

      {/* Lots awaiting storage */}
      <Panel
        title="Approved lots awaiting storage"
        subtitle={`${toStore.data?.length ?? 0} ${(toStore.data?.length ?? 0) === 1 ? 'lot' : 'lots'} cleared by quality`}
        bodyClassName=""
        action={<PackageCheck className="h-3.5 w-3.5 text-ink-3" />}
      >
        {toStore.initialLoading ? (
          <LoadingPanel rows={2} />
        ) : (toStore.data?.length ?? 0) === 0 ? (
          <EmptyState
            title="Nothing to store"
            description="Every approved lot has been physically stored."
          />
        ) : (
          <ul className="divide-y divide-line">
            {toStore.data?.map((lot) => (
              <li key={lot.id} className="flex flex-wrap items-center gap-3 px-5 py-3.5">
                <button
                  type="button"
                  onClick={() => setSelectedLotId(lot.id)}
                  className="numeric text-xs font-medium text-ink hover:text-accent"
                >
                  {lot.lot_number}
                </button>
                <span className="numeric text-xs text-ink-2">{lot.part.reference}</span>
                <span className="text-2xs text-ink-3">{lot.part.designation}</span>
                <span className="numeric ml-auto text-xs text-ink">
                  {formatNumber(lot.quantity_approved)} {lot.part.unit}
                </span>
                <Button size="sm" variant="primary" onClick={() => setStoring(lot)}>
                  Confirm storage
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      {/* Interactive map */}
      <Panel
        title="Warehouse map"
        subtitle={grid.data ? `${grid.data.warehouse_name} — click an address` : 'Loading…'}
        bodyClassName="p-5"
        action={<WarehouseIcon className="h-3.5 w-3.5 text-ink-3" />}
      >
        {grid.initialLoading ? (
          <LoadingPanel rows={3} />
        ) : grid.error ? (
          <ErrorPanel message={grid.error} onRetry={grid.refresh} />
        ) : grid.data ? (
          <div className="space-y-4">
            {zones.map((zone) => {
              const locations = grid.data!.locations.filter((item) => item.zone === zone)
              return (
                <div key={zone} className="flex items-start gap-4">
                  <div className="w-10 shrink-0 pt-3">
                    <p className="numeric text-sm font-semibold text-ink-3">{zone}</p>
                  </div>
                  <div className="grid flex-1 grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-5">
                    {locations.map((location, index) => {
                      const severity = occupancySeverity(
                        location,
                        grid.data!.warning_threshold,
                        grid.data!.critical_threshold,
                      )
                      return (
                        <motion.button
                          key={location.id}
                          type="button"
                          initial={{ opacity: 0, scale: 0.96 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ duration: 0.3, delay: index * 0.03 }}
                          onClick={() => setLocationId(location.id)}
                          className={cn(
                            'group rounded-lg border bg-elevated/60 p-3 text-left transition-colors',
                            severity === 'crit'
                              ? 'border-crit/40 hover:border-crit/70'
                              : severity === 'warn'
                                ? 'border-warn/40 hover:border-warn/70'
                                : severity === 'ok'
                                  ? 'border-ok/30 hover:border-ok/60'
                                  : 'border-line hover:border-line-strong',
                          )}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="numeric text-xs font-semibold text-ink">
                              {location.code}
                            </span>
                            <StatusDot severity={severity} pulse={severity === 'crit'} />
                          </div>
                          <p className="numeric mt-2 text-2xs text-ink-2">
                            {formatNumber(location.occupied)} / {formatNumber(location.capacity)}
                          </p>
                          <Meter
                            value={location.occupancy_percent}
                            severity={severity}
                            label={location.code}
                            className="mt-2"
                          />
                          <p className="numeric mt-1.5 text-[10px] text-ink-3">
                            {formatDecimal(location.occupancy_percent)}%
                          </p>
                        </motion.button>
                      )
                    })}
                  </div>
                </div>
              )
            })}

            <div className="flex flex-wrap items-center gap-4 border-t border-line pt-3 text-2xs text-ink-3">
              <span className="flex items-center gap-1.5">
                <StatusDot severity="info" /> empty
              </span>
              <span className="flex items-center gap-1.5">
                <StatusDot severity="ok" /> normal
              </span>
              <span className="flex items-center gap-1.5">
                <StatusDot severity="warn" /> above {grid.data.warning_threshold}%
              </span>
              <span className="flex items-center gap-1.5">
                <StatusDot severity="crit" /> saturated above {grid.data.critical_threshold}%
              </span>
            </div>
          </div>
        ) : null}
      </Panel>

      {/* Stock */}
      <Panel
        title="Available stock"
        subtitle={`${stock.data?.length ?? 0} references`}
        bodyClassName=""
        action={<Boxes className="h-3.5 w-3.5 text-ink-3" />}
      >
        {stock.initialLoading ? (
          <LoadingPanel rows={5} />
        ) : (stock.data?.length ?? 0) === 0 ? (
          <EmptyState title="No stock yet" description="Confirm a storage to create stock." />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line">
                  <th className="eyebrow px-5 py-2.5 font-semibold">Reference</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Category</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Available</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Reserved</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Safety</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Demand</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Cover</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Addresses</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">State</th>
                </tr>
              </thead>
              <tbody>
                {stock.data?.map((row) => (
                  <tr key={row.part_id} className="border-b border-line/60 last:border-0">
                    <td className="px-5 py-3">
                      <span className="numeric text-xs font-medium text-ink">
                        {row.reference}
                      </span>
                      <span className="block truncate text-2xs text-ink-3">
                        {row.designation}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-2xs text-ink-3">{row.category ?? '—'}</td>
                    <td className="numeric px-5 py-3 text-right text-xs font-semibold text-ink">
                      {formatNumber(row.quantity_available)}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                      {formatNumber(row.quantity_reserved)}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-3">
                      {formatNumber(row.safety_stock)}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                      {formatNumber(row.open_demand)}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                      {row.days_of_cover !== null ? `${row.days_of_cover} d` : '—'}
                    </td>
                    <td className="numeric px-5 py-3 text-2xs text-ink-3">
                      {row.locations.join(', ') || '—'}
                    </td>
                    <td className="px-5 py-3">
                      <Badge severity={toSeverity(row.severity)}>
                        {ts(row.severity)}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {locationId !== null && (
        <LocationDialog locationId={locationId} onClose={() => setLocationId(null)} />
      )}

      {storing && (
        <StorageDialog
          lot={storing}
          onClose={() => setStoring(null)}
          onDone={() => {
            setStoring(null)
            refreshAll()
          }}
        />
      )}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}

function LocationDialog({ locationId, onClose }: { locationId: number; onClose: () => void }) {
  const detail = useApiResource(() => warehouseApi.location(locationId), [locationId])

  return (
    <Modal
      open
      onClose={onClose}
      title={detail.data ? `Address ${detail.data.code}` : 'Address'}
      subtitle="Capacity, occupancy and content"
    >
      {detail.initialLoading ? (
        <LoadingPanel rows={3} />
      ) : detail.error ? (
        <ErrorPanel message={detail.error} onRetry={detail.refresh} />
      ) : detail.data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Capacity" value={formatNumber(detail.data.capacity)} />
            <Metric label="Occupied" value={formatNumber(detail.data.occupied)} />
            <Metric label="Free" value={formatNumber(detail.data.free_capacity)} />
            <Metric label="Occupancy" value={`${formatDecimal(detail.data.occupancy_percent)}%`} />
          </div>

          <Meter
            value={detail.data.occupancy_percent}
            severity={toSeverity(detail.data.severity)}
            label={detail.data.code}
          />

          <div>
            <p className="eyebrow mb-2">References stored</p>
            {detail.data.references.length === 0 ? (
              <p className="text-xs text-ink-3">This address is empty.</p>
            ) : (
              <div className="flex flex-wrap gap-1.5">
                {detail.data.references.map((reference) => (
                  <span
                    key={reference}
                    className="numeric rounded border border-line bg-elevated px-2 py-0.5 text-2xs text-ink-2"
                  >
                    {reference}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div>
            <p className="eyebrow mb-2">Lots held ({detail.data.lots.length})</p>
            <ul className="space-y-1.5">
              {detail.data.lots.map((lot) => (
                <li
                  key={lot.id}
                  className="flex items-center gap-2 rounded border border-line bg-elevated/60 px-2.5 py-2"
                >
                  <span className="numeric text-2xs text-ink">{lot.lot_number}</span>
                  <span className="numeric text-2xs text-ink-3">{lot.part.reference}</span>
                  <span className="numeric ml-auto text-2xs text-ink-2">
                    {formatNumber(lot.quantity_available)} {lot.part.unit}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Modal>
  )
}

function StorageDialog({
  lot,
  onClose,
  onDone,
}: {
  lot: Lot
  onClose: () => void
  onDone: () => void
}) {
  const plan = useApiResource<StoragePlan>(() => warehouseApi.storagePlan(lot.id), [lot.id])
  const { byRole, actorId } = useActor()
  const toast = useToast()
  const operator = byRole('WAREHOUSE_OPERATOR')

  const [overrides, setOverrides] = useState<Record<number, number>>({})
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  const allocations = useMemo(() => {
    if (!plan.data) return []
    return plan.data.suggestions.map((item) => ({
      ...item,
      quantity: overrides[item.location_id] ?? item.quantity,
    }))
  }, [plan.data, overrides])

  const total = allocations.reduce((sum, item) => sum + item.quantity, 0)
  const expected = plan.data?.quantity_to_store ?? 0
  const balanced = total === expected

  async function submit() {
    if (!balanced) {
      toast.error(
        'Quantities do not add up',
        `Allocated ${total} for ${expected} approved units.`,
      )
      return
    }
    setSaving(true)
    try {
      const movements = await warehouseApi.confirmStorage(lot.id, {
        allocations: allocations
          .filter((item) => item.quantity > 0)
          .map((item) => ({ location_id: item.location_id, quantity: item.quantity })),
        actor_id: operator?.id ?? actorId,
        notes: notes || null,
      })
      const added = movements.reduce((sum, movement) => sum + movement.quantity, 0)
      toast.success(
        `Storage confirmed — stock +${added}`,
        `${lot.part.reference}: ${movements[0]?.quantity_before ?? 0} → ${
          movements[movements.length - 1]?.quantity_after ?? added
        } units.`,
      )
      onDone()
    } catch (error) {
      toast.error('Storage refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Confirm storage — ${lot.lot_number}`}
      subtitle="This is the only operation that increments stock"
      width="lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={saving}
            disabled={!balanced}
            onClick={() => void submit()}
          >
            Confirm and increment stock
          </Button>
        </>
      }
    >
      {plan.initialLoading ? (
        <LoadingPanel rows={3} />
      ) : plan.error ? (
        <ErrorPanel message={plan.error} onRetry={plan.refresh} />
      ) : plan.data ? (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <Metric label="Part" value={plan.data.part_reference} />
            <Metric label="To store" value={formatNumber(plan.data.quantity_to_store)} />
            <Metric label="Allocated" value={formatNumber(total)} />
          </div>

          {!plan.data.fully_allocatable && (
            <div className="rounded-lg border border-crit/35 bg-crit/10 px-3 py-2.5 text-xs text-ink-2">
              The warehouse does not have enough free capacity for the whole quantity. Free space
              or reduce the allocation.
            </div>
          )}

          <div>
            <p className="eyebrow mb-2">
              Proposed allocation — primary address first, then secondary
            </p>
            <ul className="space-y-2">
              {allocations.map((item) => (
                <li
                  key={item.location_id}
                  className="flex flex-wrap items-center gap-3 rounded-lg border border-line bg-elevated/60 px-3 py-2.5"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="numeric text-xs font-semibold text-ink">
                        {item.location_code}
                      </span>
                      <Badge severity={item.role === 'PRIMARY' ? 'ok' : 'info'}>
                        {item.role === 'PRIMARY' ? 'Primary' : 'Secondary'}
                      </Badge>
                    </div>
                    <p className="mt-1 text-2xs text-ink-3">{item.rationale}</p>
                  </div>
                  <input
                    type="number"
                    min={0}
                    max={item.free_capacity}
                    value={item.quantity}
                    onChange={(event) =>
                      setOverrides((current) => ({
                        ...current,
                        [item.location_id]: Number(event.target.value),
                      }))
                    }
                    className="numeric w-24 rounded border border-line bg-panel px-2 py-1.5 text-right text-xs text-ink focus:border-accent/60 focus:outline-none"
                  />
                </li>
              ))}
            </ul>
          </div>

          {!balanced && (
            <p className="text-2xs text-warn-soft">
              The allocated total ({total}) must match the approved quantity ({expected}).
            </p>
          )}

          <div>
            <p className="eyebrow mb-1.5">Notes</p>
            <Textarea
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              placeholder="Storage conditions, pallet number…"
              rows={2}
            />
          </div>
        </div>
      ) : null}
    </Modal>
  )
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-2xs text-ink-3">{label}</p>
      <p className="numeric mt-0.5 text-xs font-semibold text-ink">{value}</p>
    </div>
  )
}
