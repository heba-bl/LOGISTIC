/**
 * What a click on the dashboard answers.
 *
 * Selecting a reference, a zone or a quality state replaces guesswork with a
 * short factual strip: the figures for that one thing, and the way out towards
 * the screen that can act on it. Numbers only - the reader came here to decide,
 * not to read.
 */

import { motion } from 'framer-motion'
import { ArrowRight, X } from 'lucide-react'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { RiskChip, useUnitLabel } from './primitives'
import type { MessageKey } from '@/i18n/messages'
import type { Severity4 } from '@/types/overview'

export interface DetailFigure {
  labelKey: MessageKey
  value: string
  /** Set when the figure itself is the alarming part. */
  tone?: 'ok' | 'warn' | 'crit'
}

interface SelectionDetailProps {
  title: string
  subtitle?: string
  risk?: Severity4
  figures: DetailFigure[]
  actionLabel: string
  onAction: () => void
  onClear: () => void
}

const TONE: Record<'ok' | 'warn' | 'crit', string> = {
  ok: 'text-ok-soft',
  warn: 'text-warn-soft',
  crit: 'text-crit-soft',
}

export function SelectionDetail({
  title,
  subtitle,
  risk,
  figures,
  actionLabel,
  onAction,
  onClear,
}: SelectionDetailProps) {
  const { t } = useI18n()

  return (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
      className="overflow-hidden"
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3 rounded-lg border border-accent/30 bg-accent/[0.06] px-4 py-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="numeric text-sm font-semibold text-ink">{title}</span>
          {subtitle && <span className="truncate text-2xs text-ink-3">{subtitle}</span>}
          {risk && <RiskChip risk={risk} />}
        </div>

        <dl className="flex flex-wrap items-baseline gap-x-5 gap-y-2">
          {figures.map((figure) => (
            <div key={figure.labelKey} className="flex items-baseline gap-1.5">
              <dt className="text-2xs text-ink-3">{t(figure.labelKey)}</dt>
              <dd
                className={cn(
                  'numeric text-sm font-semibold',
                  figure.tone ? TONE[figure.tone] : 'text-ink',
                )}
              >
                {figure.value}
              </dd>
            </div>
          ))}
        </dl>

        <div className="ml-auto flex items-center gap-1.5">
          <button
            type="button"
            onClick={onAction}
            className="inline-flex items-center gap-1.5 rounded-lg bg-accent px-3 py-1.5 text-2xs font-semibold text-white transition-colors hover:bg-accent-soft"
          >
            {actionLabel}
            <ArrowRight className="h-3 w-3" />
          </button>
          <button
            type="button"
            onClick={onClear}
            aria-label={t('filter.clear')}
            title={t('filter.clear')}
            className="grid h-7 w-7 place-items-center rounded-lg border border-line text-ink-3 transition-colors hover:border-line-strong hover:text-ink"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </motion.div>
  )
}

/** One figure, formatted with its unit token resolved. */
export function useFigure() {
  const unitLabel = useUnitLabel()
  return (value: string | number, unit?: string) =>
    unit ? `${value} ${unitLabel(unit)}` : String(value)
}
