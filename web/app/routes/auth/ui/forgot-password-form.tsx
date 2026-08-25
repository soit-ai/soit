import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Link } from "@/components/ui/link"

export function ForgotPasswordForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<'div'>) {
  return (
    <div className={cn('flex flex-col gap-6', className)} {...props}>
      <div className="space-y-2 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-foreground dark:text-white">
          Forgot your password?
        </h2>
        <p className="text-sm leading-6 text-muted-foreground">
          Password reset is not available yet. Please contact your administrator.
        </p>
      </div>
      <div className="grid gap-4">
        <div className="text-center text-sm text-muted-foreground">
          Remember your password?{' '}
          <Link to="/sign-in" className="font-medium text-foreground underline underline-offset-4 dark:text-white">
            Sign in
          </Link>
        </div>
        <Button className="h-11 w-full rounded-lg" asChild>
          <Link to="/sign-in">Back to sign in</Link>
        </Button>
      </div>
    </div>
  )
}
