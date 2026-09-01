/**
 * The shape every supervision screen takes.
 *
 * These five screens watch what the plant did in Excel; they never act on it.
 * That constraint is what makes one shell possible: each is the same four
 * blocks in the same order - what happened (figures), how it splits (charts),
 * narrow it down (filters), and the line-by-line record underneath.
 *
 * Reading order matters more than novelty here. A logistics manager who learns
 * the Receiving screen already knows how to read Quality.
 */

import { useMemo, useState, type ReactNode } from 'react'
import { Search, X } from 'lucide-react'

import { cn } from '@/utils/cn'
import { useI18n } from '@/i18n/I18nProvider'
import type { MessageKey } from '@/i18n/messages'
import type { Severity4 } from '@/types/overview'

// ------------------------------------------------------------------ banner
/**
 * Says out loud where the data comes from.
 *
 * Without this a manager could reasonably assume the screen is where the work
 * happens, and wonder why nothing can be edited. It is the first thing to read
 * and the reason the rest has no buttons.
 */
export function SourceNote({ zone }: { zone: MessageKey }) {
  const { t } = useI18n()
  return (
    <p className="rounded-md border border-line bg-elevated/60 px-3 py-2 text-2xs leading-relaxed text-ink-3">
      <span className="font-semibold text-ink-2">{t('supervision.readOnly')}</span>{' '}
      {t('supervision.source', { zone: t(zone) })}
    </p>
  )
}

// --------------------------------------------------------------------- KPI
export interface SupervisionKpi {
  key: string
  label: string
  value: string
  unit?: string
  hint?: string
  severity?: Severity4
}

//: State lives on the left edge, where the eye enters the tile, and in a dot
//: beside the label. Never in the figure itself: a number that changes colour
//: is a number somebody has to interpret twice.
const EDGE: Record<Severity4, string> = {
  OK: 'bg-ok',
  WARNING: 'bg-warn',
  CRITICAL: 'bg-crit',
  INFO: 'bg-gradient-to-b from-accent to-accent-2',
}

const DOT: Record<Severity4, string> = {
  OK: 'bg-ok',
  WARNING: 'bg-warn',
  CRITICAL: 'bg-crit',
  INFO: 'bg-accent',
}

const TINT: Record<Severity4, string> = {
  OK: 'group-hover:bg-ok/5',
  WARNING: 'group-hover:bg-warn/5',
  CRITICAL: 'group-hover:bg-crit/5',
  INFO: 'group-hover:bg-accent/5',
}

export function KpiRow({ items }: { items: SupervisionKpi[] }) {
  return (
    <section
      className="grid gap-3 sm:grid-cols-2"
      style={{ gridTemplateColumns: `repeat(auto-fit, minmax(205px, 1fr))` }}
    >
      {items.map((item, index) => {
        const severity = item.severity ?? 'INFO'
        return (
          <article
            key={item.key}
            className="panel panel-interactive group rise relative overflow-hidden py-4 pl-5 pr-4"
            style={{ '--rise-delay': `${index * 45}ms` } as React.CSSProperties}
          >
            <span
              className={cn('absolute inset-y-0 left-0 w-1', EDGE[severity])}
              aria-hidden="true"
            />
            <span
              className={cn(
                'absolute inset-0 transition-colors duration-300',
                TINT[severity],
              )}
              aria-hidden="true"
            />

            <div className="relative">
              <p className="eyebrow flex items-center gap-1.5 truncate">
                <span
                  className={cn('h-1.5 w-1.5 shrink-0 rounded-full', DOT[severity])}
                  aria-hidden="true"
                />
                {item.label}
              </p>
              <p className="mt-3 flex items-baseline gap-1.5">
                <span className="figure text-[28px] leading-none">{item.value}</span>
                {item.unit && (
                  <span className="text-xs font-medium text-ink-3">{item.unit}</span>
                )}
              </p>
              {item.hint && (
                <p className="mt-2 truncate text-2xs text-ink-3">{item.hint}</p>
              )}
            </div>
          </article>
        )
      })}
    </section>
  )
}

// ------------------------------------------------------------------ filters
export interface SelectFilter {
  key: string
  label: string
  value: string
  options: { value: string; label: string }[]
  onChange: (value: string) => void
}

interface FilterBarProps {
  search: string
  onSearch: (value: string) => void
  placeholder: string
  selects?: SelectFilter[]
  /** Shown on the right: how many rows survive the filters. */
  count?: string
  onReset?: () => void
}

export function FilterBar({
  search,
  onSearch,
  placeholder,
  selects = [],
  count,
  onReset,
}: FilterBarProps) {
  const { t } = useI18n()
  const dirty = search.length > 0 || selects.some((item) => item.value !== '')

  return (
    <div className="panel flex flex-wrap items-center gap-2.5 px-4 py-3">
      <div className="relative min-w-[240px] flex-1">
        <Search
          className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-ink-3"
          aria-hidden="true"
        />
        {/* 38px tall, not 28: a search field somebody misses is a filter
            somebody stops using. */}
        <input
          value={search}
          onChange={(event) => onSearch(event.target.value)}
          placeholder={placeholder}
          aria-label={placeholder}
          className="h-[38px] w-full rounded-xl border border-line bg-elevated/60 pl-10 pr-3 text-xs text-ink transition-colors placeholder:text-ink-3 focus:border-accent focus:bg-panel focus:outline-none"
        />
      </div>

      {selects.map((filter) => (
        <label key={filter.key} className="flex items-center gap-1.5">
          <span className="sr-only">{filter.label}</span>
          <select
            value={filter.value}
            onChange={(event) => filter.onChange(event.target.value)}
            aria-label={filter.label}
            className="h-[38px] cursor-pointer rounded-xl border border-line bg-elevated/60 px-3 text-xs text-ink transition-colors focus:border-accent focus:bg-panel focus:outline-none"
          >
            <option value="">{filter.label}</option>
            {filter.options.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      ))}

      {dirty && onReset && (
        <button
          type="button"
          onClick={onReset}
          className="inline-flex h-[38px] cursor-pointer items-center gap-1.5 rounded-xl border border-line px-3 text-2xs font-medium text-ink-2 transition-colors hover:border-crit/40 hover:bg-crit/10 hover:text-crit"
        >
          <X className="h-3 w-3" />
          {t('filter.reset')}
        </button>
      )}

      {count && <span className="numeric ml-auto text-2xs text-ink-3">{count}</span>}
    </div>
  )
}

/** Case- and accent-insensitive contains, so "réception" matches "reception". */
export function matches(haystack: (string | null | undefined)[], needle: string): boolean {
  if (!needle) return true
  const fold = (value: string) =>
    value
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .toLowerCase()
  const target = fold(needle)
  return haystack.some((value) => value && fold(value).includes(target))
}

// ------------------------------------------------------------------- report
interface ReportTableProps {
  columns: { key: string; label: string; align?: 'right' }[]
  children: ReactNode
  empty?: ReactNode
  minWidth?: number
}

export function ReportTable({ columns, children, empty, minWidth = 900 }: ReportTableProps) {
  if (empty) return <>{empty}</>
  return (
    <div className="overflow-x-auto">
      <table className="data-table" style={{ minWidth }}>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={column.align === 'right' ? 'text-right' : undefined}>
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}

/** Rows surviving a text search plus any number of equality filters. */
export function useFiltered<T>(
  rows: T[],
  search: string,
  searchable: (row: T) => (string | null | undefined)[],
  equals: ((row: T) => boolean)[] = [],
): T[] {
  return useMemo(
    () =>
      rows.filter(
        (row) => matches(searchable(row), search) && equals.every((test) => test(row)),
      ),
    // The callbacks are rebuilt each render by design; the rows and the filter
    // values are what actually decide the result.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [rows, search, ...equals.map(() => 0)],
  )
}

/** Search box plus a set of select filters, wired together. */
export function useFilterState(keys: string[]) {
  const [search, setSearch] = useState('')
  const [values, setValues] = useState<Record<string, string>>(
    () => Object.fromEntries(keys.map((key) => [key, ''])),
  )

  return {
    search,
    setSearch,
    values,
    set: (key: string, value: string) =>
      setValues((current) => ({ ...current, [key]: value })),
    reset: () => {
      setSearch('')
      setValues(Object.fromEntries(keys.map((key) => [key, ''])))
    },
  }
}
