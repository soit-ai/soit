import { Activity, AlertTriangle, CircleDollarSign, ShieldCheck, Waypoints } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { WorkspaceSummary } from '@/services/observability-service'

type WorkspaceSummaryProps = {
  summary?: WorkspaceSummary
}

const items = [
  { key: 'run_count', label: 'Runs', icon: Waypoints },
  { key: 'failed_run_count', label: 'Failed Runs', icon: AlertTriangle },
  { key: 'active_run_count', label: 'Active Runs', icon: Activity },
  { key: 'pending_approvals', label: 'Pending Approvals', icon: ShieldCheck },
  { key: 'total_cost_usd', label: 'Cost (USD)', icon: CircleDollarSign },
] as const

export function WorkspaceSummaryCards({ summary }: WorkspaceSummaryProps) {
  return (
    <div className="grid gap-4 lg:grid-cols-5">
      {items.map((item) => {
        const Icon = item.icon
        const value = summary ? summary[item.key] : '...'
        return (
          <Card key={item.key}>
            <CardHeader className="pb-2">
              <CardDescription>{item.label}</CardDescription>
              <CardTitle className="flex items-center gap-2 text-2xl">
                <Icon className="h-5 w-5 text-sky-500" />
                {item.key === 'total_cost_usd' && typeof value === 'number' ? value.toFixed(2) : value}
              </CardTitle>
            </CardHeader>
            {item.key === 'pending_approvals' && (
              <CardContent className="pt-0 text-xs text-muted-foreground">
                Feedback events: {summary?.feedback_count ?? '...'}
              </CardContent>
            )}
          </Card>
        )
      })}
    </div>
  )
}
