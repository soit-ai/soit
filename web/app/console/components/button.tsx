import { cn } from '@/lib/utils'

/**
 * Console button (prototype .btn), per the v13 flat spec: solid fills, no
 * gradients, no drop shadows; primary hover goes one stop darker
 * (--primary-press). The 0.5px press offset is feedback, not skeuomorphism.
 */
type ConsoleButtonVariant = 'default' | 'primary' | 'ghost'

interface ConsoleButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ConsoleButtonVariant
  size?: 'default' | 'sm'
}

export function ConsoleButton({
  className,
  variant = 'default',
  size = 'default',
  type,
  ...props
}: ConsoleButtonProps) {
  return (
    <button
      type={type ?? 'button'}
      className={cn(
        'btn',
        variant === 'primary' && 'primary',
        variant === 'ghost' && 'ghost',
        size === 'sm' && 'h-6! px-2.5! text-[11px]!',
        className,
      )}
      {...props}
    />
  )
}
