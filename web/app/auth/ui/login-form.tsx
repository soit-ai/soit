import { useState } from 'react'

import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'

import { Link } from '@/components/ui/link'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import {
  authCompleteMfaLogin,
  authLogin,
  getAuthCapabilities,
  isMfaChallenge,
  type LoginRequest,
  type LoginResult,
  type TokenResponse,
} from '@/services/auth-service'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { resolveSafeAuthRedirect, storeAuthTokens } from '@/utils/auth-session'
import { storage } from '@/utils/storage'

import { AuthError, AuthSubmit, FieldError } from './auth-controls'

/**
 * Sign-in (v13 prototype: signin.html).
 *
 * The reset link appears only where the deployment can send mail. That keeps
 * the rule the truthful-journeys work established -- never advertise a flow
 * that cannot complete here -- without withholding the feature from
 * deployments where it works.
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

  // Held between the two steps of a sign-in that needs a second factor. It is
  // not a session: it authorizes nothing but the code exchange, and the server
  // refuses it as a bearer token.
  const [mfaToken, setMfaToken] = useState('')
  const [mfaCode, setMfaCode] = useState('')

  const finishSignIn = async (data: TokenResponse) => {
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
  }

  const capabilities = useQuery({
    queryKey: ['auth', 'capabilities'],
    queryFn: () => getAuthCapabilities({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const loginMutation = useMutation<LoginResult, Error, LoginRequest>({
    mutationKey: ['login'],
    mutationFn: (data) => authLogin(data),
    onSuccess: async (result) => {
      if (isMfaChallenge(result)) {
        setMfaToken(result.mfa_token)
        return
      }
      await finishSignIn(result)
    },
  })

  const mfaMutation = useMutation<TokenResponse, Error, void>({
    mutationKey: ['login', 'mfa'],
    mutationFn: () => authCompleteMfaLogin(mfaToken, mfaCode),
    onSuccess: (data) => finishSignIn(data),
  })

  const onSubmit = (data: LoginRequest) =>
    loginMutation.mutate({ email: data.email, password: data.password })

  if (mfaToken) {
    return (
      <form
        className="auth-card"
        onSubmit={(event) => {
          event.preventDefault()
          mfaMutation.mutate(undefined)
        }}
        noValidate
      >
        <span className="auth-eyebrow">
          <i aria-hidden />
          Two-factor
        </span>

        <h1>Enter your code</h1>
        <p className="auth-lede">
          Open your authenticator app and enter the six-digit code for SOIT. A
          recovery code works here too, and can only be used once.
        </p>

        {mfaMutation.isError && (
          <AuthError>That code was not accepted. Codes expire every 30 seconds.</AuthError>
        )}

        <div className="auth-field">
          <label htmlFor="mfaCode">Authentication code</label>
          <input
            id="mfaCode"
            className="input"
            inputMode="text"
            autoComplete="one-time-code"
            autoFocus
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
          />
        </div>

        <AuthSubmit pending={mfaMutation.isPending} pendingLabel="Checking code">
          Continue
        </AuthSubmit>

        <div className="auth-alt">
          <button
            type="button"
            className="auth-linkish"
            onClick={() => {
              setMfaToken('')
              setMfaCode('')
            }}
          >
            Use a different account
          </button>
        </div>
      </form>
    )
  }

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

      {/* Offered only when this deployment can send mail. A reset link nobody
          can deliver is the kind of advertised-but-broken flow the truthful
          journeys work removed; asking first keeps that guarantee while
          letting the feature exist where it works. */}
      {capabilities.data?.mail_enabled && (
        <div className="auth-alt">
          <Link to="/forgot-password">Forgot your password?</Link>
        </div>
      )}

      <div className="auth-alt">
        New to SOIT? <Link to="/sign-up">Create an account</Link>
      </div>
    </form>
  )
}
