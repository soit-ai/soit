import { useTranslation } from '@/i18n'
import Box from './box'
import { BoxSidebar } from './ui/box-sidebar'
import { NavLayout, NavHeader } from '@/components/layout/nav-layout'
import { Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbSeparator, BreadcrumbPage } from '@/components/ui/breadcrumb'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { RefreshCwIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
function IndexPage() {
  // const { setTitle } = useSiteContext()
  const { t } = useTranslation()
  // useEffect(() => {
  //   const title = t('window.title', { title: t('c.store') })
  //   setTitle(title)
  // }, [setTitle, t])

  return (
    <NavLayout left={<BoxSidebar></BoxSidebar>}>
      <Box></Box>
    </NavLayout>
  )
}

export default IndexPage
