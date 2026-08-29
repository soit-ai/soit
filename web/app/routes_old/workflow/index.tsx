import { useTranslation } from '@/i18n'
import Box from './box'
import { BoxSidebar } from './ui/box-sidebar'
import { NavLayout, NavHeader } from '@/components/layout/nav-layout'
import { RefreshCwIcon } from 'lucide-react'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
function IndexPage() {
  // const { setTitle } = useSiteContext()
  const { t } = useTranslation()

  return (
    <NavLayout left={<BoxSidebar></BoxSidebar>}>
      <Box></Box>
    </NavLayout>
  )
}

export default IndexPage
