import * as React from 'react'
import { 
  LayoutDashboard,
  BookOpen, 
  Bot, 
  FileText, 
  Settings2, 
  LifeBuoy, 
  Send, 
  FolderTree,
  Tags,
  History,
  Star,
  Users,
  Search,
  Database,
  User,
  Globe,
  Key,
  Shield,
  Lock,
  Info,
  Bell,
  ChevronRightIcon,
  ChevronDownIcon,
  ServerIcon,
  RefreshCwIcon,
  ExternalLink,
  GitBranch as Github
} from 'lucide-react'

import { NavMain } from '@/components/nav/nav-main'
import { NavProjects } from '@/components/nav/nav-projects'
import { SidebarOptInForm } from '@/components/common/sidebar-opt-in-form'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, useSidebar, SidebarTrigger } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Separator } from '@/components/ui/separator'
import { useEffect, useState } from 'react'

// Define menu item types.
interface MenuItem {
  id: string;
  icon: React.ReactNode;
  label: string;
  description: string;
  url: string;
  badge?: number | null;
  section: 'account' | 'system' | 'advanced';
  status?: 'normal' | 'warning' | 'critical';
  subItems?: SubMenuItem[];
}

// Define submenu item types.
interface SubMenuItem {
  id: string;
  parentId: string;
  label: string;
  description: string;
  url: string;
  badge?: number | null;
}

export function BoxSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { setOpen } = useSidebar()
  
  const menuItems: MenuItem[] = React.useMemo(() => ([
    {
      id: 'overview',
      icon: <LayoutDashboard size={16} />,
      label: 'Overview',
      description: 'Workspace-level defaults, roles, and main chain settings.',
      url: '/settings',
      section: 'account',
    },
    {
      id: 'account',
      icon: <User size={16} />,
      label: t('system.settings.sidebar.menu.account.label'),
      description: t('system.settings.sidebar.menu.account.description'),
      url: '/settings/account',
      section: 'account',
    },
    {
      id: 'lang',
      icon: <Globe size={16} />,
      label: t('system.settings.sidebar.menu.lang.label'),
      description: t('system.settings.sidebar.menu.lang.description'),
      url: '/settings/lang',
      section: 'account',
    },
    {
      id: 'api',
      icon: <Key size={16} />,
      label: t('system.settings.sidebar.menu.api.label'),
      description: t('system.settings.sidebar.menu.api.description'),
      url: '/settings/api',
      section: 'account',
    },
    {
      id: 'team',
      icon: <Users size={16} />,
      label: t('system.settings.sidebar.menu.team.label'),
      description: t('system.settings.sidebar.menu.team.description'),
      url: '/settings/team',
      section: 'account',
    },
    {
      id: 'security',
      icon: <Shield size={16} />,
      label: t('system.settings.sidebar.menu.security.label'),
      description: t('system.settings.sidebar.menu.security.description'),
      url: '/settings/security',
      section: 'system',
    },
    {
      id: 'secrets',
      icon: <Lock size={16} />,
      label: t('system.settings.sidebar.menu.secrets.label'),
      description: t('system.settings.sidebar.menu.secrets.description'),
      url: '/settings/secrets',
      section: 'system',
    },
    {
      id: 'notifications',
      icon: <Bell size={16} />,
      label: t('system.settings.sidebar.menu.notifications.label'),
      description: t('system.settings.sidebar.menu.notifications.description'),
      url: '/settings/notifications',
      section: 'system',
    },
    {
      id: 'about',
      icon: <Info size={16} />,
      label: t('system.settings.sidebar.menu.about.label'),
      description: t('system.settings.sidebar.menu.about.description'),
      url: '/settings/about',
      section: 'advanced',
    },
  ]), [t])

  // State management.
  const [activeTab, setActiveTab] = useState<string>('account')
  const [expandedSections, setExpandedSections] = useState<{ [key: string]: boolean }>({
    account: true,
    system: true,
    advanced: true
  })
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})
  
  // Update the active menu item based on the current path.
  useEffect(() => {
    const path = window.location.pathname
    if (path === '/settings') {
      setActiveTab('overview')
      return
    }
    const pathSegments = path.split('/')
    if (pathSegments.length >= 3) {
      const tabId = pathSegments[2] // e.g. /settings/account -> account
      setActiveTab(tabId)
    }
  }, [])
  
  // Toggle section expansion.
  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }))
  }
  
  // Toggle menu item expansion.
  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId]
    }))
  }
  
  // Handle menu item click.
  const handleMenuItemClick = (itemId: string, url: string) => {
    // Toggle expansion for items with submenus.
    const item = menuItems.find(item => item.id === itemId)
    if (item?.subItems && item.subItems.length > 0) {
      toggleMenuItem(itemId)
      return
    }
    
    // Otherwise, set active tab and navigate.
    setActiveTab(itemId)
    navigate(url)
  }
  
  // Handle submenu item click.
  const handleSubItemClick = (parentId: string, subItemId: string, url: string) => {
    setActiveTab(`${parentId}/${subItemId}`)
    navigate(url)
  }
  
  // Resolve status badge.
  const getStatusBadge = (status?: 'normal' | 'warning' | 'critical') => {
    if (!status || status === 'normal') return null
    
    return (
      <div className="h-2 w-2 rounded-full absolute top-1 right-1">
        <span className={cn(
          "absolute top-0 right-0 h-2 w-2 rounded-full",
          status === 'warning' ? "bg-amber-500" : "bg-red-500",
          "animate-ping opacity-75"
        )}></span>
        <span className={cn(
          "absolute top-0 right-0 h-2 w-2 rounded-full",
          status === 'warning' ? "bg-amber-500" : "bg-red-500"
        )}></span>
      </div>
    )
  }
  
  // Render a menu item.
  const renderMenuItem = (item: MenuItem) => {
    const isActive = activeTab === item.id || activeTab.startsWith(`${item.id}/`)
    const isExpanded = expandedItems[item.id] || false
    const hasSubItems = item.subItems && item.subItems.length > 0
    
    return (
      <div key={item.id} className="space-y-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isActive ? "secondary" : "ghost"}
              className="w-full justify-start gap-2 relative"
              onClick={() => handleMenuItemClick(item.id, item.url)}
            >
              <div className="relative">
                {item.icon}
                {getStatusBadge(item.status)}
              </div>
              <span>{item.label}</span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={isActive ? "default" : "secondary"}
                >
                  {item.badge}
                </Badge>
              ) : null}
              {hasSubItems && (
                <div className="ml-auto">
                </div>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{item.description}</p>
          </TooltipContent>
        </Tooltip>
        
        {/* Submenu items */}
        {hasSubItems && (
          <div className="pl-8 space-y-1 animate-in slide-in-from-left-5 duration-200">
            {item.subItems!.map((subItem) => {
              const isSubActive = activeTab === `${item.id}/${subItem.id}`
              
              return (
                <Tooltip key={subItem.id}>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant={isSubActive ? "secondary" : "ghost"}
                      className="w-full justify-start gap-2 text-sm"
                      onClick={() => handleSubItemClick(item.id, subItem.id, subItem.url)}
                    >
                      <span>{subItem.label}</span>
                      {subItem.badge ? (
                        <Badge
                          className="ml-auto"
                          variant={isSubActive ? "default" : "secondary"}
                        >
                          {subItem.badge}
                        </Badge>
                      ) : null}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{subItem.description}</p>
                  </TooltipContent>
                </Tooltip>
              )
            })}
          </div>
        )}
      </div>
    )
  }
  
  // Render section title.
  const renderSectionTitle = (title: string, section: string) => {
    return (
      <div
        className="flex items-center px-2 mb-2 cursor-pointer group"
      >
        <h2 className="pl-2 text-sm font-semibold tracking-tight text-muted-foreground transition-colors">
          {title}
        </h2>
      </div>
    )
  }
  
  // Resolve items by section.
  const accountMenuItems = menuItems.filter(item => item.section === 'account')
  const systemMenuItems = menuItems.filter(item => item.section === 'system')
  const advancedMenuItems = menuItems.filter(item => item.section === 'advanced')
  
  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="flex w-full items-center justify-between px-2">
          <div className="text-lg font-medium text-foreground">{t('system.settings.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('system.settings.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            {/* Account section */}
            <div className="px-2 py-2">
              {renderSectionTitle(t('system.settings.sidebar.sections.account'), 'account')}
              {expandedSections.account && (
                <div className="space-y-1 animate-in fade-in-50 duration-100">
                  {accountMenuItems.map(renderMenuItem)}
                </div>
              )}
            </div>
            
            {/* System section */}
            <div className="px-2 py-2">
              {renderSectionTitle(t('system.settings.sidebar.sections.system'), 'system')}
              {expandedSections.system && (
                <div className="space-y-1 animate-in fade-in-50 duration-100">
                  {systemMenuItems.map(renderMenuItem)}
                </div>
              )}
            </div>
            
            {/* Advanced section */}
            <div className="px-2 py-2">
              {renderSectionTitle(t('system.settings.sidebar.sections.advanced'), 'advanced')}
              {expandedSections.advanced && (
                <div className="space-y-1 animate-in fade-in-50 duration-100">
                  {advancedMenuItems.map(renderMenuItem)}
                </div>
              )}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex items-center">
              <ServerIcon className="mr-2 h-5 w-5 text-primary" />
              <h3 className="font-semibold">{t('system.settings.sidebar.info.title')}</h3>
            </div>
            <div className="mt-2 flex items-center justify-between py-1 text-sm text-muted-foreground">
              <span>Edition</span>
              <Badge variant="outline">Community</Badge>
            </div>
            <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1" asChild>
                  <a href="https://docs.soit.ai" target="_blank" rel="noreferrer">
                  <BookOpen className="h-3.5 w-3.5" />
                  <span>{t('system.settings.sidebar.info.docs')}</span>
                  </a>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1" asChild>
                  <a href="https://github.com/soit-ai/soit" target="_blank" rel="noreferrer">
                  <Github className="h-3.5 w-3.5" />
                  <span>{t('system.settings.sidebar.info.github')}</span>
                  </a>
                </Button>
              </div>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
