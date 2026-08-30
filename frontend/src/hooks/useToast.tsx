import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'

import { cn } from '@/utils/cn'
import { severityStyles } from '@/utils/status'
import type { Severity } from '@/types'

interface Toast {
  id: number
  severity: Severity
  title: string
  description?: string
}

interface ToastContextValue {
  push: (toast: Omit<Toast, 'id'>) => void
  success: (title: string, description?: string) => void
  error: (title: string, description?: string) => void
  info: (title: string, description?: string) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

const ICONS = {
  ok: CheckCircle2,
  warn: AlertTriangle,
  crit: XCircle,
  info: Info,
} as const

let nextId = 1

/** Feedback for every write: the operator always sees what the backend decided. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id))
  }, [])

  const push = useCallback(
    (toast: Omit<Toast, 'id'>) => {
      const id = nextId++
      setToasts((current) => [...current, { ...toast, id }])
      window.setTimeout(() => dismiss(id), toast.severity === 'crit' ? 9000 : 5000)
    },
    [dismiss],
  )

  const value = useMemo<ToastContextValue>(
    () => ({
      push,
      success: (title, description) => push({ severity: 'ok', title, description }),
      error: (title, description) => push({ severity: 'crit', title, description }),
      info: (title, description) => push({ severity: 'info', title, description }),
    }),
    [push],
  )

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-50 flex w-full max-w-sm flex-col gap-2">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => {
            const styles = severityStyles[toast.severity]
            const Icon = ICONS[toast.severity]
            return (
              <motion.div
                key={toast.id}
                layout
                initial={{ opacity: 0, x: 40, scale: 0.96 }}
                animate={{ opacity: 1, x: 0, scale: 1 }}
                exit={{ opacity: 0, x: 40, scale: 0.96 }}
                transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
                className={cn(
                  'pointer-events-auto flex gap-3 rounded-lg border bg-panel/95 p-3.5 shadow-panel backdrop-blur',
                  styles.border,
                )}
              >
                <Icon className={cn('mt-0.5 h-4 w-4 shrink-0', styles.text)} strokeWidth={2} />
                <div className="min-w-0 flex-1">
                  <p className="text-xs font-semibold text-ink">{toast.title}</p>
                  {toast.description && (
                    <p className="mt-1 text-2xs leading-relaxed text-ink-2">
                      {toast.description}
                    </p>
                  )}
                </div>
                <button
                  type="button"
                  onClick={() => dismiss(toast.id)}
                  className="shrink-0 text-ink-3 transition-colors hover:text-ink"
                  aria-label="Dismiss"
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </motion.div>
            )
          })}
        </AnimatePresence>
      </div>
    </ToastContext.Provider>
  )
}

export function useToast(): ToastContextValue {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used inside a ToastProvider')
  }
  return context
}
