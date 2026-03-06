import { RefreshCw, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { useTranslation } from '@/i18n'

type LogHeaderProps = {
  onRefresh: () => void
}

export function LogHeader({ onRefresh }: LogHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">All Inboxes</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>{t('bot.log.header.title')}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="h-4 w-4 mr-1" />
          {t('bot.log.header.refresh')}
        </Button>
        <Button variant="outline" size="sm">
          <Download className="h-4 w-4 mr-1" />
          {t('bot.log.header.export')}
        </Button>
      </div>
    </div>
  )
}
