import * as React from 'react'
import {
  AlertTriangle,
  Archive,
  BarChart,
  ExternalLink,
  History,
  Home,
  PackageCheck,
  RefreshCw,
  ShieldCheck,
  Store,
  Upload,
} from 'lucide-react'
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
import { listPluginCapabilities, listPlugins } from '@/services/plugin-service'

interface PrimaryNavItem {
  id: string
  labelKey: TranslationKey
  url: string
  icon: React.ComponentType<{ size?: number }>
}

const primaryNavItems: PrimaryNavItem[] = [
  {
    id: 'overview',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.workspace',
    url: '/plugins',
    icon: Home,
  },
  {
    id: 'library',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.library',
    url: '/plugins?view=library',
    icon: Store,
  },
  {
    id: 'run-history',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.runHistory',
    url: '/observe/runs?subject_kind=plugin',
    icon: History,
  },
  {
    id: 'market',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.market',
    url: '/plugins?view=market',
    icon: PackageCheck,
  },
  {
    id: 'publish-review',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.publishReview',
    url: '/plugins?view=publish-review',
    icon: Upload,
  },
  {
    id: 'incidents',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.incidents',
    url: '/plugins?view=incidents',
    icon: AlertTriangle,
  },
  {
    id: 'recycle-bin',
    labelKey: 'plugin.workspaceDashboard.sidebar.menu.recycleBin',
    url: '/plugins?view=recycle-bin',
    icon: Archive,
  },
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
  const [searchParams] = useSearchParams()
  const { setOpen } = useSidebar()
  const navigate = useNavigate()
  const resolvedActiveTab = searchParams.get('view') || activeTab

  const {
    data: pluginPage,
    isFetching: pluginsFetching,
    refetch: refetchPlugins,
  } = useQuery({
    queryKey: ['plugins', 'sidebar', 'plugins'],
    queryFn: () => listPlugins({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: capabilityPage,
    isFetching: capabilitiesFetching,
    refetch: refetchCapabilities,
  } = useQuery({
    queryKey: ['plugins', 'sidebar', 'capabilities'],
    queryFn: () => listPluginCapabilities({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const plugins = pluginPage?.items || []
  const capabilities = capabilityPage?.items || []
  const activePlugins = plugins.filter((plugin) => plugin.installed && plugin.enabled).length
  const highRiskCount = plugins.filter((plugin) => {
    const risk = String(plugin.metadata_json?.risk || plugin.metadata_json?.risk_level || '').toLowerCase()
    return risk === 'high' || (plugin.installed && plugin.enabled === false)
  }).length
  const healthRate = plugins.length ? Math.round(((plugins.length - highRiskCount) / plugins.length) * 100) : 100
  const isFetching = pluginsFetching || capabilitiesFetching
  const updatedAt = plugins
    .map((plugin) => plugin.updated_at)
    .filter(Boolean)
    .sort()
    .at(-1)

  const refresh = () => {
    void refetchPlugins()
    void refetchCapabilities()
  }

  const handleMenuItemClick = (item: PrimaryNavItem) => {
    onTabChange?.(item.id)
    navigate(item.url)
  }

  const renderMenuItem = (item: PrimaryNavItem) => {
    const isActive = resolvedActiveTab === item.id || (item.id === 'overview' && resolvedActiveTab === activeTab)

    return (
      <Tooltip key={item.id}>
        <TooltipTrigger asChild>
          <Button
            variant={isActive ? 'secondary' : 'ghost'}
            className="w-full justify-start gap-2"
            onClick={() => handleMenuItemClick(item)}
          >
            <item.icon size={16} />
            <span>{t(item.labelKey)}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">
          <p>{t(item.labelKey)}</p>
        </TooltipContent>
      </Tooltip>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="mb-2 flex w-full items-center justify-between px-2">
          <div className="text-lg font-medium text-foreground">{t('plugin.workspaceDashboard.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('plugin.workspaceDashboard.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full px-2 py-2">
            <div className="space-y-1 animate-in fade-in-50 duration-100">
              {primaryNavItems.slice(0, 4).map(renderMenuItem)}
            </div>
            <div className="mt-5 px-3 text-xs font-semibold uppercase text-muted-foreground">
              {t('plugin.workspaceDashboard.sidebar.management')}
            </div>
            <div className="mt-2 space-y-1">
              {primaryNavItems.slice(4).map(renderMenuItem)}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border bg-card p-3 text-card-foreground shadow-sm">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <PackageCheck className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('plugin.workspaceDashboard.sidebar.stats.title')}</h3>
                </div>
                <Button variant="ghost" size="icon" className="h-6 w-6" onClick={refresh} disabled={isFetching}>
                  <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('plugin.workspaceDashboard.sidebar.stats.total')}</span>
                  <span className="font-semibold">{plugins.length}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('plugin.workspaceDashboard.sidebar.stats.active')}</span>
                  <span className="font-semibold">{activePlugins}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('plugin.workspaceDashboard.sidebar.stats.capabilities')}</span>
                  <span>{capabilities.length}</span>
                </div>
                <Progress value={Math.min(capabilities.length, 100)} className="bg-primary/12" />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('plugin.workspaceDashboard.sidebar.stats.risks')}</span>
                  <span>{highRiskCount}</span>
                </div>
                <Progress value={Math.min(highRiskCount * 10, 100)} className={highRiskCount > 0 ? 'bg-warning/12' : 'bg-muted'} />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('plugin.workspaceDashboard.sidebar.stats.health')}</span>
                  <span>{healthRate}%</span>
                </div>
                <Progress value={healthRate} className="bg-success/12" />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('plugin.workspaceDashboard.sidebar.stats.updatedAt', {
                  timestamp: updatedAt ? new Date(updatedAt).toLocaleString() : '-',
                })}
              </div>

              <div className="mt-2 flex justify-between border-t pt-2 text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('plugin.workspaceDashboard.sidebar.stats.report')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('plugin.workspaceDashboard.sidebar.stats.details')}</span>
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
