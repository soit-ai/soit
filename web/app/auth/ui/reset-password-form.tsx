import { useSearchParams } from 'react-router'

import { useForm } from 'react-hook-form'

import { Link } from '@/components/ui/link'
import { useMutation } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import { confirmPasswordReset } from '@/services/auth-service'

import { AuthError, AuthSubmit, FieldError } from './auth-controls'

interface ResetForm {
  password: string
  confirm: string
}

/**
 * Setting a new password from a mailed link.
 *
 * The link is the credential, so it arrives in the query string and is spent
 * on submit. Every other session ends server-side when it is: a reset is what
 * someone does when they think the account is compromised, and leaving the
 * intruder signed in would make it pointless.
 */
export function ResetPasswordForm() {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') || ''
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<ResetForm>()

  const resetMutation = useMutation<void, Error, ResetForm>({
    mutationKey: ['auth', 'password-reset-confirm'],
    mutationFn: (data) => confirmPasswordReset(token, data.password),
    onSuccess: () => navigate('/sign-in'),
  })

  if (!token) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow warn">
          <i aria-hidden />
          {t('auth.reset.missingEyebrow')}
        </span>
        <h1>{t('auth.reset.missingTitle')}</h1>
        <p className="auth-lede">{t('auth.reset.missingLede')}</p>
        <Link to="/forgot-password" className="btn primary auth-submit">
          {t('auth.reset.newLink')}
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

      <h1>{t('auth.reset.title')}</h1>
      <p className="auth-lede">{t('auth.reset.lede')}</p>

      {resetMutation.isError && <AuthError>{t('auth.reset.failed')}</AuthError>}

      <div className="auth-field">
        <label htmlFor="password">{t('auth.reset.password')}</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            required: t('auth.reset.passwordRequired'),
            minLength: { value: 8, message: t('auth.common.passwordMin') },
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="confirm">{t('auth.reset.confirm')}</label>
        <input
          id="confirm"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.confirm)}
          {...register('confirm', {
            required: t('auth.reset.confirmRequired'),
            validate: (value) => value === watch('password') || t('auth.reset.mismatch'),
          })}
        />
        <FieldError message={errors.confirm?.message} />
      </div>

      <AuthSubmit pending={resetMutation.isPending} pendingLabel={t('auth.reset.pending')}>
        {t('auth.reset.submit')}
      </AuthSubmit>

      <div className="auth-alt">
        {t('auth.common.rememberedIt')} <Link to="/sign-in">{t('auth.common.signIn')}</Link>
      </div>
    </form>
  )
}
