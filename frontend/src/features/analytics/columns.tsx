/**
 * Vertical grouped columns: stock against demand, reference by reference.
 *
 * The pair is read side by side, in the direction a bar chart is normally read,
 * and the demand column answers in its own colour - amber while the stock still
 * covers it, red the moment it does not. So the verdict lands before any number
 * is read, and the number sits on the column anyway.
 */

import { useState } from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import { ChartEmpty, ChartTooltip } from './primitives'
import type { MessageKey } from '@/i18n/messages'
import type { Severity4 } from '@/types/overview'

export interface ColumnPairRow {
  part_id: number
  reference: string
  designation: string
  available: number
  demand: number
  gap: number
  coverage_days: number | null
  risk: Severity4
}

interface ColumnPairsProps {
  rows: ColumnPairRow[]
  emptyMessage: string
  onSelect?: (partId: number) => void
  selectedId?: number | null
}

export function AnalyticsColumnPairs({
  rows,
  emptyMessage,
  onSelect,
  selectedId,
}: ColumnPairsProps) {
  const { t, formatDecimal, formatNumber } = useI18n()
  const [hover, setHover] = useState<number | null>(null)

  if (rows.length === 0) return <ChartEmpty message={emptyMessage} />

  const width = 760
  const height = 300
  const padding = { top: 26, right: 12, bottom: 56, left: 24 }
  const innerWidth = width - padding.left - padding.right
  const innerHeight = height - padding.top - padding.bottom

  /*
   * A common scale would flatten the reference that matters: a fastener held by
   * the thousand next to a suspension arm with a demand of twelve leaves the arm
   * as one invisible pixel - and the arm is the one that stops the line. Each
   * pair is therefore scaled to itself, which is exactly the comparison the
   * chart is asked to make. Absolute magnitudes are printed on every column.
   */
  const slot = innerWidth / rows.length
  const columnWidth = Math.min(slot * 0.3, 34)
  const groupGap = 5

  const baseline = padding.top + innerHeight
  const columnHeight = (value: number, ceiling: number) =>
    ceiling > 0 ? Math.max((value / ceiling) * innerHeight, value > 0 ? 3 : 0) : 0

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${width} ${height}`}
        className="w-full"
        role="img"
        aria-label={t('card.stockVsDemand.title')}
      >
        {/* Three recessive gridlines: enough to read a level, not a grid. */}
        {[0.33, 0.66, 1].map((fraction) => (
          <line
            key={fraction}
            x1={padding.left}
            x2={width - padding.right}
            y1={baseline - innerHeight * fraction}
            y2={baseline - innerHeight * fraction}
            className="stroke-line"
            strokeDasharray="2 4"
          />
        ))}
        <line
          x1={padding.left}
          x2={width - padding.right}
          y1={baseline}
          y2={baseline}
          className="stroke-line-strong"
        />

        {rows.map((row, index) => {
          const ceiling = Math.max(row.available, row.demand, 1)
          const uncovered = row.available < row.demand
          const selected = selectedId === row.part_id
          const dimmed = selectedId != null && !selected
          const centre = padding.left + slot * index + slot / 2

          const stockHeight = columnHeight(row.available, ceiling)
          const demandHeight = columnHeight(row.demand, ceiling)

          return (
            <g
              key={row.part_id}
              className={cn(dimmed && 'opacity-40', onSelect && 'cursor-pointer')}
              onMouseEnter={() => setHover(index)}
              onMouseLeave={() => setHover(null)}
              onClick={onSelect ? () => onSelect(row.part_id) : undefined}
            >
              {/* Hit target covering the whole column group. */}
              <rect
                x={padding.left + slot * index}
                y={padding.top - 20}
                width={slot}
                height={innerHeight + 20}
                fill="transparent"
              />

              {selected && (
                <rect
                  x={padding.left + slot * index + 2}
                  y={padding.top - 20}
                  width={slot - 4}
                  height={innerHeight + 20}
                  rx={8}
                  className="fill-accent/[0.08] stroke-accent/40"
                />
              )}

              <motion.rect
                x={centre - columnWidth - groupGap / 2}
                width={columnWidth}
                rx={4}
                initial={{ y: baseline, height: 0 }}
                animate={{ y: baseline - stockHeight, height: stockHeight }}
                transition={{ duration: 0.55, delay: index * 0.05, ease: [0.22, 1, 0.36, 1] }}
                className="fill-chart-1"
              />
              <motion.rect
                x={centre + groupGap / 2}
                width={columnWidth}
                rx={4}
                initial={{ y: baseline, height: 0 }}
                animate={{ y: baseline - demandHeight, height: demandHeight }}
                transition={{
                  duration: 0.55,
                  delay: index * 0.05 + 0.06,
                  ease: [0.22, 1, 0.36, 1],
                }}
                className={uncovered ? 'fill-crit' : 'fill-warn'}
              />

              {/* Values sit on the columns: the fills need a direct label. */}
              <text
                x={centre - columnWidth / 2 - groupGap / 2}
                y={baseline - stockHeight - 6}
                textAnchor="middle"
                className="fill-current text-ink-2"
                style={{ fontSize: 10, fontWeight: 600 }}
              >
                {formatNumber(row.available)}
              </text>
              <text
                x={centre + columnWidth / 2 + groupGap / 2}
                y={baseline - demandHeight - 6}
                textAnchor="middle"
                className={cn('fill-current', uncovered ? 'text-crit-soft' : 'text-ink-2')}
                style={{ fontSize: 10, fontWeight: 600 }}
              >
                {formatNumber(row.demand)}
              </text>

              <text
                x={centre}
                y={baseline + 17}
                textAnchor="middle"
                className="fill-current text-ink"
                style={{ fontSize: 11, fontWeight: 600 }}
              >
                {row.reference}
              </text>
              <text
                x={centre}
                y={baseline + 32}
                textAnchor="middle"
                className={cn('fill-current', uncovered ? 'text-crit-soft' : 'text-ink-3')}
                style={{ fontSize: 9.5, fontWeight: uncovered ? 600 : 400 }}
              >
                {row.gap > 0 ? '+' : ''}
                {formatNumber(row.gap)}
              </text>
            </g>
          )
        })}
      </svg>

      {hover !== null && (
        <ChartTooltip
          x={((hover + 0.5) / rows.length) * 100}
          y={8}
          title={rows[hover].reference}
          rows={[
            { label: t('chart.stock'), value: formatNumber(rows[hover].available) },
            { label: t('chart.demand'), value: formatNumber(rows[hover].demand) },
            {
              label: t('chart.gap'),
              value: `${rows[hover].gap > 0 ? '+' : ''}${formatNumber(rows[hover].gap)}`,
              className: rows[hover].gap < 0 ? 'text-crit-soft' : 'text-ok-soft',
            },
            ...(rows[hover].coverage_days !== null
              ? [
                  {
                    label: t('chart.coverage'),
                    value: t('chart.coverageDays', {
                      days: formatDecimal(rows[hover].coverage_days as number, 1),
                    }),
                  },
                ]
              : []),
            {
              label: t('table.risk'),
              value: t(`risk.${rows[hover].risk}` as MessageKey),
            },
          ]}
        />
      )}
    </div>
  )
}
