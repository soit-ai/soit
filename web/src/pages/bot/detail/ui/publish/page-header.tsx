import { Breadcrumb, BreadcrumbItem, BreadcrumbLink, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from '@/components/ui/breadcrumb'
import { Button } from '@/components/ui/button'
import { Rocket } from 'lucide-react'

interface PageHeaderProps {
  isPublishing: boolean
  onPublish: () => void
}

export function PageHeader({ isPublishing, onPublish }: PageHeaderProps) {
  return (
    <div className="flex flex-row flex-1 items-center justify-between">
      <Breadcrumb>
        <BreadcrumbList>
          <BreadcrumbItem className="hidden md:block">
            <BreadcrumbLink href="#">All Inboxes</BreadcrumbLink>
          </BreadcrumbItem>
          <BreadcrumbSeparator className="hidden md:block" />
          <BreadcrumbItem>
            <BreadcrumbPage>{'发布管理'}</BreadcrumbPage>
          </BreadcrumbItem>
        </BreadcrumbList>
      </Breadcrumb>

      <div className="flex items-center gap-2">
        <Button onClick={onPublish} size={'sm'} disabled={isPublishing}>
          <Rocket className="h-4 w-4 mr-2" />
          {isPublishing ? '发布中...' : '发布新版本'}
        </Button>
      </div>
    </div>
  )
}
