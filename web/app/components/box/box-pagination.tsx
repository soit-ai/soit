import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'

interface BoxPaginationProps {
  total: number
  pageSize: number
  currentPage: number
  pages: number[]
  labels?: {
    totalSuffix?: string
    pageSizeSuffix?: string
    goTo?: string
    page?: string
  }
  hasPrevious?: boolean
  hasNext?: boolean
  onPrevious?: () => void
  onNext?: () => void
  onPageChange?: (page: number) => void
  className?: string
}

export function BoxPagination({
  total,
  pageSize,
  currentPage,
  pages,
  labels,
  hasPrevious,
  hasNext,
  onPrevious,
  onNext,
  onPageChange,
  className,
}: BoxPaginationProps) {
  const totalSuffix = labels?.totalSuffix
  const pageSizeSuffix = labels?.pageSizeSuffix
  const goToLabel = labels?.goTo
  const pageLabel = labels?.page

  return (
    <div className={cn('flex flex-col gap-3 text-sm text-muted-foreground lg:flex-row lg:items-center lg:justify-between', className)}>
      <div><span className="font-semibold text-foreground">{total}</span>{totalSuffix ? <> {totalSuffix}</> : null}</div>
      <div className="flex flex-wrap items-center gap-4">
        <Button variant="outline" size="sm" className="h-9 min-w-[104px] border-border bg-panel text-foreground">
          {pageSize}{pageSizeSuffix ? <> {pageSizeSuffix}</> : null}
        </Button>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-8 w-8 text-muted-foreground"
            disabled={hasPrevious === false}
            onClick={onPrevious}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          {pages.map((page) => (
            <Button
              key={page}
              variant={page === currentPage ? 'outline' : 'ghost'}
              size="icon-sm"
              className={cn(
                'h-8 w-8',
                page === currentPage
                  ? 'border-primary/30 bg-primary/10 text-primary shadow-none'
                  : 'text-foreground',
              )}
              onClick={() => onPageChange?.(page)}
            >
              {page}
            </Button>
          ))}
          <Button
            variant="ghost"
            size="icon-sm"
            className="h-8 w-8 text-muted-foreground"
            disabled={hasNext === false}
            onClick={onNext}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
        {goToLabel || pageLabel ? (
          <div className="flex items-center gap-2">
            {goToLabel ? <span>{goToLabel}</span> : null}
            <Input value={currentPage} readOnly className="h-8 w-12 border-border bg-panel text-center" />
            {pageLabel ? <span>{pageLabel}</span> : null}
          </div>
        ) : null}
      </div>
    </div>
  )
}
