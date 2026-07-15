import * as React from 'react'
import {
  AlertTriangle,
  BarChart3,
  Bot,
  Clock3,
  ExternalLink,
  Home,
  Library,
  MessageCircle,
  RefreshCw,
  Store,
  Trash2,
} from 'lucide-react'
import type { ComponentType } from 'react'
import { useSearchParams } from 'react-router'

import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarInput,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import { getAgentWorkbench } from '@/services/agent-service'

interface AgentSidebarItem {
  id: string
  labelKey: TranslationKey
  url: string
  icon: ComponentType<{ className?: string }>
}

const primaryItems = [
  {
    id: 'overview',
    labelKey: 'agent.sidebar.menu.overview',
    url: '/agents?view=overview',
    icon: Home,
  },
  {
    id: 'library',
    labelKey: 'agent.sidebar.menu.library',
    url: '/agents?view=library',
    icon: Library,
  },
  {
    id: 'runs',
    labelKey: 'agent.sidebar.menu.runs',
    url: '/observe/runs?mode=agent',
    icon: Clock3,
  },
  {
    id: 'marketplace',
    labelKey: 'agent.sidebar.menu.marketplace',
    url: '/agents?view=marketplace',
    icon: Store,
  },
] satisfies AgentSidebarItem[]

const managementItems = [
  {
    id: 'review',
    labelKey: 'agent.sidebar.management.review',
    url: '/agents?view=management/review',
    icon: MessageCircle,
  },
  {
    id: 'exceptions',
    labelKey: 'agent.sidebar.management.exceptions',
    url: '/agents?view=management/exceptions',
    icon: AlertTriangle,
  },
  {
    id: 'recycle',
    labelKey: 'agent.sidebar.management.recycle',
    url: '/agents?view=management/recycle',
    icon: Trash2,
  },
 ] satisfies AgentSidebarItem[]

function SidebarMenuButton({
  item,
  active,
  onClick,
}: {
  item: AgentSidebarItem
  active: boolean
  onClick: () => void
}) {
  const { t } = useTranslation()
  const Icon = item.icon

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant={active ? 'secondary' : 'ghost'}
          className={cn(
            'relative h-10 w-full justify-start gap-2 rounded-lg px-3 text-sm',
            active && 'bg-primary/10 text-primary shadow-none hover:bg-primary/12',
          )}
          onClick={onClick}
        >
          {active ? <span className="absolute left-0 top-2 h-6 w-1 rounded-r-full bg-primary" /> : null}
          <Icon className="h-4 w-4" />
          <span className="truncate">{t(item.labelKey)}</span>
        </Button>
      </TooltipTrigger>
      <TooltipContent side="right">
        <p>{t(item.labelKey)}</p>
      </TooltipContent>
    </Tooltip>
  )
}

function MiniSparkline({
  values,
  className,
}: {
  values: number[]
  className?: string
}) {
  const path = React.useMemo(() => {
    const min = Math.min(...values)
    const max = Math.max(...values)
    const range = max - min || 1
    return values
      .map((value, index) => {
        const x = Number(((index * 72) / (values.length - 1)).toFixed(2))
        const y = Number((24 - ((value - min) / range) * 24).toFixed(2))
        return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
      })
      .join(' ')
  }, [values])

  return (
    <svg className={cn('h-7 w-20', className)} viewBox="0 0 72 24" aria-hidden="true">
      <path d={path} fill="none" stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </svg>
  )
}

export function AgentBoxSidebar({
  activeTab = 'overview',
  onTabChange,
  ...props
}: {
  activeTab?: string
  onTabChange?: (tabId: string) => void
} & React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setOpen } = useSidebar()
  const [searchParams] = useSearchParams()
  const resolvedActiveTab = searchParams.get('view') || activeTab
  const { data: workbench, isFetching, refetch } = useQuery({
    queryKey: ['agents', 'workbench', 'sidebar'],
    queryFn: () => getAgentWorkbench({ page_size: 1 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const handleNavigate = (item: AgentSidebarItem) => {
    onTabChange?.(item.id)
    navigate(item.url)
  }

  const summary = workbench?.summary
  const successRate = summary?.success_rate ?? 0

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="mb-2 flex w-full items-center justify-between px-2">
          <div className="text-lg font-semibold text-foreground">{t('agent.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('agent.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full px-2 py-2">
            <div className="space-y-1">
              {primaryItems.map((item) => (
                <SidebarMenuButton
                  key={item.id}
                  item={item}
                  active={resolvedActiveTab === item.id || (item.id === 'overview' && !resolvedActiveTab)}
                  onClick={() => handleNavigate(item)}
                />
              ))}
            </div>

            <div className="mt-5 space-y-1">
              <h2 className="mb-2 px-3 text-xs font-semibold text-muted-foreground">
                {t('agent.sidebar.management.title')}
              </h2>
              {managementItems.map((item) => (
                <SidebarMenuButton
                  key={item.id}
                  item={item}
                  active={resolvedActiveTab === `management/${item.id}` || resolvedActiveTab === item.id}
                  onClick={() => handleNavigate(item)}
                />
              ))}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border border-border bg-panel p-3 text-card-foreground shadow-sm">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex min-w-0 items-center">
                  <Bot className="mr-2 h-5 w-5 shrink-0 text-primary" />
                  <h3 className="truncate font-semibold">{t('agent.sidebar.stats.title')}</h3>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-xs"
                  aria-label={t('agent.sidebar.stats.refresh')}
                  title={t('agent.sidebar.stats.refresh')}
                  className="h-7 w-7"
                  onClick={() => refetch()}
                  disabled={isFetching}
                >
                  <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('agent.sidebar.stats.totalAgents')}</span>
                  <span className="font-semibold text-foreground">{summary?.total_agents ?? 0}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('agent.sidebar.stats.onlineAgents')}</span>
                  <span className="font-semibold text-foreground">{summary?.running_agents ?? 0}</span>
                </div>
              </div>

              <div className="border-t border-border pt-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground">{t('agent.sidebar.stats.todayCalls')}</div>
                    <div className="text-sm font-semibold text-foreground">{(summary?.today_calls ?? 0).toLocaleString()}</div>
                  </div>
                  <MiniSparkline values={[5, 7, 6, 8, 11, 9, 13, 7, 10, 9]} className="text-blue-500 dark:text-blue-300" />
                </div>
              </div>

              <div className="border-t border-border pt-3">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-muted-foreground">{t('agent.sidebar.stats.successRate')}</div>
                    <div className="text-sm font-semibold text-foreground">{successRate.toFixed(successRate % 1 === 0 ? 0 : 1)}%</div>
                  </div>
                  <MiniSparkline values={[8, 9, 8, 11, 10, 13, 9, 12, 11, 14]} className="text-emerald-500 dark:text-emerald-300" />
                </div>
                <Progress value={successRate} className="mt-2 h-1.5 bg-emerald-100 dark:bg-emerald-400/10" />
              </div>

              <div className="border-t border-border pt-3 text-xs text-muted-foreground">
                {t('agent.sidebar.stats.updatedAt', { timestamp: summary?.updated_at ? new Date(summary.updated_at).toLocaleString() : '-' })}
              </div>

              <div className="flex justify-between border-t border-border pt-2 text-xs">
                <Button type="button" variant="ghost" size="sm" className="h-8 gap-1 px-2">
                  <BarChart3 className="h-3.5 w-3.5" />
                  <span>{t('agent.sidebar.stats.report')}</span>
                </Button>
                <Button type="button" variant="ghost" size="sm" className="h-8 gap-1 px-2">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('agent.sidebar.stats.details')}</span>
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
