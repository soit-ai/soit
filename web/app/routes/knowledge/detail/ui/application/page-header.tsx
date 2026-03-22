import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'

interface PageHeaderProps {
  title: string
  onRefresh: () => void
}

export function PageHeader({ title, onRefresh }: PageHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">{t('knowledge.application.breadcrumb.root')}</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage className="flex items-center">
              {title}
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center gap-2">
        <Button variant="outline" onClick={onRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('knowledge.application.actions.refresh')}
        </Button>
      </div>
    </div>
  )
}
