import type { ComponentType, ReactNode } from 'react'

import { BarChart3, Edit, MoreHorizontal, RefreshCw, Settings2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

import { ProviderAppIcon } from './icon'

export type ModelOverviewMetric = {
  id: string
  label: string
  value: string
  delta?: string
  trend?: number[]
  icon: ComponentType<{ className?: string }>
  tone?: 'blue' | 'green' | 'amber' | 'red' | 'cyan'
}

export type ModelLibraryRow = {
  id: string
  providerId?: string
  name: string
  version: string
  provider: string
  providerKind?: string
  type: string
  status: 'available' | 'disabled' | 'abnormal'
  context: string
  price: string
  todayCalls: string
  avgLatency: string
  updatedAt: string
  owner: string
}

export type ProviderTableRow = {
  id: string
  name: string
  kind: string
  status: 'online' | 'disabled' | 'error'
  availableModels: number
  modelTypes: string[]
  region: string
  monthCalls: string
  monthCost: string
  quotaLabel: string
  quotaPercent: number
  availability: string
  lastSync: string
  owner: string
}

export type QuotaReminderRow = {
  id: string
  label: string
  used: string
  remaining: string
  status: 'normal' | 'warning'
  percent: number
}

const statusClassName = {
  available: 'border-success/20 bg-success/12 text-success-foreground',
  online: 'border-success/20 bg-success/12 text-success-foreground',
  normal: 'border-success/20 bg-success/12 text-success-foreground',
  disabled: 'border-border bg-muted text-muted-foreground',
  abnormal: 'border-danger/20 bg-danger/12 text-danger-foreground',
  error: 'border-danger/20 bg-danger/12 text-danger-foreground',
  warning: 'border-warning/20 bg-warning/12 text-warning-foreground',
} satisfies Record<string, string>

export function WorkbenchPanel({ title, action, children, className }: { title: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cn('rounded-lg border border-border bg-panel p-5 shadow-sm', className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        {action ? <div className="shrink-0">{action}</div> : null}
      </div>
      {children}
    </section>
  )
}

export function ModelNameCell({ row }: { row: ModelLibraryRow }) {
  return (
    <div className="flex min-w-[240px] items-center gap-3">
      <ProviderAppIcon name={row.providerKind || row.provider} size={32} />
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <span className="truncate font-semibold text-foreground">{row.name}</span>
          <Badge variant="secondary" className="rounded-md px-2 py-0 text-[11px]">{row.version}</Badge>
        </div>
        <div className="mt-0.5 text-xs text-muted-foreground">{row.type}</div>
      </div>
    </div>
  )
}

export function ProviderNameCell({ row }: { row: ProviderTableRow }) {
  return (
    <div className="flex min-w-[210px] items-center gap-3">
      <ProviderAppIcon name={row.kind} size={32} />
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.name}</div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{row.kind}</div>
      </div>
    </div>
  )
}

export function StatusBadge({ label, status }: { label: ReactNode; status: keyof typeof statusClassName }) {
  return <Badge className={cn('rounded-md border px-2 py-1', statusClassName[status])}>{label}</Badge>
}

export function TypeBadges({ values }: { values: string[] }) {
  if (!values.length) return <span className="text-muted-foreground">--</span>

  return (
    <div className="flex min-w-[140px] flex-wrap gap-1.5">
      {values.slice(0, 3).map((value) => (
        <Badge key={value} variant="secondary" className="rounded-md px-2 py-0.5 text-[11px]">
          {value}
        </Badge>
      ))}
      {values.length > 3 ? <Badge variant="outline" className="rounded-md px-2 py-0.5 text-[11px]">+{values.length - 3}</Badge> : null}
    </div>
  )
}

export function QuotaProgress({ label, value }: { label: string; value: number }) {
  const tone = value >= 80 ? 'bg-warning' : 'bg-primary'

  return (
    <div className="min-w-[150px] space-y-1">
      <div className="text-xs font-medium text-foreground">{label}</div>
      <div className="h-2 overflow-hidden rounded-full bg-muted">
        <div className={cn('h-full rounded-full transition-all', tone)} style={{ width: `${Math.min(Math.max(value, 0), 100)}%` }} />
      </div>
    </div>
  )
}

export function OperationButtons({
  onReport,
  onEdit,
  onRefresh,
  onMore,
}: {
  onReport?: () => void
  onEdit?: () => void
  onRefresh?: () => void
  onMore?: () => void
}) {
  return (
    <div className="flex items-center gap-2">
      {onReport ? (
        <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none" onClick={onReport}>
          <BarChart3 className="h-3.5 w-3.5" />
        </Button>
      ) : null}
      {onEdit ? (
        <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none" onClick={onEdit}>
          <Edit className="h-3.5 w-3.5" />
        </Button>
      ) : null}
      {onRefresh ? (
        <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none" onClick={onRefresh}>
          <RefreshCw className="h-3.5 w-3.5" />
        </Button>
      ) : null}
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none" onClick={onMore}>
        {onMore ? <MoreHorizontal className="h-3.5 w-3.5" /> : <Settings2 className="h-3.5 w-3.5" />}
      </Button>
    </div>
  )
}
