const AUTH_STORAGE_KEYS = ['token', 'tenant_id', 'workspace_id', 'soit-user-store'] as const

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
