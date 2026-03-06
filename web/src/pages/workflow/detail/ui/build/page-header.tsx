import React from 'react'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Save } from 'lucide-react'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { useTranslation } from '@/i18n'

interface PageHeaderProps {
  id?: string
  title?: string
  navigate: (path: string) => void
  handleSave: () => void
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  id,
  title,
  navigate,
  handleSave
}) => {
  const { t } = useTranslation()
  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">{t('workflow.build.header.root')}</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center space-x-2">
        <Button variant="outline" onClick={() => navigate(`/bot/${id || ''}`)}>{t('workflow.build.header.cancel')}</Button>
        <Button onClick={handleSave}>
          {t('workflow.build.header.save')} <Save className="ml-2 h-4 w-4" />
        </Button>
      </div>
    </div>
  )
}

export default PageHeader
