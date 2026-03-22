import { useTranslation } from '@/i18n'
import { BoxSidebar } from './ui/box-sidebar'
import { NavLayout, NavHeader } from '@/components/layout/nav-layout'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@/components/ui/separator'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { RefreshCwIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Outlet } from 'react-router'
function IndexPage() {
  // const { setTitle } = useSiteContext()
  const { t } = useTranslation()

  const renderHeader = () => {
    return (
      <div className="flex flex-1 justify-between">
        <div className="flex items-center gap-2">
          <Breadcrumb>
            <BreadcrumbList>
              <BreadcrumbItem className="hidden md:block">
                <BreadcrumbLink >All Inboxes</BreadcrumbLink>
              </BreadcrumbItem>
              <BreadcrumbSeparator className="hidden md:block" />
              <BreadcrumbItem>
                <BreadcrumbPage>Inbox</BreadcrumbPage>
              </BreadcrumbItem>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div className="flex gap-2">
          <Button size={'sm'} variant={'outline'} title="Refresh Data">
            <RefreshCwIcon></RefreshCwIcon>
          </Button>
        </div>
      </div>
    )
  }
  return (
    <NavLayout left={<BoxSidebar></BoxSidebar>}>
      {/* <NavHeader>{renderHeader()}</NavHeader> */}
      <div className="flex flex-1 flex-col gap-4">
        <Outlet />
      </div>
    </NavLayout>
  )
}

export default IndexPage
