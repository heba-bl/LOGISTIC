import { Fragment } from 'react'
import { motion } from 'framer-motion'
import {
  Boxes,
  ClipboardCheck,
  Factory,
  PackageSearch,
  ShieldCheck,
  Truck,
  type LucideIcon,
} from 'lucide-react'

import { StatusDot } from '@/components/ui'
import { cn } from '@/utils/cn'
import { formatNumber } from '@/utils/format'
import { useI18n } from '@/i18n/I18nProvider'
import { lotStatusSeverity, severityStyles, toSeverity } from '@/utils/status'
import type { MessageKey } from '@/i18n/messages'
import type { FlowStage, FlowStageId, Lot } from '@/types/domain'

const STAGE_ICONS: Record<FlowStageId, LucideIcon> = {
  SUPPLIER: Truck,
  RECEIVING: PackageSearch,
  INSPECTION: ClipboardCheck,
  QUALITY: ShieldCheck,
  WAREHOUSE: Boxes,
  PRODUCTION: Factory,
}

interface LogisticsFlowProps {
  stages: FlowStage[]
  onSelectLot?: (lot: Lot) => void
}

/**
 * The wire between two stages, with a light running down it.
 *
 * The direction is set in CSS, not here: the flow stacks vertically on a narrow
 * screen and runs horizontally on a wide one, and a single JS translate cannot
 * serve both. It used to animate `y` in both cases, which on a wide screen sent
 * the light drifting across the wire instead of along it.
 *
 * The stagger is what makes the chain read as one movement rather than five
 * blinking dots.
 */
function Connector({ index }: { index: number }) {
  return (
    <div
      className="relative flex shrink-0 items-center justify-center xl:h-full xl:w-8"
      aria-hidden="true"
    >
      <div className="h-6 w-px bg-line xl:h-px xl:w-full" />
      <span
        className="flow-pulse absolute h-1.5 w-1.5 rounded-full bg-accent shadow-glow"
        style={{ animationDelay: `${index * 0.3}s` }}
      />
    </div>
  )
}

/**
 * The six stages of the supervised flow, driven by live backend counts.
 * Clicking a lot chip opens its full history.
 */
export function LogisticsFlow({ stages, onSelectLot }: LogisticsFlowProps) {
  const { t } = useI18n()
  return (
    <div className="flex flex-col gap-4 xl:flex-row xl:items-stretch">
      {stages.map((stage, index) => {
        const Icon = STAGE_ICONS[stage.id]
        const severity = toSeverity(stage.severity)
        const styles = severityStyles[severity]

        return (
          <Fragment key={stage.id}>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.45, delay: index * 0.08, ease: [0.22, 1, 0.36, 1] }}
              className="group relative flex-1 rounded-lg border border-line bg-elevated/60 p-4 transition-colors duration-200 hover:border-line-strong"
            >
              <span
                className={cn('absolute left-0 top-4 h-8 w-[2px] rounded-r', styles.bar)}
                aria-hidden="true"
              />

              <div className="flex items-center justify-between gap-2">
                <div
                  className={cn(
                    'grid h-8 w-8 place-items-center rounded-md border',
                    styles.border,
                    styles.bg,
                  )}
                >
                  <Icon className={cn('h-4 w-4', styles.text)} strokeWidth={1.9} />
                </div>
                <span className="numeric text-2xs text-ink-3">
                  {String(index + 1).padStart(2, '0')}
                </span>
              </div>

              <p className="mt-3 text-sm font-semibold tracking-tight text-ink">
                {t(`stage.${stage.id}` as MessageKey)}
              </p>
              <p className="mt-0.5 min-h-[2rem] text-2xs leading-snug text-ink-3">
                {t(`stage.caption.${stage.id}` as MessageKey)}
              </p>

              <div className="mt-3 flex items-baseline gap-1.5 border-t border-line pt-3">
                <span className="numeric text-lg font-semibold leading-none text-ink">
                  {formatNumber(stage.quantity)}
                </span>
                <span className="text-2xs text-ink-3">PCS</span>
                <span className="ml-auto flex items-center gap-1.5 whitespace-nowrap text-2xs text-ink-2">
                  <StatusDot severity={severity} pulse={severity === 'crit'} />
                  {stage.lot_count} {stage.lot_count === 1 ? 'lot' : 'lots'}
                </span>
              </div>

              {stage.lots.length > 0 && (
                <div className="mt-3 space-y-1">
                  {stage.lots.map((lot) => (
                    <button
                      key={lot.id}
                      type="button"
                      onClick={() => onSelectLot?.(lot)}
                      title={`${lot.lot_number} · ${lot.part.reference}`}
                      className="flex min-h-[34px] w-full cursor-pointer items-center gap-1.5 rounded-lg border border-line bg-panel/70 px-2.5 text-left transition-all duration-[var(--t-fast)] hover:-translate-y-px hover:border-accent/40 hover:bg-panel hover:shadow-panel"
                    >
                      <StatusDot severity={lotStatusSeverity[lot.status]} />
                      <span className="numeric truncate text-[11px] text-ink-2">
                        {lot.lot_number}
                      </span>
                      <span className="numeric ml-auto text-[11px] text-ink-3">
                        {lot.status === 'STORED' ? lot.quantity_available : lot.quantity_received}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </motion.div>

            {index < stages.length - 1 && <Connector index={index} />}
          </Fragment>
        )
      })}
    </div>
  )
}
