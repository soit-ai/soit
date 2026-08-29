import * as React from "react"
import { mergeProps } from "@base-ui/react/merge-props"
import { useRender } from "@base-ui/react/use-render"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex w-fit shrink-0 items-center justify-center gap-1 overflow-hidden rounded-full border px-2.5 py-1 text-[11px] font-medium whitespace-nowrap [&>svg]:size-3 [&>svg]:pointer-events-none focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px] aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40 aria-invalid:border-destructive transition-[background-color,border-color,color]",
  {
    variants: {
      variant: {
        default: "border-primary/15 bg-primary/10 text-primary [a&]:hover:bg-primary/14",
        secondary:
          "border-border/70 bg-secondary text-secondary-foreground [a&]:hover:bg-secondary/92",
        destructive:
          "border-destructive/15 bg-destructive/10 text-destructive [a&]:hover:bg-destructive/14 focus-visible:ring-destructive/20 dark:focus-visible:ring-destructive/40",
        success:
          "border-success/20 bg-success/12 text-success-foreground [a&]:hover:bg-success/18",
        warning:
          "border-warning/20 bg-warning/16 text-warning-foreground [a&]:hover:bg-warning/22",
        info:
          "border-info/20 bg-info/12 text-info-foreground [a&]:hover:bg-info/18",
        outline:
          "border-border/80 bg-panel/72 text-foreground [a&]:hover:bg-elevated",
        ghost: "border-transparent bg-transparent [a&]:hover:bg-accent [a&]:hover:text-accent-foreground",
        link: "text-primary underline-offset-4 [a&]:hover:underline",
        muted: "border-transparent bg-muted text-muted-foreground [a&]:hover:bg-muted/90",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant = "default",
  render,
  ...props
}: useRender.ComponentProps<"span"> & VariantProps<typeof badgeVariants>) {
  return useRender({
    defaultTagName: "span",
    render,
    props: mergeProps<"span">(
      {
        "data-slot": "badge",
        "data-variant": variant,
        className: cn(badgeVariants({ variant }), className),
      } as React.ComponentProps<"span">,
      props
    ),
  })
}

export { Badge, badgeVariants }
