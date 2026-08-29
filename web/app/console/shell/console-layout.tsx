import { useCallback, useEffect, useState } from 'react'

import { Outlet, useLocation, useNavigate as useRouterNavigate, useSearchParams } from 'react-router'

import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@/console/styles/console.css'

import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { cn } from '@/lib/utils'
import { signInRouteFor } from '@/utils/auth-session'

import { CommandPalette } from './command-palette'
import { ConsoleThemeProvider, useConsoleTheme } from './console-theme'
import { ContextPanel } from './context-panel'
import { IconRail } from './icon-rail'
import { Topbar } from './topbar'

const PANEL_COLLAPSED_STORAGE_KEY = 'soit-console-panel-collapsed'

function readPanelCollapsed() {
  if (typeof window === 'undefined') return false
  return window.localStorage.getItem(PANEL_COLLAPSED_STORAGE_KEY) === '1'
}

function ConsoleRoot() {
  const { theme } = useConsoleTheme()
  const [searchParams] = useSearchParams()
  const nosider = Boolean(searchParams.get('nosider'))
  const [panelCollapsed, setPanelCollapsed] = useState(readPanelCollapsed)
  const [searchOpen, setSearchOpen] = useState(false)

  const setCollapsed = useCallback((collapsed: boolean) => {
    setPanelCollapsed(collapsed)
    window.localStorage.setItem(PANEL_COLLAPSED_STORAGE_KEY, collapsed ? '1' : '0')
  }, [])

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault()
        setSearchOpen((open) => !open)
      }
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [])

  return (
    <div
      className={cn(
        'console-root flex h-dvh min-w-0 overflow-hidden bg-background text-foreground',
        theme === 'dark' && 'dark',
      )}
    >
      {!nosider && <IconRail />}
      {!nosider && !panelCollapsed && <ContextPanel onCollapse={() => setCollapsed(true)} />}
      <div className="flex min-w-0 flex-1 flex-col">
        {!nosider && (
          <Topbar
            panelCollapsed={panelCollapsed}
            onExpandPanel={() => setCollapsed(false)}
            onOpenSearch={() => setSearchOpen(true)}
          />
        )}
        <main className="console-glow min-h-0 flex-1 overflow-y-auto px-6 pb-12 pt-5.5">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  )
}

export default function ConsoleLayout() {
  const location = useLocation()
  const navigate = useRouterNavigate()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const clearUser = useUserStore((state) => state.clearUser)

  // Same session guard as the legacy root layout: unauthenticated visits go
  // to sign-in with a return path; authenticated ones sync the user profile.
  // Dev builds skip the interception so screens are viewable without login.
  useEffect(() => {
    if (typeof window === 'undefined') return
    const token = localStorage.getItem('token')
    if (!token) {
      if (import.meta.env.DEV) return
      clearUser()
      const returnTo = `${location.pathname}${location.search}${location.hash}`
      navigate(signInRouteFor(returnTo), { replace: true })
      return
    }
    let canceled = false
    const syncCurrentUser = async () => {
      try {
        const currentUser = await getCurrentUser()
        if (!canceled) setCurrentUser(currentUser)
      } catch (error) {
        console.warn('Failed to sync current user in console layout:', error)
      }
    }
    void syncCurrentUser()
    return () => {
      canceled = true
    }
  }, [clearUser, location.hash, location.pathname, location.search, navigate, setCurrentUser])

  if (
    typeof window !== 'undefined' &&
    !localStorage.getItem('token') &&
    !import.meta.env.DEV
  ) {
    return null
  }

  return (
    <ConsoleThemeProvider>
      <ConsoleRoot />
    </ConsoleThemeProvider>
  )
}
