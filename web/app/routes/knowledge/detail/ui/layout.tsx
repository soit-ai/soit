import { Link, Outlet, useParams } from 'react-router'
import { useTranslation } from '@/i18n'
import { NavSidebar } from './knowledge-sidebar'
import NavLayout from '@/components/layout/nav-layout'
import { Breadcrumb, BreadcrumbList, BreadcrumbItem, BreadcrumbLink, BreadcrumbSeparator, BreadcrumbPage } from '@/components/ui/breadcrumb'
import type { Route } from '../../+types'

export interface LayoutPageProps extends Route.LoaderArgs {}

function LayoutPage(_props: LayoutPageProps) {
  const { t } = useTranslation()
  const { knowledgeId } = useParams()

  const renderHeader = () => {
    return (
      <>
        <Breadcrumb>
          <BreadcrumbList>
            <BreadcrumbItem className="hidden md:block">
              <BreadcrumbLink asChild>
                <Link to="/knowledge">{t('knowledge.document.header.breadcrumb.root')}</Link>
              </BreadcrumbLink>
            </BreadcrumbItem>
            <BreadcrumbSeparator className="hidden md:block" />
            <BreadcrumbItem>
              <BreadcrumbPage>{t('knowledge.document.header.title')}</BreadcrumbPage>
            </BreadcrumbItem>
          </BreadcrumbList>
        </Breadcrumb>
      </>
    )
  }
  return (
    <NavLayout left={<NavSidebar knowledgeId={knowledgeId}></NavSidebar>} header={renderHeader()}>
      <div className="flex flex-1 flex-col gap-4">  
        <Outlet />
      </div>
    </NavLayout>
  )
}

export default LayoutPage
