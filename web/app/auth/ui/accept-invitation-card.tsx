import { useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router'

import { Link } from '@/components/ui/link'
import { useMutation } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import { acceptInvitation, type WorkspaceInvitation } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { clearAuthSessionStorage, signInRouteFor } from '@/utils/auth-session'

import { AuthError, AuthSubmit } from './auth-controls'

function responseStatus(error: unknown): number | undefined {
  return (error as { response?: { status?: number } } | null)?.response?.status
}

/**
 * Redeeming the link an invitation mail carries.
 *
 * The link is the credential and arrives in the query string. Accepting takes
 * a click rather than happening on load, so opening a link never changes
 * anyone's memberships by itself. Someone without a session is offered both
 * ways in: signing in comes back here, and signing up carries the token so
 * the new account lands in the invited workspace directly. Once accepted, the
 * invited workspace becomes the current one; it may belong to another
 * organization, which needs no new sign-in.
 */
export function AcceptInvitationCard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const queryClient = useQueryClient()
  const clearUser = useUserStore((state) => state.clearUser)
  const token = searchParams.get('token') || ''
  const returnHere = `/accept-invitation?token=${encodeURIComponent(token)}`
  const signedIn = typeof window !== 'undefined' && Boolean(window.localStorage.getItem('token'))

  const acceptMutation = useMutation<WorkspaceInvitation, unknown, void>({
    mutationKey: ['auth', 'accept-invitation'],
    mutationFn: () => acceptInvitation(token, { suppressErrorToast: true }),
    onSuccess: (invitation) => {
      window.localStorage.setItem('workspace_id', invitation.workspace_id)
      queryClient.clear()
      // A full load, as the workspace switcher does: nothing read under the
      // previous workspace may survive into the new one.
      window.location.assign('/')
    },
  })

  const signInAsSomeoneElse = () => {
    queryClient.clear()
    clearUser()
    clearAuthSessionStorage()
    navigate(signInRouteFor(returnHere))
  }

  if (!token) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow warn">
          <i aria-hidden />
          {t('auth.invite.missingEyebrow')}
        </span>
        <h1>{t('auth.invite.missingTitle')}</h1>
        <p className="auth-lede">{t('auth.invite.missingLede')}</p>
        <Link to="/sign-in" className="btn primary auth-submit">
          {t('auth.common.signIn')}
        </Link>
      </div>
    )
  }

  if (!signedIn) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow">
          <i aria-hidden />
          {t('auth.invite.eyebrow')}
        </span>
        <h1>{t('auth.invite.title')}</h1>
        <p className="auth-lede">{t('auth.invite.signedOutLede')}</p>
        <Link to={signInRouteFor(returnHere)} className="btn primary auth-submit">
          {t('auth.invite.signIn')}
        </Link>
        <div className="auth-alt">
          {t('auth.invite.noAccount')}{' '}
          <Link to={`/sign-up?invitation=${encodeURIComponent(token)}`}>
            {t('auth.invite.signUp')}
          </Link>
        </div>
      </div>
    )
  }

  const status = acceptMutation.isError ? responseStatus(acceptMutation.error) : undefined

  return (
    <form
      className="auth-card"
      onSubmit={(event) => {
        event.preventDefault()
        acceptMutation.mutate()
      }}
      noValidate
    >
      <span className="auth-eyebrow">
        <i aria-hidden />
        {t('auth.invite.eyebrow')}
      </span>
      <h1>{t('auth.invite.title')}</h1>
      <p className="auth-lede">{t('auth.invite.lede')}</p>

      {acceptMutation.isError && (
        <AuthError>
          {status === 403 ? t('auth.invite.otherAddress') : t('auth.invite.invalid')}
        </AuthError>
      )}

      <AuthSubmit pending={acceptMutation.isPending} pendingLabel={t('auth.invite.pending')}>
        {t('auth.invite.accept')}
      </AuthSubmit>

      <div className="auth-alt">
        {t('auth.invite.wrongAccount')}{' '}
        <button type="button" onClick={signInAsSomeoneElse}>
          {t('auth.invite.switchAccount')}
        </button>
      </div>
    </form>
  )
}
