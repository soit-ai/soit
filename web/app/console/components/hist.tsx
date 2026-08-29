import { cn } from '@/lib/utils'

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
