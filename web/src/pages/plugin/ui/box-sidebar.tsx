import * as React from 'react'
import { useState } from 'react'
import {
  Send,
  BrainCog,
  Settings2,
  LifeBuoy,
  Workflow,
  Star,
  Clock,
  Upload,
  BarChart,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Puzzle,
  Code,
  Zap,
  Cloud,
  GitBranch,
  Package
} from 'lucide-react'

import { useTranslation } from '@/i18n'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface PluginStatus {
  totalPlugins: number
  activePlugins: number
  recentUpdates: number
  storageUsage: number
  storageLimit: number
  lastUpdated: string
  healthStatus: 'normal' | 'warning' | 'critical'
  apiUsage: {
    calls: number
    limit: number
  }
}

const navData = {
  navMain: [
    {
      id: 'overview',
      titleKey: 'plugin.sidebar.main.overview',
      url: '/plugins/dashboard',
      icon: Puzzle,
      isActive: true,
      items: [],
    },
    {
      id: 'browse',
      titleKey: 'plugin.sidebar.main.browse',
      url: '/plugins/browse',
      icon: BrainCog,
      items: [
        {
          id: 'all',
          titleKey: 'plugin.sidebar.browse.all',
          url: '/plugins/browse/all',
        },
        {
          id: 'recent',
          titleKey: 'plugin.sidebar.browse.recent',
          url: '/plugins/browse/recent',
          icon: Clock,
        },
        {
          id: 'favorites',
          titleKey: 'plugin.sidebar.browse.favorites',
          url: '/plugins/browse/favorites',
          icon: Star,
        },
        {
          id: 'uploads',
          titleKey: 'plugin.sidebar.browse.uploads',
          url: '/plugins/browse/uploads',
          icon: Upload,
        },
      ],
    },
    {
      id: 'development',
      titleKey: 'plugin.sidebar.main.development',
      url: '/plugins/development',
      icon: Code,
      items: [
        {
          id: 'editor',
          titleKey: 'plugin.sidebar.development.editor',
          url: '/plugins/development/editor',
        },
        {
          id: 'debug',
          titleKey: 'plugin.sidebar.development.debug',
          url: '/plugins/development/debug',
        },
        {
          id: 'version',
          titleKey: 'plugin.sidebar.development.version',
          url: '/plugins/development/version',
          icon: GitBranch,
        },
      ],
    },
    {
      id: 'integration',
      titleKey: 'plugin.sidebar.main.integration',
      url: '/plugins/integration',
      icon: Zap,
      items: [
        {
          id: 'api',
          titleKey: 'plugin.sidebar.integration.api',
          url: '/plugins/integration/api',
          icon: Cloud,
        },
        {
          id: 'workflow',
          titleKey: 'plugin.sidebar.integration.workflow',
          url: '/plugins/integration/workflow',
          icon: Workflow,
        },
      ],
    },
    {
      id: 'management',
      titleKey: 'plugin.sidebar.main.management',
      url: '/plugins/management',
      icon: Settings2,
      items: [
        {
          id: 'dependencies',
          titleKey: 'plugin.sidebar.management.dependencies',
          url: '/plugins/management/dependencies',
          icon: Package,
        },
        {
          id: 'permissions',
          titleKey: 'plugin.sidebar.management.permissions',
          url: '/plugins/management/permissions',
        },
        {
          id: 'analytics',
          titleKey: 'plugin.sidebar.management.analytics',
          url: '/plugins/management/analytics',
          icon: BarChart,
        },
      ],
    },
  ],
  navSecondary: [
    {
      id: 'docs',
      titleKey: 'plugin.sidebar.secondary.docs',
      url: '/help/plugin',
      icon: LifeBuoy,
    },
    {
      id: 'feedback',
      titleKey: 'plugin.sidebar.secondary.feedback',
      url: '/observability/feedback',
      icon: Send,
    },
  ],
  projects: [
    {
      id: 'favorites',
      nameKey: 'plugin.sidebar.projects.favorites',
      url: '/plugins/favorites',
      icon: Star,
    },
    {
      id: 'recent',
      nameKey: 'plugin.sidebar.projects.recent',
      url: '/plugins/recent',
      icon: Clock,
    },
    {
      id: 'mine',
      nameKey: 'plugin.sidebar.projects.mine',
      url: '/plugins/my',
      icon: Puzzle,
    },
  ],
}

export function BoxSidebar({
  activeTab = 'overview',
  onTabChange,
  ...props
}: {
  activeTab?: string
  onTabChange?: (tabId: string) => void
} & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()
  const [pluginStatus, setPluginStatus] = useState<PluginStatus>(() => ({
    totalPlugins: 78,
    activePlugins: 42,
    recentUpdates: 15,
    storageUsage: 3.2,
    storageLimit: 10,
    lastUpdated: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
    healthStatus: 'normal',
    apiUsage: {
      calls: 356,
      limit: 500,
    },
  }))

  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})

  // Refresh plugin status.
  const refreshPluginStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setPluginStatus({
        totalPlugins: 78,
        activePlugins: Math.floor(Math.random() * 10) + 35,
        recentUpdates: Math.floor(Math.random() * 10) + 10,
        storageUsage: parseFloat((Math.random() * 1 + 3).toFixed(1)),
        storageLimit: 10,
        lastUpdated: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
        healthStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        apiUsage: {
          calls: Math.floor(Math.random() * 50) + 330,
          limit: 500,
        },
      })
      setIsRefreshing(false)
    }, 800)
  }

  // Toggle menu item expand/collapse state.
  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId],
    }))
  }

  // Handle menu item click.
  const handleMenuItemClick = (itemId: string) => {
    const item = navData.navMain.find(navItem => navItem.id === itemId)
    if (item?.items && item.items.length > 0) {
      toggleMenuItem(itemId)
      return
    }

    if (onTabChange) {
      onTabChange(itemId)
    }
  }

  // Handle sub menu item click.
  const handleSubItemClick = (parentId: string, subItemId: string) => {
    if (onTabChange) {
      onTabChange(`${parentId}/${subItemId}`)
    }
  }

  const { setOpen } = useSidebar()
  const navigate = useNavigate()

  // Render menu item.
  const renderMenuItem = (item: any) => {
    const isActive = activeTab === item.id || activeTab.startsWith(`${item.id}/`)
    const isExpanded = expandedItems[item.id] || false
    const hasSubItems = item.items && item.items.length > 0
    const title = t(item.titleKey)
    const description = item.descriptionKey ? t(item.descriptionKey) : title

    return (
      <div key={item.id} className="space-y-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isActive ? 'secondary' : 'ghost'}
              className="w-full justify-start gap-2 relative"
              onClick={() => handleMenuItemClick(item.id)}
            >
              <div className="relative">
                {item.icon && <item.icon size={16} />}
              </div>
              <span>{title}</span>
              {hasSubItems && (
                <div className="ml-auto">
                  {isExpanded ? (
                    <ChevronDown size={14} />
                  ) : (
                    <ChevronRight size={14} />
                  )}
                </div>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{description}</p>
          </TooltipContent>
        </Tooltip>

        {hasSubItems && isExpanded && (
          <div className="pl-8 space-y-1 animate-in slide-in-from-left-5 duration-200">
            {item.items.map((subItem: any) => {
              const isSubActive = activeTab === `${item.id}/${subItem.id}`
              const subTitle = t(subItem.titleKey)
              const subDescription = subItem.descriptionKey ? t(subItem.descriptionKey) : subTitle

              return (
                <Tooltip key={subItem.id}>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant={isSubActive ? 'secondary' : 'ghost'}
                      className="w-full justify-start gap-2 text-sm"
                      onClick={() => handleSubItemClick(item.id, subItem.id)}
                    >
                      <span>{subTitle}</span>
                      {subItem.icon && <subItem.icon size={14} className="ml-auto" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{subDescription}</p>
                  </TooltipContent>
                </Tooltip>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="flex w-full items-center justify-between mb-2 px-2">
          <div className="text-lg font-medium text-foreground">{t('plugin.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('plugin.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            {/* Primary menu. */}
            <div className="px-2 py-2">
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {navData.navMain.map(renderMenuItem)}
              </div>
            </div>

            {/* Favorite plugins menu. */}
            <div className="px-2 py-2">
              <h2 className="px-3 mb-2 text-sm font-semibold tracking-tight text-muted-foreground">
                {t('plugin.sidebar.projects.title')}
              </h2>
              <div className="space-y-1">
                {navData.projects.map((project: any) => (
                  <Button
                    key={project.id}
                    variant="ghost"
                    className="w-full justify-start gap-2"
                    onClick={() => {
                      setOpen(false)
                      navigate(project.url)
                    }}
                  >
                    {project.icon && <project.icon size={16} />}
                    <span>{t(project.nameKey)}</span>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        {/* Plugin stats card. */}
        <div className="px-2 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Puzzle className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('plugin.sidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshPluginStatus}
                  disabled={isRefreshing}
                >
                  <RefreshCw
                    className={cn(
                      'h-4 w-4',
                      isRefreshing && 'animate-spin'
                    )}
                  />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('plugin.sidebar.stats.total')}</span>
                  <span className="font-semibold">{pluginStatus.totalPlugins}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('plugin.sidebar.stats.active')}</span>
                  <span className="font-semibold">{pluginStatus.activePlugins}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('plugin.sidebar.stats.storageUsage')}</span>
                  <span>{pluginStatus.storageUsage}/{pluginStatus.storageLimit} GB</span>
                </div>
                <Progress
                  value={(pluginStatus.storageUsage / pluginStatus.storageLimit) * 100}
                  className={cn(
                    pluginStatus.storageUsage / pluginStatus.storageLimit > 0.8 ? 'bg-amber-200' : 'bg-blue-200'
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('plugin.sidebar.stats.apiCalls')}</span>
                  <span>{pluginStatus.apiUsage.calls}/{pluginStatus.apiUsage.limit}</span>
                </div>
                <Progress
                  value={(pluginStatus.apiUsage.calls / pluginStatus.apiUsage.limit) * 100}
                  className="bg-purple-200"
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('plugin.sidebar.stats.updatedAt', { time: pluginStatus.lastUpdated })}
              </div>

              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('plugin.sidebar.stats.report')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('plugin.sidebar.stats.details')}</span>
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
