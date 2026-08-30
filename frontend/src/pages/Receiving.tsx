import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CheckCircle2, PackagePlus, PackageSearch, Truck } from 'lucide-react'

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
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import { catalogApi, receivingApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { receptionStatusSeverity } from '@/utils/status'
import type { TolerancePreview } from '@/types/domain'

/**
 * Receiving.
 *
 * Books a delivered lot in and checks the quantity against the configured
 * tolerance. The tolerance rule is resolved by the backend and previewed live,
 * so the operator sees the accepted window before confirming. No stock is
 * created here.
 */
export default function Receiving() {
  const { ts } = useI18n()
  const receptions = useApiResource(() => receivingApi.list(), [])
  const parts = useApiResource(() => catalogApi.parts(), [])
  const suppliers = useApiResource(() => catalogApi.suppliers(), [])

  const [open, setOpen] = useState(false)
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Receiving"
        description="Register supplier deliveries and check received quantities."
        actions={
          <Button
            variant="primary"
            icon={<PackagePlus className="h-3.5 w-3.5" />}
            onClick={() => setOpen(true)}
          >
            New reception
          </Button>
        }
      />

      <Panel
        title="Receptions"
        subtitle={`${receptions.data?.length ?? 0} deliveries recorded`}
        bodyClassName=""
        action={<Truck className="h-3.5 w-3.5 text-ink-3" />}
      >
        {receptions.initialLoading ? (
          <LoadingPanel rows={5} />
        ) : receptions.error ? (
          <ErrorPanel message={receptions.error} onRetry={receptions.refresh} />
        ) : (receptions.data?.length ?? 0) === 0 ? (
          <EmptyState
            icon={<PackageSearch className="h-5 w-5" />}
            title="No reception yet"
            description="Register the first delivery to start the flow."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[900px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line">
                  <th className="eyebrow px-5 py-2.5 font-semibold">Reference</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Lot</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Part</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Supplier</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Expected</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Received</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Gap</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Check</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Date</th>
                </tr>
              </thead>
              <tbody>
                {receptions.data?.map((reception) => (
                  <tr
                    key={reception.id}
                    onClick={() => setSelectedLotId(reception.lot.id)}
                    className="cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-elevated/50"
                  >
                    <td className="numeric px-5 py-3 text-xs text-ink-2">
                      {reception.reference}
                    </td>
                    <td className="numeric px-5 py-3 text-xs font-medium text-ink">
                      {reception.lot.lot_number}
                    </td>
                    <td className="px-5 py-3">
                      <span className="numeric text-xs text-ink-2">
                        {reception.lot.part.reference}
                      </span>
                      <span className="block truncate text-2xs text-ink-3">
                        {reception.lot.part.designation}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-xs text-ink-2">{reception.lot.supplier.name}</td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                      {formatNumber(reception.quantity_expected)}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink">
                      {formatNumber(reception.quantity_received)}
                    </td>
                    <td
                      className={cn(
                        'numeric px-5 py-3 text-right text-xs',
                        reception.quantity_gap === 0
                          ? 'text-ink-3'
                          : reception.status === 'QUANTITY_MISMATCH'
                            ? 'text-crit-soft'
                            : 'text-warn-soft',
                      )}
                    >
                      {reception.quantity_gap > 0 ? '+' : ''}
                      {reception.quantity_gap}
                    </td>
                    <td className="px-5 py-3">
                      <Badge severity={receptionStatusSeverity[reception.status]}>
                        {ts(reception.status)}
                      </Badge>
                    </td>
                    <td className="numeric px-5 py-3 text-right text-2xs text-ink-3">
                      {formatTimestamp(reception.received_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <ReceptionForm
        open={open}
        onClose={() => setOpen(false)}
        parts={parts.data ?? []}
        suppliers={suppliers.data ?? []}
        onCreated={() => {
          setOpen(false)
          void receptions.refresh()
        }}
      />

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}

interface ReceptionFormProps {
  open: boolean
  onClose: () => void
  parts: { id: number; reference: string; designation: string; size_class: string }[]
  suppliers: { id: number; name: string; code: string }[]
  onCreated: () => void
}

function ReceptionForm({ open, onClose, parts, suppliers, onCreated }: ReceptionFormProps) {
  const { ts } = useI18n()
  const { actorId, byRole } = useActor()
  const toast = useToast()

  const [partId, setPartId] = useState('')
  const [supplierId, setSupplierId] = useState('')
  const [expected, setExpected] = useState('')
  const [received, setReceived] = useState('')
  const [deliveryNote, setDeliveryNote] = useState('')
  const [notes, setNotes] = useState('')
  const [preview, setPreview] = useState<TolerancePreview | null>(null)
  const [saving, setSaving] = useState(false)

  const receptionist = byRole('RECEPTIONIST')

  // The tolerance is resolved server-side: the UI never recomputes the rule.
  useEffect(() => {
    const quantity = Number(expected)
    if (!partId || !quantity || quantity <= 0) {
      setPreview(null)
      return
    }
    let cancelled = false
    receivingApi
      .tolerancePreview(Number(partId), quantity)
      .then((payload) => {
        if (!cancelled) setPreview(payload)
      })
      .catch(() => {
        if (!cancelled) setPreview(null)
      })
    return () => {
      cancelled = true
    }
  }, [partId, expected])

  const verdict = useMemo(() => {
    if (!preview || !received) return null
    const value = Number(received)
    if (Number.isNaN(value)) return null
    if (value === preview.quantity_expected) {
      return { severity: 'ok' as const, label: 'Exact quantity — will be accepted' }
    }
    if (value >= preview.minimum_accepted && value <= preview.maximum_accepted) {
      return {
        severity: 'warn' as const,
        label: `Within the ${preview.tolerance_percent}% tolerance — accepted with a gap`,
      }
    }
    return {
      severity: 'crit' as const,
      label: 'Outside tolerance — the lot will be sent to the Red Cage',
    }
  }, [preview, received])

  function reset() {
    setPartId('')
    setSupplierId('')
    setExpected('')
    setReceived('')
    setDeliveryNote('')
    setNotes('')
    setPreview(null)
  }

  async function submit() {
    if (!partId || !supplierId || !expected || !received) {
      toast.error('Incomplete form', 'Part, supplier and both quantities are required.')
      return
    }
    setSaving(true)
    try {
      const reception = await receivingApi.create({
        part_id: Number(partId),
        supplier_id: Number(supplierId),
        quantity_expected: Number(expected),
        quantity_received: Number(received),
        delivery_note: deliveryNote || null,
        notes: notes || null,
        actor_id: receptionist?.id ?? actorId,
      })
      toast.success(
        `Lot ${reception.lot.lot_number} received`,
        `Quantity check: ${ts(reception.status)}. Stock unchanged — a reception never creates stock.`,
      )
      reset()
      onCreated()
    } catch (error) {
      toast.error('Reception refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="New reception"
      subtitle="A reception records what arrived — it never creates stock"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" loading={saving} onClick={() => void submit()}>
            Register the delivery
          </Button>
        </>
      }
    >
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Part reference" required>
          <Select value={partId} onChange={(event) => setPartId(event.target.value)}>
            <option value="">Select a reference…</option>
            {parts.map((part) => (
              <option key={part.id} value={part.id}>
                {part.reference} — {part.designation} ({part.size_class})
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Supplier" required>
          <Select value={supplierId} onChange={(event) => setSupplierId(event.target.value)}>
            <option value="">Select a supplier…</option>
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>
                {supplier.name}
              </option>
            ))}
          </Select>
        </Field>

        <Field label="Expected quantity" required>
          <Input
            type="number"
            min={1}
            value={expected}
            onChange={(event) => setExpected(event.target.value)}
            placeholder="500"
          />
        </Field>

        <Field label="Received quantity" required>
          <Input
            type="number"
            min={0}
            value={received}
            onChange={(event) => setReceived(event.target.value)}
            placeholder="500"
          />
        </Field>

        <Field label="Delivery note" className="sm:col-span-2">
          <Input
            value={deliveryNote}
            onChange={(event) => setDeliveryNote(event.target.value)}
            placeholder="BL-2026-0042"
          />
        </Field>

        <Field label="Notes" className="sm:col-span-2">
          <Textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            placeholder="Observations on the delivery…"
          />
        </Field>
      </div>

      {/* Live tolerance rule, resolved by the backend */}
      {preview && (
        <div className="mt-5 rounded-lg border border-line bg-elevated/60 p-4">
          <p className="eyebrow">Applicable tolerance rule</p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Class" value={preview.size_class} />
            <Metric label="Tolerance" value={`${preview.tolerance_percent}%`} />
            <Metric label="Minimum" value={formatNumber(preview.minimum_accepted)} />
            <Metric label="Maximum" value={formatNumber(preview.maximum_accepted)} />
          </div>
          <p className="mt-2 text-2xs text-ink-3">Source: {preview.tolerance_source}</p>

          {verdict && (
            <div
              className={cn(
                'mt-3 flex items-start gap-2 rounded-md border px-3 py-2',
                verdict.severity === 'ok'
                  ? 'border-ok/35 bg-ok/10'
                  : verdict.severity === 'warn'
                    ? 'border-warn/35 bg-warn/10'
                    : 'border-crit/35 bg-crit/10',
              )}
            >
              {verdict.severity === 'ok' ? (
                <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-ok-soft" />
              ) : (
                <AlertTriangle
                  className={cn(
                    'mt-0.5 h-3.5 w-3.5 shrink-0',
                    verdict.severity === 'warn' ? 'text-warn-soft' : 'text-crit-soft',
                  )}
                />
              )}
              <p className="text-xs leading-relaxed text-ink-2">{verdict.label}</p>
            </div>
          )}
        </div>
      )}
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
