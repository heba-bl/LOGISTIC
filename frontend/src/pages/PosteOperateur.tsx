import { useEffect, useMemo, useState } from 'react'
import { CheckCircle2, ClipboardCheck, PackageCheck, PackagePlus, Send } from 'lucide-react'

import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  Field,
  Input,
  LoadingPanel,
  Panel,
  Select,
  Textarea,
} from '@/components/ui'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import {
  catalogApi,
  inspectionApi,
  lotsApi,
  productionApi,
  qualityApi,
  receivingApi,
  warehouseApi,
} from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { lotStatusSeverity } from '@/utils/status'
import type { Lot, User, Zone } from '@/types/domain'

/**
 * Operator station.
 *
 * Deliberately the opposite of the manager dashboard: one identity, one zone,
 * one task, two buttons. No KPI, no chart, no navigation noise - an operator on
 * the shop floor must be able to use it without training.
 */
export default function PosteOperateur() {
  const { t, ts } = useI18n()
  const { actor, setActor } = useActor()
  const users = useApiResource(() => catalogApi.users(), [])

  const [selectedId, setSelectedId] = useState<number | null>(null)

  // Default to the operator already chosen in the header.
  useEffect(() => {
    if (selectedId === null && actor) setSelectedId(actor.id)
  }, [actor, selectedId])

  const operator = useMemo(
    () => users.data?.find((user) => user.id === selectedId) ?? null,
    [users.data, selectedId],
  )
  const zone = operator?.zone ?? null

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      {/* Identity */}
      <Panel>
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div className="min-w-0">
            <p className="eyebrow">{t('operator.title')}</p>
            <h1 className="mt-1 text-2xl font-semibold tracking-tight text-ink">
              {operator
                ? t('operator.hello', { name: operator.first_name ?? operator.full_name })
                : t('operator.selectOperator')}
            </h1>
            {operator && (
              <p className="numeric mt-1 text-xs text-ink-3">
                {operator.employee_number} · {operator.role?.label}
              </p>
            )}
          </div>

          <div className="w-full sm:w-72">
            <Field label={t('common.matricule')}>
              <Select
                value={selectedId ?? ''}
                onChange={(event) => {
                  const id = Number(event.target.value)
                  setSelectedId(id)
                  const next = users.data?.find((user) => user.id === id)
                  if (next) setActor(next)
                }}
              >
                <option value="">{t('operator.selectOperator')}</option>
                {(users.data ?? [])
                  .filter((user) => user.is_active)
                  .map((user) => (
                    <option key={user.id} value={user.id}>
                      {user.employee_number} — {user.full_name}
                    </option>
                  ))}
              </Select>
            </Field>
          </div>
        </div>

        {zone && (
          <div className="mt-4 flex items-center gap-2 border-t border-line pt-3">
            <span className="eyebrow">{t('operator.yourZone')}</span>
            <Badge severity="info">{ts(zone)}</Badge>
          </div>
        )}
      </Panel>

      {users.initialLoading ? (
        <Panel bodyClassName="">
          <LoadingPanel rows={3} />
        </Panel>
      ) : !operator ? (
        <Panel bodyClassName="">
          <EmptyState title={t('operator.selectOperator')} />
        </Panel>
      ) : (
        <ZoneWorkspace operator={operator} zone={zone} />
      )}
    </div>
  )
}

function ZoneWorkspace({ operator, zone }: { operator: User; zone: Zone | null }) {
  switch (zone) {
    case 'RECEPTION':
      return <ReceptionTask operator={operator} />
    case 'INSPECTION':
      return <InspectionTask operator={operator} />
    case 'QUALITY':
      return <QualityTask operator={operator} />
    case 'WAREHOUSE':
      return <WarehouseTask operator={operator} />
    case 'PRODUCTION':
      return <ProductionTask operator={operator} />
    default:
      return <SupervisorNotice />
  }
}

function SupervisorNotice() {
  const { t } = useI18n()
  return (
    <Panel bodyClassName="">
      <EmptyState
        icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
        title={t('operator.noTask')}
        description={t('operator.noTaskHint')}
      />
    </Panel>
  )
}

/** Reception: a short entry form - the operator counts and records. */
function ReceptionTask({ operator }: { operator: User }) {
  const { t } = useI18n()
  const toast = useToast()
  const parts = useApiResource(() => catalogApi.parts(), [])
  const suppliers = useApiResource(() => catalogApi.suppliers(), [])

  const [partId, setPartId] = useState('')
  const [supplierId, setSupplierId] = useState('')
  const [expected, setExpected] = useState('')
  const [received, setReceived] = useState('')
  const [note, setNote] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (!partId || !supplierId || !expected || !received) {
      toast.error(t('common.required'))
      return
    }
    setSaving(true)
    try {
      const reception = await receivingApi.create({
        part_id: Number(partId),
        supplier_id: Number(supplierId),
        quantity_expected: Number(expected),
        quantity_received: Number(received),
        delivery_note: note || null,
        actor_id: operator.id,
      })
      toast.success(
        `${reception.lot.lot_number}`,
        `${t('operator.done')} — ${reception.status}`,
      )
      setExpected('')
      setReceived('')
      setNote('')
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Panel title={t('operator.yourTask')} subtitle={t('nav.receiving')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('common.reference')} required>
          <Select value={partId} onChange={(event) => setPartId(event.target.value)}>
            <option value="">—</option>
            {(parts.data ?? []).map((part) => (
              <option key={part.id} value={part.id}>
                {part.reference} — {part.designation}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Fournisseur" required>
          <Select value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
            <option value="">—</option>
            {(suppliers.data ?? []).map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('operator.expected')} required>
          <Input
            type="number"
            inputMode="numeric"
            value={expected}
            onChange={(event) => setExpected(event.target.value)}
            className="text-lg"
          />
        </Field>
        <Field label={t('operator.received')} required>
          <Input
            type="number"
            inputMode="numeric"
            value={received}
            onChange={(event) => setReceived(event.target.value)}
            className="text-lg"
          />
        </Field>
        <Field label="Bon de livraison" className="sm:col-span-2">
          <Input value={note} onChange={(event) => setNote(event.target.value)} />
        </Field>
      </div>

      <div className="mt-5 flex justify-end">
        <Button
          variant="primary"
          size="md"
          loading={saving}
          icon={<PackagePlus className="h-4 w-4" />}
          onClick={() => void submit()}
          className="px-6 py-3 text-sm"
        >
          {t('operator.finishCheck')}
        </Button>
      </div>
    </Panel>
  )
}

/** Inspection: the lots waiting, one simple form each. */
function InspectionTask({ operator }: { operator: User }) {
  const { t } = useI18n()
  const queue = useApiResource(
    () => lotsApi.list({ status: ['PENDING_INSPECTION', 'INSPECTION_IN_PROGRESS'] }),
    [],
  )
  const [active, setActive] = useState<Lot | null>(null)

  return (
    <>
      <TaskList
        lots={queue.data ?? []}
        loading={queue.initialLoading}
        error={queue.error}
        onRetry={queue.refresh}
        onPick={setActive}
        actionLabel={t('common.review')}
      />
      {active && (
        <InspectionForm
          lot={active}
          operator={operator}
          onDone={() => {
            setActive(null)
            void queue.refresh()
          }}
          onCancel={() => setActive(null)}
        />
      )}
    </>
  )
}

function InspectionForm({
  lot,
  operator,
  onDone,
  onCancel,
}: {
  lot: Lot
  operator: User
  onDone: () => void
  onCancel: () => void
}) {
  const { t } = useI18n()
  const toast = useToast()
  const suggestion = useApiResource(() => inspectionApi.sampleSuggestion(lot.id), [lot.id])

  const [sample, setSample] = useState('')
  const [defects, setDefects] = useState('0')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (suggestion.data) setSample(String(suggestion.data.suggested_sample_size))
  }, [suggestion.data])

  async function submit() {
    setSaving(true)
    try {
      if (lot.status === 'PENDING_INSPECTION') {
        await inspectionApi.start(lot.id, operator.id)
      }
      const result = await inspectionApi.record(lot.id, {
        sample_size: Number(sample),
        defects_found: Number(defects),
        actor_id: operator.id,
      })
      toast.success(t('operator.done'), `${lot.lot_number} — ${result.result}`)
      onDone()
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Panel
      title={t('operator.yourTask')}
      subtitle={`${lot.lot_number} · ${lot.part.reference} · ${lot.quantity_received}`}
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t('operator.sample')} required>
          <Input
            type="number"
            inputMode="numeric"
            value={sample}
            onChange={(event) => setSample(event.target.value)}
            className="text-lg"
          />
        </Field>
        <Field label={t('operator.defects')} required>
          <Input
            type="number"
            inputMode="numeric"
            value={defects}
            onChange={(event) => setDefects(event.target.value)}
            className="text-lg"
          />
        </Field>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel}>
          {t('common.cancel')}
        </Button>
        <Button
          variant="primary"
          loading={saving}
          icon={<ClipboardCheck className="h-4 w-4" />}
          onClick={() => void submit()}
          className="px-6 py-3 text-sm"
        >
          {t('operator.finishCheck')}
        </Button>
      </div>
    </Panel>
  )
}

/** Quality: the responsible decides, with a mandatory justification. */
function QualityTask({ operator }: { operator: User }) {
  const { t } = useI18n()
  const toast = useToast()
  const pending = useApiResource(() => qualityApi.pending(), [])
  const [active, setActive] = useState<Lot | null>(null)
  const [justification, setJustification] = useState('')
  const [saving, setSaving] = useState(false)

  async function decide(approve: boolean) {
    if (!active || justification.trim().length < 3) {
      toast.error(t('common.required'), t('common.reason'))
      return
    }
    setSaving(true)
    try {
      const payload = { justification, actor_id: operator.id }
      if (approve) await qualityApi.approve(active.id, payload)
      else await qualityApi.reject(active.id, payload)
      toast.success(t('operator.done'), active.lot_number)
      setActive(null)
      setJustification('')
      void pending.refresh()
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  if (!active) {
    return (
      <TaskList
        lots={pending.data ?? []}
        loading={pending.initialLoading}
        error={pending.error}
        onRetry={pending.refresh}
        onPick={setActive}
        actionLabel={t('common.review')}
      />
    )
  }

  return (
    <Panel
      title={t('operator.yourTask')}
      subtitle={`${active.lot_number} · ${active.part.reference}`}
    >
      <Field label={t('common.reason')} required>
        <Textarea
          value={justification}
          onChange={(event) => setJustification(event.target.value)}
          rows={3}
        />
      </Field>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => setActive(null)}>
          {t('common.cancel')}
        </Button>
        <Button variant="danger" loading={saving} onClick={() => void decide(false)}>
          {t('common.reject')}
        </Button>
        <Button
          variant="success"
          loading={saving}
          onClick={() => void decide(true)}
          className="px-6 py-3 text-sm"
        >
          {t('common.approve')}
        </Button>
      </div>
    </Panel>
  )
}

/** Warehouse: confirm the storage the backend proposes. */
function WarehouseTask({ operator }: { operator: User }) {
  const { t } = useI18n()
  const toast = useToast()
  const queue = useApiResource(() => lotsApi.list({ status: ['APPROVED'] }), [])
  const [active, setActive] = useState<Lot | null>(null)
  const plan = useApiResource(
    () => warehouseApi.storagePlan(active!.id),
    [active?.id],
    { enabled: Boolean(active) },
  )
  const [saving, setSaving] = useState(false)

  async function confirm() {
    if (!active || !plan.data) return
    setSaving(true)
    try {
      const movements = await warehouseApi.confirmStorage(active.id, {
        allocations: plan.data.suggestions.map((item) => ({
          location_id: item.location_id,
          quantity: item.quantity,
        })),
        actor_id: operator.id,
      })
      const added = movements.reduce((sum, movement) => sum + movement.quantity, 0)
      toast.success(t('operator.done'), `${active.lot_number} — stock +${added}`)
      setActive(null)
      void queue.refresh()
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  if (!active) {
    return (
      <TaskList
        lots={queue.data ?? []}
        loading={queue.initialLoading}
        error={queue.error}
        onRetry={queue.refresh}
        onPick={setActive}
        actionLabel={t('common.confirm')}
      />
    )
  }

  return (
    <Panel
      title={t('operator.yourTask')}
      subtitle={`${active.lot_number} · ${active.part.reference} · ${active.quantity_approved}`}
    >
      {plan.initialLoading ? (
        <LoadingPanel rows={2} />
      ) : plan.data ? (
        <ul className="space-y-2">
          {plan.data.suggestions.map((item) => (
            <li
              key={item.location_id}
              className="flex items-center justify-between gap-3 rounded-md border border-line bg-elevated px-3 py-2.5"
            >
              <span className="numeric text-sm font-medium text-ink">
                {item.location_code}
              </span>
              <span className="numeric text-sm text-ink-2">{item.quantity}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-5 flex justify-end gap-2">
        <Button variant="ghost" onClick={() => setActive(null)}>
          {t('common.cancel')}
        </Button>
        <Button
          variant="primary"
          loading={saving}
          icon={<PackageCheck className="h-4 w-4" />}
          onClick={() => void confirm()}
          className="px-6 py-3 text-sm"
        >
          {t('common.confirm')}
        </Button>
      </div>
    </Panel>
  )
}

/** Production: the station leader asks for parts. */
function ProductionTask({ operator }: { operator: User }) {
  const { t } = useI18n()
  const toast = useToast()
  const parts = useApiResource(() => catalogApi.parts(), [])
  const stations = useApiResource(() => catalogApi.stations(), [])

  const [stationId, setStationId] = useState('')
  const [partId, setPartId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (!stationId || !partId || !quantity) {
      toast.error(t('common.required'))
      return
    }
    setSaving(true)
    try {
      const request = await productionApi.create({
        station_id: Number(stationId),
        part_id: Number(partId),
        quantity: Number(quantity),
        actor_id: operator.id,
        submit_immediately: true,
      })
      toast.success(request.reference, t('operator.pendingValidation'))
      setQuantity('')
    } catch (error) {
      toast.error(t('common.error'), toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Panel title={t('operator.yourTask')} subtitle={t('nav.production')}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Station" required>
          <Select value={stationId} onChange={(event) => setStationId(event.target.value)}>
            <option value="">—</option>
            {(stations.data ?? []).map((station) => (
              <option key={station.id} value={station.id}>
                {station.code} — {station.name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('common.reference')} required>
          <Select value={partId} onChange={(event) => setPartId(event.target.value)}>
            <option value="">—</option>
            {(parts.data ?? []).map((part) => (
              <option key={part.id} value={part.id}>
                {part.reference}
              </option>
            ))}
          </Select>
        </Field>
        <Field label={t('common.quantity')} required className="sm:col-span-2">
          <Input
            type="number"
            inputMode="numeric"
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            className="text-lg"
          />
        </Field>
      </div>
      <div className="mt-5 flex justify-end">
        <Button
          variant="primary"
          loading={saving}
          icon={<Send className="h-4 w-4" />}
          onClick={() => void submit()}
          className="px-6 py-3 text-sm"
        >
          {t('operator.record')}
        </Button>
      </div>
    </Panel>
  )
}

function TaskList({
  lots,
  loading,
  error,
  onRetry,
  onPick,
  actionLabel,
}: {
  lots: Lot[]
  loading: boolean
  error: string | null
  onRetry: () => void
  onPick: (lot: Lot) => void
  actionLabel: string
}) {
  const { t, ts } = useI18n()

  return (
    <Panel
      title={t('operator.yourTask')}
      subtitle={t('operator.tasksWaiting', { count: lots.length })}
      bodyClassName=""
    >
      {loading ? (
        <LoadingPanel rows={3} />
      ) : error ? (
        <ErrorPanel message={error} onRetry={onRetry} />
      ) : lots.length === 0 ? (
        <EmptyState
          icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
          title={t('operator.noTask')}
          description={t('operator.noTaskHint')}
        />
      ) : (
        <ul className="divide-y divide-line">
          {lots.map((lot) => (
            <li key={lot.id} className="flex flex-wrap items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="numeric text-sm font-medium text-ink">{lot.lot_number}</p>
                <p className="text-2xs text-ink-3">
                  {lot.part.reference} · {lot.supplier.name}
                </p>
              </div>
              <span className="numeric text-sm text-ink-2">
                {lot.status === 'APPROVED' ? lot.quantity_approved : lot.quantity_received}
              </span>
              <Badge severity={lotStatusSeverity[lot.status]}>{ts(lot.status)}</Badge>
              <Button
                variant="primary"
                size="sm"
                onClick={() => onPick(lot)}
                className={cn('px-4 py-2')}
              >
                {actionLabel}
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  )
}
