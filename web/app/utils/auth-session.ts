const AUTH_STORAGE_KEYS = [
  'token',
  'refresh_token',
  'tenant_id',
  'workspace_id',
  'soit-user-store',
] as const

export const REFRESH_TOKEN_KEY = 'refresh_token'

export function storedRefreshToken(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(REFRESH_TOKEN_KEY) || ''
}

export function storeAuthTokens(accessToken: string, refreshToken?: string | null): void {
  if (typeof window === 'undefined') return
  window.localStorage.setItem('token', accessToken)
  // A refresh response that omits the token leaves the stored one alone; only
  // an explicit new value replaces it, so a partial response cannot sign the
  // user out on the next expiry.
  if (refreshToken) window.localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken)
}

export function clearAuthSessionStorage(): void {
  if (typeof window === 'undefined') return
  for (const key of AUTH_STORAGE_KEYS) {
    window.localStorage.removeItem(key)
    window.localStorage.removeItem(`${key}_typeof`)
  }
}

export function currentLocalRoute(): string {
  if (typeof window === 'undefined') return '/'
  return `${window.location.pathname}${window.location.search}${window.location.hash}`
}

export function signInRouteFor(returnTo: string): string {
  return `/sign-in?redirect=${encodeURIComponent(returnTo)}`
}

export function resolveSafeAuthRedirect(value: string | null | undefined): string {
  if (!value || typeof window === 'undefined') return '/'
  try {
    if (value.startsWith('//')) return '/'
    const target = new URL(value, window.location.origin)
    if (target.origin !== window.location.origin) return '/'
    return `${target.pathname}${target.search}${target.hash}` || '/'
  } catch {
    return '/'
  }
}
