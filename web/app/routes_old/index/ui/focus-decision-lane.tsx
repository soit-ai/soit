import { ArrowRight, type LucideIcon } from 'lucide-react'

type FocusDecisionLaneItem = {
  primary: string
  secondary: string
  badge?: string
  badgeClassName?: string
}

type FocusDecisionLaneProps = {
  title: string
  metric: string
  hint?: string
  actionLabel: string
  icon: LucideIcon
  iconClassName: string
  items: FocusDecisionLaneItem[]
  onAction: () => void
}

export function FocusDecisionLane({
  title,
  metric,
  hint,
  actionLabel,
  icon: Icon,
  iconClassName,
  items,
  onAction,
}: FocusDecisionLaneProps) {
  return (
    <section className="rounded-[24px] border border-border bg-[linear-gradient(180deg,rgba(248,250,252,0.92)_0%,rgba(241,245,249,0.84)_100%)] p-4 dark:bg-[linear-gradient(180deg,rgba(15,23,42,0.7)_0%,rgba(15,23,42,0.48)_100%)]">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-[20px] border border-border bg-white/80 p-2.5 dark:bg-panel">
            <Icon className={`h-4 w-4 ${iconClassName}`} />
          </div>
          <div>
            <div className="text-sm font-medium">{title}</div>
            {hint && <div className="mt-1 text-xs text-muted-foreground">{hint}</div>}
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-semibold">{metric}</div>
        </div>
      </div>

      <div className="mt-4 grid gap-2.5">
        {items.map((item, index) => (
          <div
            key={`${item.primary}-${index}`}
            className="flex items-start justify-between gap-3 rounded-[20px] border border-border bg-white/82 px-3 py-2.5 dark:bg-panel"
          >
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{item.primary}</div>
              <div className="mt-1 truncate text-xs text-muted-foreground">{item.secondary}</div>
            </div>
            {item.badge && (
              <span
                className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium ${item.badgeClassName || 'border-border text-muted-foreground dark:border-border dark:text-muted-foreground'}`}
              >
                {item.badge}
              </span>
            )}
          </div>
        ))}
      </div>

      <button
        type="button"
        onClick={onAction}
        className="mt-4 flex w-full items-center justify-between rounded-[20px] border border-dashed border-border px-3 py-2.5 text-sm text-muted-foreground transition-colors hover:border-border hover:text-foreground dark:hover:text-white"
      >
        <span>{actionLabel}</span>
        <ArrowRight className="h-4 w-4" />
      </button>
    </section>
  )
}
