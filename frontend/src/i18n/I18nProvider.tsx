import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

import { CATALOGUES, type Locale, type MessageKey } from './messages'

/**
 * Translation.
 *
 * A small typed catalogue rather than a runtime i18n library: keys are checked
 * at compile time, so a missing translation is a build error instead of an
 * English string leaking into a French screen.
 */
interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  /** Translate a key, with optional `{placeholder}` substitution. */
  t: (key: MessageKey, values?: Record<string, string | number>) => string
  /** Translate a backend status/enum value, falling back to a readable form. */
  ts: (value: string | null | undefined) => string
  /** Locale-aware date/number helpers. */
  formatDate: (iso: string) => string
  /** Calendar day only, for `YYYY-MM-DD` values that carry no time. */
  formatDay: (iso: string) => string
  formatTime: (iso: string) => string
  formatNumber: (value: number) => string
  /** Fixed-decimal figure. The separator follows the locale, never the author. */
  formatDecimal: (value: number, digits?: number) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)
const STORAGE_KEY = 'slcc.locale'

//: French is the working language of the plant, so it is the default.
const DEFAULT_LOCALE: Locale = 'fr'

function initialLocale(): Locale {
  const stored = window.localStorage.getItem(STORAGE_KEY)
  if (stored === 'fr' || stored === 'en') return stored
  // French unconditionally, not "French unless the browser says otherwise":
  // the plant runs in French, and a browser installed in English is not a
  // statement about the shop floor.
  return DEFAULT_LOCALE
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(initialLocale)

  useEffect(() => {
    window.localStorage.setItem(STORAGE_KEY, locale)
    document.documentElement.lang = locale
  }, [locale])

  const setLocale = useCallback((next: Locale) => setLocaleState(next), [])

  const value = useMemo<I18nContextValue>(() => {
    const catalogue = CATALOGUES[locale]
    const tag = locale === 'fr' ? 'fr-FR' : 'en-GB'

    const t = (key: MessageKey, values?: Record<string, string | number>) => {
      let text: string = catalogue[key] ?? key
      if (values) {
        for (const [name, replacement] of Object.entries(values)) {
          text = text.replace(new RegExp(`\\{${name}\\}`, 'g'), String(replacement))
        }
      }
      return text
    }

    const ts = (raw: string | null | undefined) => {
      if (!raw) return '—'
      const key = `status.${raw}` as MessageKey
      if (key in catalogue) return catalogue[key]
      // Unknown value: render it readably rather than shouting the enum.
      const lower = raw.replace(/_/g, ' ').toLowerCase()
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    }

    const formatDate = (iso: string) => {
      const date = new Date(iso)
      if (Number.isNaN(date.getTime())) return '—'
      return date.toLocaleString(tag, {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
      })
    }

    //: A date-only value has no time and no zone. Feeding it to the datetime
    //: formatter parses it as UTC midnight, which renders as the previous day
    //: for anyone west of Greenwich - the axis would be silently off by one.
    const formatDay = (iso: string) => {
      const [year, month, day] = iso.slice(0, 10).split('-').map(Number)
      if (!year || !month || !day) return '—'
      const date = new Date(year, month - 1, day)
      return date.toLocaleDateString(tag, {
        day: '2-digit',
        month: '2-digit',
        year: '2-digit',
      })
    }

    const formatTime = (iso: string) => {
      const date = new Date(iso)
      if (Number.isNaN(date.getTime())) return '--:--'
      return date.toLocaleTimeString(tag, { hour: '2-digit', minute: '2-digit' })
    }

    const formatNumber = (input: number) =>
      new Intl.NumberFormat(tag).format(Math.round(input))

    //: `toFixed().replace('.', ',')` is a French comma hard-coded into an
    //: English screen. Intl knows which separator each locale uses.
    const formatDecimal = (input: number, digits = 1) =>
      new Intl.NumberFormat(tag, {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      }).format(input)

    return {
      locale,
      setLocale,
      t,
      ts,
      formatDate,
      formatDay,
      formatTime,
      formatNumber,
      formatDecimal,
    }
  }, [locale, setLocale])

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>
}

export function useI18n(): I18nContextValue {
  const context = useContext(I18nContext)
  if (!context) {
    throw new Error('useI18n must be used inside an I18nProvider')
  }
  return context
}
