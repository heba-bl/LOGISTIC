import { AnimatePresence, motion } from 'framer-motion'
import { X } from 'lucide-react'

import { Badge, ErrorPanel, LoadingPanel, StatusDot } from '@/components/ui'
import { useApiResource } from '@/hooks'
import { useI18n } from '@/i18n/I18nProvider'
import { traceabilityApi } from '@/services/slcc.service'
import { blockingReason } from '@/utils/blocking'
import { cn } from '@/utils/cn'
import { formatNumber, formatTimestamp } from '@/utils/format'
import { lotStatusSeverity, severityStyles, toSeverity } from '@/utils/status'

interface LotDetailDrawerProps {
  lotId: number | null
  onClose: () => void
}

/**
 * Full history of a lot: reference, quantity, status, location, destination and
 * every audited event. Opened from any lot chip in the application.
 */
export function LotDetailDrawer({ lotId, onClose }: LotDetailDrawerProps) {
  const { t } = useI18n()
  const { ts } = useI18n()
  const trace = useApiResource(
    () => traceabilityApi.lot(lotId as number),
    [lotId],
    { enabled: lotId !== null },
  )

  return (
    <AnimatePresence>
      {lotId !== null && (
        <div className="fixed inset-0 z-40 flex justify-end">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={onClose}
            className="absolute inset-0 bg-canvas/75 backdrop-blur-sm"
          />

          <motion.aside
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
            className="relative z-10 flex h-full w-full max-w-lg flex-col border-l border-line bg-panel shadow-panel"
            role="dialog"
            aria-label={t('lot.detail')}
          >
            <header className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
              <div className="min-w-0">
                <p className="eyebrow">{t('lot.traceability')}</p>
                <h2 className="numeric mt-1 text-lg font-semibold text-ink">
                  {trace.data?.lot.lot_number ?? '…'}
                </h2>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded p-1 text-ink-3 transition-colors hover:bg-elevated hover:text-ink"
                aria-label={t('common.close')}
              >
                <X className="h-4 w-4" />
              </button>
            </header>

            <div className="flex-1 overflow-y-auto">
              {trace.initialLoading ? (
                <LoadingPanel rows={5} />
              ) : trace.error ? (
                <ErrorPanel message={trace.error} onRetry={trace.refresh} />
              ) : trace.data ? (
                <div className="space-y-5 p-5">
                  {/* Identity */}
                  <section className="grid grid-cols-2 gap-3">
                    <Detail label={t('wh.part')} value={trace.data.lot.part.reference} mono />
                    <Detail label={t('lot.designation')} value={trace.data.lot.part.designation} />
                    <Detail label={t('recv.field.supplier')} value={trace.data.lot.supplier.name} />
                    <Detail
                      label={t('lot.location')}
                      value={trace.data.lot.location?.code ?? 'Not stored'}
                      mono
                    />
                    <Detail
                      label={t('recv.col.received')}
                      value={`${formatNumber(trace.data.lot.quantity_received)} ${trace.data.lot.part.unit}`}
                      mono
                    />
                    <Detail
                      label={t('wh.col.available')}
                      value={`${formatNumber(trace.data.lot.quantity_available)} ${trace.data.lot.part.unit}`}
                      mono
                    />
                    <div>
                      <p className="eyebrow">{t('common.status')}</p>
                      <div className="mt-1.5">
                        <Badge severity={lotStatusSeverity[trace.data.lot.status]}>
                          {ts(trace.data.lot.status)}
                        </Badge>
                      </div>
                    </div>
                    <Detail
                      label={t('lot.movements')}
                      value={`+${trace.data.total_in} / -${trace.data.total_out}`}
                      mono
                    />
                  </section>

                  {trace.data.lot.blocked_reason && (
                    <div className="rounded-lg border border-crit/35 bg-crit/10 px-3 py-2.5">
                      <p className="text-2xs font-semibold uppercase tracking-wider text-crit-soft">
                        Blocking reason
                      </p>
                      <p className="mt-1 text-xs leading-relaxed text-ink-2">
                        {blockingReason(trace.data.lot, t)}
                      </p>
                    </div>
                  )}

                  {/* Timeline */}
                  <section>
                    <p className="eyebrow mb-3">
                      History — {trace.data.events.length} audited events
                    </p>
                    <ol className="relative">
                      <span
                        className="absolute bottom-3 left-[5px] top-2 w-px bg-line"
                        aria-hidden="true"
                      />
                      {trace.data.events.map((event) => {
                        const styles = severityStyles[toSeverity(event.severity)]
                        return (
                          <li key={event.id} className="relative flex gap-3 pb-4 last:pb-0">
                            <span
                              className={cn(
                                'relative z-10 mt-1 h-2.5 w-2.5 shrink-0 rounded-full ring-4 ring-panel',
                                styles.bar,
                              )}
                            />
                            <div className="min-w-0 flex-1">
                              <div className="flex flex-wrap items-baseline gap-x-2">
                                <p className="text-xs font-medium text-ink">{event.label}</p>
                                <span className="numeric text-2xs text-ink-3">
                                  {formatTimestamp(event.occurred_at)}
                                </span>
                              </div>
                              <p className="mt-0.5 text-2xs leading-relaxed text-ink-3">
                                {event.detail}
                              </p>
                              <p className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-ink-3/80">
                                <span className="inline-flex items-center gap-1">
                                  <StatusDot severity={toSeverity(event.severity)} />
                                  {event.actor_reference
                                    ? `${event.actor_reference} · ${event.actor_name}`
                                    : event.actor_name}
                                </span>
                                {event.checker_reference && (
                                  <span className="text-ok-soft">
                                    checked by {event.checker_reference}
                                    {event.decision ? ` (${event.decision})` : ''}
                                  </span>
                                )}
                                {event.status_before && event.status_after && (
                                  <span className="numeric">
                                    {event.status_before} → {event.status_after}
                                  </span>
                                )}
                                {event.location_code && (
                                  <span className="numeric">{event.location_code}</span>
                                )}
                              </p>
                            </div>
                          </li>
                        )
                      })}
                    </ol>
                  </section>
                </div>
              ) : null}
            </div>
          </motion.aside>
        </div>
      )}
    </AnimatePresence>
  )
}

function Detail({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0">
      <p className="eyebrow">{label}</p>
      <p className={cn('mt-1 truncate text-xs text-ink', mono && 'numeric')}>{value}</p>
    </div>
  )
}
