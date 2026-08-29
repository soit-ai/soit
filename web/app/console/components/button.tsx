import { cva, type VariantProps } from 'class-variance-authority'

import { cn } from '@/lib/utils'

/**
 * Console button, per the v13 flat spec: solid fills, no gradients, no drop
 * shadows; primary hover goes one stop darker (--primary-press). The 0.5px
 * press offset is feedback, not skeuomorphism, and stays.
 * Shared shadcn primitives keep their own Button; console-authored screens
 * use this one.
 */
const consoleButtonVariants = cva(
  'inline-flex h-[30px] cursor-pointer items-center justify-center gap-1.5 whitespace-nowrap rounded-[7px] px-3 text-xs font-semibold outline-none transition-colors focus-visible:ring-[3px] focus-visible:ring-ring/50 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-3.5 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default: 'border border-border bg-panel text-foreground hover:border-border-strong hover:bg-raised',
        primary: 'bg-primary text-primary-foreground hover:bg-primary-press',
        ghost: 'text-muted-foreground hover:bg-hover-wash hover:text-foreground',
      },
      size: {
        default: '',
        sm: 'h-6 px-2.5 text-[11.5px]',
        icon: 'size-[30px] px-0',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  },
)

interface ConsoleButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof consoleButtonVariants> {}

export function ConsoleButton({ className, variant, size, type, ...props }: ConsoleButtonProps) {
  return (
    <button
      type={type ?? 'button'}
      className={cn(consoleButtonVariants({ variant, size }), className)}
      {...props}
    />
  )
}
