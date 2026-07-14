import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface BoxPageHeaderProps {
  title: ReactNode
  description?: ReactNode
  action?: ReactNode
  className?: string
}

export function BoxPageHeader({
  title,
  description,
  action,
  className,
}: BoxPageHeaderProps) {
  return (
    <div className={cn('flex flex-col gap-4 md:flex-row md:items-start md:justify-between', className)}>
      <div className="min-w-0 space-y-1">
        <h1 className="text-[22px] font-semibold leading-8 text-foreground">{title}</h1>
        {description ? (
          <p className="text-wrap break-words text-sm font-medium leading-5 text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action ? <div className="flex shrink-0 items-center gap-2">{action}</div> : null}
    </div>
  )
}
