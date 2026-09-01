import { useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'
import { Menu } from 'lucide-react'

import { AmbientBackdrop } from '@/components/AmbientBackdrop'
import { useSession } from '@/hooks/useSession'
import { useI18n } from '@/i18n/I18nProvider'
import { Sidebar } from './Sidebar'

/**
 * Application shell: one rail, and the content.
 *
 * There is no header. Every page already opens with its own title block, so a
 * top bar was spending sixty-four pixels of every screen restating it beside
 * six controls somebody touches twice a day. Those controls moved to the foot
 * of the rail; the pixels went back to the data.
 *
 * On a narrow screen the rail becomes a drawer, so the button that opens it has
 * to live somewhere: it floats over the content rather than bringing the whole
 * header back for one icon.
 */
export function AppLayout() {
  const location = useLocation()
  const { user } = useSession()
  const { t } = useI18n()
  const [navOpen, setNavOpen] = useState(false)

  // Every screen behind the door, in one place: a route added later cannot
  // forget to check, because it never gets the chance.
  if (!user) return <Navigate to="/" replace />

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />

      <div className="relative flex min-w-0 flex-1 flex-col lg:py-3 lg:pr-3">
        <AmbientBackdrop />

        <button
          type="button"
          onClick={() => setNavOpen(true)}
          className="absolute left-4 top-4 z-30 cursor-pointer rounded-xl border border-line bg-panel/80 p-2.5 text-ink-2 shadow-panel backdrop-blur-xl transition-colors hover:text-ink lg:hidden"
          aria-label={t('topbar.openNav')}
        >
          <Menu className="h-4 w-4" />
        </button>

        <main className="relative flex-1 overflow-y-auto overflow-x-hidden lg:rounded-2xl lg:border lg:border-line lg:bg-panel/40 lg:shadow-panel">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto w-full max-w-[1600px] px-6 py-7 pt-16 lg:pt-7"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
