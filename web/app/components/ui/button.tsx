import { Button as ButtonPrimitive } from "@base-ui/react/button"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "cursor-pointer inline-flex min-h-10 items-center justify-center gap-2 whitespace-nowrap rounded-md border border-transparent text-sm font-medium transition-[background-color,border-color,color,box-shadow,transform] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg:not([class*='size-'])]:size-4 shrink-0 [&_svg]:shrink-0 outline-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive",
  {
    variants: {
      variant: {
        default:
          "border-primary/80 bg-primary text-primary-foreground shadow-[0_14px_34px_rgba(14,165,233,0.18)] hover:bg-primary/94 hover:shadow-[0_18px_40px_rgba(14,165,233,0.24)]",
        destructive:
          "border-destructive/70 bg-destructive text-white shadow-[0_14px_34px_rgba(225,29,72,0.18)] hover:bg-destructive/92 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40",
        outline:
          "border-border/80 bg-panel/88 text-foreground shadow-[0_10px_24px_rgba(15,23,42,0.08)] hover:bg-elevated",
        secondary:
          "border-border/70 bg-secondary text-secondary-foreground hover:bg-secondary/92",
        ghost:
          "border-transparent bg-transparent text-foreground/80 hover:bg-secondary hover:text-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "px-4 py-2 has-[>svg]:px-3",
        xs: "min-h-7 gap-1 rounded-md px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "min-h-9 gap-1.5 rounded-md px-3 has-[>svg]:px-2.5",
        lg: "min-h-11 rounded-[var(--radius-xl)] px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-7 rounded-[0.75rem] [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8 rounded-[0.875rem]",
        "icon-lg": "size-10 rounded-[var(--radius-lg)]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  ...props
}: ButtonPrimitive.Props & VariantProps<typeof buttonVariants>) {
  return (
    <ButtonPrimitive
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button, buttonVariants }
