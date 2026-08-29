import type { ComponentType } from 'react'
import { Bot, Database, PieChart, RefreshCw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { getModelWorkbenchOverview } from '@/services/provider-service'

type ModelNavItem = {
  id: 'overview' | 'library' | 'providers'
  titleKey: 'model.sidebar.menu.overview' | 'model.sidebar.menu.library' | 'model.sidebar.menu.providers'
  url: string
  icon: ComponentType<{ size?: number }>
}

const navigation: ModelNavItem[] = [
  { id: 'overview', titleKey: 'model.sidebar.menu.overview', url: '/models/overview', icon: PieChart },
  { id: 'library', titleKey: 'model.sidebar.menu.library', url: '/models/library', icon: Database },
  { id: 'providers', titleKey: 'model.sidebar.menu.providers', url: '/models/providers', icon: Bot },
]

export function BoxSidebar({
  activeTab = 'overview',
  onTabChange,
  ...props
}: {
  activeTab?: string
  onTabChange?: (tabId: string) => void
} & React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const overviewQuery = useQuery({
    queryKey: ['models', 'workbench', 'sidebar'],
    queryFn: () => getModelWorkbenchOverview(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const summary = overviewQuery.data?.summary

  const openItem = (item: ModelNavItem) => {
    onTabChange?.(item.id)
    navigate(item.url)
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="mb-2 flex w-full items-center justify-between px-2">
          <div className="text-lg font-medium text-foreground">{t('model.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="space-y-1 px-2 py-2">
            {navigation.map((item) => (
              <Button
                key={item.id}
                variant={activeTab === item.id ? 'secondary' : 'ghost'}
                className="w-full justify-start gap-2"
                onClick={() => openItem(item)}
              >
                <item.icon size={16} />
                <span>{t(item.titleKey)}</span>
              </Button>
            ))}
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold">{t('model.sidebar.stats.title')}</h3>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                aria-label="Refresh model summary"
                disabled={overviewQuery.isFetching}
                onClick={() => void overviewQuery.refetch()}
              >
                <RefreshCw className={cn('h-4 w-4', overviewQuery.isFetching && 'animate-spin')} />
              </Button>
            </div>
            {overviewQuery.isError ? (
              <p className="mt-3 text-xs text-destructive">Model summary unavailable.</p>
            ) : (
              <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-xs text-muted-foreground">{t('model.sidebar.stats.totalModels')}</div>
                  <div className="font-semibold">{summary?.total_models ?? '-'}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">{t('model.sidebar.stats.activeModels')}</div>
                  <div className="font-semibold">{summary?.available_models ?? '-'}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Month calls</div>
                  <div className="font-semibold">{summary?.month_calls?.toLocaleString() ?? '-'}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">Average latency</div>
                  <div className="font-semibold">{summary?.avg_latency_ms == null ? '-' : `${summary.avg_latency_ms.toLocaleString()}ms`}</div>
                </div>
              </div>
            )}
            <div className="mt-3 text-xs text-muted-foreground">
              {summary?.updated_at ? new Date(summary.updated_at).toLocaleString() : 'Waiting for runtime data'}
            </div>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
