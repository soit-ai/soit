import type { CSSProperties, ComponentType } from 'react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: ComponentType<{ className?: string }>
  title: React.ReactNode
  description?: React.ReactNode
  /** Categorical accent for the glyph; defaults to the brand primary. */
  accent?: string
  /** CTA area — buttons or links. */
  children?: React.ReactNode
  className?: string
}

export function EmptyState({ icon: Icon, title, description, accent, children, className }: EmptyStateProps) {
  const style = accent ? ({ '--c': accent } as CSSProperties) : undefined

  return (
    <div
      className={cn(
        'flex flex-col items-center gap-2.5 rounded-lg border border-dashed border-border-strong px-5 py-14 text-center',
        className,
      )}
      style={style}
    >
      {Icon && (
        <div
          className="grid size-11 place-items-center rounded-md"
          style={{
            background: 'color-mix(in srgb, var(--c, var(--primary)) 12%, transparent)',
            color: 'var(--c, var(--primary))',
          }}
        >
          <Icon className="size-5" />
        </div>
      )}
      <h2 className="text-[15px] font-semibold">{title}</h2>
      {description && <p className="max-w-105 text-xs text-muted-foreground">{description}</p>}
      {children && <div className="mt-1.5 flex items-center gap-2">{children}</div>}
    </div>
  )
}
