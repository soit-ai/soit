import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate as useRouterNavigate, useSearchParams } from 'react-router'

import { RootSidebar } from '@/components/nav/root-sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { RootHeader } from '@/components/nav/root-header'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { signInRouteFor } from '@/utils/auth-session'

export default function RootLayout() {
  const [searchParams] = useSearchParams()
  const location = useLocation()
  const navigate = useRouterNavigate()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const clearUser = useUserStore((state) => state.clearUser)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    const token = localStorage.getItem('token')
    if (!token) {
      // Dev builds skip the sign-in interception for local screen review.
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
        if (!canceled) {
          setCurrentUser(currentUser)
        }
      } catch (error) {
        console.warn('Failed to sync current user in root layout:', error)
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
    <SidebarProvider
      style={
        {
          '--root-sidebar-width': searchParams.get('nosider') ? '0px' : '64px',
          '--root-header-height': searchParams.get('nosider') ? '0px' : '72px',
          height: '100vh',
          minHeight: '500px',
        } as React.CSSProperties
      }
    >
      {searchParams.get('nosider') ? (
        <div className="flex flex-1 w-full h-full p-0 overflow-hidden">
          <Outlet />
        </div>
      ) : (
        <div className="flex h-full w-full overflow-hidden bg-transparent">
          <RootSidebar className="fixed z-30 flex h-full w-[calc(var(--root-sidebar-width)+1px)] flex-col overflow-hidden border-r border-border/60 bg-shell/78 p-0 backdrop-blur-xl" />
          <div className="ml-[calc(var(--root-sidebar-width)+1px)] flex h-full min-w-0 flex-1 flex-col p-0">
            <RootHeader />
            <div className="flex h-full min-w-0 w-full flex-1 flex-col gap-0 overflow-hidden p-0 pt-[var(--root-header-height)]">
              <ScrollArea className="flex min-w-0 flex-1 h-screen">
                <Outlet />
              </ScrollArea>
            </div>
          </div>
        </div>
      )}
    </SidebarProvider>
  )
}
