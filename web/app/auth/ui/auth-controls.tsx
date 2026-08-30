/**
 * The three auth screens share a small set of controls, so the error, the
 * field message and the submit button live here rather than being repeated
 * with drifting markup in each form.
 */

export function AuthError({ children }: { children: React.ReactNode }) {
  return (
    <div className="auth-bar" role="alert">
      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v6M12 16.5v.5" />
      </svg>
      <span>{children}</span>
    </div>
  )
}

/** Renders nothing without a message, so the layout does not reserve a gap. */
export function FieldError({ message }: { message?: string }) {
  if (!message) return null
  return (
    <span className="auth-err" role="alert">
      {message}
    </span>
  )
}

interface AuthSubmitProps {
  pending: boolean
  pendingLabel: string
  children: React.ReactNode
}

export function AuthSubmit({ pending, pendingLabel, children }: AuthSubmitProps) {
  return (
    <button type="submit" className="btn primary auth-submit" disabled={pending}>
      {pending ? (
        <>
          <span className="auth-spinner" aria-hidden />
          {pendingLabel}
        </>
      ) : (
        <>
          {children}
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden>
            <path d="M5 12h13M13 6l6 6-6 6" />
          </svg>
        </>
      )}
    </button>
  )
}
