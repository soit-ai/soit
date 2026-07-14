import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface BoxShellProps {
  children: ReactNode
  className?: string
}

export function BoxShell({ children, className }: BoxShellProps) {
  return (
    <main className={cn('flex min-h-full min-w-0 flex-1 flex-col bg-background', className)}>
      <div className="mx-auto flex min-w-0 w-full flex-1 flex-col gap-4 px-5 py-6 lg:px-8">
        {children}
      </div>
    </main>
  )
}
