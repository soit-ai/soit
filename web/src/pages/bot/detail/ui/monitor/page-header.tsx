import { Download, RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { Button } from '@/components/ui/button'
import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'

interface PageHeaderProps {
  title: string
  timeRange: string
  onTimeRangeChange: (value: string) => void
  onRefresh: () => void
}

export function PageHeader({ title, timeRange, onTimeRangeChange, onRefresh }: PageHeaderProps) {
  const { t } = useTranslation()
  return (
    <div className="flex flex-row flex-1 items-center justify-between">
     <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">{t('bot.monitor.header.root')}</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>{title}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>
      <div className="flex items-center gap-2">
        
        <Button variant="outline" size="sm" onClick={onRefresh}>
          <RefreshCw className="h-4 w-4 mr-1" />
          {t('bot.monitor.actions.refresh')}
        </Button>
        <Button variant="outline" size="sm">
          <Download className="h-4 w-4 mr-1" />
          {t('bot.monitor.actions.export')}
        </Button>
      </div>
    </div>
  )
}
