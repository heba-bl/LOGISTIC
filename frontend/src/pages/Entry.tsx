import { Navigate } from 'react-router-dom'
import { motion } from 'framer-motion'

import { BrandEmblem } from '@/components/BrandMark'
import { SignInPanel } from '@/features/entry/SignInPanel'
import { useI18n } from '@/i18n/I18nProvider'
import { useSession } from '@/hooks/useSession'

/**
 * The way in.
 *
 * This used to be a scroll-locked reveal: the doors opened as you scrubbed, and
 * the form arrived at the end. It looked good once and was wrong twice over.
 *
 * It pinned `document.body` to `position: fixed` with a negative `top` taken
 * from the current scroll position - so a reload while scrolled pushed the
 * whole page off screen and left nothing but white. And it put a ceremony in
 * front of a tool somebody opens fifteen times a day, where the only thing
 * wanted is the password field.
 *
 * The scene stays as a backdrop, because it is good, and it costs nothing now
 * that nothing depends on it. The page scrolls like a page.
 */
export default function Entry() {
  const { t } = useI18n()
  const { user } = useSession()

  if (user) return <Navigate to="/mission-control" replace />

  return (
    <div className="relative flex min-h-[100dvh] w-full items-center justify-center overflow-hidden bg-canvas px-5 py-10">
      {/* The room: racking receding into depth, drawn rather than filmed. */}
      <div className="pointer-events-none absolute inset-0" aria-hidden="true">
        <div className="hero-scene absolute inset-0 opacity-90" />
        <div className="hero-rails absolute inset-x-0 bottom-0 top-1/3" />
        <div className="hero-glow absolute left-1/2 top-1/2 h-[46rem] w-[46rem] -translate-x-1/2 -translate-y-1/2 rounded-full" />
      </div>

      <motion.div
        initial={{ opacity: 0, y: 18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="relative flex w-full max-w-sm flex-col items-center gap-7"
      >
        <div className="flex flex-col items-center gap-5 text-center">
          <div className="rounded-3xl bg-white px-8 py-5 shadow-[0_18px_50px_-22px_rgba(15,35,60,0.4)] ring-1 ring-black/5">
            <BrandEmblem className="h-28 w-auto object-contain" />
          </div>
          <div>
            <h1 className="text-[clamp(1.35rem,3.4vw,2rem)] font-bold leading-tight tracking-tight text-ink">
              {t('entry.title')}
            </h1>
            <p className="mt-2 text-xs text-ink-2">{t('entry.tagline')}</p>
          </div>
        </div>

        <SignInPanel />
      </motion.div>
    </div>
  )
}
