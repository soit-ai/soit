import { useEffect } from 'react'
import { Outlet, useSearchParams } from 'react-router'

import { RootSidebar } from '@/components/nav/root-sidebar'
import { SidebarProvider } from '@/components/ui/sidebar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { RootHeader } from '@/components/nav/root-header'
import { getCurrentUser } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'

export default function RootLayout() {
  const [searchParams] = useSearchParams()
  const setCurrentUser = useUserStore((state) => state.setCurrentUser)
  const clearUser = useUserStore((state) => state.clearUser)

  useEffect(() => {
    if (typeof window === 'undefined') {
      return
    }
    const token = localStorage.getItem('token')
    if (!token) {
      clearUser()
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
  }, [clearUser, setCurrentUser])

  return (
    <SidebarProvider
      style={
        {
          '--root-sidebar-width': searchParams.get('nosider') ? '0px' : '48px',
          '--root-header-height': searchParams.get('nosider') ? '0px' : '61px',
          // '--sidebar-width': '320px',
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
        <div className="flex flex-1 w-full h-full p-0 overflow-hidden">
          <RootSidebar className="flex flex-col w-[calc(var(--root-sidebar-width)+1px)] border-r h-full fixed p-0 overflow-hidden  z-20" />
          <div className="flex flex-1 h-full w-full flex-col p-0 ml-[calc(var(--root-sidebar-width)+1px)]">
            <RootHeader />
            <div className="flex flex-1 w-full h-full flex-col gap-0 p-0 overflow-hidden pt-[var(--root-header-height)]">
              <ScrollArea className="flex flex-1 h-screen">
              <Outlet />
              </ScrollArea>
            </div>
          </div>
        </div>
      )}
    </SidebarProvider>
  )
}
