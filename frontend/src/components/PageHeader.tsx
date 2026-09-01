import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

interface PageHeaderProps {
  title: string
  description?: string
  actions?: ReactNode
}

/** Consistent page title block used by every module. */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="mb-6 flex flex-wrap items-end justify-between gap-4"
    >
      <div className="min-w-0">
        {/* The accent stroke ties the title to the rail's active item, so the
            eye can jump from one to the other without re-reading either. */}
        <div className="flex items-center gap-3">
          <span
            className="h-7 w-1 shrink-0 rounded-full bg-gradient-to-b from-accent to-accent-2"
            aria-hidden="true"
          />
          <h1 className="truncate text-2xl font-bold tracking-tight text-ink">{title}</h1>
        </div>
        {description && <p className="mt-1.5 pl-4 text-xs text-ink-2">{description}</p>}
      </div>
      {actions}
    </motion.div>
  )
}
