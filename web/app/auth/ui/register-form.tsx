import { useForm } from 'react-hook-form'
import { useSearchParams } from 'react-router'

import { Link } from '@/components/ui/link'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import {
  authRegister,
  getAuthCapabilities,
  type RegisterRequest,
  type TokenResponse,
} from '@/services/auth-service'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { storeAuthTokens } from '@/utils/auth-session'
import { storage } from '@/utils/storage'

import { AuthError, AuthSubmit, FieldError, lockoutMinutes } from './auth-controls'

type RegisterFormValues = RegisterRequest & { confirmPassword: string }

/**
 * Sign-up (v13 prototype: signup.html).
 *
 * What a sign-up does depends on the deployment, so the form asks before it
 * says. An invitation link (`?invitation=`) joins the inviting workspace; a
 * single-organization deployment that already has its organization admits a
 * new account as a member with a workspace of its own, so there is no
 * organization to name; and with public registration off, only an invitation
 * gets in. Until the answer arrives the form assumes the founding case, which
 * is what an unreachable capabilities endpoint has always meant.
 */
export const RegisterForm = () => {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const invitationToken = searchParams.get('invitation') || ''
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const capabilities = useQuery({
    queryKey: ['auth', 'capabilities'],
    queryFn: () => getAuthCapabilities({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const foundsOrganization =
    !invitationToken && capabilities.data?.sign_up_founds_organization !== false
  const closed = !invitationToken && capabilities.data?.public_registration === false
  const mode = invitationToken ? 'invite' : foundsOrganization ? 'found' : 'join'
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
      tenant_name: foundsOrganization ? data.tenant_name : undefined,
      invitation_token: invitationToken || undefined,
    })

  if (closed) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow warn">
          <i aria-hidden />
          {t('auth.register.closedEyebrow')}
        </span>
        <h1>{t('auth.register.closedTitle')}</h1>
        <p className="auth-lede">{t('auth.register.closedLede')}</p>
        <Link to="/sign-in" className="btn primary auth-submit">
          {t('auth.common.signIn')}
        </Link>
      </div>
    )
  }

  return (
    <form className="auth-card" onSubmit={handleSubmit(onSubmit)} noValidate>
      <span className="auth-eyebrow">
        <i aria-hidden />
        {mode === 'invite'
          ? t('auth.register.inviteEyebrow')
          : mode === 'join'
            ? t('auth.register.joinEyebrow')
            : t('auth.register.eyebrow')}
      </span>

      <h1>{t('auth.register.title')}</h1>
      <p className="auth-lede">
        {mode === 'invite'
          ? t('auth.register.inviteLede')
          : mode === 'join'
            ? t('auth.register.joinLede')
            : t('auth.register.lede')}
      </p>

      {registerMutation.isError && (
        <AuthError>
          {lockoutMinutes(registerMutation.error) != null
            ? t('auth.common.tooManyAttempts', { minutes: lockoutMinutes(registerMutation.error) })
            : mode === 'invite'
              ? t('auth.register.inviteFailed')
              : t('auth.register.failed')}
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
            required: t('auth.register.emailRequired'),
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: t('auth.common.emailInvalid'),
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="name">{t('auth.register.name')}</label>
        <input
          id="name"
          type="text"
          className="input"
          placeholder={t('auth.register.namePlaceholder')}
          autoComplete="name"
          aria-invalid={Boolean(errors.name)}
          {...register('name', { required: t('auth.register.nameRequired') })}
        />
        <FieldError message={errors.name?.message} />
      </div>

      {foundsOrganization && (
        <div className="auth-field">
          <div className="auth-field-head">
            <label htmlFor="tenant-name">{t('auth.register.organisation')}</label>
            <span className="auth-opt">{t('auth.register.optional')}</span>
          </div>
          <input
            id="tenant-name"
            type="text"
            className="input"
            placeholder={t('auth.register.organisationPlaceholder')}
            {...register('tenant_name')}
          />
          <span className="auth-hint">{t('auth.register.organisationHint')}</span>
        </div>
      )}

      <div className="auth-field">
        <label htmlFor="password">{t('auth.common.password')}</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            required: t('auth.register.passwordRequired'),
            // The server refuses anything shorter; saying so here beats a
            // generic "could not be created".
            minLength: { value: 8, message: t('auth.common.passwordMin') },
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="confirm-password">{t('auth.common.confirmPassword')}</label>
        <input
          id="confirm-password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.confirmPassword)}
          {...register('confirmPassword', {
            required: t('auth.register.confirmRequired'),
            validate: (value: string) =>
              value === watch('password') || t('auth.register.mismatch'),
          })}
        />
        <FieldError message={errors.confirmPassword?.message} />
      </div>

      <AuthSubmit pending={registerMutation.isPending} pendingLabel={t('auth.register.pending')}>
        {t('auth.register.submit')}
      </AuthSubmit>

      <div className="auth-alt">
        {t('auth.register.haveAccount')} <Link to="/sign-in">{t('auth.common.signIn')}</Link>
      </div>
    </form>
  )
}
