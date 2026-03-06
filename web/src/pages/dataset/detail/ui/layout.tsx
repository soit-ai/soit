import { Outlet, useParams } from 'react-router'
import { useTranslation } from '@/i18n'
import { NavSidebar } from './app-sidebar'
import NavLayout from '@/components/layout/nav-layout'
import { Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbSeparator, BreadcrumbPage } from '@/components/ui/breadcrumb'
import { SidebarTrigger } from '@/components/ui/sidebar'
import { Separator } from '@radix-ui/react-separator'
import type { Route } from '../../+types'

export interface LayoutPageProps extends Route.LoaderArgs {}

function LayoutPage(props: LayoutPageProps) {
  const { t } = useTranslation()
  const { datasetId } = useParams()
  // const { setTitle } = useSiteContext()
  // useEffect(() => {
  //   const title = t('window.title', { title: t('c.store') })
  //   setTitle(title)
  // }, [setTitle, t])

  const renderHeader = () => {
    return (
      <>
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden md:block">
              <BreadcrumbLink href="#">All Inboxes</BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>Inbox</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </>
    )
  }
  return (
    <NavLayout left={<NavSidebar datasetId={datasetId}></NavSidebar>} header={renderHeader()}>
      <div className="flex flex-1 flex-col gap-4">  
        <Outlet />
      </div>
    </NavLayout>
  )
}

export default LayoutPage
