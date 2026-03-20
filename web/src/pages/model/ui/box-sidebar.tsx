import * as React from 'react'
import { useState } from 'react'
import { 
  Send, 
  BookOpen, 
  Bot, 
  Frame, 
  Map, 
  PieChart, 
  Settings2, 
  SquareTerminal, 
  LifeBuoy, 
  Scroll, 
  Database, 
  RefreshCw, 
  CheckCircle, 
  AlertTriangle, 
  Info, 
  ChevronRight, 
  ChevronDown, 
  ExternalLink, 
  BarChart, 
  Star, 
  Clock, 
  Search, 
  Cpu, 
  Zap, 
  Code,
  GitBranch,
  FileText,
  Users
} from 'lucide-react'

import { NavCheck } from '@/components/nav/nav-check'
import { NavProjects } from '@/components/nav/nav-projects'
import { SidebarOptInForm } from '@/components/common/sidebar-opt-in-form'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n'

// Model status types.
interface ModelStatus {
  totalModels: number;
  activeModels: number;
  apiUsage: number;
  apiLimit: number;
  lastUpdated: string;
  healthStatus: 'normal' | 'warning' | 'critical';
  performance: {
    latency: number;
    throughput: number;
  };
}

const data = {
  navMain: [
    {
      id: 'overview',
      titleKey: 'system.model.sidebar.menu.overview',
      url: '/models/dashboard',
      icon: PieChart,
      isActive: true,
      items: [],
    },
    {
      id: 'types',
      titleKey: 'system.model.sidebar.menu.types',
      url: '/models/types',
      icon: Cpu,
      items: [
        {
          id: 'llm',
          titleKey: 'system.model.sidebar.menu.typesItems.llm',
          url: '/models/types/llm',
          icon: Bot,
        },
        {
          id: 'embedding',
          titleKey: 'system.model.sidebar.menu.typesItems.embedding',
          url: '/models/types/embedding',
          icon: Code,
        },
        {
          id: 'speech2text',
          titleKey: 'system.model.sidebar.menu.typesItems.speech2text',
          url: '/models/types/speech2text',
          icon: FileText,
        },
        {
          id: 'moderation',
          titleKey: 'system.model.sidebar.menu.typesItems.moderation',
          url: '/models/types/moderation',
          icon: Search,
        },
        {
          id: 'tts',
          titleKey: 'system.model.sidebar.menu.typesItems.tts',
          url: '/models/types/tts',
          icon: Scroll,
        },
        {
          id: 'vision',
          titleKey: 'system.model.sidebar.menu.typesItems.vision',
          url: '/models/types/vision',
          icon: SquareTerminal,
        },
      ],
    },
    {
      id: 'management',
      titleKey: 'system.model.sidebar.menu.management',
      url: '/models/management',
      icon: Settings2,
      items: [
        {
          id: 'deployment',
          titleKey: 'system.model.sidebar.menu.managementItems.deployment',
          url: '/models/management/deployment',
          icon: GitBranch,
        },
        {
          id: 'performance',
          titleKey: 'system.model.sidebar.menu.managementItems.performance',
          url: '/models/management/performance',
          icon: Zap,
        },
        {
          id: 'versions',
          titleKey: 'system.model.sidebar.menu.managementItems.versions',
          url: '/models/management/versions',
          icon: Clock,
        },
      ],
    },
    {
      id: 'usage',
      titleKey: 'system.model.sidebar.menu.usage',
      url: '/models/usage',
      icon: BarChart,
      items: [
        {
          id: 'apiUsage',
          titleKey: 'system.model.sidebar.menu.usageItems.apiUsage',
          url: '/models/usage/api',
        },
        {
          id: 'userAnalysis',
          titleKey: 'system.model.sidebar.menu.usageItems.userAnalysis',
          url: '/models/usage/users',
          icon: Users,
        },
      ],
    },
  ],
  navSecondary: [
    {
      id: 'help',
      titleKey: 'system.model.sidebar.secondary.help',
      url: '/help/model',
      icon: LifeBuoy,
    },
    {
      id: 'feedback',
      titleKey: 'system.model.sidebar.secondary.feedback',
      url: '/observability/feedback',
      icon: Send,
    },
  ],
  projects: [
    {
      id: 'favorites',
      nameKey: 'system.model.sidebar.projects.favorites',
      url: '/models/favorites',
      icon: Star,
    },
    {
      id: 'recent',
      nameKey: 'system.model.sidebar.projects.recent',
      url: '/models/recent',
      icon: Clock,
    },
    {
      id: 'mine',
      nameKey: 'system.model.sidebar.projects.mine',
      url: '/models/my',
      icon: Database,
    },
  ],
}

export function BoxSidebar({ activeTab = 'overview', onTabChange, ...props }: { activeTab?: string, onTabChange?: (tabId: string) => void } & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()

  // Model status data.
  const [modelStatus, setModelStatus] = useState<ModelStatus>({
    totalModels: 42,
    activeModels: 28,
    apiUsage: 8750,
    apiLimit: 10000,
    lastUpdated: '2025-06-01 20:45',
    healthStatus: 'normal',
    performance: {
      latency: 245,  // ms
      throughput: 125 // requests/min
    }
  })
  
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})

  // Refresh model status.
  const refreshModelStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setModelStatus({
        totalModels: 42,
        activeModels: Math.floor(Math.random() * 10) + 25, // 25-35 random range
        apiUsage: Math.floor(Math.random() * 1000) + 8000, // 8000-9000 random range
        apiLimit: 10000,
        lastUpdated: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
        healthStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        performance: {
          latency: Math.floor(Math.random() * 100) + 200,  // 200-300 random range
          throughput: Math.floor(Math.random() * 50) + 100  // 100-150 random range
        }
      })
      setIsRefreshing(false)
    }, 800)
  }

  // Toggle menu item expand/collapse state.
  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }))
  }

  // Handle menu item clicks.
  const handleMenuItemClick = (itemId: string) => {
    // Toggle expand state for items with children.
    const item = data.navMain.find(item => item.id === itemId)
    if (item?.items && item.items.length > 0) {
      toggleMenuItem(itemId)
      return
    }

    // Otherwise, trigger a tab change.
    if (onTabChange) {
      onTabChange(itemId)
    }
  }

  // Handle sub menu item clicks.
  const handleSubItemClick = (parentId: string, subItemId: string) => {
    if (onTabChange) {
      onTabChange(`${parentId}/${subItemId}`)
    }
  }

  // Resolve status icon.
  const getStatusIcon = (status: 'normal' | 'warning' | 'critical') => {
    switch (status) {
      case 'normal':
        return <CheckCircle className="h-4 w-4 text-green-500" />
      case 'warning':
        return <AlertTriangle className="h-4 w-4 text-amber-500" />
      case 'critical':
        return <AlertTriangle className="h-4 w-4 text-red-500" />
      default:
        return <Info className="h-4 w-4 text-blue-500" />
    }
  }
  
  const [activeItem, setActiveItem] = React.useState(data.navMain[0])
  const { setOpen } = useSidebar()
  const navigate = useNavigate()
  
  // Render menu items.
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
              <span>{t(item.titleKey)}</span>
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
            <p>{item.descriptionKey ? t(item.descriptionKey) : t(item.titleKey)}</p>
          </TooltipContent>
        </Tooltip>

        {/* Sub menu items. */}
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
                      <span>{t(subItem.titleKey)}</span>
                      {subItem.icon && <subItem.icon size={14} className="ml-auto" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{subItem.descriptionKey ? t(subItem.descriptionKey) : t(subItem.titleKey)}</p>
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
          <div className="text-lg font-medium text-foreground">{t('system.model.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('system.model.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            {/* Main menu. */}
            <div className="px-2 py-2">
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {data.navMain.map(renderMenuItem)}
              </div>
            </div>
            
            {/* Project menu. */}
            <div className="px-2 py-2">
              <h2 className="px-3 mb-2 text-sm font-semibold tracking-tight text-muted-foreground">
                {t('system.model.sidebar.projects.title')}
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
                    <span>{t(project.nameKey)}</span>
                  </Button>
                ))}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          {/* Model stats card. */}
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Cpu className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('system.model.sidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshModelStatus}
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
                  <span className="text-muted-foreground text-xs">{t('system.model.sidebar.stats.totalModels')}</span>
                  <span className="font-semibold">{modelStatus.totalModels}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('system.model.sidebar.stats.activeModels')}</span>
                  <span className="font-semibold">{modelStatus.activeModels}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('system.model.sidebar.stats.apiUsage')}</span>
                  <span>{modelStatus.apiUsage}/{modelStatus.apiLimit}</span>
                </div>
                <Progress
                  value={(modelStatus.apiUsage / modelStatus.apiLimit) * 100}
                  className={cn(
                    modelStatus.apiUsage / modelStatus.apiLimit > 0.8 ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('system.model.sidebar.stats.performance')}</span>
                  <span>{t('system.model.sidebar.stats.latency', { value: modelStatus.performance.latency })}</span>
                </div>
                <Progress
                  value={Math.min((modelStatus.performance.latency / 500) * 100, 100)}
                  className="bg-purple-200"
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('system.model.sidebar.stats.updatedAt', { timestamp: modelStatus.lastUpdated })}
              </div>
              
              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('system.model.sidebar.stats.report')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('system.model.sidebar.stats.details')}</span>
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
