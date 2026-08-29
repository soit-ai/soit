import { Outlet } from 'react-router'
import { NavSidebar } from './workflow-sidebar'
import NavLayout from '@/components/layout/nav-layout'
import type { Route } from '../../+types'

export interface LayoutPageProps extends Route.LoaderArgs {}

function LayoutPage(props: LayoutPageProps) {
  const { params } = props
  return (
    <NavLayout left={<NavSidebar workflowId={(params as any)?.id || ''}></NavSidebar>} fixed>
      <div className="flex flex-1 flex-col gap-4 h-full">
        <Outlet />
      </div>
    </NavLayout>
  )
}

export default LayoutPage
