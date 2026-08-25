import type { ReactNode } from 'react'

import { AlertTriangle, Info, ShieldAlert } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

type BoxAlertSeverity = 'info' | 'warning' | 'critical'

interface BoxAlertProps {
  severity: BoxAlertSeverity
  badge?: ReactNode
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}

const severityMap = {
  info: {
    icon: Info,
    container: 'border-primary/20 bg-primary/12 text-primary',
    iconClassName: 'text-primary',
    badge: 'border-primary/20 bg-primary/12 text-primary',
  },
  warning: {
    icon: AlertTriangle,
    container: 'border-warning/20 bg-warning/12 text-warning-foreground',
    iconClassName: 'text-warning-foreground',
    badge: 'border-warning/20 bg-warning/12 text-warning-foreground',
  },
  critical: {
    icon: ShieldAlert,
    container: 'border-danger/20 bg-danger/12 text-danger-foreground',
    iconClassName: 'text-danger-foreground',
    badge: 'border-danger/20 bg-danger/12 text-danger-foreground',
  },
} satisfies Record<BoxAlertSeverity, {
  icon: typeof Info
  container: string
  iconClassName: string
  badge: string
}>

export function BoxAlert({
  severity,
  badge,
  title,
  description,
  action,
  className,
}: BoxAlertProps) {
  const config = severityMap[severity]
  const Icon = config.icon

  return (
    <div className={cn('flex flex-col gap-3 rounded-lg border px-5 py-3 shadow-sm md:flex-row md:items-center md:justify-between', config.container, className)}>
      <div className="flex min-w-0 items-center gap-3">
        <Icon className={cn('h-5 w-5 shrink-0', config.iconClassName)} />
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-sm">
          <span className="font-semibold">{title}</span>
          {badge ? <Badge className={cn('h-6 rounded-md px-2 py-0 text-xs', config.badge)}>{badge}</Badge> : null}
          {description ? <span className="min-w-0 break-words text-muted-foreground">{description}</span> : null}
        </div>
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  )
}
