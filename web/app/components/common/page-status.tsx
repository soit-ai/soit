import type { ComponentType } from 'react'
import { AlertCircle, Inbox, Loader2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type PageStatusVariant = 'loading' | 'empty' | 'error'

interface PageStatusProps {
  variant: PageStatusVariant
  title: string
  description: string
  actionLabel?: string
  onAction?: () => void
  className?: string
}

const iconMap = {
  loading: Loader2,
  empty: Inbox,
  error: AlertCircle,
} satisfies Record<PageStatusVariant, ComponentType<{ className?: string }>>

const containerClassNameMap = {
  loading: 'border-border bg-muted/30 text-muted-foreground',
  empty: 'border-dashed border-border bg-background text-muted-foreground',
  error: 'border-destructive/40 bg-destructive/5 text-destructive',
} satisfies Record<PageStatusVariant, string>

const iconClassNameMap = {
  loading: 'animate-spin text-muted-foreground',
  empty: 'text-muted-foreground',
  error: 'text-destructive',
} satisfies Record<PageStatusVariant, string>

export function PageStatus({
  variant,
  title,
  description,
  actionLabel,
  onAction,
  className,
}: PageStatusProps) {
  const Icon = iconMap[variant]

  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border px-6 py-10 text-center',
        containerClassNameMap[variant],
        className,
      )}
    >
      <div className="flex h-12 w-12 items-center justify-center rounded-full border border-current/15 bg-background/70">
        <Icon className={cn('h-5 w-5', iconClassNameMap[variant])} />
      </div>
      <div className="space-y-1">
        <div className="text-sm font-medium text-foreground">{title}</div>
        <div className="max-w-xl text-sm text-muted-foreground">{description}</div>
      </div>
      {actionLabel && onAction && (
        <Button variant={variant === 'error' ? 'destructive' : 'outline'} onClick={onAction}>
          {actionLabel}
        </Button>
      )}
    </div>
  )
}
