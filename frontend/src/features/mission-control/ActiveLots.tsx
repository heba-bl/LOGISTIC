import { motion } from 'framer-motion'
import { ArrowRight } from 'lucide-react'

import { Badge, EmptyState } from '@/components/ui'
import { useI18n } from '@/i18n/I18nProvider'
import { formatNumber } from '@/utils/format'
import { lotStatusSeverity } from '@/utils/status'
import type { Lot } from '@/types/domain'

interface ActiveLotsProps {
  lots: Lot[]
  onSelectLot?: (lot: Lot) => void
}

/** Register of the lots currently moving through the flow. */
export function ActiveLots({ lots, onSelectLot }: ActiveLotsProps) {
  const { t, ts } = useI18n()
  if (lots.length === 0) {
    return (
      <EmptyState title={t('mission.noLots')} description={t('mission.noLotsHint')} />
    )
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[680px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line">
            <th className="eyebrow px-5 py-2.5 font-semibold">{t('table.lot')}</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">{t('table.part')}</th>
            <th className="eyebrow px-5 py-2.5 text-right font-semibold">
              {t('common.quantity')}
            </th>
            <th className="eyebrow px-5 py-2.5 font-semibold">{t('common.status')}</th>
            <th className="eyebrow px-5 py-2.5 font-semibold">{t('table.location')}</th>
          </tr>
        </thead>
        <tbody>
          {lots.map((lot, index) => (
            <motion.tr
              key={lot.id}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.3, delay: Math.min(index, 8) * 0.04 }}
              onClick={() => onSelectLot?.(lot)}
              className="group cursor-pointer border-b border-line/60 transition-colors last:border-0 hover:bg-elevated/50"
            >
              <td className="numeric px-5 py-3 text-xs font-medium text-ink">
                {lot.lot_number}
              </td>
              <td className="px-5 py-3">
                <span className="numeric text-xs text-ink-2">{lot.part.reference}</span>
                <span className="block text-2xs text-ink-3">{lot.supplier.name}</span>
              </td>
              <td className="numeric px-5 py-3 text-right text-xs text-ink">
                {formatNumber(
                  lot.status === 'STORED' ? lot.quantity_available : lot.quantity_received,
                )}
                <span className="ml-1 text-2xs text-ink-3">{lot.part.unit}</span>
              </td>
              <td className="px-5 py-3">
                <Badge severity={lotStatusSeverity[lot.status]}>
                  {ts(lot.status)}
                </Badge>
              </td>
              <td className="px-5 py-3">
                <span className="inline-flex items-center gap-1.5 text-xs text-ink-2">
                  <span className="numeric">{lot.location?.code ?? '—'}</span>
                  <ArrowRight className="h-3 w-3 text-ink-3 opacity-0 transition-opacity group-hover:opacity-100" />
                </span>
              </td>
            </motion.tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
