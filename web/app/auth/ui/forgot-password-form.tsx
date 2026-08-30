import { useState } from 'react'

import { useForm } from 'react-hook-form'

import { Link } from '@/components/ui/link'
import { useMutation, useQuery } from '@/hooks/use-query'
import { getAuthCapabilities, requestPasswordReset } from '@/services/auth-service'

import { AuthSubmit, FieldError } from './auth-controls'

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
    // The server answers the same way whether or not the address is
    // registered, and so does this screen.
    onSuccess: () => setSent(true),
    onError: () => setSent(true),
  })

  if (capabilities.data?.mail_enabled === false) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow warn">
          <i aria-hidden />
          Not available
        </span>

        <h1>Password reset</h1>
        <p className="auth-lede">
          This deployment has no mail outlet configured, so it cannot send you a
          reset link.
        </p>

        <div className="auth-bar warn">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M12 3 2 20h20L12 3ZM12 10v5M12 18v.5" />
          </svg>
          <span>
            Asking for your email here would look like a reset was on its way.
            It would not be.
          </span>
        </div>

        <ol className="auth-steps">
          <li>
            <span className="auth-n">1</span>
            <span>
              <b>Ask a workspace owner.</b> An owner can remove your membership
              and re-invite you, which lets you set a new password.
            </span>
          </li>
          <li>
            <span className="auth-n">2</span>
            <span>
              <b>Running this yourself?</b> Configure a mail outlet
              (<code>SYSTEM_MAIL_URL</code>) and this page starts working, or
              reset the hash directly in the database.
            </span>
          </li>
        </ol>

        <Link to="/sign-in" className="btn primary auth-submit">
          Back to sign in
        </Link>

        <div className="auth-alt">
          No account yet? <Link to="/sign-up">Create one</Link>
        </div>
      </div>
    )
  }

  if (sent) {
    return (
      <div className="auth-card">
        <span className="auth-eyebrow">
          <i aria-hidden />
          Check your mail
        </span>

        <h1>If that address has an account</h1>
        <p className="auth-lede">
          A reset link is on its way. It works once and expires in 30 minutes.
        </p>
        <p className="auth-lede">
          Nothing here confirms whether the address is registered — saying so
          would let anyone use this form to find out who has an account.
        </p>

        <Link to="/sign-in" className="btn primary auth-submit">
          Back to sign in
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

      <h1>Reset your password</h1>
      <p className="auth-lede">
        Enter the address for your account and we will send a link to set a new
        password.
      </p>

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
            required: 'Enter the email address for your account.',
            pattern: {
              value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i,
              message: 'Enter a valid email address.',
            },
          })}
        />
        <FieldError message={errors.email?.message} />
      </div>

      <AuthSubmit pending={resetMutation.isPending} pendingLabel="Sending link">
        Send reset link
      </AuthSubmit>

      <div className="auth-alt">
        Remembered it? <Link to="/sign-in">Sign in</Link>
      </div>
    </form>
  )
}
