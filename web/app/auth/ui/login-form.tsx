import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'

import { Link } from '@/components/ui/link'
import { useMutation } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { authLogin, type LoginRequest, type TokenResponse } from '@/services/auth-service'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { resolveSafeAuthRedirect, storeAuthTokens } from '@/utils/auth-session'
import { storage } from '@/utils/storage'

import { AuthError, AuthSubmit, FieldError } from './auth-controls'

/**
 * Sign-in (v13 prototype: signin.html).
 *
 * Password reset is deliberately not offered here. There is no reset flow
 * behind it, and advertising one is what the truthful-journeys work removed;
 * `/forgot-password` stays reachable by URL and says so itself.
 */
export const LoginForm = () => {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginRequest>()

  const loginMutation = useMutation<TokenResponse, Error, LoginRequest>({
    mutationKey: ['login'],
    mutationFn: (data) => authLogin(data),
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
        console.warn('Failed to sync current user after login:', error)
      }
      navigate(resolveSafeAuthRedirect(searchParams.get('redirect')))
    },
  })

  const onSubmit = (data: LoginRequest) =>
    loginMutation.mutate({ email: data.email, password: data.password })

  return (
    <form className="auth-card" onSubmit={handleSubmit(onSubmit)} noValidate>
      <span className="auth-eyebrow">
        <i aria-hidden />
        Workspace access
      </span>

      <h1>Sign in to SOIT</h1>
      <p className="auth-lede">
        Agents, workflows, knowledge and every run they produce — under one
        workspace&apos;s policy and one audit trail.
      </p>

      {/* Says nothing about which of the two was wrong: naming the field tells
          an attacker which addresses are registered. */}
      {loginMutation.isError && (
        <AuthError>That email and password combination did not match an account.</AuthError>
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
            required: 'Enter the email address for your workspace account.',
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: 'Enter a valid email address.',
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="password">Password</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="current-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            required: 'Enter your password.',
            minLength: { value: 6, message: 'Passwords are at least 6 characters.' },
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <AuthSubmit pending={loginMutation.isPending} pendingLabel="Opening workspace">
        Open workspace
      </AuthSubmit>

      <div className="auth-alt">
        New to SOIT? <Link to="/sign-up">Create an account</Link>
      </div>
    </form>
  )
}
