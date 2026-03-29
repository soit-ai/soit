import * as React from 'react'
import { useCallback, useEffect, useState } from 'react'
import {
  SquareChartGantt,
  Settings2,
  BotMessageSquare,
  ArrowLeft,
  MessagesSquare,
  ChartSpline,
  PencilRuler,
  InfoIcon,
  Share2,
} from 'lucide-react'

import { useTranslation } from '@/i18n'
import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { BoxHeader } from '@/components/ui/app/box-card'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { useLocation } from 'react-router'
import type { TranslationKey } from '@/i18n/types'

export interface NavSidebarProps extends React.ComponentProps<typeof Sidebar> {
  workflowId?: string
}

interface NavItem {
  id: string
  titleKey: string
  descriptionKey: string
  url: string
  icon: React.ElementType
  isActive?: boolean
  badge?: number | null
}

export function NavSidebar({ ...props }: NavSidebarProps) {
  const { workflowId = '' } = props
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [navItems, setNavItems] = useState<NavItem[]>([])

  // Update active navigation state based on the current route.
  useEffect(() => {
    const currentPath = location.pathname

    const items: NavItem[] = [
      {
        id: 'build',
        titleKey: 'workflow.detail.sidebar.nav.build',
        descriptionKey: 'workflow.detail.sidebar.nav.buildDesc',
        url: `/workflow/${workflowId}/build`,
        icon: PencilRuler,
        isActive: currentPath.includes(`/workflow/${workflowId}/build`),
      },
      {
        id: 'logs',
        titleKey: 'workflow.detail.sidebar.nav.logs',
        descriptionKey: 'workflow.detail.sidebar.nav.logsDesc',
        url: `/workflow/${workflowId}/log`,
        icon: SquareChartGantt,
        isActive: currentPath.includes(`/workflow/${workflowId}/log`),
      },
      {
        id: 'monitor',
        titleKey: 'workflow.detail.sidebar.nav.monitor',
        descriptionKey: 'workflow.detail.sidebar.nav.monitorDesc',
        url: `/workflow/${workflowId}/monitor`,
        icon: ChartSpline,
        isActive: currentPath.includes(`/workflow/${workflowId}/monitor`),
      },
      {
        id: 'publish',
        titleKey: 'workflow.detail.sidebar.nav.publish',
        descriptionKey: 'workflow.detail.sidebar.nav.publishDesc',
        url: `/workflow/${workflowId}/publish`,
        icon: Share2,
        badge: 1,
        isActive: currentPath.includes(`/workflow/${workflowId}/publish`),
      },
      {
        id: 'setting',
        titleKey: 'workflow.detail.sidebar.nav.setting',
        descriptionKey: 'workflow.detail.sidebar.nav.settingDesc',
        url: `/workflow/${workflowId}/setting`,
        icon: Settings2,
        isActive: currentPath.includes(`/workflow/${workflowId}/setting`),
      },
    ]

    setNavItems(items)
  }, [location.pathname, workflowId])

  const workflowInfo = {
    id: workflowId,
    title: t('workflow.detail.sidebar.info.sample.title'),
    subtitle: workflowId,
    icon: <BotMessageSquare color="blue" />,
    iconType: 'icon',
    desc: t('workflow.detail.sidebar.info.sample.description'),
    tags: ['AI', 'Research', 'NLP'],
    version: '1.2.0',
    lastUpdated: '2025-05-30',
    status: t('workflow.detail.sidebar.info.status.published'),
  }

  const handleNavItemClick = useCallback((url: string) => {
    navigate(url)
  }, [navigate])

  const handleNavItemHover = useCallback((item: NavItem) => {
    return t(item.descriptionKey as TranslationKey)
  }, [t])

  const openRunChat = useCallback(() => {
    navigate(`/chat/${workflowId}`)
  }, [navigate, workflowId])

  const goBackToWorkflowList = useCallback(() => {
    navigate('/workflow')
  }, [navigate])

  const renderNavItem = (item: NavItem) => {
    return (
      <div key={item.id} className="mb-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={item.isActive ? 'secondary' : 'ghost'}
              className={cn(
                'w-full justify-start transition-all duration-200',
                item.isActive && 'bg-secondary'
              )}
              onClick={() => handleNavItemClick(item.url)}
            >
              <span className="flex items-center">
                {React.createElement(item.icon, {
                  className: cn('h-4 w-4', item.isActive ? 'text-primary' : ''),
                })}
                <span className={cn('ml-2', item.isActive ? 'font-medium' : '')}>
                  {t(item.titleKey as TranslationKey)}
                </span>
              </span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={item.isActive ? 'default' : 'secondary'}
                >
                  {item.badge}
                </Badge>
              ) : null}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right" className="max-w-[220px]">
            <p>{handleNavItemHover(item)}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-2">
        <BoxHeader
          title={workflowInfo.title}
          subtitle={workflowInfo.subtitle}
          icon={workflowInfo.icon}
          iconType={workflowInfo.iconType as 'icon'}
          iconHover={
            <ArrowLeft
              className="w-6 h-6 cursor-pointer"
              onClick={goBackToWorkflowList}
            />
          }
        />
        <div className="px-3 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3 mt-2">
            <div className="flex items-center mb-2">
              <InfoIcon className="mr-2 h-4 w-4 text-blue-500" />
              <h3 className="font-semibold text-sm">{t('workflow.detail.sidebar.info.title')}</h3>
            </div>
            <p className="text-xs text-muted-foreground">{workflowInfo.desc}</p>
            <div className="flex flex-wrap gap-1 mt-2">
              {workflowInfo.tags.map(tag => (
                <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
              ))}
            </div>
            <div className="mt-2 pt-2 border-t border-border">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{t('workflow.detail.sidebar.info.version')}</span>
                <span>{workflowInfo.version}</span>
              </div>
              <div className="flex justify-between text-xs text-muted-foreground mt-1">
                <span>{t('workflow.detail.sidebar.info.updatedAt')}</span>
                <span>{workflowInfo.lastUpdated}</span>
              </div>
              <div className="flex justify-between text-xs mt-1">
                <span>{t('workflow.detail.sidebar.info.status.label')}</span>
                <span className="text-green-500 font-medium">{workflowInfo.status}</span>
              </div>
            </div>
          </div>
        </div>
        <Separator className="mt-1 mb-1" />
      </SidebarHeader>
      <SidebarContent>
        <ScrollArea className="h-full">
          <div className="px-1 py-2">
            <div className="space-y-1">
              {navItems.map(renderNavItem)}
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>
      <SidebarFooter>
        <div className="p-3 space-y-2">
          <Button
            className="w-full bg-sidebar-primary text-sidebar-primary-foreground shadow-none hover:bg-sidebar-primary/90"
            onClick={openRunChat}
          >
            {t('workflow.detail.sidebar.actions.run')}
            <MessagesSquare className="ml-2 h-4 w-4" />
          </Button>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => navigate(`/workflow/${workflowId}/setting`)}
            >
              <Settings2 className="h-3 w-3 mr-1" /> {t('workflow.detail.sidebar.actions.setting')}
            </Button>
            <Button
              variant="outline"
              size="sm"
              className="flex-1 text-xs"
              onClick={() => window.open(`/workflow/${workflowId}/share`, '_blank')}
            >
              <Share2 className="h-3 w-3 mr-1" /> {t('workflow.detail.sidebar.actions.share')}
            </Button>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
