import { useEffect, useState } from 'react'
import { ClipboardCheck, FlaskConical, Play } from 'lucide-react'

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
import { inspectionApi, lotsApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { inspectionResultSeverity, lotStatusSeverity } from '@/utils/status'
import type { Lot, SampleSuggestion } from '@/types/domain'

/**
 * Inspection.
 *
 * Quality does not check every part: the backend computes a sample size from the
 * configured rate and floor, and the defect rate on that sample decides whether
 * the lot moves on or goes to the Red Cage.
 */
export default function Inspection() {
  const { ts } = useI18n()
  const queue = useApiResource(
    () => lotsApi.list({ status: ['PENDING_INSPECTION', 'INSPECTION_IN_PROGRESS'] }),
    [],
  )
  const history = useApiResource(() => inspectionApi.list(50), [])
  const [target, setTarget] = useState<Lot | null>(null)
  const [selectedLotId, setSelectedLotId] = useState<number | null>(null)

  function refreshAll() {
    void queue.refresh()
    void history.refresh()
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Inspection"
        description="Sampling and defect recording — an inspection never creates stock."
      />

      <div className="grid gap-4 xl:grid-cols-3">
        <Panel
          className="xl:col-span-2"
          title="Lots to inspect"
          subtitle={`${queue.data?.length ?? 0} lots waiting`}
          bodyClassName=""
          action={<ClipboardCheck className="h-3.5 w-3.5 text-ink-3" />}
        >
          {queue.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : queue.error ? (
            <ErrorPanel message={queue.error} onRetry={queue.refresh} />
          ) : (queue.data?.length ?? 0) === 0 ? (
            <EmptyState
              icon={<ClipboardCheck className="h-5 w-5" />}
              title="Nothing to inspect"
              description="Every received lot has been sampled."
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-left">
                <thead>
                  <tr className="border-b border-line">
                    <th className="eyebrow px-5 py-2.5 font-semibold">Lot</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Part</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Quantity</th>
                    <th className="eyebrow px-5 py-2.5 font-semibold">Status</th>
                    <th className="eyebrow px-5 py-2.5 text-right font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {queue.data?.map((lot) => (
                    <tr
                      key={lot.id}
                      className="border-b border-line/60 transition-colors last:border-0 hover:bg-elevated/50"
                    >
                      <td
                        className="numeric cursor-pointer px-5 py-3 text-xs font-medium text-ink"
                        onClick={() => setSelectedLotId(lot.id)}
                      >
                        {lot.lot_number}
                      </td>
                      <td className="px-5 py-3">
                        <span className="numeric text-xs text-ink-2">{lot.part.reference}</span>
                        <span className="block text-2xs text-ink-3">{lot.supplier.name}</span>
                      </td>
                      <td className="numeric px-5 py-3 text-right text-xs text-ink">
                        {formatNumber(lot.quantity_received)}
                      </td>
                      <td className="px-5 py-3">
                        <Badge severity={lotStatusSeverity[lot.status]}>
                          {ts(lot.status)}
                        </Badge>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <Button
                          size="sm"
                          variant="primary"
                          icon={<FlaskConical className="h-3 w-3" />}
                          onClick={() => setTarget(lot)}
                        >
                          Inspect
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>

        <Panel
          title="Inspection history"
          subtitle={`${history.data?.length ?? 0} records`}
          bodyClassName=""
        >
          {history.initialLoading ? (
            <LoadingPanel rows={4} />
          ) : (history.data?.length ?? 0) === 0 ? (
            <EmptyState title="No inspection yet" />
          ) : (
            <ul className="divide-y divide-line">
              {history.data?.map((inspection) => (
                <li key={inspection.id} className="px-5 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="numeric text-xs font-medium text-ink">
                      {inspection.reference}
                    </span>
                    <Badge severity={inspectionResultSeverity[inspection.result]}>
                      {ts(inspection.result)}
                    </Badge>
                  </div>
                  <p className="mt-1 text-2xs text-ink-3">
                    Sample {inspection.sample_size} · {inspection.defects_found} defects ·{' '}
                    <span
                      className={cn(
                        'numeric',
                        inspection.defect_rate_percent > inspection.defect_threshold_percent
                          ? 'text-crit-soft'
                          : 'text-ok-soft',
                      )}
                    >
                      {inspection.defect_rate_percent}%
                    </span>{' '}
                    (threshold {inspection.defect_threshold_percent}%)
                  </p>
                  <p className="mt-0.5 text-[10px] text-ink-3/80">
                    {inspection.inspector?.full_name ?? 'system'} ·{' '}
                    {formatTimestamp(inspection.inspected_at)}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>

      {target && (
        <InspectionForm
          lot={target}
          onClose={() => setTarget(null)}
          onDone={() => {
            setTarget(null)
            refreshAll()
          }}
        />
      )}

      <LotDetailDrawer lotId={selectedLotId} onClose={() => setSelectedLotId(null)} />
    </div>
  )
}

function InspectionForm({
  lot,
  onClose,
  onDone,
}: {
  lot: Lot
  onClose: () => void
  onDone: () => void
}) {
  const { byRole, actorId } = useActor()
  const toast = useToast()
  const inspector = byRole('QUALITY_INSPECTOR')

  const [suggestion, setSuggestion] = useState<SampleSuggestion | null>(null)
  const [sampleSize, setSampleSize] = useState('')
  const [defects, setDefects] = useState('0')
  const [observations, setObservations] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    inspectionApi
      .sampleSuggestion(lot.id)
      .then((payload) => {
        setSuggestion(payload)
        setSampleSize(String(payload.suggested_sample_size))
      })
      .catch(() => setSuggestion(null))
  }, [lot.id])

  const rate =
    Number(sampleSize) > 0 ? (Number(defects) / Number(sampleSize)) * 100 : 0
  const threshold = suggestion?.defect_threshold_percent ?? 0
  const willBeConform = rate <= threshold

  async function submit() {
    setSaving(true)
    try {
      if (lot.status === 'PENDING_INSPECTION') {
        await inspectionApi.start(lot.id, inspector?.id ?? actorId)
      }
      const inspection = await inspectionApi.record(lot.id, {
        sample_size: Number(sampleSize),
        defects_found: Number(defects),
        observations: observations || null,
        actor_id: inspector?.id ?? actorId,
      })
      if (inspection.result === 'CONFORM') {
        toast.success(
          `${lot.lot_number} conform`,
          'The lot moves on to the quality decision. Stock unchanged.',
        )
      } else {
        toast.error(
          `${lot.lot_number} non conform`,
          `Defect rate ${inspection.defect_rate_percent}% above the ${inspection.defect_threshold_percent}% threshold — sent to the Red Cage.`,
        )
      }
      onDone()
    } catch (error) {
      toast.error('Inspection refused', toErrorMessage(error))
    } finally {
      setSaving(false)
    }
  }

  return (
    <Modal
      open
      onClose={onClose}
      title={`Inspect ${lot.lot_number}`}
      subtitle={`${lot.part.reference} · ${formatNumber(lot.quantity_received)} units received`}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            variant="primary"
            loading={saving}
            icon={<Play className="h-3.5 w-3.5" />}
            onClick={() => void submit()}
          >
            Record the result
          </Button>
        </>
      }
    >
      {suggestion && (
        <div className="mb-4 rounded-lg border border-line bg-elevated/60 p-4">
          <p className="eyebrow">Sampling plan</p>
          <div className="mt-2 grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Metric label="Lot" value={formatNumber(suggestion.quantity_received)} />
            <Metric label="Rate" value={`${suggestion.sample_percent}%`} />
            <Metric label="Minimum" value={String(suggestion.minimum_sample)} />
            <Metric
              label="Suggested sample"
              value={String(suggestion.suggested_sample_size)}
            />
          </div>
        </div>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Sample size" required hint="Number of units actually checked">
          <Input
            type="number"
            min={1}
            max={lot.quantity_received}
            value={sampleSize}
            onChange={(event) => setSampleSize(event.target.value)}
          />
        </Field>

        <Field label="Defects found" required>
          <Input
            type="number"
            min={0}
            max={Number(sampleSize) || undefined}
            value={defects}
            onChange={(event) => setDefects(event.target.value)}
          />
        </Field>

        <Field label="Observations" className="sm:col-span-2">
          <Textarea
            value={observations}
            onChange={(event) => setObservations(event.target.value)}
            placeholder="Nature of the defects, affected area…"
          />
        </Field>
      </div>

      {Number(sampleSize) > 0 && (
        <div
          className={cn(
            'mt-4 rounded-lg border px-3 py-2.5',
            willBeConform ? 'border-ok/35 bg-ok/10' : 'border-crit/35 bg-crit/10',
          )}
        >
          <p className="text-xs text-ink-2">
            Defect rate{' '}
            <span className="numeric font-semibold text-ink">{rate.toFixed(2)}%</span> versus a{' '}
            <span className="numeric">{threshold}%</span> threshold —{' '}
            <span
              className={cn('font-semibold', willBeConform ? 'text-ok-soft' : 'text-crit-soft')}
            >
              {willBeConform ? 'the lot will be conform' : 'the lot will go to the Red Cage'}
            </span>
            .
          </p>
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
