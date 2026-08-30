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
      className="mb-5 flex flex-wrap items-end justify-between gap-4"
    >
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 text-xs text-ink-2">{description}</p>}
      </div>
      {actions}
    </motion.div>
  )
}
