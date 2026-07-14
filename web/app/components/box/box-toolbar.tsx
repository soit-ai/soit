import type { ReactNode } from 'react'

import { ChevronDown, RefreshCw, Search, SlidersHorizontal } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

export interface BoxToolbarTab {
  id: string
  label: string
  count?: number | string
}

interface BoxToolbarProps {
  tabs?: BoxToolbarTab[]
  activeTab?: string
  onTabChange?: (tabId: string) => void
  searchValue?: string
  onSearchChange?: (value: string) => void
  searchPlaceholder?: string
  filterLabel?: string
  timeLabel?: string
  refreshLabel?: string
  onRefresh?: () => void
  actions?: ReactNode
  className?: string
}

export function BoxToolbar({
  tabs = [],
  activeTab,
  onTabChange,
  searchValue = '',
  onSearchChange,
  searchPlaceholder,
  filterLabel,
  timeLabel,
  refreshLabel,
  onRefresh,
  actions,
  className,
}: BoxToolbarProps) {
  return (
    <div className={cn('flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between', className)}>
      {tabs.length ? (
        <div className="flex max-w-full flex-wrap items-center gap-1 rounded-lg border border-border bg-panel p-1 shadow-sm">
          {tabs.map((tab) => {
            const selected = activeTab === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => onTabChange?.(tab.id)}
                className={cn(
                  'flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
                  selected && 'bg-primary/10 text-primary shadow-[inset_0_0_0_1px_rgba(37,99,235,0.18)]',
                )}
              >
                <span>{tab.label}</span>
                {tab.count !== undefined ? (
                  <span className={cn('rounded-full px-2 py-0.5 text-xs', selected ? 'bg-background text-primary' : 'bg-muted text-muted-foreground')}>
                    {tab.count}
                  </span>
                ) : null}
              </button>
            )
          })}
        </div>
      ) : <div />}

      <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center lg:justify-end">
        <div className="relative min-w-[240px] sm:w-[310px]">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchValue}
            onChange={(event) => onSearchChange?.(event.target.value)}
            placeholder={searchPlaceholder}
            className="h-10 border-border bg-panel pl-9 text-sm shadow-sm"
          />
        </div>
        {filterLabel ? (
          <Button variant="outline" size="sm" className="h-10 border-border bg-panel px-4 text-foreground shadow-sm">
            <SlidersHorizontal className="h-4 w-4" />
            {filterLabel}
          </Button>
        ) : null}
        {timeLabel ? (
          <Button variant="outline" size="sm" className="h-10 border-border bg-panel px-4 text-foreground shadow-sm">
            {timeLabel}
            <ChevronDown className="h-4 w-4" />
          </Button>
        ) : null}
        {refreshLabel ? (
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={refreshLabel}
            className="h-10 w-10 border-border bg-panel text-foreground shadow-sm"
            onClick={onRefresh}
          >
            <RefreshCw className="h-4 w-4" />
          </Button>
        ) : null}
        {actions}
      </div>
    </div>
  )
}
