import * as React from 'react'
import {
  SquareTerminal,
  History,
  BarChart,
  Home,
  Upload,
  RefreshCw,
  ExternalLink,
  Layers,
} from 'lucide-react'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { useSearchParams } from 'react-router'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { useQuery } from '@/hooks/use-query'
import { getWorkflowWorkbench } from '@/services/workflow-service'

interface PrimaryNavItem {
  id: string
  labelKey: TranslationKey
  url: string
  icon: React.ComponentType<{ size?: number }>
}

const primaryNavItems: PrimaryNavItem[] = [
  {
    id: 'overview',
    labelKey: 'workflow.sidebar.menu.workspace',
    url: '/workflow',
    icon: Home,
  },
  {
    id: 'library',
    labelKey: 'workflow.sidebar.menu.library',
    url: '/workflow?view=library',
    icon: Layers,
  },
  {
    id: 'run-history',
    labelKey: 'workflow.sidebar.menu.runHistory',
    url: '/observe/runs?mode=workflow',
    icon: History,
  },
  {
    id: 'publish-management',
    labelKey: 'workflow.sidebar.menu.publishManagement',
    url: '/workflow?view=publish-management',
    icon: Upload,
  },
]

export function BoxSidebar({ activeTab = 'overview', onTabChange, ...props }: { activeTab?: string, onTabChange?: (tabId: string) => void } & React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const resolvedActiveTab = searchParams.get('view') || activeTab
  const {
    data: workbench,
    isFetching,
    refetch,
  } = useQuery({
    queryKey: ['workflows', 'workbench', 'sidebar'],
    queryFn: () => getWorkflowWorkbench({ page_size: 1 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const summary = workbench?.summary
  const runningRuns = workbench?.items.filter((item) => item.status === 'running').length ?? 0
  const healthStatus = (summary?.recent_exceptions ?? 0) > 0 ? 'warning' : 'normal'

  const handleMenuItemClick = (itemId: string) => {
    const item = primaryNavItems.find(item => item.id === itemId)
    if (onTabChange) {
      onTabChange(itemId)
    }
    if (item?.url) {
      navigate(item.url)
    }
  }

  const { setOpen } = useSidebar()
  const navigate = useNavigate()
  
  const renderMenuItem = (item: PrimaryNavItem) => {
    const isActive = resolvedActiveTab === item.id

    return (
      <div key={item.id} className="space-y-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isActive ? "secondary" : "ghost"}
              className="w-full justify-start gap-2 relative"
              onClick={() => handleMenuItemClick(item.id)}
            >
              <div className="relative">
                <item.icon size={16} />
              </div>
              <span>{t(item.labelKey)}</span>
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{t(item.labelKey)}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }
  
  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="flex w-full items-center justify-between mb-2 px-2">
          <div className="text-lg font-medium text-foreground">{t('workflow.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('workflow.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            <div className="px-2 py-2">
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {primaryNavItems.map(renderMenuItem)}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <SquareTerminal className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('workflow.sidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => refetch()}
                  disabled={isFetching}
                >
                  <RefreshCw className={cn(
                    "h-4 w-4",
                    isFetching && "animate-spin"
                  )} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('workflow.sidebar.stats.totalWorkflows')}</span>
                  <span className="font-semibold">{summary?.total_workflows ?? 0}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('workflow.sidebar.stats.activeWorkflows')}</span>
                  <span className="font-semibold">{summary?.published_workflows ?? 0}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.recentRuns')}</span>
                  <span>{summary?.today_runs ?? 0}</span>
                </div>
                <Progress
                  value={Math.min(summary?.today_runs ?? 0, 100)}
                  className={cn(
                    healthStatus === 'warning' ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.runningRuns')}</span>
                  <span>{runningRuns}</span>
                </div>
                <Progress
                  value={Math.min(runningRuns * 10, 100)}
                  className={cn(
                    runningRuns > 0 ? "bg-blue-200" : "bg-muted"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.failedRuns')}</span>
                  <span>{summary?.recent_exceptions ?? 0}</span>
                </div>
                <Progress
                  value={Math.min((summary?.recent_exceptions ?? 0) * 10, 100)}
                  className={(summary?.recent_exceptions ?? 0) > 0 ? "bg-amber-200" : "bg-muted"}
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('workflow.sidebar.stats.updatedAt', { timestamp: summary?.updated_at ? new Date(summary.updated_at).toLocaleString() : '-' })}
              </div>
              
              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('workflow.sidebar.stats.usageReport')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('workflow.sidebar.stats.details')}</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
