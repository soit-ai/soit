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
    container: 'border-blue-200 bg-blue-50 text-blue-950 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-100',
    iconClassName: 'text-blue-600 dark:text-blue-300',
    badge: 'border-blue-200 bg-blue-100 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  },
  warning: {
    icon: AlertTriangle,
    container: 'border-amber-200 bg-amber-50 text-amber-950 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-100',
    iconClassName: 'text-amber-600 dark:text-amber-300',
    badge: 'border-amber-200 bg-amber-100 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200',
  },
  critical: {
    icon: ShieldAlert,
    container: 'border-red-200 bg-red-50 text-red-950 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-100',
    iconClassName: 'text-red-600 dark:text-red-300',
    badge: 'border-red-200 bg-red-100 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
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
