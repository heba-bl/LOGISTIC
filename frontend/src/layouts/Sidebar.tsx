import { useEffect, useRef, useState, type ReactNode } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import {
  ChevronsLeft,
  LogOut,
  PanelLeft,
  X,
} from 'lucide-react'

import { BrandMark } from '@/components/BrandMark'
import { useActor, useApiHealth, useApiResource } from '@/hooks'
import { useSession } from '@/hooks/useSession'
import { useI18n } from '@/i18n/I18nProvider'
import { dashboardApi } from '@/services/slcc.service'
import { cn } from '@/utils/cn'
import { NAV_ITEMS, type NavEntry } from './navigation'

interface SidebarProps {
  /** Drawer state on small screens; the desktop sidebar is always visible. */
  open?: boolean
  onClose?: () => void
}

const COLLAPSE_KEY = 'slcc.nav.collapsed'

/**
 * The rail can be reduced to its icons.
 *
 * Kept in localStorage because it is a working preference, not session state:
 * somebody on a 1366px screen collapses it once and should never be asked
 * again.
 */
function useCollapsed(): [boolean, (next: boolean) => void] {
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return window.localStorage.getItem(COLLAPSE_KEY) === '1'
    } catch {
      return false
    }
  })

  useEffect(() => {
    try {
      window.localStorage.setItem(COLLAPSE_KEY, collapsed ? '1' : '0')
    } catch {
      // A browser refusing storage must not break the navigation.
    }
  }, [collapsed])

  return [collapsed, setCollapsed]
}

/** The label that appears beside a collapsed icon, on hover and on focus. */
function Tip({ children }: { children: ReactNode }) {
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 translate-x-1
        whitespace-nowrap rounded-lg bg-ink px-2.5 py-1.5 text-2xs font-medium text-canvas opacity-0
        shadow-lift transition-all duration-[var(--t-fast)]
        group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100"
    >
      {children}
    </span>
  )
}

function Brand({ collapsed, onClose }: { collapsed: boolean; onClose?: () => void }) {
  const { t } = useI18n()
  return (
    <div className={cn('flex items-center gap-3 pb-4 pt-5', collapsed ? 'px-3' : 'px-4')}>
      {collapsed ? (
        <div className="grid h-10 w-10 place-items-center rounded-xl bg-accent text-sm font-bold text-white">
          S
        </div>
      ) : (
        // The mark alone. The divider and the "SLCC / Centre de controle"
        // block restated on every screen what the mark already says, and cost
        // three lines at the top of the rail to do it.
        <BrandMark
          inline
          className="h-10 w-auto max-w-[11rem] shrink-0 object-contain object-left"
        />
      )}
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="btn-icon ml-auto lg:hidden"
          aria-label={t('common.close')}
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

/**
 * The navigation.
 *
 * A single hover plate travels between entries on a spring, rather than a
 * background appearing under whichever item the cursor is over: the eye
 * follows a moving object and does not follow a blink. The active bar slides
 * the same way.
 *
 * Sub-destinations appear only while the rail is expanded and only under the
 * section you are already in. A permanently open tree is a second menu.
 */
function Navigation({
  collapsed,
  onNavigate,
  badges,
}: {
  collapsed: boolean
  onNavigate?: () => void
  badges: Record<string, number>
}) {
  const { t } = useI18n()
  const location = useLocation()
  const listRef = useRef<HTMLElement>(null)
  const [hover, setHover] = useState<{ top: number; height: number } | null>(null)

  const isActive = (entry: NavEntry) =>
    location.pathname === entry.path || location.pathname.startsWith(`${entry.path}/`)

  return (
    <nav
      ref={listRef}
      onMouseLeave={() => setHover(null)}
      className={cn(
        'relative flex-1 space-y-0.5 overflow-y-auto pb-4',
        collapsed ? 'px-2' : 'px-3',
      )}
    >
      <AnimatePresence>
        {hover && !collapsed && (
          <motion.span
            aria-hidden="true"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1, top: hover.top, height: hover.height }}
            exit={{ opacity: 0 }}
            transition={{ type: 'spring', stiffness: 500, damping: 40, mass: 0.6 }}
            className="pointer-events-none absolute inset-x-3 z-0 rounded-xl bg-elevated"
          />
        )}
      </AnimatePresence>

      {NAV_ITEMS.map((entry) => {
        const active = isActive(entry)
        const count = entry.badge ? (badges[entry.badge] ?? 0) : 0

        return (
          <div key={entry.path}>
            {entry.sectionKey && !collapsed && (
              <p className="eyebrow relative z-10 px-2.5 pb-1.5 pt-5 first:pt-1">
                {t(entry.sectionKey)}
              </p>
            )}
            {entry.sectionKey && collapsed && (
              <div className="mx-2 my-3 h-px bg-line first:mt-1" aria-hidden="true" />
            )}

            <NavLink
              to={entry.path}
              onClick={onNavigate}
              onMouseEnter={(event) => {
                const parent = listRef.current
                if (!parent) return
                setHover({
                  top: event.currentTarget.offsetTop - parent.scrollTop,
                  height: event.currentTarget.offsetHeight,
                })
              }}
              className={cn(
                'group relative z-10 flex cursor-pointer items-center rounded-xl text-sm transition-colors duration-[var(--t-fast)]',
                collapsed ? 'justify-center px-0 py-2' : 'gap-3 px-2.5 py-2',
                active ? 'text-ink' : 'text-ink-2 hover:text-ink',
              )}
            >
              {active && (
                <motion.span
                  layoutId="nav-bar"
                  transition={{ type: 'spring', stiffness: 480, damping: 38 }}
                  className={cn(
                    'absolute top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-accent',
                    collapsed ? '-left-2' : '-left-3',
                  )}
                />
              )}

              <span
                className={cn(
                  'relative grid h-8 w-8 shrink-0 place-items-center rounded-xl transition-all duration-[var(--t-fast)]',
                  active
                    ? 'bg-accent text-white shadow-[0_4px_12px_-4px_rgb(var(--c-accent)/0.9)]'
                    : 'bg-elevated text-ink-3 group-hover:scale-105 group-hover:text-ink-2',
                )}
              >
                <entry.icon className="h-4 w-4" strokeWidth={active ? 2.3 : 2} />
                {/* The badge rides on the icon, so a waiting count survives the
                    rail being collapsed. */}
                {count > 0 && (
                  <span className="absolute -right-1 -top-1 grid h-4 min-w-[1rem] place-items-center rounded-full bg-warn px-1 text-[11px] font-bold leading-none text-ink ring-2 ring-panel">
                    {count > 99 ? '99+' : count}
                  </span>
                )}
              </span>

              {!collapsed && (
                <span className={cn('truncate', active && 'font-semibold')}>
                  {t(entry.labelKey)}
                </span>
              )}
              {collapsed && <Tip>{t(entry.labelKey)}</Tip>}
            </NavLink>

            <AnimatePresence initial={false}>
              {entry.children && active && !collapsed && (
                <motion.ul
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                  className="relative z-10 ml-[26px] overflow-hidden border-l border-line pl-3"
                >
                  {entry.children.map((child) => (
                    <li key={child.path}>
                      <NavLink
                        to={child.path}
                        end
                        onClick={onNavigate}
                        className={({ isActive: on }) =>
                          cn(
                            'flex min-h-[34px] cursor-pointer items-center rounded-lg px-2.5 py-1.5 text-2xs transition-colors duration-[var(--t-fast)]',
                            on
                              ? 'font-semibold text-accent'
                              : 'text-ink-3 hover:bg-elevated hover:text-ink-2',
                          )
                        }
                      >
                        {t(child.labelKey)}
                      </NavLink>
                    </li>
                  ))}
                </motion.ul>
              )}
            </AnimatePresence>
          </div>
        )
      })}
    </nav>
  )
}

/**
 * The foot of the rail: everything the removed top bar used to hold.
 *
 * Connection first, because every figure on every screen is only as true as
 * that line. Then language and theme, then who is signed in and the way out.
 */
/**
 * The foot of the rail: who is signed in, and the way out.
 *
 * It used to carry the connection state, the language, the theme, the account
 * and a version string - a quarter of the rail spent on controls touched twice
 * a day, on every screen. Language and theme live in Parametres, which is where
 * somebody looks for them; the connection state survives as a dot on the
 * account row, because a stale screen still has to be able to say so.
 */
function Footer({
  collapsed,
  onNavigate,
}: {
  collapsed: boolean
  onNavigate?: () => void
}) {
  const { t } = useI18n()
  const { status } = useApiHealth()
  const { actor } = useActor()
  const { user, signOut } = useSession()
  const who = user ?? actor

  const apiLabel =
    status === 'online'
      ? t('topbar.online')
      : status === 'offline'
        ? t('topbar.offline')
        : t('topbar.connecting')

  if (!who) return null

  if (collapsed) {
    return (
      <div className="border-t border-line px-2 py-2">
        <button
          type="button"
          onClick={signOut}
          className="group relative grid h-9 w-full place-items-center rounded-xl text-ink-3 transition-colors hover:bg-crit/10 hover:text-crit"
          aria-label={t('auth.signOut')}
        >
          <LogOut className="h-4 w-4" />
          <Tip>{t('auth.signOut')}</Tip>
        </button>
      </div>
    )
  }

  return (
    <div className="flex items-center gap-2 border-t border-line px-3 py-2.5">
      <div className="relative shrink-0">
        <div className="grid h-8 w-8 place-items-center rounded-full bg-accent text-2xs font-bold text-white">
          {(who.first_name?.[0] ?? who.full_name[0]) + (who.last_name?.[0] ?? '')}
        </div>
        {/* The connection, reduced to a dot on the avatar: it only has to be
            noticed when it is not green. */}
        <span
          title={apiLabel}
          className={cn(
            'absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-panel',
            status === 'online' ? 'bg-ok' : status === 'offline' ? 'bg-crit' : 'bg-warn',
          )}
        />
      </div>

      <div className="min-w-0 leading-tight">
        <p className="truncate text-2xs font-semibold text-ink">{who.full_name}</p>
        <p className="numeric truncate text-[11px] text-ink-3">{who.employee_number}</p>
      </div>

      <button
        type="button"
        onClick={() => {
          onNavigate?.()
          signOut()
        }}
        title={t('auth.signOut')}
        aria-label={t('auth.signOut')}
        className="ml-auto grid h-8 w-8 shrink-0 cursor-pointer place-items-center rounded-full text-ink-3 transition-colors duration-[var(--t-fast)] hover:bg-crit/15 hover:text-crit"
      >
        <LogOut className="h-4 w-4" aria-hidden="true" />
      </button>
    </div>
  )
}

export function Sidebar({ open = false, onClose }: SidebarProps) {
  const { t } = useI18n()
  const [collapsed, setCollapsed] = useCollapsed()

  // The badges read the same endpoint Mission Control does, so a count on the
  // rail can never disagree with the figure on the screen it points at.
  const dashboard = useApiResource(() => dashboardApi.get(), [], { pollMs: 60_000 })
  const badges = {
    alerts: dashboard.data?.alerts?.filter((alert) => alert.severity === 'CRITICAL').length ?? 0,
    pending: Number(
      dashboard.data?.kpis?.find((kpi) => kpi.id === 'pending-inspections')?.value ?? 0,
    ),
  }

  const rail = (mobile: boolean) => (
    <>
      <Brand collapsed={!mobile && collapsed} onClose={mobile ? onClose : undefined} />
      <Navigation
        collapsed={!mobile && collapsed}
        onNavigate={mobile ? onClose : undefined}
        badges={badges}
      />
      <Footer collapsed={!mobile && collapsed} onNavigate={mobile ? onClose : undefined} />
    </>
  )

  return (
    <>
      <motion.aside
        animate={{ width: collapsed ? 84 : 256 }}
        transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
        className="relative hidden shrink-0 flex-col py-3 pl-3 lg:flex"
      >
        <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-line bg-panel shadow-panel">
          {rail(false)}
        </div>

        {/* The handle sits on the rail's own edge, where a handle belongs. */}
        <button
          type="button"
          onClick={() => setCollapsed(!collapsed)}
          title={collapsed ? t('nav.expand') : t('nav.collapse')}
          aria-label={collapsed ? t('nav.expand') : t('nav.collapse')}
          aria-expanded={!collapsed}
          className="absolute -right-3.5 top-1/2 z-20 grid h-8 w-8 -translate-y-1/2 cursor-pointer place-items-center
            rounded-full border border-line bg-panel text-ink-3 shadow-panel transition-colors duration-[var(--t-fast)]
            hover:border-accent hover:text-accent"
        >
          {collapsed ? <PanelLeft className="h-3.5 w-3.5" /> : <ChevronsLeft className="h-3.5 w-3.5" />}
        </button>
      </motion.aside>

      {/* Small screens: drawer, so every module stays reachable */}
      <AnimatePresence>
        {open && (
          <div className="fixed inset-0 z-40 lg:hidden">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={onClose}
              className="absolute inset-0 bg-ink/40 backdrop-blur-[2px]"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
              className="relative z-10 flex h-full w-[276px] flex-col border-r border-line bg-panel"
              role="dialog"
              aria-label={t('nav.section.supervision')}
            >
              {rail(true)}
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
