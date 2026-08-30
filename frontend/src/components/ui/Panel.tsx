import type { ReactNode } from 'react'
import { motion } from 'framer-motion'

import { cn } from '@/utils/cn'

interface PanelProps {
  title?: string
  subtitle?: string
  action?: ReactNode
  className?: string
  bodyClassName?: string
  children: ReactNode
  /** Stagger index used for the entry animation. */
  delay?: number
}

/** The standard surface of the control center: bordered, dark, subtly lit. */
export function Panel({
  title,
  subtitle,
  action,
  className,
  bodyClassName,
  children,
  delay = 0,
}: PanelProps) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay, ease: [0.22, 1, 0.36, 1] }}
      className={cn('panel flex min-w-0 flex-col', className)}
    >
      {title && (
        <header className="panel-header">
          <div className="min-w-0">
            <h2 className="eyebrow">{title}</h2>
            {subtitle && <p className="mt-1 truncate text-xs text-ink-3">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={cn('flex-1', bodyClassName ?? 'p-5')}>{children}</div>
    </motion.section>
  )
}
