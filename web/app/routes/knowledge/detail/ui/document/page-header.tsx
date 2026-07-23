import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { ListChecks, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { Link } from 'react-router'

interface PageHeaderProps {
  documentCount: number
  selectedDocs: string[]
  onShowUploadDialog: () => void
  onShowTasksDialog: () => void
  onBatchDelete: () => void
  onRefresh: () => void
}

export function PageHeader({ documentCount, selectedDocs, onShowUploadDialog, onShowTasksDialog, onBatchDelete, onRefresh }: PageHeaderProps) {
  const { t } = useTranslation()

  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink asChild>
              <Link to="/knowledge">{t('knowledge.document.header.breadcrumb.root')}</Link>
            </BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage className="flex items-center">
              {t('knowledge.document.header.title')}
              <Badge variant="outline" className="ml-1">
                {t('knowledge.document.header.count', { count: documentCount })}
              </Badge>
            </BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center gap-2">
        {selectedDocs.length > 0 && (
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" size="sm">
                {t('knowledge.document.header.batchActions', { count: selectedDocs.length })}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem className="text-destructive" onClick={onBatchDelete}>
                <Trash2 className="mr-2 h-4 w-4" />
                {t('knowledge.document.header.actions.deleteSelected')}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        )}
        <Button variant="outline" size="sm" onClick={onShowTasksDialog}>
          <ListChecks className="mr-2 h-4 w-4" />
          {t('knowledge.document.header.actions.tasks')}
        </Button>
        <Button variant="ghost" size="sm" onClick={onRefresh}>
          <RefreshCw className="mr-2 h-4 w-4" />
          {t('knowledge.document.header.actions.refresh')}
        </Button>
        <Button size="sm" onClick={onShowUploadDialog}>
          <Plus className="mr-2 h-4 w-4" />
          {t('knowledge.document.header.actions.add')}
        </Button>
      </div>
    </div>
  )
}
