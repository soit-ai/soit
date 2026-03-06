import * as React from 'react'
import { useState } from 'react'
import {
  Send,
  BookOpen,
  Bot,
  History,
  Database,
  Wrench,
  Settings2,
  SquareTerminal,
  LifeBuoy,
  MessageSquare,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  ExternalLink,
  Search,
  Star,
  Clock,
  Code,
  FileText,
  BarChart,
  Home,
} from 'lucide-react'

import { useTranslation } from '@/i18n'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

// Defines the bot status shape for the sidebar.
interface BotStatus {
  totalChats: number;
  activeChats: number;
  apiUsage: number;
  apiLimit: number;
  lastActive: string;
  healthStatus: 'normal' | 'warning' | 'critical';
  modelUsage: {
    calls: number;
    limit: number;
  };
}

const data = {
  navMain: [
    {
      id: 'overview',
      titleKey: 'bot.sidebar.menu.overview',
      url: '/bot/dashboard',
      icon: Home,
      isActive: true,
      items: [],
    },
    {
      id: 'conversations',
      titleKey: 'bot.sidebar.menu.conversations',
      url: '/bot/chats',
      icon: MessageSquare,
      items: [
        {
          id: 'all',
          titleKey: 'bot.sidebar.menu.conversationsAll',
          url: '/bot/chats/all',
        },
        {
          id: 'recent',
          titleKey: 'bot.sidebar.menu.conversationsRecent',
          url: '/bot/chats/recent',
          icon: Clock,
        },
        {
          id: 'favorites',
          titleKey: 'bot.sidebar.menu.conversationsFavorites',
          url: '/bot/chats/favorites',
          icon: Star,
        },
        {
          id: 'archived',
          titleKey: 'bot.sidebar.menu.conversationsArchived',
          url: '/bot/chats/archived',
          icon: History,
        },
      ],
    },
    {
      id: 'knowledge',
      titleKey: 'bot.sidebar.menu.knowledge',
      url: '/bot/knowledge',
      icon: Database,
      items: [
        {
          id: 'linked',
          titleKey: 'bot.sidebar.menu.knowledgeLinked',
          url: '/bot/knowledge/linked',
        },
        {
          id: 'documents',
          titleKey: 'bot.sidebar.menu.knowledgeDocuments',
          url: '/bot/knowledge/documents',
          icon: FileText,
        },
        {
          id: 'external',
          titleKey: 'bot.sidebar.menu.knowledgeExternal',
          url: '/bot/knowledge/external',
        },
      ],
    },
    {
      id: 'tools',
      titleKey: 'bot.sidebar.menu.tools',
      url: '/bot/tools',
      icon: Wrench,
      items: [
        {
          id: 'code-interpreter',
          titleKey: 'bot.sidebar.menu.toolsCodeInterpreter',
          url: '/bot/tools/code-interpreter',
          icon: Code,
        },
        {
          id: 'file-analysis',
          titleKey: 'bot.sidebar.menu.toolsFileAnalysis',
          url: '/bot/tools/file-analysis',
        },
        {
          id: 'web-search',
          titleKey: 'bot.sidebar.menu.toolsWebSearch',
          url: '/bot/tools/web-search',
          icon: Search,
        },
        {
          id: 'data-analysis',
          titleKey: 'bot.sidebar.menu.toolsDataAnalysis',
          url: '/bot/tools/data-analysis',
          icon: BarChart,
        },
      ],
    },
    {
      id: 'models',
      titleKey: 'bot.sidebar.menu.models',
      url: '/bot/models',
      icon: Bot,
      items: [
        {
          id: 'gpt4',
          titleKey: 'bot.sidebar.menu.modelsGpt4',
          url: '/bot/models/gpt4',
        },
        {
          id: 'claude',
          titleKey: 'bot.sidebar.menu.modelsClaude',
          url: '/bot/models/claude',
        },
        {
          id: 'custom',
          titleKey: 'bot.sidebar.menu.modelsCustom',
          url: '/bot/models/custom',
        },
      ],
    },
    {
      id: 'settings',
      titleKey: 'bot.sidebar.menu.settings',
      url: '/bot/settings',
      icon: Settings2,
      items: [
        {
          id: 'general',
          titleKey: 'bot.sidebar.menu.settingsGeneral',
          url: '/bot/settings/general',
        },
        {
          id: 'api-key',
          titleKey: 'bot.sidebar.menu.settingsApiKey',
          url: '/bot/settings/api-key',
        },
        {
          id: 'usage-limits',
          titleKey: 'bot.sidebar.menu.settingsUsageLimits',
          url: '/bot/settings/usage-limits',
        },
        {
          id: 'appearance',
          titleKey: 'bot.sidebar.menu.settingsAppearance',
          url: '/bot/settings/appearance',
        },
      ],
    },
  ],
  navSecondary: [
    {
      id: 'help',
      titleKey: 'bot.sidebar.menu.helpCenter',
      url: '/help/bot',
      icon: LifeBuoy,
    },
    {
      id: 'feedback',
      titleKey: 'bot.sidebar.menu.feedback',
      url: '/feedback',
      icon: Send,
    },
  ],
  projects: [
    {
      id: 'personal',
      nameKey: 'bot.sidebar.projects.personalAssistant',
      url: '/bot/personal',
      icon: Bot,
    },
    {
      id: 'code',
      nameKey: 'bot.sidebar.projects.codeAssistant',
      url: '/bot/code',
      icon: SquareTerminal,
    },
    {
      id: 'research',
      nameKey: 'bot.sidebar.projects.researchAssistant',
      url: '/bot/research',
      icon: BookOpen,
    },
  ],
}

export function BoxSidebar({ activeTab = 'overview', onTabChange, ...props }: { activeTab?: string, onTabChange?: (tabId: string) => void } & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()
  const [botStatus, setBotStatus] = useState<BotStatus>(() => ({
    totalChats: 342,
    activeChats: 12,
    apiUsage: 6.8,
    apiLimit: 10,
    lastActive: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
    healthStatus: 'normal',
    modelUsage: {
      calls: 756,
      limit: 1000,
    },
  }))
  
  const [isRefreshing, setIsRefreshing] = useState(false)
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})

  const refreshBotStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setBotStatus({
        totalChats: 342,
        activeChats: Math.floor(Math.random() * 10) + 8, // Random value between 8-18.
        apiUsage: parseFloat((Math.random() * 1 + 6.5).toFixed(1)), // Random value between 6.5-7.5.
        apiLimit: 10,
        lastActive: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
        healthStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        modelUsage: {
          calls: 756,
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

  const { setOpen } = useSidebar()
  const navigate = useNavigate()
  
  const renderMenuItem = (item: any) => {
    const isActive = activeTab === item.id || activeTab.startsWith(`${item.id}/`)
    const isExpanded = expandedItems[item.id] || false
    const hasSubItems = item.items && item.items.length > 0
    const title = t(item.titleKey)

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
            <p>{item.descriptionKey ? t(item.descriptionKey) : title}</p>
          </TooltipContent>
        </Tooltip>

        {hasSubItems && isExpanded && (
          <div className="pl-8 space-y-1 animate-in slide-in-from-left-5 duration-200">
            {item.items.map((subItem: any) => {
              const subTitle = t(subItem.titleKey)
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
                      <span>{subTitle}</span>
                      {subItem.icon && <subItem.icon size={14} className="ml-auto" />}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{subItem.descriptionKey ? t(subItem.descriptionKey) : subTitle}</p>
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
          <div className="text-lg font-medium text-foreground">{t('bot.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('bot.sidebar.searchPlaceholder')} className="mx-2 w-auto"/>
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
                {t('bot.sidebar.projects.title')}
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
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <Bot className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('bot.sidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshBotStatus}
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
                  <span className="text-muted-foreground text-xs">{t('bot.sidebar.stats.totalChats')}</span>
                  <span className="font-semibold">{botStatus.totalChats}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-muted-foreground text-xs">{t('bot.sidebar.stats.activeChats')}</span>
                  <span className="font-semibold">{botStatus.activeChats}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('bot.sidebar.stats.apiUsage')}</span>
                  <span>{botStatus.apiUsage}/{botStatus.apiLimit} GB</span>
                </div>
                <Progress
                  value={(botStatus.apiUsage / botStatus.apiLimit) * 100}
                  className={cn(
                    botStatus.apiUsage / botStatus.apiLimit > 0.8 ? "bg-amber-200" : "bg-blue-200"
                  )}
                />
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('bot.sidebar.stats.modelCalls')}</span>
                  <span>{botStatus.modelUsage.calls}/{botStatus.modelUsage.limit}</span>
                </div>
                <Progress
                  value={(botStatus.modelUsage.calls / botStatus.modelUsage.limit) * 100}
                  className="bg-purple-200"
                />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('bot.sidebar.stats.lastActive', { timestamp: botStatus.lastActive })}
              </div>
              
              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart className="h-3.5 w-3.5" />
                  <span>{t('bot.sidebar.stats.usageReport')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('bot.sidebar.stats.details')}</span>
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
