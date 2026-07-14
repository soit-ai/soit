import { ArrowRight, KeyRound, Loader2, LockKeyhole, Mail, ShieldCheck } from 'lucide-react'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useForm } from 'react-hook-form'
import { useMutation } from '@/hooks/use-query'
import { authLogin } from '@/services/auth-service'
import { useNavigate } from '@/hooks/use-navigate'
import { storage } from '@/utils/storage'
import { toast } from 'sonner'
import { type LoginRequest, type TokenResponse } from '@/services/auth-service'
import { Link } from '@/components/ui/link'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'

export const LoginForm = ({ className, ...props }: React.ComponentPropsWithoutRef<'form'>) => {
  const navigate = useNavigate()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginRequest>()

  // Login mutation
  const loginMutation = useMutation<TokenResponse, Error, LoginRequest>({
    mutationKey: ['login'],
    mutationFn: (data) => authLogin(data),
    onSuccess: async (data) => {
      storage.set('token', data.access_token)
      if (data.workspace_id) {
        storage.set('workspace_id', data.workspace_id)
      } else {
        storage.delete('workspace_id')
      }
      try {
        const currentUser = await getCurrentUser()
        setCurrentUser(currentUser)
      } catch (error) {
        console.warn('Failed to sync current user after login:', error)
      }
      toast.success('Login successful')
      navigate('/')
    },
    onError: (error) => {
      toast.error('Login failed. Please check your credentials.')
    },
  })

  const onSubmit = (data: LoginRequest) => {
    loginMutation.mutate({
      email: data.email,
      password: data.password,
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className={cn('flex flex-col gap-5', className)} {...props}>
      <div className="space-y-3">
        <div className="inline-flex items-center gap-2 rounded-[0.5rem] border border-emerald-200/80 bg-emerald-50 px-3 py-2 text-xs font-medium text-emerald-700 dark:border-emerald-300/20 dark:bg-emerald-300/10 dark:text-emerald-100">
          <ShieldCheck className="h-4 w-4" />
          Secure SOIT workspace
        </div>
        <div className="space-y-2">
          <h2 className="text-2xl font-semibold text-slate-950 dark:text-white">Sign in to SOIT</h2>
          <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
            Access agents, knowledge, workflows, and runtime telemetry from one workspace.
          </p>
        </div>
      </div>
      <div className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor="email" className="text-sm text-slate-700 dark:text-slate-200">
            Email
          </Label>
          <div className="relative">
            <Mail className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <Input
              id="email"
              type="email"
              placeholder="name@company.com"
              autoComplete="email"
              aria-invalid={Boolean(errors.email)}
              className="h-12 rounded-[0.5rem] border-slate-200/90 bg-slate-50/80 pl-10 text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)] placeholder:text-slate-400 dark:border-white/10 dark:bg-white/6 dark:text-white dark:shadow-none"
              {...register('email', {
                required: 'Email is required',
                pattern: {
                  value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                  message: 'Invalid email address',
                },
              })}
            />
          </div>
          {errors.email && (
            <p role="alert" className="text-sm text-red-500">
              {errors.email.message}
            </p>
          )}
        </div>
        <div className="grid gap-2">
          <div className="flex items-center">
            <Label htmlFor="password" className="text-sm text-slate-700 dark:text-slate-200">
              Password
            </Label>
            <Link
              to="/forgot-password"
              className="ml-auto text-sm font-medium text-slate-500 underline-offset-4 hover:text-slate-950 hover:underline dark:text-slate-400 dark:hover:text-white"
            >
              Forgot your password?
            </Link>
          </div>
          <div className="relative">
            <LockKeyhole className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={Boolean(errors.password)}
              className="h-12 rounded-[0.5rem] border-slate-200/90 bg-slate-50/80 pl-10 text-slate-950 shadow-[inset_0_1px_0_rgba(255,255,255,0.75)] dark:border-white/10 dark:bg-white/6 dark:text-white dark:shadow-none"
              {...register('password', {
                required: 'Password is required',
                minLength: {
                  value: 6,
                  message: 'Password must be at least 6 characters',
                },
              })}
            />
          </div>
          {errors.password && (
            <p role="alert" className="text-sm text-red-500">
              {errors.password.message}
            </p>
          )}
        </div>
        <Button
          type="submit"
          className="h-11 w-full rounded-[0.5rem] bg-slate-950 text-white shadow-[0_18px_42px_rgba(15,23,42,0.18)] hover:bg-slate-800 dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200"
          disabled={loginMutation.isPending}
        >
          {loginMutation.isPending ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Signing in
            </>
          ) : (
            <>
              Open workspace
              <ArrowRight className="h-4 w-4" />
            </>
          )}
        </Button>
        <div className="text-center text-sm text-slate-600 dark:text-slate-300">
          New to SOIT?{' '}
          <Link to="/sign-up" className="font-medium text-slate-950 underline underline-offset-4 dark:text-white">
            Request workspace access
          </Link>
        </div>
        <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-slate-200 dark:after:border-white/10">
          <span className="relative z-10 bg-white/90 px-3 text-slate-500 dark:bg-slate-950 dark:text-slate-400">
            Enterprise access
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full rounded-[0.5rem] border-slate-200/90 bg-white/74 shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/6 dark:hover:bg-white/10"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="mr-2 h-4 w-4">
              <path
                d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"
                fill="currentColor"
              />
            </svg>
            Apple
          </Button>
          <Button
            type="button"
            variant="outline"
            className="h-11 w-full rounded-[0.5rem] border-slate-200/90 bg-white/74 shadow-none hover:bg-slate-50 dark:border-white/10 dark:bg-white/6 dark:hover:bg-white/10"
          >
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="mr-2 h-4 w-4">
              <path
                d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
                fill="currentColor"
              />
            </svg>
            Google
          </Button>
        </div>
      </div>
      <div className="text-balance text-center text-xs text-slate-500 dark:text-slate-400 [&_a]:underline [&_a]:underline-offset-4">
        Protected by SOIT workspace policy. By continuing, you agree to the <a href="#">Terms</a> and{' '}
        <a href="#">Privacy Policy</a>.
      </div>
    </form>
  )
}
