import { cn } from '@/lib/utils'

/** Slots in an outcome strip; the workbench rows carry this many recent outcomes. */
export const HIST_SLOTS = 28

/**
 * Turn run statuses ordered oldest first into a strip pattern: the newest run
 * lands on the right and missing history pads the left with empty slots.
 */
export function outcomePattern(statuses: readonly string[], slots = HIST_SLOTS): string {
  return statuses
    .slice(-slots)
    .map((status) =>
      status === 'succeeded'
        ? 'p'
        : status === 'failed' || status === 'cancelled' || status === 'canceled'
          ? 'f'
          : 'd',
    )
    .join('')
    .padStart(slots, 'e')
}

/**
 * Prototype .hist — the outcome history strip. Pattern chars:
 * p = pass, d = degraded, f = failed, e = empty slot.
 */
export function Hist({ pattern, className, label }: { pattern: string; className?: string; label?: string }) {
  return (
    <span className={cn('hist', className)} aria-label={label}>
      {pattern.split('').map((char, index) => (
        <i key={index} className={char === 'p' ? undefined : char === 'd' ? 'd' : char === 'f' ? 'f' : 'e'} />
      ))}
    </span>
  )
}
