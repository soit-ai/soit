import { IconSearch } from './icons'

import { cn } from '@/lib/utils'

/** Prototype .fchip — quick filter chip, optionally with a mono count. */
export function FilterChip({
  active,
  count,
  className,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  active?: boolean
  count?: React.ReactNode
}) {
  return (
    <button type="button" className={cn('fchip', active && 'on', className)} {...props}>
      {children}
      {count != null && <span className="mono dimmer">{count}</span>}
    </button>
  )
}

/** Prototype .fsearch — the inline filter search box. */
export function FilterSearch({
  className,
  ...props
}: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <div className={cn('fsearch', className)}>
      <IconSearch size={12} style={{ color: 'var(--faint)' }} />
      <input {...props} />
    </div>
  )
}

/** Prototype .seg — the mono segmented range control (1h / 24h / 7d / 30d). */
export function Seg<T extends string>({
  options,
  value,
  onChange,
  className,
}: {
  options: readonly T[] | readonly { value: T; label: React.ReactNode }[]
  value: T
  onChange: (value: T) => void
  className?: string
}) {
  return (
    <div className={cn('seg', className)}>
      {options.map((option) => {
        const opt = typeof option === 'string' ? { value: option, label: option } : option
        return (
          <button
            key={opt.value}
            type="button"
            className={cn(opt.value === value && 'on')}
            onClick={() => onChange(opt.value)}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
