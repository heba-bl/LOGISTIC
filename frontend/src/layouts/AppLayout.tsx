import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import { AnimatePresence, motion } from 'framer-motion'

import { Sidebar } from './Sidebar'
import { Topbar } from './Topbar'

/** Application shell: fixed sidebar, sticky topbar, animated routed content. */
export function AppLayout() {
  const location = useLocation()
  const [navOpen, setNavOpen] = useState(false)

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <Sidebar open={navOpen} onClose={() => setNavOpen(false)} />
      <div className="relative flex min-w-0 flex-1 flex-col">
        {/* Industrial grid texture */}
        <div
          className="pointer-events-none absolute inset-0 bg-grid bg-grid opacity-[0.55]"
          aria-hidden="true"
        />
        <Topbar onOpenNav={() => setNavOpen(true)} />
        <main className="relative flex-1 overflow-y-auto overflow-x-hidden">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
              className="mx-auto w-full max-w-[1600px] px-6 py-6"
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
