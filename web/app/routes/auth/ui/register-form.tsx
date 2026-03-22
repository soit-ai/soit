import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { useForm } from "react-hook-form"
import { useMutation } from "@/hooks/use-query"
import { authRegister } from "@/services/auth-service"
import { useNavigate } from "@/hooks/use-navigate"
import { storage } from "@/utils/storage"
import { toast } from "sonner"
import { type RegisterRequest, type TokenResponse } from '@/services/auth-service'
import { Link } from "@/components/ui/link"
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'

export function RegisterForm({
  className,
  ...props
}: React.ComponentPropsWithoutRef<'form'>) {
  const navigate = useNavigate()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const {
    register,
    handleSubmit,
    formState: { errors },
    watch,
  } = useForm<RegisterRequest & { confirmPassword: string }>()

  // Register mutation
  const registerMutation = useMutation<TokenResponse, Error, RegisterRequest>({
    mutationKey: ['register'],
    mutationFn: (data) => authRegister(data),
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
        console.warn('Failed to sync current user after register:', error)
      }
      toast.success('Registration successful')
      navigate('/')
    },
    onError: (error) => {
      toast.error('Registration failed. Please try again.')
    },
  })

  const onSubmit = (data: RegisterRequest & { confirmPassword: string }) => {
    registerMutation.mutate({
      email: data.email,
      password: data.password,
      name: data.name,
      tenant_name: data.tenant_name,
    })
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} className={cn('flex flex-col gap-6', className)} {...props}>
      <div className="space-y-2 text-center">
        <h2 className="text-2xl font-semibold tracking-tight text-slate-950 dark:text-white">Create an account</h2>
        <p className="text-sm leading-6 text-slate-600 dark:text-slate-300">
          Enter your email below to create your account
        </p>
      </div>
      <div className="grid gap-6">
        <div className="grid gap-2">
          <Label htmlFor="email" className="text-slate-700 dark:text-slate-200">
            Email
          </Label>
          <Input
            id="email"
            type="email"
            placeholder="m@example.com"
            className="h-11 rounded-lg border-slate-200 bg-slate-50 px-4 dark:border-slate-800 dark:bg-slate-950"
            {...register('email', {
              required: 'Email is required',
              pattern: {
                value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
                message: 'Invalid email address',
              },
            })}
          />
          {errors.email && <p className="text-sm text-red-500">{errors.email.message}</p>}
        </div>
        <div className="grid gap-6 md:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="name" className="text-slate-700 dark:text-slate-200">
              Name
            </Label>
            <Input
              id="name"
              type="text"
              placeholder="Your name"
              className="h-11 rounded-lg border-slate-200 bg-slate-50 px-4 dark:border-slate-800 dark:bg-slate-950"
              {...register('name', {
                required: 'Name is required',
              })}
            />
            {errors.name && <p className="text-sm text-red-500">{errors.name.message}</p>}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="tenant-name" className="text-slate-700 dark:text-slate-200">
              Tenant Name (optional)
            </Label>
            <Input
              id="tenant-name"
              type="text"
              placeholder="tenant name"
              className="h-11 rounded-lg border-slate-200 bg-slate-50 px-4 dark:border-slate-800 dark:bg-slate-950"
              {...register('tenant_name')}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password" className="text-slate-700 dark:text-slate-200">
              Password
            </Label>
            <Input
              id="password"
              type="password"
              className="h-11 rounded-lg border-slate-200 bg-slate-50 px-4 dark:border-slate-800 dark:bg-slate-950"
              {...register('password', {
                required: 'Password is required',
                minLength: {
                  value: 8,
                  message: 'Password must be at least 8 characters',
                },
              })}
            />
            {errors.password && <p className="text-sm text-red-500">{errors.password.message}</p>}
          </div>
          <div className="grid gap-2">
            <Label htmlFor="confirm-password" className="text-slate-700 dark:text-slate-200">
              Confirm Password
            </Label>
            <Input
              id="confirm-password"
              type="password"
              className="h-11 rounded-lg border-slate-200 bg-slate-50 px-4 dark:border-slate-800 dark:bg-slate-950"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (val: string) => {
                  if (watch('password') !== val) {
                    return 'Passwords do not match'
                  }
                },
              })}
            />
            {errors.confirmPassword && <p className="text-sm text-red-500">{errors.confirmPassword.message}</p>}
          </div>
        </div>
        <Button type="submit" className="h-11 w-full rounded-lg" disabled={registerMutation.isPending}>
          {registerMutation.isPending ? 'Creating account...' : 'Sign up'}
        </Button>
        <div className="text-center text-sm text-slate-600 dark:text-slate-300">
          Already have an account?{' '}
          <Link to="/sign-in" className="font-medium text-slate-950 underline underline-offset-4 dark:text-white">
            Sign in
          </Link>
        </div>
        <div className="relative text-center text-sm after:absolute after:inset-0 after:top-1/2 after:z-0 after:border-t after:border-slate-200 dark:after:border-slate-800">
          <span className="relative z-10 bg-white px-2 text-slate-500 dark:bg-slate-900 dark:text-slate-400">
            Or continue with
          </span>
        </div>
        <Button
          type="button"
          variant="outline"
          className="h-11 w-full rounded-lg border-slate-200 bg-transparent dark:border-slate-800"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="mr-2 h-4 w-4">
            <path
              d="M12.152 6.896c-.948 0-2.415-1.078-3.96-1.04-2.04.027-3.91 1.183-4.961 3.014-2.117 3.675-.546 9.103 1.519 12.09 1.013 1.454 2.208 3.09 3.792 3.039 1.52-.065 2.09-.987 3.935-.987 1.831 0 2.35.987 3.96.948 1.637-.026 2.676-1.48 3.676-2.948 1.156-1.688 1.636-3.325 1.662-3.415-.039-.013-3.182-1.221-3.22-4.857-.026-3.04 2.48-4.494 2.597-4.559-1.429-2.09-3.623-2.324-4.39-2.376-2-.156-3.675 1.09-4.61 1.09zM15.53 3.83c.843-1.012 1.4-2.427 1.245-3.83-1.207.052-2.662.805-3.532 1.818-.78.896-1.454 2.338-1.273 3.714 1.338.104 2.715-.688 3.559-1.701"
              fill="currentColor"
            />
          </svg>
          Sign up with Apple
        </Button>
        <Button
          type="button"
          variant="outline"
          className="h-11 w-full rounded-lg border-slate-200 bg-transparent dark:border-slate-800"
        >
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" className="mr-2 h-4 w-4">
            <path
              d="M12.48 10.92v3.28h7.84c-.24 1.84-.853 3.187-1.787 4.133-1.147 1.147-2.933 2.4-6.053 2.4-4.827 0-8.6-3.893-8.6-8.72s3.773-8.72 8.6-8.72c2.6 0 4.507 1.027 5.907 2.347l2.307-2.307C18.747 1.44 16.133 0 12.48 0 5.867 0 .307 5.387.307 12s5.56 12 12.173 12c3.573 0 6.267-1.173 8.373-3.36 2.16-2.16 2.84-5.213 2.84-7.667 0-.76-.053-1.467-.173-2.053H12.48z"
              fill="currentColor"
            />
          </svg>
          Sign up with Google
        </Button>
      </div>
      <div className="text-balance text-center text-xs text-slate-500 dark:text-slate-400 [&_a]:underline [&_a]:underline-offset-4">
        By clicking continue, you agree to our <a href="#">Terms of Service</a> and <a href="#">Privacy Policy</a>.
      </div>
    </form>
  )
}
