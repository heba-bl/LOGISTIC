import { useState } from 'react'
import { Ban, CheckCircle2, ShieldAlert, ShieldCheck, Trash2 } from 'lucide-react'

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
  Textarea,
} from '@/components/ui'
import { LotDetailDrawer } from '@/features/traceability/LotDetailDrawer'
import { useActor, useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { toErrorMessage } from '@/services/apiClient'
import { qualityApi } from '@/services/slcc.service'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { lotStatusSeverity } from '@/utils/status'
import type { Lot } from '@/types/domain'

type Decision = 'approve' | 'reject' | 'scrap'

const DECISION_META: Record<Decision, { title: string; verb: string; variant: 'success' | 'danger' }> =
  {
    approve: { title: 'Approve the lot', verb: 'Approve', variant: 'success' },
    reject: { title: 'Reject the lot', verb: 'Reject', variant: 'danger' },
    scrap: { title: 'Scrap the lot', verb: 'Scrap', variant: 'danger' },
  }

/**
 * Quality and Red Cage.
 *
 * The Red Cage is the quarantine where a lot waits for a decision, whether it
 * failed inspection or arrived outside the quantity tolerance. Approving a lot
 * unlocks storage — it does not create stock.
 */
export default function Quality() {
  const { ts } = useI18n()
  const pending = useApiResource(() => qualityApi.pending(), [])
  const redCage = useApiResource(() => qualityApi.redCage(), [])
  const history = useApiResource(() => qualityApi.history(40), [])

  const [decision, setDecision] = useState<{ lot: Lot; kind: Decision } | null>(null)
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  function refreshAll() {
    void pending.refresh()
    void redCage.refresh()
    void history.refresh()
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Quality"
        description="Validation gate before storage, and Red Cage quarantine management."
      />

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Awaiting decision */}
        <Panel
          title="Awaiting quality decision"
          subtitle={`${pending.data?.length ?? 0} inspected lots`}
          bodyClassName=""
          action={<ShieldCheck className="h-3.5 w-3.5 text-ink-3" />}
        >
          {pending.initialLoading ? (
            <LoadingPanel rows={3} />
          ) : pending.error ? (
            <ErrorPanel message={pending.error} onRetry={pending.refresh} />
          ) : (pending.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
              title="No pending decision"
              description="Every inspected lot has been decided."
            />
          ) : (
            <ul className="divide-y divide-line">
              {pending.data?.map((lot) => (
                <li key={lot.id} className="px-5 py-3.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedLotId(lot.id)}
                      className="numeric text-xs font-medium text-ink hover:text-accent"
                    >
                      {lot.lot_number}
                    </button>
                    <Badge severity={lotStatusSeverity[lot.status]}>
                      {ts(lot.status)}
                    </Badge>
                    <span className="numeric ml-auto text-2xs text-ink-3">
                      {formatNumber(lot.quantity_received)} {lot.part.unit}
                    </span>
                  </div>
                  <p className="mt-1 text-2xs text-ink-3">
                    {lot.part.reference} · {lot.supplier.name}
                  </p>
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="success"
                      icon={<CheckCircle2 className="h-3 w-3" />}
                      onClick={() => setDecision({ lot, kind: 'approve' })}
                    >
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon={<Ban className="h-3 w-3" />}
                      onClick={() => setDecision({ lot, kind: 'reject' })}
                    >
                      Reject
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        {/* Red Cage */}
        <Panel
          title="Red Cage"
          subtitle={`${redCage.data?.length ?? 0} quarantined lots`}
          bodyClassName=""
          action={<ShieldAlert className="h-3.5 w-3.5 text-crit" />}
        >
          {redCage.initialLoading ? (
            <LoadingPanel rows={3} />
          ) : (redCage.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={<CheckCircle2 className="h-5 w-5 text-ok" />}
              title="Red Cage empty"
              description="No lot is blocked."
            />
          ) : (
            <ul className="divide-y divide-line">
              {redCage.data?.map((lot) => (
                <li key={lot.id} className="px-5 py-3.5">
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedLotId(lot.id)}
                      className="numeric text-xs font-medium text-ink hover:text-accent"
                    >
                      {lot.lot_number}
                    </button>
                    <Badge severity="crit">Red Cage</Badge>
                    <span className="numeric ml-auto text-2xs text-ink-3">
                      {formatNumber(lot.quantity_received)} {lot.part.unit}
                    </span>
                  </div>
                  <p className="mt-1 text-2xs text-ink-3">
                    {lot.part.reference} · {lot.supplier.name}
                  </p>
                  {lot.blocked_reason && (
                    <p className="mt-2 rounded border border-crit/25 bg-crit/5 px-2.5 py-1.5 text-2xs leading-relaxed text-ink-2">
                      {lot.blocked_reason}
                    </p>
                  )}
                  <div className="mt-2.5 flex flex-wrap gap-2">
                    <Button
                      size="sm"
                      variant="success"
                      icon={<CheckCircle2 className="h-3 w-3" />}
                      onClick={() => setDecision({ lot, kind: 'approve' })}
                    >
                      Release (derogation)
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon={<Trash2 className="h-3 w-3" />}
                      onClick={() => setDecision({ lot, kind: 'scrap' })}
                    >
                      Scrap
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      <Panel
        title="Decision history"
        subtitle="Every decision carries its justification"
        bodyClassName=""
      >
        {history.initialLoading ? (
          <LoadingPanel rows={4} />
        ) : (history.data?.length ?? 0) === 0 ? (
          <EmptyState title="No decision recorded" />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] border-collapse text-left">
              <thead>
                <tr className="border-b border-line">
                  <th className="eyebrow px-5 py-2.5 font-semibold">Lot</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Decision</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Approved</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">Justification</th>
                  <th className="eyebrow px-5 py-2.5 font-semibold">By</th>
                  <th className="eyebrow px-5 py-2.5 text-right font-semibold">Date</th>
                </tr>
              </thead>
              <tbody>
                {history.data?.map((validation) => (
                  <tr key={validation.id} className="border-b border-line/60 last:border-0">
                    <td
                      className="numeric cursor-pointer px-5 py-3 text-xs text-ink hover:text-accent"
                      onClick={() => setSelectedLotId(validation.lot_id)}
                    >
                      #{validation.lot_id}
                    </td>
                    <td className="px-5 py-3">
                      <Badge
                        severity={
                          validation.decision === 'APPROVED'
                            ? 'ok'
                            : validation.decision === 'RED_CAGE'
                              ? 'warn'
                              : 'crit'
                        }
                      >
                        {ts(validation.decision)}
                      </Badge>
                    </td>
                    <td className="numeric px-5 py-3 text-right text-xs text-ink-2">
                      {formatNumber(validation.quantity_approved)}
                    </td>
                    <td className="max-w-xs px-5 py-3 text-2xs text-ink-3">
                      {validation.justification}
                    </td>
                    <td className="px-5 py-3 text-2xs text-ink-2">
                      {validation.decided_by?.full_name ?? 'system'}
                    </td>
                    <td className="numeric px-5 py-3 text-right text-2xs text-ink-3">
                      {formatTimestamp(validation.decided_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {decision && (
        <DecisionDialog
          lot={decision.lot}
          kind={decision.kind}
          onClose={() => setDecision(null)}
          onDone={() => {
            setDecision(null)
            refreshAll()
          }}
        />
      )}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}

function DecisionDialog({
  lot,
  kind,
  onClose,
  onDone,
}: {
  lot: Lot
  kind: Decision
  onClose: () => void
  onDone: () => void
}) {
  const { byRole, actorId } = useActor()
  const toast = useToast()
  const manager = byRole('QUALITY_MANAGER')

  const [justification, setJustification] = useState('')
  const [quantity, setQuantity] = useState(String(lot.quantity_received))
  const [saving, setSaving] = useState(false)

  const meta = DECISION_META[kind]

  async function submit() {
    if (justification.trim().length < 3) {
      toast.error('Justification required', 'A quality decision is never recorded without a reason.')
      return
    }
    setSaving(true)
    const payload = {
      justification,
      actor_id: manager?.id ?? actorId,
      quantity_approved: kind === 'approve' ? Number(quantity) : undefined,
    }
    try {
      if (kind === 'approve') {
        await qualityApi.approve(lot.id, payload)
        toast.success(
          `${lot.lot_number} approved`,
          'Storage is now unlocked. Stock is still unchanged until the warehouse confirms.',
        )
      } else if (kind === 'reject') {
        await qualityApi.reject(lot.id, payload)
        toast.info(`${lot.lot_number} rejected`, 'The lot will never become stock.')
      } else {
        await qualityApi.scrap(lot.id, payload)
        toast.info(`${lot.lot_number} scrapped`, 'Terminal decision recorded in the audit trail.')
      }
      onDone()
    } catch (error) {
      toast.error('Decision refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={meta.title}
      subtitle={`${lot.lot_number} · ${lot.part.reference} · ${formatNumber(lot.quantity_received)} units`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant={meta.variant} loading={saving} onClick={() => void submit()}>
            {meta.verb}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        {kind === 'approve' && (
          <Field
            label="Approved quantity"
            required
            hint="May be lower than the received quantity in case of a partial derogation"
          >
            <Input
              type="number"
              min={1}
              max={lot.quantity_received}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
            />
          </Field>
        )}

        <Field
          label="Justification"
          required
          hint="Recorded in the audit trail and visible in the lot history"
        >
          <Textarea
            value={justification}
            onChange={(event) => setJustification(event.target.value)}
            placeholder="Sample conform, no functional impact…"
            rows={4}
          />
        </Field>

        {lot.blocked_reason && (
          <div className="rounded-lg border border-line bg-elevated/60 px-3 py-2.5">
            <p className="eyebrow">Recorded blocking reason</p>
            <p className="mt-1 text-xs leading-relaxed text-ink-2">{lot.blocked_reason}</p>
          </div>
        )}
      </div>
    </Modal>
  )
}
