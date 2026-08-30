import { Toaster } from 'sonner'

import '@/auth/styles/auth.css'
import '@/console/styles/console.css'
import { IconLogo, IconMoon, IconSun } from '@/console/components/icons'
import { ConsoleThemeProvider, useConsoleTheme } from '@/console/shell/console-theme'
import { cn } from '@/lib/utils'

interface AuthShellProps {
  children: React.ReactNode
  /**
   * The right-hand column. Each screen says something different there, so the
   * shell holds the layout and the screen supplies the argument.
   */
  aside?: React.ReactNode
}

/**
 * The frame around sign-in, sign-up and password reset (v13 prototype:
 * signin/signup/forgot).
 *
 * It takes `.console-root` for the console's tokens and control skin but not
 * `.shell`, whose flex layout belongs to the rail-and-panel chrome these
 * screens do not have. Signing in and arriving then read as one product
 * instead of two.
 */
function AuthShellInner({ children, aside }: AuthShellProps) {
  const { theme, toggleTheme } = useConsoleTheme()

  return (
    <div className={cn('console-root auth-root', theme === 'dark' && 'dark')}>
      <div className="auth-form-side">
        <div className="auth-top">
          <span className="rail-logo" title="SOIT">
            <IconLogo size={20} />
          </span>
          <span className="auth-wordmark">SOIT</span>
          <button
            type="button"
            className="btn ghost auth-theme"
            onClick={toggleTheme}
            title="Toggle theme"
            aria-label="Toggle theme"
            style={{ width: 28, height: 28, padding: 0, display: 'grid', placeItems: 'center' }}
          >
            {theme === 'dark' ? <IconMoon size={14} /> : <IconSun size={14} />}
          </button>
        </div>

        <div className="auth-form-wrap">{children}</div>

        <div className="auth-foot">
          <i aria-hidden />
          soit console
          <span>Email and password only on community builds</span>
        </div>
      </div>

      {aside ? <div className="auth-aside">{aside}</div> : null}

      <Toaster position="top-center" richColors />
    </div>
  )
}

export function AuthShell({ children, aside }: AuthShellProps) {
  return (
    <ConsoleThemeProvider>
      <AuthShellInner aside={aside}>{children}</AuthShellInner>
    </ConsoleThemeProvider>
  )
}
