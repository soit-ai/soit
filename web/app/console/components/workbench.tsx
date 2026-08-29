import { cn } from '@/lib/utils'

/**
 * The console's six-segment list-page template (v13 prototype workbench):
 * ① page head (title + actions + description) ② stat tiles ③ tabs
 * ④ filter bar ⑤ content panels ⑥ footer / pagination.
 * Data-heavy slots reuse the Box suite (BoxDataTable / MetricStrip /
 * BoxPagination, re-exported from ./index.ts) inside `children` and `footer`.
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
    <section className={cn('mx-auto w-full max-w-[1240px]', className)}>
      <div className="mb-4.5 flex flex-wrap items-center gap-3">
        <h1 className="text-lg font-semibold tracking-tight">{title}</h1>
        <span className="flex-1" />
        {actions}
        {description && (
          <p className="-mt-1.5 order-10 w-full text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      {tiles}
      {tabs}
      {filters && <div className="mb-3 flex flex-wrap items-center gap-2">{filters}</div>}
      {children}
      {footer}
    </section>
  )
}

/** Panel wrapper for workbench content: bordered surface with the depth layer. */
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
    <div className={cn('console-depth rounded-md border border-border bg-panel', className)}>
      {(title || hint || actions) && (
        <div className="flex items-center gap-2.5 border-b border-border px-3.5 py-2.5">
          {title && <h2 className="text-xs font-semibold">{title}</h2>}
          {hint && <span className="font-mono text-[11px] text-muted-foreground/70">{hint}</span>}
          {actions && <span className="ml-auto flex items-center gap-2">{actions}</span>}
        </div>
      )}
      {children}
    </div>
  )
}
