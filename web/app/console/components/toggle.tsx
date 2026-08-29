import { cn } from '@/lib/utils'

/** Prototype .toggle — the 28x16 enable switch used in list rows. */
export function ConsoleToggle({
  on,
  onChange,
  label,
  className,
}: {
  on: boolean
  onChange?: (next: boolean) => void
  label?: string
  className?: string
}) {
  return (
    <span
      role="switch"
      aria-checked={on}
      aria-label={label}
      tabIndex={0}
      className={cn('toggle', on && 'on', className)}
      onClick={(event) => {
        event.stopPropagation()
        onChange?.(!on)
      }}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onChange?.(!on)
        }
      }}
    />
  )
}
