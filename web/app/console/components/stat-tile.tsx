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
  /** Optional sparkline or decoration, absolutely positioned bottom-right. */
  spark?: React.ReactNode
  className?: string
}

/** Prototype .tile — label / mono value / sub row with a status-toned delta. */
export function StatTile({ label, value, na, sub, delta, spark, className }: StatTileProps) {
  return (
    <div className={cn('tile', className)}>
      <div className="lbl">{label}</div>
      <div className={cn('val', na && 'na')}>{value}</div>
      {(sub || delta) && (
        <div className="sub">
          {delta && <span className={cn('delta', delta.direction)}>{delta.label}</span>}
          {sub}
        </div>
      )}
      {spark}
    </div>
  )
}

/** Prototype .tiles — the four-up stat grid above a workbench table. */
export function StatTileGrid({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('tiles', className)}>{children}</div>
}
