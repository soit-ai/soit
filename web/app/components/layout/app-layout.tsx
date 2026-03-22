import { SidebarProvider } from '@/components/ui/sidebar'
import { Outlet } from 'react-router'

export default function AppLayout() {
  return (
    <SidebarProvider
      style={
        {
          '--root-sidebar-width': '0px',
          '--root-header-height': '0px',
          // '--sidebar-width': '320px',
          height: '100vh',
          minHeight: '500px',
        } as React.CSSProperties
      }
    >
      <div className="flex flex-1 w-full h-full p-0 overflow-hidden">
        <Outlet />
      </div>
    </SidebarProvider>
  )
}
