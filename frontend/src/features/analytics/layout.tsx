/**
 * Spatial forms: what is where.
 *
 *   AnalyticsMatrix  a reference against the zones that hold it
 *   WarehouseMap     the racks drawn as a plan, not as a list
 *
 * Both exist because a bar chart flattens a dimension these questions need. A
 * reference held entirely in one saturated zone and the same quantity spread
 * over three are different problems, and no single bar can tell them apart.
 */

import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { ChartEmpty, RAMP_BG, RAMP_TEXT, RiskChip, STATE_BG, rampStep } from './primitives'
import type { Severity4 } from '@/types/overview'

// ------------------------------------------------------------------- matrix
export interface MatrixRow {
  reference: string
  designation: string
  total: number
  risk: Severity4
  cells: { zone: string; quantity: number }[]
}

interface MatrixProps {
  zones: string[]
  rows: MatrixRow[]
  emptyMessage: string
  zoneLabel: string
  onSelectCell?: (row: MatrixRow, zone: string, quantity: number) => void
  selected?: { reference: string; zone: string } | null
}

export function AnalyticsMatrix({
  zones,
  rows,
  emptyMessage,
  zoneLabel,
  onSelectCell,
  selected,
}: MatrixProps) {
  const { t, formatNumber } = useI18n()

  if (rows.length === 0 || zones.length === 0) return <ChartEmpty message={emptyMessage} />

  //: Shading is per row: the question is how one reference is spread, not how
  //: two references compare in absolute terms.
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] border-separate border-spacing-y-1">
        <thead>
          <tr>
            <th className="eyebrow px-2 pb-1 text-left font-semibold">
              {t('common.reference')}
            </th>
            {zones.map((zone) => (
              <th key={zone} className="eyebrow px-1 pb-1 text-center font-semibold">
                {zoneLabel} {zone}
              </th>
            ))}
            <th className="eyebrow px-2 pb-1 text-right font-semibold">{t('matrix.total')}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const peak = Math.max(...row.cells.map((cell) => cell.quantity), 1)
            return (
              <motion.tr
                key={row.reference}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3, delay: index * 0.03 }}
              >
                <td className="px-2 py-1 align-middle">
                  <div className="flex items-center gap-2">
                    <span className="numeric text-xs font-semibold text-ink">
                      {row.reference}
                    </span>
                    <RiskChip risk={row.risk} />
                  </div>
                  <span className="block truncate text-[11px] text-ink-3">
                    {row.designation}
                  </span>
                </td>

                {row.cells.map((cell) => {
                  const empty = cell.quantity === 0
                  const step = rampStep((cell.quantity / peak) * 100)
                  const active =
                    selected?.reference === row.reference && selected?.zone === cell.zone
                  const Element = onSelectCell && !empty ? 'button' : 'div'
                  return (
                    <td key={cell.zone} className="px-1 py-1">
                      <Element
                        type={onSelectCell && !empty ? 'button' : undefined}
                        onClick={
                          onSelectCell && !empty
                            ? () => onSelectCell(row, cell.zone, cell.quantity)
                            : undefined
                        }
                        title={`${row.reference} · ${zoneLabel} ${cell.zone} · ${formatNumber(
                          cell.quantity,
                        )}`}
                        className={cn(
                          'grid h-9 w-full place-items-center rounded-lg transition-all',
                          empty ? 'bg-line/30' : RAMP_BG[step],
                          active && 'ring-2 ring-accent ring-offset-1 ring-offset-panel',
                          onSelectCell && !empty && 'cursor-pointer hover:brightness-110',
                        )}
                      >
                        <span
                          className={cn(
                            'numeric text-[11px] font-semibold',
                            empty ? 'text-ink-3/50' : RAMP_TEXT[step],
                          )}
                        >
                          {empty ? '—' : formatNumber(cell.quantity)}
                        </span>
                      </Element>
                    </td>
                  )
                })}

                <td className="numeric px-2 py-1 text-right text-xs font-semibold text-ink">
                  {formatNumber(row.total)}
                </td>
              </motion.tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// -------------------------------------------------------------------- map
export interface MapZone {
  zone: string
  capacity: number
  occupied: number
  free: number
  locations: number
  references: number
  occupancy_percent: number
  severity: Severity4
}

interface WarehouseMapProps {
  zones: MapZone[]
  emptyMessage: string
  selectedZone?: string | null
  onSelectZone?: (zone: string) => void
}

/**
 * The racks as a plan.
 *
 * Block area follows capacity and the fill bar follows occupancy, so a small
 * zone at 95 % and a large one at 60 % are both readable for what they are: a
 * list of percentages loses the fact that one of them holds three times more.
 */
export function WarehouseMap({
  zones,
  emptyMessage,
  selectedZone,
  onSelectZone,
}: WarehouseMapProps) {
  const { t, formatNumber, formatDecimal } = useI18n()

  if (zones.length === 0) return <ChartEmpty message={emptyMessage} />

  const totalCapacity = zones.reduce((sum, zone) => sum + zone.capacity, 0) || 1

  return (
    <div className="grid auto-rows-[132px] grid-cols-2 gap-2 sm:grid-cols-3">
      {zones.map((zone, index) => {
        const share = (zone.capacity / totalCapacity) * 100
        //: A zone holding a fifth of the warehouse gets two cells, not one.
        const wide = share > 18
        const active = selectedZone === zone.zone
        const dimmed = selectedZone != null && !active
        const Element = onSelectZone ? 'button' : 'div'

        return (
          <motion.div
            key={zone.zone}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: dimmed ? 0.45 : 1, y: 0 }}
            transition={{ duration: 0.35, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
            className={cn(wide && 'col-span-2')}
          >
            <Element
              type={onSelectZone ? 'button' : undefined}
              onClick={onSelectZone ? () => onSelectZone(zone.zone) : undefined}
              aria-pressed={onSelectZone ? active : undefined}
              className={cn(
                'flex h-full w-full flex-col justify-between rounded-xl border bg-elevated/60 p-3 text-left transition-all duration-200',
                active ? 'border-accent shadow-lift' : 'border-line',
                onSelectZone && 'cursor-pointer hover:-translate-y-px hover:border-accent/50',
              )}
            >
              <div className="flex items-start justify-between gap-2">
                <span className="numeric text-sm font-semibold text-ink">
                  {t('warehouse.zone')} {zone.zone}
                </span>
                <span
                  className={cn(
                    'numeric rounded px-1.5 py-0.5 text-[11px] font-semibold text-white',
                    STATE_BG[zone.severity],
                  )}
                >
                  {formatDecimal(zone.occupancy_percent, 0)} %
                </span>
              </div>

              {/* The fill is the plan: how much of this block is taken. */}
              <div className="mt-2 h-6 w-full overflow-hidden rounded-md bg-line/50">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${Math.min(zone.occupancy_percent, 100)}%` }}
                  transition={{ duration: 0.6, delay: index * 0.05 }}
                  className={cn('h-full', STATE_BG[zone.severity])}
                />
              </div>

              <p className="mt-1.5 flex flex-wrap gap-x-3 text-[11px] text-ink-3">
                <span className="numeric">
                  {formatNumber(zone.occupied)} / {formatNumber(zone.capacity)}
                </span>
                <span>{t('warehouse.locations', { count: zone.locations })}</span>
                <span>{t('warehouse.references', { count: zone.references })}</span>
              </p>
            </Element>
          </motion.div>
        )
      })}
    </div>
  )
}
