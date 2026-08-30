import { NavLink } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Hexagon, X } from 'lucide-react'

import { NAV_ITEMS } from './navigation'
import { useI18n } from '@/i18n/I18nProvider'
import { cn } from '@/utils/cn'

interface SidebarProps {
  /** Drawer state on small screens; the desktop sidebar is always visible. */
  open?: boolean
  onClose?: () => void
}

function Brand({ onClose }: { onClose?: () => void }) {
  const { t } = useI18n()
  return (
    <div className="flex items-center gap-3 border-b border-line px-4 py-4">
      <div className="grid h-8 w-8 place-items-center rounded-md bg-accent/10 text-accent">
        <Hexagon className="h-4 w-4" strokeWidth={2} />
      </div>
      <div className="min-w-0 leading-tight">
        <p className="truncate text-sm font-semibold tracking-tight text-ink">
          {t('app.name')}
        </p>
        <p className="truncate text-2xs text-ink-3">{t('app.tagline')}</p>
      </div>
      {onClose && (
        <button
          type="button"
          onClick={onClose}
          className="ml-auto rounded p-1 text-ink-3 transition-colors hover:bg-elevated hover:text-ink lg:hidden"
          aria-label={t('common.close')}
        >
          <X className="h-4 w-4" />
        </button>
      )}
    </div>
  )
}

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { t } = useI18n()
  return (
    <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
      {NAV_ITEMS.map((item) => (
        <div key={item.path}>
          {item.sectionKey && (
            <p className="eyebrow px-2 pb-1.5 pt-4 first:pt-0">{t(item.sectionKey)}</p>
          )}
          <NavLink
            to={item.path}
            onClick={onNavigate}
            className={({ isActive }) =>
              cn(
                'group relative flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm transition-colors',
                isActive
                  ? 'bg-accent/10 font-medium text-accent'
                  : 'text-ink-2 hover:bg-elevated hover:text-ink',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <span className="absolute -left-2 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r bg-accent" />
                )}
                <item.icon
                  className={cn(
                    'h-4 w-4 shrink-0',
                    isActive ? 'text-accent' : 'text-ink-3 group-hover:text-ink-2',
                  )}
                  strokeWidth={1.8}
                />
                <span className="truncate">{t(item.labelKey)}</span>
              </>
            )}
          </NavLink>
        </div>
      ))}
    </nav>
  )
}

function Footer() {
  return (
    <div className="border-t border-line px-4 py-3">
      <p className="text-2xs text-ink-3">
        SLCC <span className="numeric">v1.1.0</span>
      </p>
    </div>
  )
}

export function Sidebar({ open = false, onClose }: SidebarProps) {
  const { t } = useI18n()
  return (
    <>
      {/* Desktop: permanent rail */}
      <aside className="hidden w-[232px] shrink-0 flex-col border-r border-line bg-panel lg:flex">
        <Brand />
        <Navigation />
        <Footer />
      </aside>

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
              className="absolute inset-0 bg-ink/40"
            />
            <motion.aside
              initial={{ x: '-100%' }}
              animate={{ x: 0 }}
              exit={{ x: '-100%' }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="relative z-10 flex h-full w-[264px] flex-col border-r border-line bg-panel"
              role="dialog"
              aria-label={t('nav.section.supervision')}
            >
              <Brand onClose={onClose} />
              <Navigation onNavigate={onClose} />
              <Footer />
            </motion.aside>
          </div>
        )}
      </AnimatePresence>
    </>
  )
}
