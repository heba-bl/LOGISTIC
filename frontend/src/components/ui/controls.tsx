/** Form and action primitives shared by every operational screen. */

import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { Loader2 } from 'lucide-react'

import { useI18n } from '@/i18n/I18nProvider'
import { cn } from '@/utils/cn'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'success'

const VARIANTS: Record<Variant, string> = {
  primary: 'border-accent/40 bg-accent-dim text-accent hover:border-accent/70 hover:bg-accent/20',
  secondary: 'border-line bg-elevated text-ink-2 hover:border-line-strong hover:text-ink',
  ghost: 'border-transparent text-ink-2 hover:bg-elevated hover:text-ink',
  danger: 'border-crit/40 bg-crit/10 text-crit-soft hover:border-crit/70 hover:bg-crit/20',
  success: 'border-ok/40 bg-ok/10 text-ok-soft hover:border-ok/70 hover:bg-ok/20',
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  loading?: boolean
  icon?: ReactNode
  size?: 'sm' | 'md'
}

export function Button({
  variant = 'secondary',
  loading = false,
  icon,
  size = 'md',
  className,
  children,
  disabled,
  ...props
}: ButtonProps) {
  return (
    <button
      type="button"
      disabled={disabled || loading}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-45',
        size === 'sm' ? 'px-2.5 py-1.5 text-2xs' : 'px-3.5 py-2 text-xs',
        VARIANTS[variant],
        className,
      )}
      {...props}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : icon}
      {children}
    </button>
  )
}

interface FieldProps {
  label: string
  hint?: string
  error?: string | null
  required?: boolean
  children: ReactNode
  className?: string
}

export function Field({ label, hint, error, required, children, className }: FieldProps) {
  return (
    <label className={cn('block', className)}>
      <span className="eyebrow flex items-center gap-1">
        {label}
        {required && <span className="text-crit">*</span>}
      </span>
      <div className="mt-1.5">{children}</div>
      {error ? (
        <span className="mt-1 block text-2xs text-crit-soft">{error}</span>
      ) : (
        hint && <span className="mt-1 block text-2xs text-ink-3">{hint}</span>
      )}
    </label>
  )
}

const CONTROL_BASE =
  'w-full rounded-lg border border-line bg-elevated px-3 py-2 text-xs text-ink ' +
  'placeholder:text-ink-3 transition-colors hover:border-line-strong ' +
  'focus:border-accent/60 focus:outline-none disabled:cursor-not-allowed disabled:opacity-50'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={cn(CONTROL_BASE, className)} {...props} />
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={cn(CONTROL_BASE, 'resize-y', className)} rows={3} {...props} />
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cn(CONTROL_BASE, 'cursor-pointer', className)} {...props}>
      {children}
    </select>
  )
}

/** Placeholder shown when a list is legitimately empty. */
export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      {icon && (
        <div className="grid h-11 w-11 place-items-center rounded-xl border border-line bg-elevated text-ink-3">
          {icon}
        </div>
      )}
      <div>
        <p className="text-xs font-semibold text-ink">{title}</p>
        {description && <p className="mt-1 text-2xs text-ink-3">{description}</p>}
      </div>
      {action}
    </div>
  )
}

/** Loading placeholder that keeps the layout stable. */
export function Skeleton({ className }: { className?: string }) {
  return <div className={cn('animate-pulse rounded-md bg-line/60', className)} />
}

export function LoadingPanel({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-2 p-5">
      {Array.from({ length: rows }).map((_, index) => (
        <Skeleton key={index} className="h-9 w-full" />
      ))}
    </div>
  )
}

export function ErrorPanel({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const { t } = useI18n()
  return (
    <EmptyState
      title={t('common.error')}
      description={message}
      action={
        onRetry ? (
          <Button variant="secondary" onClick={onRetry}>
            Retry
          </Button>
        ) : undefined
      }
    />
  )
}
