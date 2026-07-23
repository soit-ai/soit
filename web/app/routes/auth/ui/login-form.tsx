import { ArrowRight, Loader2, LockKeyhole, Mail, ShieldCheck } from 'lucide-react'
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
import { useSearchParams } from 'react-router'
import { resolveSafeAuthRedirect } from '@/utils/auth-session'

export const LoginForm = ({ className, ...props }: React.ComponentPropsWithoutRef<'form'>) => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
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
      navigate(resolveSafeAuthRedirect(searchParams.get('redirect')))
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
          <Label htmlFor="password" className="text-sm text-slate-700 dark:text-slate-200">
            Password
          </Label>
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
            Create an account
          </Link>
        </div>
      </div>
      <p className="text-balance text-center text-xs text-slate-500 dark:text-slate-400">
        Community authentication supports email and password only.
      </p>
    </form>
  )
}
