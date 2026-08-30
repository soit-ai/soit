import { useSearchParams } from 'react-router'

import { useForm } from 'react-hook-form'

import { Link } from '@/components/ui/link'
import { useMutation } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
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
          Link incomplete
        </span>
        <h1>This link is missing its token</h1>
        <p className="auth-lede">
          Open the link from the email exactly as it arrived, or ask for a new
          one.
        </p>
        <Link to="/forgot-password" className="btn primary auth-submit">
          Send a new link
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
        Account recovery
      </span>

      <h1>Choose a new password</h1>
      <p className="auth-lede">
        Setting it signs you out everywhere else, so anyone else holding a
        session loses it.
      </p>

      {resetMutation.isError && (
        <AuthError>
          That link is no longer valid. Reset links work once and expire after
          30 minutes.
        </AuthError>
      )}

      <div className="auth-field">
        <label htmlFor="password">New password</label>
        <input
          id="password"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.password)}
          {...register('password', {
            required: 'Enter a new password.',
            minLength: { value: 8, message: 'Passwords are at least 8 characters.' },
          })}
        />
        <FieldError message={errors.password?.message} />
      </div>

      <div className="auth-field">
        <label htmlFor="confirm">Confirm new password</label>
        <input
          id="confirm"
          type="password"
          className="input"
          autoComplete="new-password"
          aria-invalid={Boolean(errors.confirm)}
          {...register('confirm', {
            required: 'Repeat the new password.',
            validate: (value) =>
              value === watch('password') || 'The two passwords do not match.',
          })}
        />
        <FieldError message={errors.confirm?.message} />
      </div>

      <AuthSubmit pending={resetMutation.isPending} pendingLabel="Setting password">
        Set password
      </AuthSubmit>

      <div className="auth-alt">
        Remembered it? <Link to="/sign-in">Sign in</Link>
      </div>
    </form>
  )
}
