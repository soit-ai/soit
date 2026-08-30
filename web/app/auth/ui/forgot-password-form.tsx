import { Link } from '@/components/ui/link'

/**
 * Password reset (v13 prototype: forgot.html).
 *
 * There is no mail sender and no reset token to issue, so this screen says so
 * rather than collecting an address and doing nothing with it. Sign-in does
 * not link here on purpose — offering a reset that cannot complete is the
 * thing the truthful-journeys work removed — but the route stays reachable for
 * anyone who arrives with a bookmark, and it explains the ways out that work.
 */
export function ForgotPasswordForm() {
  return (
    <div className="auth-card">
      <span className="auth-eyebrow warn">
        <i aria-hidden />
        Not available
      </span>

      <h1>Password reset</h1>
      <p className="auth-lede">
        Community builds have no password reset. There is no mail sender
        configured and no reset token to issue, so this page cannot send you
        anything.
      </p>

      <div className="auth-bar warn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
          <path d="M12 3 2 20h20L12 3ZM12 10v5M12 18v.5" />
        </svg>
        <span>
          Asking for your email here would look like a reset was on its way. It
          would not be.
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
            <b>Self-hosted and you are the owner?</b> Reset the hash directly in
            the database, or create a new owner with the bootstrap script.
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
