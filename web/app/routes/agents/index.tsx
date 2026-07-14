import { NavLayout } from '@/components/layout/nav-layout'

import AgentBoxPage from './box'
import { AgentBoxSidebar } from './ui/box-sidebar'

function AgentsPage() {
  return (
    <NavLayout left={<AgentBoxSidebar />}>
      <AgentBoxPage />
    </NavLayout>
  )
}

export default AgentsPage
