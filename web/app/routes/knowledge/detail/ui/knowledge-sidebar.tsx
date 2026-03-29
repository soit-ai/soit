import * as React from 'react'
import { useCallback, useEffect, useState } from 'react'
import { useTranslation } from '@/i18n'
import { useLocation } from 'react-router'
import {
  ArrowLeft,
  BarChart3,
  Database,
  FileText,
  InfoIcon,
  Settings2,
  AppWindow,
} from 'lucide-react'

import { Sidebar, SidebarContent, SidebarFooter, SidebarHeader, SidebarRail } from '@/components/ui/sidebar'
import { useNavigate } from '@/hooks/use-navigate'
import { BoxHeader } from '@/components/ui/app/box-card'
import { Separator } from '@/components/ui/separator'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import { ScrollArea } from '@/components/ui/scroll-area'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import { getKnowledgeBase, type KnowledgeBase } from '@/services/knowledge-service'
// This is sample data.

export interface NavSidebarProps extends React.ComponentProps<typeof Sidebar> {
  knowledgeId?: string
}

// Navigation item shape for the sidebar.
interface NavItem {
  title: string;
  url: string;
  icon: React.ElementType;
  description: string;
  badge?: number | null;
}

export function NavSidebar({ ...props }: NavSidebarProps) {
  const { knowledgeId = '' } = props
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [knowledge, setKnowledge] = useState<KnowledgeBase | null>(null)
  const [loading, setLoading] = useState(false)

  // Sidebar navigation definition.
  const navItems: NavItem[] = [
    {
      title: t('knowledge.detail.sidebar.nav.documents'),
      url: `/knowledge/${knowledgeId}/document`,
      icon: FileText,
      description: t('knowledge.detail.sidebar.nav.documentsDesc')
    },
    {
      title: t('knowledge.detail.sidebar.nav.analytics'),
      url: `/knowledge/${knowledgeId}/analytics`,
      icon: BarChart3,
      description: t('knowledge.detail.sidebar.nav.analyticsDesc')
    },
    {
      title: t('knowledge.detail.sidebar.nav.usages'),
      url: `/knowledge/${knowledgeId}/usages`,
      icon: AppWindow,
      description: t('knowledge.detail.sidebar.nav.usagesDesc')
    },
    {
      title: t('knowledge.detail.sidebar.nav.settings'),
      url: `/knowledge/${knowledgeId}/setting`,
      icon: Settings2,
      description: t('knowledge.detail.sidebar.nav.settingsDesc')
    },
  ]
  
  useEffect(() => {
    if (!knowledgeId) return
    const fetchKnowledge = async () => {
      try {
        setLoading(true)
        const data = await getKnowledgeBase(knowledgeId)
        setKnowledge(data)
      } catch (error) {
        toast.error(t('knowledge.detail.sidebar.toast.fetchError'))
        console.error('Failed to fetch knowledge:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchKnowledge()
  }, [knowledgeId])

  // Handle navigation item clicks.
  const handleNavItemClick = useCallback((url: string) => {
    navigate(url)
  }, [navigate])

  // Navigate back to knowledge list.
  const goBackToKnowledgeList = useCallback(() => {
    navigate('/knowledge')
  }, [navigate])

  // Check active route.
  const isRouteActive = useCallback((url: string) => {
    return location.pathname === url
  }, [location.pathname])

  // Render a navigation item.
  const renderNavItem = (item: NavItem) => {
    const isActive = isRouteActive(item.url)
    return (
      <div key={item.title} className="mb-1">
        <Tooltip>
          <TooltipTrigger asChild>
            <Button
              variant={isActive ? "secondary" : "ghost"}
              className={cn(
                "w-full justify-start",
                isActive && "bg-secondary"
              )}
              onClick={() => handleNavItemClick(item.url)}
            >
              <span className="flex items-center">
                {React.createElement(item.icon, { className: "h-4 w-4" })}
                <span className="ml-2">{item.title}</span>
              </span>
              {item.badge ? (
                <Badge
                  className="ml-auto"
                  variant={isActive ? "default" : "secondary"}
                >
                  {item.badge}
                </Badge>
              ) : null}
            </Button>
          </TooltipTrigger>
          <TooltipContent side="right">
            <p>{item.description}</p>
          </TooltipContent>
        </Tooltip>
      </div>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-2">
        <BoxHeader
          title={knowledge?.name || (loading ? t('knowledge.detail.sidebar.loading') : t('knowledge.detail.sidebar.untitled'))}
          subtitle={
            knowledge
              ? t('knowledge.detail.sidebar.summary', {
                  docCount: knowledge.doc_count,
                  chunkCount: knowledge.chunk_count,
                })
              : t('knowledge.detail.sidebar.empty')
          }
          icon={<Database color="blue" />}
          iconType={'icon'}
          iconHover={
            <ArrowLeft
              className="w-6 h-6 cursor-pointer"
              onClick={goBackToKnowledgeList}
            />
          }
        />
        <div className="px-3 py-2">
          <div className="rounded-lg border bg-card text-card-foreground shadow-sm p-3 mt-2">
            <div className="flex items-center mb-2">
              <InfoIcon className="mr-2 h-4 w-4 text-blue-500" />
              <h3 className="font-semibold text-sm">{t('knowledge.detail.sidebar.infoTitle')}</h3>
            </div>
            <p className="text-xs text-muted-foreground">
              {knowledge?.description || t('knowledge.detail.sidebar.noDescription')}
            </p>
            <div className="flex flex-wrap gap-1 mt-2">
              {(knowledge?.tags || []).map(tag => (
                <Badge key={tag} variant="outline" className="text-xs">{tag}</Badge>
              ))}
              {!knowledge?.tags?.length && (
                <Badge variant="outline" className="text-xs">{t('knowledge.detail.sidebar.noTags')}</Badge>
              )}
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
        <div className="p-3">
          <Button 
            className="w-full bg-sidebar-primary text-sidebar-primary-foreground shadow-none" 
            onClick={() => navigate(`/knowledge/${knowledgeId}/document`)}
          >
            {t('knowledge.detail.sidebar.manageDocs')} <FileText className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
