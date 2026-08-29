import { NavLayout } from '@/components/layout/nav-layout'

import Box from './box'
import { BoxSidebar } from './ui/box-sidebar'

function KnowledgePage() {
  return (
    <NavLayout left={<BoxSidebar />}>
      <Box />
    </NavLayout>
  )
}

export default KnowledgePage
