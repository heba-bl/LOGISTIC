import { useState } from 'react'
import { CheckCircle2, Factory, PackageOpen, Plus, Send, Truck, XCircle } from 'lucide-react'

import { PageHeader } from '@/components/PageHeader'
import {
  Badge,
  Button,
  EmptyState,
  ErrorPanel,
  Field,
  Input,
  LoadingPanel,
  Modal,
  Panel,
  Select,
  Textarea,
} from '@/components/ui'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import { catalogApi, productionApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { prioritySeverity, requestStatusSeverity } from '@/utils/status'
import type { ProductionRequestRow, ProductionRequestStatus } from '@/types/domain'

/** Which action is offered next, given the current workflow state. */
const NEXT_ACTION: Partial<
  Record<ProductionRequestStatus, { key: string; label: string; icon: typeof Send }>
> = {
  DRAFT: { key: 'submit', label: 'Submit', icon: Send },
  SUBMITTED: { key: 'approve', label: 'Approve', icon: CheckCircle2 },
  APPROVED: { key: 'prepare', label: 'Start preparation', icon: PackageOpen },
  PREPARING: { key: 'ready', label: 'Mark ready', icon: CheckCircle2 },
  READY: { key: 'issue', label: 'Confirm issue', icon: Truck },
}

/**
 * Production.
 *
 * Full request workflow: DRAFT to ISSUED. Only the final confirmed issue
 * decrements stock — every earlier step leaves the balance untouched.
 */
export default function Production() {
  const requests = useApiResource(() => productionApi.list(), [])
  const parts = useApiResource(() => catalogApi.parts(), [])
  const stations = useApiResource(() => catalogApi.stations(), [])

  const [creating, setCreating] = useState(false)
  const [rejecting, setRejecting] = useState<ProductionRequestRow | null>(null)

  const { byRole, actorId } = useActor()
  const toast = useToast()
  const [busy, setBusy] = useState<number | null>(null)

  async function advance(row: ProductionRequestRow) {
    const next = NEXT_ACTION[row.request.status]
    if (!next) return

    setBusy(row.request.id)
    const id = row.request.id
    const manager = byRole('PRODUCTION_MANAGER')?.id ?? actorId
    const operator = byRole('WAREHOUSE_OPERATOR')?.id ?? actorId
    const leader = byRole('STATION_LEADER')?.id ?? actorId

    try {
      switch (next.key) {
        case 'submit':
          await productionApi.submit(id, leader)
          toast.info(`${row.request.reference} submitted`, 'Waiting for production validation.')
          break
        case 'approve':
          await productionApi.approve(id, manager)
          toast.success(
            `${row.request.reference} approved`,
            'Quantity reserved. Stock is unchanged until the issue is confirmed.',
          )
          break
        case 'prepare':
          await productionApi.prepare(id, operator)
          toast.info(`${row.request.reference} in preparation`, 'Warehouse is picking the parts.')
          break
        case 'ready':
          await productionApi.ready(id, operator)
          toast.info(`${row.request.reference} ready`, 'Waiting for the physical issue.')
          break
        case 'issue': {
          const movement = await productionApi.issue(id, { actor_id: operator })
          toast.success(
            `Issue confirmed — stock -${movement.quantity}`,
            `${movement.part.reference}: ${movement.quantity_before} → ${movement.quantity_after} units.`,
          )
          break
        }
      }
      void requests.refresh()
    } catch (error) {
      toast.error('Action refused', toErrorMessage(error))
    } finally {
      setBusy(null)
    }
  }

  const open = requests.data?.filter((row) => NEXT_ACTION[row.request.status]) ?? []
  const closed = requests.data?.filter((row) => !NEXT_ACTION[row.request.status]) ?? []

  return (
    <div className="space-y-4">
      <PageHeader
        title="Production"
        description="Parts requests from the lines — stock only moves on a confirmed issue."
        actions={
          <Button
            variant="primary"
            icon={<Plus className="h-3.5 w-3.5" />}
            onClick={() => setCreating(true)}
          >
            New request
          </Button>
        }
      />

      <Panel
        title="Open requests"
        subtitle={`${open.length} ${open.length === 1 ? 'request' : 'requests'} in the workflow`}
        bodyClassName=""
        action={<Factory className="h-3.5 w-3.5 text-ink-3" />}
      >
        {requests.initialLoading ? (
          <LoadingPanel rows={4} />
        ) : requests.error ? (
          <ErrorPanel message={requests.error} onRetry={requests.refresh} />
        ) : open.length === 0 ? (
          <EmptyState title="No open request" description="Every request has been processed." />
        ) : (
          <RequestTable
            rows={open}
            busy={busy}
            onAdvance={advance}
            onReject={(row) => setRejecting(row)}
          />
        )}
      </Panel>

      <Panel
        title="Closed requests"
        subtitle={`${closed.length} issued, rejected or cancelled`}
        bodyClassName=""
      >
        {closed.length === 0 ? (
          <EmptyState title="No closed request yet" />
        ) : (
          <RequestTable rows={closed} busy={busy} />
        )}
      </Panel>

      <CreateRequestDialog
        open={creating}
        onClose={() => setCreating(false)}
        parts={parts.data ?? []}
        stations={stations.data ?? []}
        onCreated={() => {
          setCreating(false)
          void requests.refresh()
        }}
      />

      {rejecting && (
        <RejectDialog
          row={rejecting}
          onClose={() => setRejecting(null)}
          onDone={() => {
            setRejecting(null)
            void requests.refresh()
          }}
        />
      )}
    </div>
  )
}

function RequestTable({
  rows,
  busy,
  onAdvance,
  onReject,
}: {
  rows: ProductionRequestRow[]
  busy: number | null
  onAdvance?: (row: ProductionRequestRow) => void
  onReject?: (row: ProductionRequestRow) => void
}) {
  const { ts } = useI18n()
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[980px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            <th className="eyebrow px-5 py-2.5 font-semibold">Reference</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">Station</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">Part</th>
            <th className="eyebrow px-5 py-2.5 text-right font-semibold">Requested</th>
            <th className="eyebrow px-5 py-2.5 text-right font-semibold">Stock</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">Coverage</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">Priority</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">Status</th>
            <th className="eyebrow px-5 py-2.5 text-right font-semibold">Action</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => {
            const next = NEXT_ACTION[row.request.status]
            const Icon = next?.icon
            return (
              <tr key={row.request.id} className="border-b border-line/60 last:border-0">
                <td className="numeric px-5 py-3 text-xs font-medium text-ink">
                  {row.request.reference}
                  <span className="block text-2xs font-normal text-ink-3">
                    {formatTimestamp(row.request.created_on)}
                  </span>
                </td>
                <td className="px-5 py-3">
                  <span className="numeric text-xs text-ink-2">{row.request.station.code}</span>
                  <span className="block text-2xs text-ink-3">{row.request.station.name}</span>
                </td>
                <td className="px-5 py-3">
                  <span className="numeric text-xs text-ink-2">{row.request.part.reference}</span>
                  <span className="block truncate text-2xs text-ink-3">
                    {row.request.part.designation}
                  </span>
                </td>
                <td className="numeric px-5 py-3 text-right text-xs text-ink">
                  {formatNumber(row.request.quantity_requested)}
                  {row.request.quantity_issued > 0 && (
                    <span className="block text-2xs text-ok-soft">
                      issued {formatNumber(row.request.quantity_issued)}
                    </span>
                  )}
                </td>
                <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                  {formatNumber(row.stock_available)}
                </td>
                <td className="px-5 py-3">
                  {row.request.status === 'ISSUED' ? (
                    <span className="text-2xs text-ink-3">—</span>
                  ) : row.is_coverable ? (
                    <Badge severity="ok">Covered</Badge>
                  ) : (
                    <Badge severity="crit">Short {formatNumber(row.shortfall)}</Badge>
                  )}
                </td>
                <td className="px-5 py-3">
                  <Badge severity={prioritySeverity[row.request.priority] ?? 'info'}>
                    P{row.request.priority}
                  </Badge>
                </td>
                <td className="px-5 py-3">
                  <Badge severity={requestStatusSeverity[row.request.status]}>
                    {ts(row.request.status)}
                  </Badge>
                </td>
                <td className="px-5 py-3">
                  <div className="flex justify-end gap-2">
                    {next && onAdvance && (
                      <Button
                        size="sm"
                        variant={next.key === 'issue' ? 'primary' : 'secondary'}
                        loading={busy === row.request.id}
                        icon={Icon ? <Icon className="h-3 w-3" /> : undefined}
                        onClick={() => onAdvance(row)}
                      >
                        {next.label}
                      </Button>
                    )}
                    {onReject && row.request.status === 'SUBMITTED' && (
                      <Button
                        size="sm"
                        variant="danger"
                        icon={<XCircle className="h-3 w-3" />}
                        onClick={() => onReject(row)}
                      >
                        Reject
                      </Button>
                    )}
                  </div>
                  {row.request.rejection_reason && (
                    <p className="mt-1 max-w-[220px] text-right text-2xs text-crit-soft">
                      {row.request.rejection_reason}
                    </p>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CreateRequestDialog({
  open,
  onClose,
  parts,
  stations,
  onCreated,
}: {
  open: boolean
  onClose: () => void
  parts: { id: number; reference: string; designation: string }[]
  stations: { id: number; code: string; name: string }[]
  onCreated: () => void
}) {
  const { byRole, actorId } = useActor()
  const toast = useToast()

  const [stationId, setStationId] = useState('')
  const [partId, setPartId] = useState('')
  const [quantity, setQuantity] = useState('')
  const [priority, setPriority] = useState('3')
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (!stationId || !partId || !quantity) {
      toast.error('Incomplete form', 'Station, reference and quantity are required.')
      return
    }
    setSaving(true)
    try {
      const request = await productionApi.create({
        station_id: Number(stationId),
        part_id: Number(partId),
        quantity: Number(quantity),
        priority: Number(priority),
        notes: notes || null,
        actor_id: byRole('STATION_LEADER')?.id ?? actorId,
        submit_immediately: true,
      })
      toast.success(
        `Request ${request.reference} created`,
        'Submitted for validation. Stock unchanged — a request never decrements stock.',
      )
      setStationId('')
      setPartId('')
      setQuantity('')
      setNotes('')
      onCreated()
    } catch (error) {
      toast.error('Request refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New production request"
      subtitle="Creating a request never decrements stock"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            Create and submit
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Station" required>
          <Select value={stationId} onChange={(event) => setStationId(event.target.value)}>
            <option value="">Select a station…</option>
            {stations.map((station) => (
              <option key={station.id} value={station.id}>
                {station.code} — {station.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Part reference" required>
          <Select value={partId} onChange={(event) => setPartId(event.target.value)}>
            <option value="">Select a reference…</option>
            {parts.map((part) => (
              <option key={part.id} value={part.id}>
                {part.reference} — {part.designation}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Quantity" required>
          <Input
            type="number"
            min={1}
            value={quantity}
            onChange={(event) => setQuantity(event.target.value)}
            placeholder="20"
          />
        </Field>

        <Field label="Priority" hint="1 = most urgent">
          <Select value={priority} onChange={(event) => setPriority(event.target.value)}>
            <option value="1">P1 — urgent</option>
            <option value="2">P2 — normal</option>
            <option value="3">P3 — planned</option>
          </Select>
        </Field>

        <Field label="Notes" className="sm:col-span-2">
          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Context of the requirement…"
          />
        </Field>
      </div>
    </Modal>
  )
}

function RejectDialog({
  row,
  onClose,
  onDone,
}: {
  row: ProductionRequestRow
  onClose: () => void
  onDone: () => void
}) {
  const { byRole, actorId } = useActor()
  const toast = useToast()
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  async function submit() {
    if (reason.trim().length < 3) {
      toast.error('Reason required', 'A rejection is never recorded without a reason.')
      return
    }
    setSaving(true)
    try {
      await productionApi.reject(
        row.request.id,
        reason,
        byRole('PRODUCTION_MANAGER')?.id ?? actorId,
      )
      toast.info(`${row.request.reference} rejected`, reason)
      onDone()
    } catch (error) {
      toast.error('Rejection refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Reject ${row.request.reference}`}
      subtitle={`${row.request.quantity_requested} x ${row.request.part.reference} for ${row.request.station.code}`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="danger" loading={saving} onClick={() => void submit()}>
            Reject
          </Button>
        </>
      }
    >
      <Field label="Reason" required hint="Recorded in the audit trail">
        <Textarea
          value={reason}
          onChange={(event) => setReason(event.target.value)}
          placeholder="Requirement not justified for this shift…"
          rows={4}
        />
      </Field>

      <div
        className={cn(
          'mt-4 rounded-lg border px-3 py-2.5 text-xs text-ink-2',
          row.is_coverable ? 'border-line bg-elevated/60' : 'border-crit/35 bg-crit/10',
        )}
      >
        Stock available: <span className="numeric">{formatNumber(row.stock_available)}</span>
        {!row.is_coverable && (
          <> — short by <span className="numeric">{formatNumber(row.shortfall)}</span> units.</>
        )}
      </div>
    </Modal>
  )
}
