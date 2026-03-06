import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Link } from "@/components/ui/link"

export function ForgotPasswordForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<"form">) {
  return (
    <div className={cn("flex flex-col gap-6", className)} {...props}>
      <div className="flex flex-col items-center gap-2 text-center">
        <h2 className="text-xl font-bold">Forgot your password?</h2>
        <p className="text-balance text-sm text-muted-foreground">
          Password reset is not available yet. Please contact your administrator.
        </p>
      </div>
      <div className="grid gap-6">
        <div className="text-center text-sm">
          Remember your password?{" "}
          <Link to="/sign-in" className="underline underline-offset-4">
            Sign in
          </Link>
        </div>
        <Button className="w-full" asChild>
          <Link to="/sign-in">Back to sign in</Link>
        </Button>
      </div>
      <div className="text-balance text-center text-xs text-muted-foreground [&_a]:underline [&_a]:underline-offset-4 [&_a]:hover:text-primary">
        By clicking continue, you agree to our <a href="#">Terms of Service</a>{" "}
        and <a href="#">Privacy Policy</a>.
      </div>
    </div>
  )
}
