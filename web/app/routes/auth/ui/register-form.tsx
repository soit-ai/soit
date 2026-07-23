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
      </div>
      <p className="text-balance text-center text-xs text-slate-500 dark:text-slate-400">
        Community registration supports email and password only.
      </p>
    </form>
  )
}
