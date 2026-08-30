import { useForm } from 'react-hook-form'

import { Link } from '@/components/ui/link'
import { useMutation } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { authRegister, type RegisterRequest, type TokenResponse } from '@/services/auth-service'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { storeAuthTokens } from '@/utils/auth-session'
import { storage } from '@/utils/storage'

import { AuthError, AuthSubmit, FieldError } from './auth-controls'

type RegisterFormValues = RegisterRequest & { confirmPassword: string }

/** Sign-up (v13 prototype: signup.html). */
export const RegisterForm = () => {
  const navigate = useNavigate()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<RegisterFormValues>()

  const registerMutation = useMutation<TokenResponse, Error, RegisterRequest>({
    mutationKey: ['register'],
    mutationFn: (data) => authRegister(data),
    onSuccess: async (data) => {
      storeAuthTokens(data.access_token, data.refresh_token)
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
      navigate('/')
    },
  })

  const onSubmit = (data: RegisterFormValues) =>
    registerMutation.mutate({
      email: data.email,
      password: data.password,
      name: data.name,
      tenant_name: data.tenant_name,
    })

  return (
    <form className="auth-card" onSubmit={handleSubmit(onSubmit)} noValidate>
      <span className="auth-eyebrow">
        <i aria-hidden />
        New workspace
      </span>

      <h1>Create your SOIT account</h1>
      <p className="auth-lede">
        You get an owner account and a workspace of your own. Everything an
        agent does in it is scoped to that workspace from the first run.
      </p>

      {registerMutation.isError && (
        <AuthError>That account could not be created. The email may already be registered.</AuthError>
      )}

      <div className="auth-field">
        <label htmlFor="email">Email</label>
        <input
          id="email"
          type="email"
          className="input"
          placeholder="name@company.com"
          autoComplete="email"
          aria-invalid={Boolean(errors.email)}
          {...register('email', {
            required: 'Enter a valid email address.',
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: 'Enter a valid email address.',
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="name">Your name</label>
        <input
          id="name"
          type="text"
          className="input"
          placeholder="Jude"
          autoComplete="name"
          aria-invalid={Boolean(errors.name)}
          {...register('name', { required: 'Your name appears on audit entries and approvals.' })}
        />
        <FieldError message={errors.name?.message} />
      </div>

      <div className="auth-field">
        <div className="auth-field-head">
          <label htmlFor="tenant-name">Organisation</label>
          <span className="auth-opt">optional</span>
        </div>
        <input
          id="tenant-name"
          type="text"
          className="input"
          placeholder="acme-robotics"
          {...register('tenant_name')}
        />
        <span className="auth-hint">Leave blank and one is created for you.</span>
      </div>

      <div className="auth-field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            required: 'Choose a password.',
            minLength: { value: 6, message: 'Passwords are at least 6 characters.' },
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="confirm-password">Confirm password</label>
        <input
          id="confirm-password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.confirmPassword)}
          {...register('confirmPassword', {
            required: 'Repeat the password.',
            validate: (value: string) =>
              value === watch('password') || 'Both passwords must match.',
          })}
        />
        <FieldError message={errors.confirmPassword?.message} />
      </div>

      <AuthSubmit pending={registerMutation.isPending} pendingLabel="Creating workspace">
        Create workspace
      </AuthSubmit>

      <div className="auth-alt">
        Already have an account? <Link to="/sign-in">Sign in</Link>
      </div>
    </form>
  )
}
