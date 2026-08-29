import type { CSSProperties, ComponentType } from 'react'

import { cn } from '@/lib/utils'

interface EmptyStateProps {
  icon?: ComponentType<{ className?: string; size?: number }>
  title: React.ReactNode
  description?: React.ReactNode
  /** Categorical accent for the glyph; defaults to the brand primary. */
  accent?: string
  /** CTA area — buttons or links. */
  children?: React.ReactNode
  className?: string
}

/** Prototype .stub — the dashed empty/coming-up placeholder card. */
export function EmptyState({ icon: Icon, title, description, accent, children, className }: EmptyStateProps) {
  const style = accent ? ({ '--c': accent } as CSSProperties) : undefined

  return (
    <div className={cn('stub', className)} style={style}>
      {Icon && (
        <div className="glyph">
          <Icon size={20} />
        </div>
      )}
      <h2>{title}</h2>
      {description && <p>{description}</p>}
      {children && <div className="mt-1.5 flex items-center gap-2">{children}</div>}
    </div>
  )
}
