import { useLocation } from 'react-router-dom'
import { AlertTriangle, Menu, Monitor, Moon, Sun, Wifi } from 'lucide-react'

import { NAV_ITEMS } from './navigation'
import { StatusDot } from '@/components/ui'
import { useActor, useApiHealth } from '@/hooks'
import { useTheme, type ThemeChoice } from '@/hooks/useTheme'
import { useI18n } from '@/i18n/I18nProvider'
import type { Locale } from '@/i18n/messages'
import { cn } from '@/utils/cn'

const THEMES: { value: ThemeChoice; icon: typeof Sun; labelKey: 'settings.themeLight' | 'settings.themeDark' | 'settings.themeSystem' }[] = [
  { value: 'light', icon: Sun, labelKey: 'settings.themeLight' },
  { value: 'dark', icon: Moon, labelKey: 'settings.themeDark' },
  { value: 'system', icon: Monitor, labelKey: 'settings.themeSystem' },
]

export function Topbar({ onOpenNav }: { onOpenNav?: () => void }) {
  const location = useLocation()
  const { status } = useApiHealth()
  const { actor } = useActor()
  const { choice, setChoice } = useTheme()
  const { t, locale, setLocale } = useI18n()

  //: Longest prefix wins, so a nested route (/analytics/stock) still names its
  //: module instead of falling back to the product name.
  const current = NAV_ITEMS.filter(
    (item) =>
      location.pathname === item.path || location.pathname.startsWith(`${item.path}/`),
  ).sort((a, b) => b.path.length - a.path.length)[0]

  const apiLabel =
    status === 'online'
      ? t('topbar.online')
      : status === 'offline'
        ? t('topbar.offline')
        : t('topbar.connecting')

  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-line bg-panel px-4">
      <button
        type="button"
        onClick={onOpenNav}
        className="-ml-1 rounded-md border border-line p-1.5 text-ink-2 transition-colors hover:bg-elevated hover:text-ink lg:hidden"
        aria-label={t('topbar.openNav')}
      >
        <Menu className="h-4 w-4" />
      </button>

      <h1 className="min-w-0 truncate text-sm font-semibold text-ink">
        {current ? t(current.labelKey) : 'SLCC'}
      </h1>

      <div className="ml-auto flex items-center gap-2">
        {/* API state - compact, colour only when it matters */}
        <span
          className="hidden items-center gap-1.5 rounded-md border border-line px-2.5 py-1.5 text-2xs text-ink-2 sm:flex"
          title={apiLabel}
        >
          {status === 'offline' ? (
            <AlertTriangle className="h-3.5 w-3.5 text-crit" />
          ) : (
            <Wifi className={cn('h-3.5 w-3.5', status === 'online' ? 'text-ok' : 'text-warn')} />
          )}
          {apiLabel}
        </span>

        {/* Language */}
        <div
          className="flex items-center rounded-md border border-line p-0.5"
          role="group"
          aria-label={t('topbar.language')}
        >
          {(['fr', 'en'] as Locale[]).map((code) => (
            <button
              key={code}
              type="button"
              onClick={() => setLocale(code)}
              className={cn(
                'rounded px-2 py-1 text-2xs font-semibold uppercase transition-colors',
                locale === code
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-3 hover:text-ink',
              )}
            >
              {code}
            </button>
          ))}
        </div>

        {/* Theme */}
        <div
          className="flex items-center rounded-md border border-line p-0.5"
          role="group"
          aria-label={t('topbar.theme')}
        >
          {THEMES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setChoice(option.value)}
              title={t(option.labelKey)}
              aria-label={t(option.labelKey)}
              aria-pressed={choice === option.value}
              className={cn(
                'rounded p-1.5 transition-colors',
                choice === option.value
                  ? 'bg-accent/10 text-accent'
                  : 'text-ink-3 hover:text-ink',
              )}
            >
              <option.icon className="h-3.5 w-3.5" />
            </button>
          ))}
        </div>

        {/* Operator */}
        {actor && (
          <div className="flex items-center gap-2 border-l border-line pl-3">
            <div className="hidden text-right leading-tight sm:block">
              <p className="numeric text-2xs font-semibold text-ink">
                {actor.employee_number}
              </p>
              <p className="flex items-center justify-end gap-1 text-[10px] text-ink-3">
                <StatusDot severity="ok" />
                {t('topbar.onShift')}
              </p>
            </div>
            <div className="grid h-8 w-8 place-items-center rounded-full bg-elevated text-2xs font-semibold text-ink-2">
              {(actor.first_name?.[0] ?? actor.full_name[0]) +
                (actor.last_name?.[0] ?? '')}
            </div>
          </div>
        )}
      </div>
    </header>
  )
}
