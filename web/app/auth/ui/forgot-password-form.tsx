import { useState } from 'react'

import { useForm } from 'react-hook-form'

import { Link } from '@/components/ui/link'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAuthCapabilities, requestPasswordReset } from '@/services/auth-service'

import { AuthError, AuthSubmit, FieldError, lockoutMinutes } from './auth-controls'

/**
 * Password reset (v13 prototype: forgot.html).
 *
 * A deployment can only reset a password if it can send mail, and not every
 * self-hosted install has an outlet configured. So the screen asks first: with
 * mail it collects an address, without it it says plainly that it cannot send
 * anything and names the ways out that do work. Collecting an address either
 * way would look like a reset was on its way when it was not.
 */
export function ForgotPasswordForm() {
  const { t } = useTranslation()
  const [sent, setSent] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ email: string }>()

  const capabilities = useQuery({
    queryKey: ['auth', 'capabilities'],
    queryFn: () => getAuthCapabilities({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const resetMutation = useMutation<void, Error, { email: string }>({
    mutationKey: ['auth', 'password-reset'],
    mutationFn: (data) => requestPasswordReset(data.email),
    onSuccess: () => setSent(true),
    // Any other failure reads as sent, so the form never tells which
    // addresses exist. The per-address cap is the exception: it applies to
    // every address alike, so saying so reveals nothing.
    onError: (error) => {
      if (lockoutMinutes(error) == null) setSent(true)
    },
  })
  const lockedFor = resetMutation.isError ? lockoutMinutes(resetMutation.error) : null

  if (capabilities.data?.mail_enabled === false) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow warn">
          <i aria-hidden />
          {t('auth.forgot.unavailableEyebrow')}
        </span>

        <h1>{t('auth.forgot.unavailableTitle')}</h1>
        <p className="auth-lede">{t('auth.forgot.unavailableLede')}</p>

        <div className="auth-bar warn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M12 3 2 20h20L12 3ZM12 10v5M12 18v.5" />
          </svg>
          <span>{t('auth.forgot.unavailableBar')}</span>
        </div>

        <ol className="auth-steps">
          <li>
            <span className="auth-n">1</span>
            <span>
              <b>{t('auth.forgot.askOwnerTitle')}</b> {t('auth.forgot.askOwner')}
            </span>
          </li>
          <li>
            <span className="auth-n">2</span>
            <span>
              <b>{t('auth.forgot.selfHostedTitle')}</b> {t('auth.forgot.selfHostedBefore')}
              <code>SYSTEM_MAIL_URL</code>
              {t('auth.forgot.selfHostedAfter')}
            </span>
          </li>
        </ol>

        <Link to="/sign-in" className="btn primary auth-submit">
          {t('auth.common.backToSignIn')}
        </Link>

        <div className="auth-alt">
          {t('auth.forgot.noAccount')} <Link to="/sign-up">{t('auth.forgot.createOne')}</Link>
        </div>
      </div>
    )
  }

  if (sent) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow">
          <i aria-hidden />
          {t('auth.forgot.sentEyebrow')}
        </span>

        <h1>{t('auth.forgot.sentTitle')}</h1>
        <p className="auth-lede">{t('auth.forgot.sentLede')}</p>
        <p className="auth-lede">{t('auth.forgot.sentPrivacy')}</p>

        <Link to="/sign-in" className="btn primary auth-submit">
          {t('auth.common.backToSignIn')}
        </Link>
      </div>
    )
  }

  return (
    <form
      className="auth-card"
      onSubmit={handleSubmit((data) => resetMutation.mutate(data))}
      noValidate
    >
      <span className="auth-eyebrow">
        <i aria-hidden />
        {t('auth.common.accountRecovery')}
      </span>

      <h1>{t('auth.forgot.title')}</h1>
      <p className="auth-lede">{t('auth.forgot.lede')}</p>

      {lockedFor != null && (
        <AuthError>{t('auth.common.tooManyAttempts', { minutes: lockedFor })}</AuthError>
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
            required: t('auth.forgot.emailRequired'),
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: t('auth.common.emailInvalid'),
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <AuthSubmit pending={resetMutation.isPending} pendingLabel={t('auth.forgot.pending')}>
        {t('auth.forgot.submit')}
      </AuthSubmit>

      <div className="auth-alt">
        {t('auth.common.rememberedIt')} <Link to="/sign-in">{t('auth.common.signIn')}</Link>
      </div>
    </form>
  )
}
