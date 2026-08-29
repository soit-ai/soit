import { cn } from '@/lib/utils'

/**
 * The console's six-segment list-page template (v13 prototype workbench):
 * ① page head (title + actions + description) ② stat tiles ③ tabs
 * ④ filter bar ⑤ content panels ⑥ footer / pagination.
 * Slots render the prototype's structural classes; data-heavy content reuses
 * the shared Box suite (re-exported from ./index.ts) inside `children`.
 */
interface WorkbenchProps {
  title: React.ReactNode
  description?: React.ReactNode
  /** Right-aligned actions on the title row: range segments, export, create. */
  actions?: React.ReactNode
  /** ② stat tiles — usually a StatTileGrid. */
  tiles?: React.ReactNode
  /** ③ tab strip switching the page's data sources. */
  tabs?: React.ReactNode
  /** ④ quick filter chips and search. */
  filters?: React.ReactNode
  /** ⑤ the content panels. */
  children: React.ReactNode
  /** ⑥ pagination or a footnote row. */
  footer?: React.ReactNode
  className?: string
}

export function Workbench({
  title,
  description,
  actions,
  tiles,
  tabs,
  filters,
  children,
  footer,
  className,
}: WorkbenchProps) {
  return (
    <section className={className}>
      <div className="page-head">
        <h1>{title}</h1>
        <span className="spacer" />
        {actions}
        {description && <p>{description}</p>}
      </div>
      {tiles}
      {tabs}
      {filters && <div className="filters">{filters}</div>}
      {children}
      {footer}
    </section>
  )
}

/** Panel wrapper (prototype .panel / .panel-head). */
export function WorkbenchPanel({
  title,
  hint,
  actions,
  children,
  className,
}: {
  title?: React.ReactNode
  hint?: React.ReactNode
  actions?: React.ReactNode
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn('panel', className)}>
      {(title || hint || actions) && (
        <div className="panel-head">
          {title && <h2>{title}</h2>}
          {hint && <span className="hint">{hint}</span>}
          {actions && <span className="ml-auto flex items-center gap-2">{actions}</span>}
        </div>
      )}
      {children}
    </div>
  )
}
