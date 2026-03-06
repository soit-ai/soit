import * as React from 'react'
import { useState } from 'react'
import {
  Bot,
  FileText,
  Settings2,
  Send,
  FolderTree,
  Tags,
  Star,
  BarChart,
  Search,
  Database,
  Home,
  Clock,
  Upload,
  Network,
  Share2,
  DownloadCloud,
  Lock,
  HelpCircle,
  RefreshCw,
  CheckCircle,
  AlertTriangle,
  Info,
  ChevronRight,
  ChevronDown,
  ExternalLink,
} from 'lucide-react'

import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { useTranslation } from '@/i18n'

// Knowledge base status model.
interface KnowledgeBaseStatus {
  totalDocuments: number;
  recentUpdates: number;
  storageUsage: number;
  storageLimit: number;
  lastUpdated: string;
  healthStatus: 'normal' | 'warning' | 'critical';
  aiUsage: {
    queries: number;
    limit: number;
  };
}

const data = {
  navMain: [
    {
      id: 'overview',
      labelKey: 'dataset.sidebar.menu.overview',
      url: '/dataset/dashboard',
      icon: Home,
      isActive: true,
      items: [],
    },
    {
      id: 'documents',
      labelKey: 'dataset.sidebar.menu.documents.title',
      url: '/dataset/documents',
      icon: FileText,
      items: [
        {
          id: 'all',
          labelKey: 'dataset.sidebar.menu.documents.all',
          url: '/dataset/documents/all',
        },
        {
          id: 'recent',
          labelKey: 'dataset.sidebar.menu.documents.recent',
          url: '/dataset/documents/recent',
          icon: Clock,
        },
        {
          id: 'favorites',
          labelKey: 'dataset.sidebar.menu.documents.favorites',
          url: '/dataset/documents/favorites',
          icon: Star,
        },
        {
          id: 'uploads',
          labelKey: 'dataset.sidebar.menu.documents.uploads',
          url: '/dataset/documents/uploads',
          icon: Upload,
        },
      ],
    },
    {
      id: 'categories',
      labelKey: 'dataset.sidebar.menu.categories.title',
      url: '/dataset/categories',
      icon: FolderTree,
      items: [
        {
          id: 'folders',
          labelKey: 'dataset.sidebar.menu.categories.folders',
          url: '/dataset/categories/folders',
        },
        {
          id: 'tags',
          labelKey: 'dataset.sidebar.menu.categories.tags',
          url: '/dataset/categories/tags',
          icon: Tags,
        },
      ],
    },
    {
      id: 'ai',
      labelKey: 'dataset.sidebar.menu.ai.title',
      url: '/dataset/ai',
      icon: Bot,
      items: [
        {
          id: 'search',
          labelKey: 'dataset.sidebar.menu.ai.search',
          url: '/dataset/ai/search',
          icon: Search,
        },
        {
          id: 'qa',
          labelKey: 'dataset.sidebar.menu.ai.qa',
          url: '/dataset/ai/qa',
        },
        {
          id: 'knowledge-graph',
          labelKey: 'dataset.sidebar.menu.ai.knowledgeGraph',
          url: '/dataset/ai/knowledge-graph',
          icon: Network,
        },
      ],
    },
    {
      id: 'collaboration',
      labelKey: 'dataset.sidebar.menu.collaboration.title',
      url: '/dataset/collaboration',
      icon: Share2,
      items: [
        {
          id: 'workspace',
          labelKey: 'dataset.sidebar.menu.collaboration.workspace',
          url: '/dataset/collaboration/workspace',
        },
        {
          id: 'sharing',
          labelKey: 'dataset.sidebar.menu.collaboration.sharing',
          url: '/dataset/collaboration/sharing',
        },
      ],
    },
    {
      id: 'management',
      labelKey: 'dataset.sidebar.menu.management.title',
      url: '/dataset/management',
      icon: Settings2,
      items: [
        {
          id: 'import-export',
          labelKey: 'dataset.sidebar.menu.management.importExport',
          url: '/dataset/management/import-export',
          icon: DownloadCloud,
        },
        {
          id: 'permissions',
          labelKey: 'dataset.sidebar.menu.management.permissions',
          url: '/dataset/management/permissions',
          icon: Lock,
        },
        {
          id: 'analytics',
          labelKey: 'dataset.sidebar.menu.management.analytics',
          url: '/dataset/management/analytics',
          icon: BarChart,
        },
        {
          id: 'settings',
          labelKey: 'dataset.sidebar.menu.management.settings',
          url: '/dataset/management/settings',
        },
      ],
    },
  ],
  navSecondary: [
    {
      id: 'help',
      labelKey: 'dataset.sidebar.menu.help',
      url: '/help/dataset',
      icon: HelpCircle,
    },
    {
      id: 'feedback',
      labelKey: 'dataset.sidebar.menu.feedback',
      url: '/feedback',
      icon: Send,
    },
  ],
  projects: [
    {
      id: 'favorites',
      labelKey: 'dataset.sidebar.projects.favorites',
      url: '/dataset/favorites',
      icon: Star,
    },
    {
      id: 'recent',
      labelKey: 'dataset.sidebar.projects.recent',
      url: '/dataset/recent',
      icon: Clock,
    },
    {
      id: 'mine',
      labelKey: 'dataset.sidebar.projects.mine',
      url: '/dataset/my',
      icon: Database,
    },
  ],
}

export function BoxSidebar({ activeTab = 'overview', onTabChange, ...props }: { activeTab?: string, onTabChange?: (tabId: string) => void } & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()
  const locale = i18n?.language || undefined
  const [knowledgeBaseStatus, setKnowledgeBaseStatus] = useState<KnowledgeBaseStatus>({
    totalDocuments: 1258,
    recentUpdates: 37,
    storageUsage: 7.6,
    storageLimit: 20,
    lastUpdated: '2025-06-01 20:30',
    healthStatus: 'normal',
    aiUsage: {
      queries: 856,
      limit: 1000
    }
  })
  
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})

  const refreshKnowledgeBaseStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setKnowledgeBaseStatus({
        totalDocuments: 1258,
        recentUpdates: Math.floor(Math.random() * 20) + 30,
        storageUsage: parseFloat((Math.random() * 2 + 7).toFixed(1)),
        storageLimit: 20,
        lastUpdated: new Date().toLocaleString(locale, { hour12: false }).replace(/\//g, '-'),
        healthStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        aiUsage: {
          queries: 856,
          limit: 1000
        }
      })
      setIsRefreshing(false)
    }, 800)
  }

  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }))
  }

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

  const handleSubItemClick = (parentId: string, subItemId: string) => {
    if (onTabChange) {
      onTabChange(`${parentId}/${subItemId}`)
    }
  }

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
          <div className="text-lg font-medium text-foreground">{t('dataset.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('dataset.sidebar.searchPlaceholder')} className="mx-2 w-auto"/>
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
              <h2 className="px-3 mb-2 text-sm font-semibold tracking-tight text-muted-foreground">
                {t('dataset.sidebar.projects.title')}
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
                  <Database className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('dataset.sidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshKnowledgeBaseStatus}
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
                  <span className="text-muted-foreground text-xs">{t('dataset.sidebar.stats.totalDocuments')}</span>
                  <span className="font-semibold">{knowledgeBaseStatus.totalDocuments}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('dataset.sidebar.stats.recentUpdates')}</span>
                  <span className="font-semibold">{knowledgeBaseStatus.recentUpdates}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('dataset.sidebar.stats.storageUsage')}</span>
                  <span>{knowledgeBaseStatus.storageUsage}/{knowledgeBaseStatus.storageLimit} {t('dataset.sidebar.stats.storageUnit')}</span>
                </div>
                <Progress
                  value={(knowledgeBaseStatus.storageUsage / knowledgeBaseStatus.storageLimit) * 100}
                  className={cn(
                    knowledgeBaseStatus.storageUsage / knowledgeBaseStatus.storageLimit > 0.8 ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('dataset.sidebar.stats.aiUsage')}</span>
                  <span>{knowledgeBaseStatus.aiUsage.queries}/{knowledgeBaseStatus.aiUsage.limit}</span>
                </div>
                <Progress
                  value={(knowledgeBaseStatus.aiUsage.queries / knowledgeBaseStatus.aiUsage.limit) * 100}
                  className="bg-purple-200"
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('dataset.sidebar.stats.updatedAt', { timestamp: knowledgeBaseStatus.lastUpdated })}
              </div>
              
              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('dataset.sidebar.stats.usageReport')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('dataset.sidebar.stats.details')}</span>
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
