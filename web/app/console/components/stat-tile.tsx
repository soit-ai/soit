import { cn } from '@/lib/utils'

export type StatTileDelta = 'up' | 'down' | 'flat'

interface StatTileProps {
  label: React.ReactNode
  /** Rendered in mono; pass a formatted string ("1,284", "$12.40", "98.2%"). */
  value: React.ReactNode
  /** Marks the value as not applicable / no data yet. */
  na?: boolean
  sub?: React.ReactNode
  delta?: { direction: StatTileDelta; label: React.ReactNode }
  className?: string
}

/* Delta colour is status semantics (better/worse), so status tokens apply. */
const DELTA_CLASS: Record<StatTileDelta, string> = {
  up: 'bg-success/12 text-success-foreground',
  down: 'bg-danger/12 text-danger-foreground',
  flat: 'bg-info/12 text-info-foreground',
}

export function StatTile({ label, value, na, sub, delta, className }: StatTileProps) {
  return (
    <div
      className={cn(
        'console-depth relative overflow-hidden rounded-md border border-border bg-panel px-3.5 py-3',
        className,
      )}
    >
      <div className="text-[10.5px] font-semibold uppercase tracking-[0.09em] text-muted-foreground/70">
        {label}
      </div>
      <div
        className={cn(
          'mt-1.5 font-mono text-[21px] font-semibold tracking-tight',
          na && 'text-muted-foreground/70',
        )}
      >
        {value}
      </div>
      {(sub || delta) && (
        <div className="mt-1 flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
          {delta && (
            <span className={cn('rounded-[5px] px-1.5 py-px text-[10.5px]', DELTA_CLASS[delta.direction])}>
              {delta.label}
            </span>
          )}
          {sub}
        </div>
      )}
    </div>
  )
}

export function StatTileGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn('mb-3 grid grid-cols-2 gap-3 xl:grid-cols-4', className)}>{children}</div>
  )
}
