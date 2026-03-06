import React from 'react'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import {
  BellIcon,
  KeyIcon,
  UserIcon,
  EyeOffIcon,
  ClipboardListIcon,
  SettingsIcon,
  ShieldAlertIcon,
  LockIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  AlertTriangleIcon,
  CheckCircleIcon,
  RefreshCwIcon,
  InfoIcon,
  DownloadIcon,
  BarChart2Icon,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail, SidebarInput, SidebarTrigger } from '@/components/ui/sidebar'

interface SafeSidebarProps {
  activeTab?: string
  onTabChange?: (tabId: string) => void
  alertCount?: number
}

// Sidebar menu item types.
interface MenuItem {
  id: string
  icon: React.ReactNode
  labelKey: string
  descriptionKey: string
  badge?: number | null
  section: 'main' | 'management'
  status?: 'normal' | 'warning' | 'critical'
  subItems?: SubMenuItem[]
}

// Sub menu item types.
interface SubMenuItem {
  id: string
  parentId: string
  labelKey: string
  descriptionKey: string
  badge?: number | null
}

// Security status summary.
interface SecurityStatus {
  score: number
  lastUpdated: string
  guardrailStatus: 'normal' | 'warning' | 'critical'
  pendingAlerts: number
  systemStatus: 'normal' | 'warning' | 'critical'
}

export function SafeSidebar({ activeTab = 'guardrail', onTabChange, alertCount = 0, ...props }: SafeSidebarProps & React.ComponentProps<typeof Sidebar>) {
  const { t, i18n } = useTranslation()
  const [expandedSections, setExpandedSections] = useState<{ [key: string]: boolean }>({ main: true, management: true })
  const [securityStatus, setSecurityStatus] = useState<SecurityStatus>({
    score: 78,
    lastUpdated: '2025-06-01 13:30',
    guardrailStatus: 'normal',
    pendingAlerts: alertCount,
    systemStatus: alertCount > 3 ? 'warning' : 'normal',
  })
  const [expandedItems, setExpandedItems] = useState<{ [key: string]: boolean }>({})
  const [isRefreshing, setIsRefreshing] = useState(false)

  // Update security status data.
  useEffect(() => {
    setSecurityStatus(prev => ({
      ...prev,
      pendingAlerts: alertCount,
      systemStatus: alertCount > 3 ? 'warning' : 'normal',
    }))
  }, [alertCount])

  // Simulate refreshing security status.
  const refreshSecurityStatus = () => {
    setIsRefreshing(true)
    setTimeout(() => {
      setSecurityStatus({
        score: Math.floor(Math.random() * 20) + 70,
        lastUpdated: new Date().toLocaleString(i18n.language, { hour12: false }).replace(/\//g, '-'),
        guardrailStatus: Math.random() > 0.8 ? 'warning' : 'normal',
        pendingAlerts: alertCount,
        systemStatus: alertCount > 3 ? 'warning' : 'normal',
      })
      setIsRefreshing(false)
    }, 800)
  }

  // Toggle section expand/collapse.
  const toggleSection = (section: string) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }))
  }

  // Toggle menu item expand/collapse.
  const toggleMenuItem = (itemId: string) => {
    setExpandedItems(prev => ({
      ...prev,
      [itemId]: !prev[itemId],
    }))
  }

  // Sidebar menu items.
  const menuItems: MenuItem[] = [
    {
      id: 'guardrail',
      icon: <ShieldAlertIcon size={16} />,
      labelKey: 'safe.sidebar.items.guardrail.label',
      descriptionKey: 'safe.sidebar.items.guardrail.description',
      section: 'main',
      status: securityStatus.guardrailStatus,
    },
    {
      id: 'alerts',
      icon: <BellIcon size={16} />,
      labelKey: 'safe.sidebar.items.alerts.label',
      descriptionKey: 'safe.sidebar.items.alerts.description',
      badge: alertCount,
      section: 'main',
      status: alertCount > 0 ? 'warning' : 'normal',
    },
    {
      id: 'sensitive',
      icon: <KeyIcon size={16} />,
      labelKey: 'safe.sidebar.items.sensitive.label',
      descriptionKey: 'safe.sidebar.items.sensitive.description',
      section: 'main',
    },
    {
      id: 'access',
      icon: <LockIcon size={16} />,
      labelKey: 'safe.sidebar.items.access.label',
      descriptionKey: 'safe.sidebar.items.access.description',
      section: 'management',
    },
    {
      id: 'user',
      icon: <UserIcon size={16} />,
      labelKey: 'safe.sidebar.items.user.label',
      descriptionKey: 'safe.sidebar.items.user.description',
      section: 'management',
    },
    {
      id: 'privacy',
      icon: <EyeOffIcon size={16} />,
      labelKey: 'safe.sidebar.items.privacy.label',
      descriptionKey: 'safe.sidebar.items.privacy.description',
      section: 'management',
    },
    {
      id: 'audit',
      icon: <ClipboardListIcon size={16} />,
      labelKey: 'safe.sidebar.items.audit.label',
      descriptionKey: 'safe.sidebar.items.audit.description',
      section: 'management',
    },
    {
      id: 'settings',
      icon: <SettingsIcon size={16} />,
      labelKey: 'safe.sidebar.items.settings.label',
      descriptionKey: 'safe.sidebar.items.settings.description',
      section: 'management',
    },
  ]

  // Handle menu item click.
  const handleMenuItemClick = (itemId: string) => {
    const item = menuItems.find(item => item.id === itemId)
    if (item?.subItems && item.subItems.length > 0) {
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

  // Resolve status badge.
  const getStatusBadge = (status?: 'normal' | 'warning' | 'critical') => {
    if (!status || status === 'normal') return null

    return (
      <div className="h-2 w-2 rounded-full absolute top-1 right-1">
        <span className={cn(
          'absolute top-0 right-0 h-2 w-2 rounded-full',
          status === 'warning' ? 'bg-amber-500' : 'bg-red-500',
          'animate-ping opacity-75'
        )}></span>
        <span className={cn(
          'absolute top-0 right-0 h-2 w-2 rounded-full',
          status === 'warning' ? 'bg-amber-500' : 'bg-red-500'
        )}></span>
      </div>
    )
  }

  // Render menu item.
  const renderMenuItem = (item: MenuItem) => {
    const isActive = activeTab === item.id || activeTab.startsWith(`${item.id}/`)
    const isExpanded = expandedItems[item.id] || false
    const hasSubItems = item.subItems && item.subItems.length > 0

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
                {item.icon}
                {getStatusBadge(item.status)}
              </div>
              <span>{t(item.labelKey)}</span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={isActive ? 'default' : 'secondary'}
                >
                  {item.badge}
                </Badge>
              ) : null}
              {hasSubItems && (
                <div className="ml-auto">
                  {isExpanded ? (
                    <ChevronDownIcon size={14} />
                  ) : (
                    <ChevronRightIcon size={14} />
                  )}
                </div>
              )}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{t(item.descriptionKey)}</p>
          </TooltipContent>
        </Tooltip>

        {/* Sub menu items. */}
        {hasSubItems && isExpanded && (
          <div className="pl-8 space-y-1 animate-in slide-in-from-left-5 duration-200">
            {item.subItems!.map((subItem) => {
              const isSubActive = activeTab === `${item.id}/${subItem.id}`

              return (
                <Tooltip key={subItem.id}>
                  <TooltipTrigger asChild>
                    <Button
                      size="sm"
                      variant={isSubActive ? 'secondary' : 'ghost'}
                      className="w-full justify-start gap-2 text-sm"
                      onClick={() => handleSubItemClick(item.id, subItem.id)}
                    >
                      <span>{t(subItem.labelKey)}</span>
                      {subItem.badge ? (
                        <Badge
                          className="ml-auto"
                          variant={isSubActive ? 'default' : 'secondary'}
                        >
                          {subItem.badge}
                        </Badge>
                      ) : null}
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent side="right">
                    <p>{t(subItem.descriptionKey)}</p>
                  </TooltipContent>
                </Tooltip>
              )})
            }
          </div>
        )}
      </div>
    )
  }

  // Render section title.
  const renderSectionTitle = (title: string) => {
    return (
      <div className="flex items-center px-2 mb-2 cursor-pointer group">
        <h2 className="pl-2 text-sm font-semibold tracking-tight text-muted-foreground transition-colors">
          {title}
        </h2>
      </div>
    )
  }

  const mainMenuItems = menuItems.filter(item => item.section === 'main')
  const managementMenuItems = menuItems.filter(item => item.section === 'management')

  // Resolve status icon.
  const getStatusIcon = (status: 'normal' | 'warning' | 'critical') => {
    switch (status) {
      case 'normal':
        return <CheckCircleIcon className="h-4 w-4 text-green-500" />
      case 'warning':
        return <AlertTriangleIcon className="h-4 w-4 text-amber-500" />
      case 'critical':
        return <AlertTriangleIcon className="h-4 w-4 text-red-500" />
      default:
        return <InfoIcon className="h-4 w-4 text-blue-500" />
    }
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="flex w-full items-center justify-between mb-2 px-2">
          <div className="text-lg font-medium text-foreground">{t('safe.sidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('safe.sidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            {/* Primary menu. */}
            <div className="px-2 py-2">
              {renderSectionTitle(t('safe.sidebar.sections.main'))}
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {mainMenuItems.map(renderMenuItem)}
              </div>
            </div>

            {/* Management menu. */}
            <div className="px-2 py-2">
              {renderSectionTitle(t('safe.sidebar.sections.management'))}
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {managementMenuItems.map(renderMenuItem)}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          {/* Security score card. */}
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <ShieldAlertIcon className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('safe.sidebar.score.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshSecurityStatus}
                  disabled={isRefreshing}
                >
                  <RefreshCwIcon className={cn(
                    'h-4 w-4',
                    isRefreshing && 'animate-spin'
                  )} />
                </Button>
              </div>

              <div className="flex items-center justify-between">
                <span className={cn(
                  'text-2xl font-bold',
                  securityStatus.score >= 80 ? 'text-green-500' :
                    securityStatus.score >= 60 ? 'text-amber-500' : 'text-red-500'
                )}>
                  {securityStatus.score}
                </span>
                <div className="text-xs text-muted-foreground">
                  {t('safe.sidebar.score.updatedAt', { time: securityStatus.lastUpdated })}
                </div>
              </div>

              <Progress
                value={securityStatus.score}
                className={cn(
                  securityStatus.score >= 80 ? 'bg-green-200' :
                    securityStatus.score >= 60 ? 'bg-amber-200' : 'bg-red-200'
                )}
              />

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex items-center gap-1">
                  {getStatusIcon(securityStatus.guardrailStatus)}
                  <span>{t('safe.sidebar.score.guardrailStatus')}</span>
                </div>
                <div className="flex items-center gap-1">
                  {getStatusIcon(securityStatus.systemStatus)}
                  <span>{t('safe.sidebar.score.systemStatus')}</span>
                </div>
              </div>

              <div className="flex justify-between mt-2 pt-2 border-t text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart2Icon className="h-3.5 w-3.5" />
                  <span>{t('safe.sidebar.score.report')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <DownloadIcon className="h-3.5 w-3.5" />
                  <span>{t('safe.sidebar.score.export')}</span>
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
