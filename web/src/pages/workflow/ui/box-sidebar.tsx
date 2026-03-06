import * as React from 'react'
import { useState } from 'react'
import {
  Send,
  Bot,
  Settings2,
  SquareTerminal,
  History,
  Star,
  Users,
  BarChart,
  Database,
  Home,
  Clock,
  Upload,
  Share2,
  DownloadCloud,
  Lock,
  HelpCircle,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Play,
  Layers,
  GitBranch,
  Zap,
  Webhook,
  Activity,
} from 'lucide-react'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n'

// Workflow status model.
interface WorkflowStatus {
  totalWorkflows: number;
  activeWorkflows: number;
  recentRuns: number;
  cpuUsage: number;
  memoryUsage: number;
  resourceLimit: number;
  lastUpdated: string;
  healthStatus: 'normal' | 'warning' | 'critical';
  apiUsage: {
    calls: number;
    limit: number;
  };
}

const data = {
  navMain: [
    {
      id: 'overview',
      labelKey: 'workflow.sidebar.menu.overview',
      url: '/workflow/dashboard',
      icon: Home,
      items: [],
    },
    {
      id: 'my-workflows',
      labelKey: 'workflow.sidebar.menu.myWorkflows.title',
      url: '/workflow/my-workflows',
      icon: Layers,
      items: [
        {
          id: 'all',
          labelKey: 'workflow.sidebar.menu.myWorkflows.all',
          url: '/workflow/my-workflows/all',
        },
        {
          id: 'recent',
          labelKey: 'workflow.sidebar.menu.myWorkflows.recent',
          url: '/workflow/my-workflows/recent',
          icon: Clock,
        },
        {
          id: 'favorites',
          labelKey: 'workflow.sidebar.menu.myWorkflows.favorites',
          url: '/workflow/my-workflows/favorites',
          icon: Star,
        },
        {
          id: 'created',
          labelKey: 'workflow.sidebar.menu.myWorkflows.created',
          url: '/workflow/my-workflows/created',
          icon: Upload,
        },
      ],
    },
    {
      id: 'execution',
      labelKey: 'workflow.sidebar.menu.execution.title',
      url: '/workflow/execution',
      icon: Play,
      items: [
        {
          id: 'history',
          labelKey: 'workflow.sidebar.menu.execution.history',
          url: '/workflow/execution/history',
          icon: History,
        },
        {
          id: 'schedule',
          labelKey: 'workflow.sidebar.menu.execution.schedule',
          url: '/workflow/execution/schedule',
          icon: Clock,
        },
        {
          id: 'monitor',
          labelKey: 'workflow.sidebar.menu.execution.monitor',
          url: '/workflow/execution/monitor',
          icon: Activity,
        },
      ],
    },
    {
      id: 'integrations',
      labelKey: 'workflow.sidebar.menu.integrations.title',
      url: '/workflow/integrations',
      icon: Bot,
      items: [
        {
          id: 'models',
          labelKey: 'workflow.sidebar.menu.integrations.models',
          url: '/workflow/integrations/models',
        },
        {
          id: 'api',
          labelKey: 'workflow.sidebar.menu.integrations.api',
          url: '/workflow/integrations/api',
          icon: Webhook,
        },
        {
          id: 'connectors',
          labelKey: 'workflow.sidebar.menu.integrations.connectors',
          url: '/workflow/integrations/connectors',
          icon: Database,
        },
      ],
    },
    {
      id: 'collaboration',
      labelKey: 'workflow.sidebar.menu.collaboration.title',
      url: '/workflow/collaboration',
      icon: Share2,
      items: [
        {
          id: 'shared',
          labelKey: 'workflow.sidebar.menu.collaboration.shared',
          url: '/workflow/collaboration/shared',
        },
        {
          id: 'versions',
          labelKey: 'workflow.sidebar.menu.collaboration.versions',
          url: '/workflow/collaboration/versions',
          icon: GitBranch,
        },
        {
          id: 'team',
          labelKey: 'workflow.sidebar.menu.collaboration.team',
          url: '/workflow/collaboration/team',
          icon: Users,
        },
      ],
    },
    {
      id: 'management',
      labelKey: 'workflow.sidebar.menu.management.title',
      url: '/workflow/management',
      icon: Settings2,
      items: [
        {
          id: 'import-export',
          labelKey: 'workflow.sidebar.menu.management.importExport',
          url: '/workflow/management/import-export',
          icon: DownloadCloud,
        },
        {
          id: 'permissions',
          labelKey: 'workflow.sidebar.menu.management.permissions',
          url: '/workflow/management/permissions',
          icon: Lock,
        },
        {
          id: 'analytics',
          labelKey: 'workflow.sidebar.menu.management.analytics',
          url: '/workflow/management/analytics',
          icon: BarChart,
        },
        {
          id: 'settings',
          labelKey: 'workflow.sidebar.menu.management.settings',
          url: '/workflow/management/settings',
        },
      ],
    },
  ],
  navSecondary: [
    {
      id: 'help',
      labelKey: 'workflow.sidebar.menu.help',
      url: '/help/workflow',
      icon: HelpCircle,
    },
    {
      id: 'feedback',
      labelKey: 'workflow.sidebar.menu.feedback',
      url: '/feedback',
      icon: Send,
    },
  ],
  projects: [
    {
      id: 'favorites',
      labelKey: 'workflow.sidebar.projects.favorites',
      url: '/workflow/favorites',
      icon: Star,
    },
    {
      id: 'recent',
      labelKey: 'workflow.sidebar.projects.recent',
      url: '/workflow/recent',
      icon: Clock,
    },
    {
      id: 'data-processing',
      labelKey: 'workflow.sidebar.projects.dataProcessing',
      url: '/workflow/data-processing',
      icon: Database,
    },
    {
      id: 'api-integration',
      labelKey: 'workflow.sidebar.projects.apiIntegration',
      url: '/workflow/api-integration',
      icon: Webhook,
    },
    {
      id: 'model-training',
      labelKey: 'workflow.sidebar.projects.modelTraining',
      url: '/workflow/model-training',
      icon: Bot,
    },
    {
      id: 'auto-deploy',
      labelKey: 'workflow.sidebar.projects.autoDeploy',
      url: '/workflow/auto-deploy',
      icon: Zap,
    },
  ],
}

export function BoxSidebar({ activeTab = 'overview', onTabChange, ...props }: { activeTab?: string, onTabChange?: (tabId: string) => void } & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()
  const locale = i18n?.language || undefined
  const [workflowStatus, setWorkflowStatus] = useState<WorkflowStatus>({
    totalWorkflows: 87,
    activeWorkflows: 12,
    recentRuns: 43,
    cpuUsage: 35,
    memoryUsage: 6.2,
    resourceLimit: 10,
    lastUpdated: '2025-06-01 21:45',
    healthStatus: 'normal',
    apiUsage: {
      calls: 756,
      limit: 1000
    }
  })
  
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({
    'my-workflows': true,
    execution: false,
    integrations: false,
    collaboration: false,
    management: false,
  })

  // Refresh workflow status.
  const refreshWorkflowStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setWorkflowStatus({
        totalWorkflows: 87,
        activeWorkflows: Math.floor(Math.random() * 5) + 10,
        recentRuns: Math.floor(Math.random() * 20) + 35,
        cpuUsage: Math.floor(Math.random() * 20) + 30,
        memoryUsage: parseFloat((Math.random() * 2 + 5).toFixed(1)),
        resourceLimit: 10,
        lastUpdated: new Date().toLocaleString(locale, { hour12: false }).replace(/\//g, '-'),
        healthStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        apiUsage: {
          calls: 756,
          limit: 1000
        }
      })
      setIsRefreshing(false)
    }, 800)
  }

  // Toggle menu item expansion state.
  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }))
  }

  // Handle menu item click.
  const handleMenuItemClick = (itemId: string) => {
    const item = data.navMain.find(item => item.id === itemId)
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
  
  const renderMenuItem = (item: any) => {
    const isActive = activeTab === item.id || activeTab.startsWith(`${item.id}/`)
    const isExpanded = expandedItems[item.id] || false
    const hasSubItems = item.items && item.items.length > 0

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
                {item.icon && <item.icon size={16} />}
              </div>
              <span>{t(item.labelKey)}</span>
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
            <p>{t(item.labelKey)}</p>
          </TooltipContent>
        </Tooltip>

        {hasSubItems && isExpanded && (
          <div className="pl-8 space-y-1 animate-in slide-in-from-left-5 duration-200">
            {item.items.map((subItem: any) => {
              const isSubActive = activeTab === `${item.id}/${subItem.id}`

              return (
                <Tooltip key={subItem.id}>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant={isSubActive ? "secondary" : "ghost"}
                      className="w-full justify-start gap-2 text-sm"
                      onClick={() => handleSubItemClick(item.id, subItem.id)}
                    >
                      <span>{t(subItem.labelKey)}</span>
                      {subItem.icon && <subItem.icon size={14} className="ml-auto" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{t(subItem.labelKey)}</p>
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
                {data.navMain.map(renderMenuItem)}
              </div>
            </div>
            
            <div className="px-2 py-2">
              <h2 className="px-2 mb-2 text-sm font-semibold tracking-tight text-muted-foreground">
                {t('workflow.sidebar.projects.title')}
              </h2>
              <div className="space-y-1">
                {data.projects.map((project: any) => (
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
                    <span>{t(project.labelKey)}</span>
                  </Button>
                ))}
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
                  onClick={refreshWorkflowStatus}
                  disabled={isRefreshing}
                >
                  <RefreshCw className={cn(
                    "h-4 w-4",
                    isRefreshing && "animate-spin"
                  )} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('workflow.sidebar.stats.totalWorkflows')}</span>
                  <span className="font-semibold">{workflowStatus.totalWorkflows}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('workflow.sidebar.stats.activeWorkflows')}</span>
                  <span className="font-semibold">{workflowStatus.activeWorkflows}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.cpuUsage')}</span>
                  <span>{workflowStatus.cpuUsage}%</span>
                </div>
                <Progress
                  value={workflowStatus.cpuUsage}
                  className={cn(
                    workflowStatus.cpuUsage > 80 ? "bg-red-200" : 
                    workflowStatus.cpuUsage > 60 ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.memoryUsage')}</span>
                  <span>
                    {workflowStatus.memoryUsage}/{workflowStatus.resourceLimit} {t('workflow.sidebar.stats.memoryUnit')}
                  </span>
                </div>
                <Progress
                  value={(workflowStatus.memoryUsage / workflowStatus.resourceLimit) * 100}
                  className={cn(
                    workflowStatus.memoryUsage / workflowStatus.resourceLimit > 0.8 ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('workflow.sidebar.stats.apiUsage')}</span>
                  <span>{workflowStatus.apiUsage.calls}/{workflowStatus.apiUsage.limit}</span>
                </div>
                <Progress
                  value={(workflowStatus.apiUsage.calls / workflowStatus.apiUsage.limit) * 100}
                  className="bg-purple-200"
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('workflow.sidebar.stats.updatedAt', { timestamp: workflowStatus.lastUpdated })}
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
