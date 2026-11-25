import { useState } from 'react'

import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'

import { Link } from '@/components/ui/link'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
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

import { AuthError, AuthSubmit, FieldError, lockoutMinutes } from './auth-controls'

/**
 * Sign-in (v13 prototype: signin.html).
 *
 * The reset link appears only where the deployment can send mail. That keeps
 * the rule the truthful-journeys work established -- never advertise a flow
 * that cannot complete here -- without withholding the feature from
 * deployments where it works.
 */
export const LoginForm = () => {
  const { t } = useTranslation()
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
          {t('auth.mfa.eyebrow')}
        </span>

        <h1>{t('auth.mfa.title')}</h1>
        <p className="auth-lede">{t('auth.mfa.lede')}</p>

        {mfaMutation.isError && (
          <AuthError>
            {lockoutMinutes(mfaMutation.error) != null
              ? t('auth.common.tooManyAttempts', { minutes: lockoutMinutes(mfaMutation.error) })
              : t('auth.mfa.failed')}
          </AuthError>
        )}

        <div className="auth-field">
          <label htmlFor="mfaCode">{t('auth.mfa.code')}</label>
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

        <AuthSubmit pending={mfaMutation.isPending} pendingLabel={t('auth.mfa.pending')}>
          {t('auth.mfa.submit')}
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
            {t('auth.mfa.otherAccount')}
          </button>
        </div>
      </form>
    )
  }

  return (
    <form className="auth-card" onSubmit={handleSubmit(onSubmit)} noValidate>
      <span className="auth-eyebrow">
        <i aria-hidden />
        {t('auth.login.eyebrow')}
      </span>

      <h1>{t('auth.login.title')}</h1>
      <p className="auth-lede">{t('auth.login.lede')}</p>

      {/* Says nothing about which of the two was wrong: naming the field tells
          an attacker which addresses are registered. */}
      {loginMutation.isError && (
        <AuthError>
          {lockoutMinutes(loginMutation.error) != null
            ? t('auth.common.tooManyAttempts', { minutes: lockoutMinutes(loginMutation.error) })
            : t('auth.login.failed')}
        </AuthError>
      )}

      <div className="auth-field">
        <label htmlFor="email">{t('auth.common.email')}</label>
        <input
          id="email"
          type="email"
          className="input"
          placeholder={t('auth.common.emailPlaceholder')}
          autoComplete="email"
          aria-invalid={Boolean(errors.email)}
          {...register('email', {
            required: t('auth.login.emailRequired'),
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: t('auth.common.emailInvalid'),
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="password">{t('auth.common.password')}</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="current-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            // No length rule on sign-in: the server decides, and a length hint
            // here tells a guesser nothing it needs.
            required: t('auth.login.passwordRequired'),
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <AuthSubmit pending={loginMutation.isPending} pendingLabel={t('auth.login.pending')}>
        {t('auth.login.submit')}
      </AuthSubmit>

      {/* Offered only when this deployment can send mail. A reset link nobody
          can deliver is the kind of advertised-but-broken flow the truthful
          journeys work removed; asking first keeps that guarantee while
          letting the feature exist where it works. */}
      {capabilities.data?.mail_enabled && (
        <div className="auth-alt">
          <Link to="/forgot-password">{t('auth.login.forgot')}</Link>
        </div>
      )}

      <div className="auth-alt">
        {t('auth.login.newHere')} <Link to="/sign-up">{t('auth.login.createAccount')}</Link>
      </div>
    </form>
  )
}
