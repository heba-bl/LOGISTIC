import { useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { CircleCheck, Play, TruckIcon } from 'lucide-react'

import { Button, Field, Modal, Select } from '@/components/ui'
import { useApiResource, useToast } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { catalogApi, simulationApi } from '@/services/slcc.service'
import { toErrorMessage } from '@/services/apiClient'
import { cn } from '@/utils/cn'
import { formatNumber } from '@/utils/format'
import type { SimulationRun } from '@/types/domain'

const STEP_LABELS: Record<string, string> = {
  reception: 'Reception',
  inspection: 'Inspection',
  quality: 'Quality',
  storage: 'Storage (stock +)',
  request: 'Production request',
  approval: 'Approval',
  preparation: 'Preparation',
  issue: 'Issue (stock -)',
}

interface SimulationPanelProps {
  onCompleted?: () => void
}

/**
 * Demonstration driver.
 *
 * Runs the whole chain - truck to production - through the real services, so the
 * dashboard, stock, traceability and AI all reflect the result immediately.
 */
export function SimulationPanel({ onCompleted }: SimulationPanelProps) {
  const [open, setOpen] = useState(false)
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<SimulationRun | null>(null)
  const [partId, setPartId] = useState<string>('')
  const [stopAfter, setStopAfter] = useState<string>('')
  const [quantity, setQuantity] = useState('120')
  const [productionQuantity, setProductionQuantity] = useState('20')

  const parts = useApiResource(() => catalogApi.parts(), [])
  const toast = useToast()
  const { t } = useI18n()

  async function run() {
    setRunning(true)
    try {
      const payload = await simulationApi.run({
        part_id: partId ? Number(partId) : null,
        quantity: Number(quantity) || 120,
        production_quantity: Number(productionQuantity) || 20,
        stop_after: stopAfter || null,
      })
      setResult(payload)
      toast.success('Simulation executed', payload.message)
      onCompleted?.()
    } catch (error) {
      toast.error('Simulation failed', toErrorMessage(error))
    } finally {
      setRunning(false)
    }
  }

  return (
    <>
      <Button variant="primary" icon={<Play className="h-3.5 w-3.5" />} onClick={() => setOpen(true)}>
        {t('mission.runSimulation')}
      </Button>

      <Modal
        open={open}
        onClose={() => setOpen(false)}
        title="End-to-end simulation"
        subtitle="Truck arrival to production issue, through the real workflow"
        width="lg"
        footer={
          <>
            <Button variant="ghost" onClick={() => setOpen(false)}>
              Close
            </Button>
            <Button
              variant="primary"
              loading={running}
              icon={<TruckIcon className="h-3.5 w-3.5" />}
              onClick={() => void run()}
            >
              Run the scenario
            </Button>
          </>
        }
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Part reference" hint="Leave empty to use the first active reference">
            <Select value={partId} onChange={(event) => setPartId(event.target.value)}>
              <option value="">Automatic</option>
              {(parts.data ?? []).map((part) => (
                <option key={part.id} value={part.id}>
                  {part.reference} — {part.designation}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Stop after" hint="Run step by step to narrate the demonstration">
            <Select value={stopAfter} onChange={(event) => setStopAfter(event.target.value)}>
              <option value="">Run the full chain</option>
              {Object.entries(STEP_LABELS).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </Select>
          </Field>

          <Field label="Quantity delivered">
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(event) => setQuantity(event.target.value)}
              className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink focus:border-accent/60 focus:outline-none"
            />
          </Field>

          <Field label="Quantity requested by production">
            <input
              type="number"
              min={1}
              value={productionQuantity}
              onChange={(event) => setProductionQuantity(event.target.value)}
              className="w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink focus:border-accent/60 focus:outline-none"
            />
          </Field>
        </div>

        <AnimatePresence>
          {result && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5"
            >
              <div className="mb-3 flex flex-wrap items-center gap-3 rounded-lg border border-line bg-elevated px-3 py-2.5">
                <span className="numeric text-xs font-semibold text-ink">
                  {result.lot_number}
                </span>
                <span className="text-2xs text-ink-3">{result.part_reference}</span>
                <span className="ml-auto flex items-center gap-2 text-xs">
                  <span className="text-ink-3">Stock</span>
                  <span className="numeric text-ink-2">
                    {formatNumber(result.stock_before)}
                  </span>
                  <span className="text-ink-3">→</span>
                  <span
                    className={cn(
                      'numeric font-semibold',
                      result.stock_after >= result.stock_before ? 'text-ok-soft' : 'text-warn-soft',
                    )}
                  >
                    {formatNumber(result.stock_after)}
                  </span>
                </span>
              </div>

              <ol className="space-y-2">
                {result.steps.map((step, index) => (
                  <motion.li
                    key={step.order}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.07 }}
                    className="flex gap-3 rounded-lg border border-line bg-panel/60 px-3 py-2.5"
                  >
                    <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-ok/40 bg-ok/10">
                      <CircleCheck className="h-3 w-3 text-ok-soft" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-medium text-ink">
                        <span className="numeric mr-2 text-ink-3">
                          {String(step.order).padStart(2, '0')}
                        </span>
                        {step.title}
                      </p>
                      <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">{step.detail}</p>
                    </div>
                  </motion.li>
                ))}
              </ol>
            </motion.div>
          )}
        </AnimatePresence>
      </Modal>
    </>
  )
}
