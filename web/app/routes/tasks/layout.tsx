import { Outlet, useLocation } from 'react-router'

import { NavLayout } from '@/components/layout/nav-layout'

import { TaskSidebar } from './ui/box-sidebar'

function activeTaskTab(pathname: string) {
  if (pathname.startsWith('/tasks/processing')) return 'processing'
  return 'center'
}

function TaskLayout() {
  const location = useLocation()

  return (
    <NavLayout left={<TaskSidebar activeTab={activeTaskTab(location.pathname)} />}>
      <Outlet />
    </NavLayout>
  )
}

export default TaskLayout
