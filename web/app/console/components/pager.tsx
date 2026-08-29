import { cn } from '@/lib/utils'

import { ConsoleButton } from './button'

/**
 * Prototype .pager — the mono footer row of a panel. Either a plain note
 * (children only) or a paged summary with prev/next controls.
 */
export function Pager({
  summary,
  onPrev,
  onNext,
  prevDisabled,
  nextDisabled,
  prevLabel = '‹ Prev',
  nextLabel = 'Next ›',
  children,
  className,
  style,
}: {
  summary?: React.ReactNode
  onPrev?: () => void
  onNext?: () => void
  prevDisabled?: boolean
  nextDisabled?: boolean
  prevLabel?: React.ReactNode
  nextLabel?: React.ReactNode
  children?: React.ReactNode
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={cn('pager', className)} style={style}>
      {summary != null && <span>{summary}</span>}
      {children}
      <span className="spacer" />
      {onPrev && (
        <ConsoleButton size="sm" disabled={prevDisabled} onClick={onPrev}>
          {prevLabel}
        </ConsoleButton>
      )}
      {onNext && (
        <ConsoleButton size="sm" disabled={nextDisabled} onClick={onNext}>
          {nextLabel}
        </ConsoleButton>
      )}
    </div>
  )
}
