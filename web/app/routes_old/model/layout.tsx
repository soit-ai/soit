import { Outlet, useLocation } from 'react-router'

import { NavLayout } from '@/components/layout/nav-layout'
import { DrawerProvider } from '@/hooks/use-drawer'

import { BoxSidebar } from './ui/box-sidebar'

function getActiveTab(pathname: string) {
  if (pathname.startsWith('/models/library')) return 'library'
  if (pathname.startsWith('/models/providers')) return 'providers'
  return 'overview'
}

function ModelLayout() {
  const location = useLocation()

  return (
    <DrawerProvider>
      <NavLayout left={<BoxSidebar activeTab={getActiveTab(location.pathname)} />}>
        <Outlet />
      </NavLayout>
    </DrawerProvider>
  )
}

export default ModelLayout
