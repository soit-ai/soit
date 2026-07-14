import Box from './box'
import { BoxSidebar } from './ui/box-sidebar'
import { NavLayout } from '@/components/layout/nav-layout'

function PluginIndexPage() {
  return (
    <NavLayout left={<BoxSidebar />}>
      <Box />
    </NavLayout>
  )
}

export default PluginIndexPage
