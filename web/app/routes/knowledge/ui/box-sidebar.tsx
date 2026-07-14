import {
  AlertTriangle,
  ArrowLeftRight,
  BarChart3,
  BookOpen,
  Database,
  ExternalLink,
  FileText,
  Home,
  RefreshCw,
  SearchCheck,
  Trash2,
} from 'lucide-react'
import { useCallback, useState } from 'react'
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
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'

interface KnowledgeMenuItem {
  id: string
  labelKey: TranslationKey
  url: string
  icon: typeof Home
}

const primaryItems: KnowledgeMenuItem[] = [
  {
    id: 'overview',
    labelKey: 'knowledge.workspaceSidebar.menu.overview',
    url: '/knowledge?view=overview',
    icon: Home,
  },
  {
    id: 'library',
    labelKey: 'knowledge.workspaceSidebar.menu.library',
    url: '/knowledge?view=library',
    icon: Database,
  },
  {
    id: 'documents',
    labelKey: 'knowledge.workspaceSidebar.menu.documents',
    url: '/knowledge?view=documents',
    icon: FileText,
  },
  {
    id: 'testing',
    labelKey: 'knowledge.workspaceSidebar.menu.testing',
    url: '/knowledge?view=testing',
    icon: SearchCheck,
  },
]

const managementItems: KnowledgeMenuItem[] = [
  {
    id: 'references',
    labelKey: 'knowledge.workspaceSidebar.menu.references',
    url: '/knowledge?view=references',
    icon: ArrowLeftRight,
  },
  {
    id: 'exceptions',
    labelKey: 'knowledge.workspaceSidebar.menu.exceptions',
    url: '/knowledge?view=exceptions',
    icon: AlertTriangle,
  },
  {
    id: 'recycle',
    labelKey: 'knowledge.workspaceSidebar.menu.recycle',
    url: '/knowledge?view=recycle',
    icon: Trash2,
  },
]

export function BoxSidebar(props: React.ComponentProps<typeof Sidebar>) {
  const navigate = useNavigate()
  const { setOpen } = useSidebar()
  const { t } = useTranslation()
  const [searchParams] = useSearchParams()
  const [isRefreshing, setIsRefreshing] = useState(false)
  const activeView = searchParams.get('view') || 'overview'

  const refreshStats = useCallback(() => {
    setIsRefreshing(true)
    window.setTimeout(() => setIsRefreshing(false), 450)
  }, [])

  const navigateTo = (url: string) => {
    navigate(url)
    setOpen(false)
  }

  const renderMenuItem = (item: KnowledgeMenuItem) => {
    const Icon = item.icon
    const label = t(item.labelKey)
    const isActive = activeView === item.id

    return (
      <Tooltip key={item.id}>
        <TooltipTrigger asChild>
          <Button
            variant={isActive ? 'secondary' : 'ghost'}
            className="relative w-full justify-start gap-2"
            onClick={() => navigateTo(item.url)}
          >
            <Icon className="h-4 w-4" />
            <span>{label}</span>
          </Button>
        </TooltipTrigger>
        <TooltipContent side="right">
          <p>{label}</p>
        </TooltipContent>
      </Tooltip>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="mb-2 flex w-full items-center justify-between px-2">
          <div className="text-lg font-semibold text-foreground">{t('knowledge.workspaceSidebar.title')}</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder={t('knowledge.workspaceSidebar.searchPlaceholder')} className="mx-2 w-auto" />
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            <div className="px-2 py-2">
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {primaryItems.map(renderMenuItem)}
              </div>
            </div>

            <div className="px-2 py-2">
              <h2 className="mb-2 px-2 text-sm font-semibold tracking-tight text-muted-foreground">{t('knowledge.workspaceSidebar.management')}</h2>
              <div className="space-y-1">
                {managementItems.map(renderMenuItem)}
              </div>
            </div>
          </div>
        </ScrollArea>
      </SidebarContent>

      <SidebarFooter className="mt-auto">
        <div className="px-2 py-2">
          <div className="rounded-lg border border-border bg-card p-3 text-card-foreground shadow-sm">
            <div className="flex flex-col space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center">
                  <BookOpen className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">{t('knowledge.workspaceSidebar.stats.title')}</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={refreshStats}
                  disabled={isRefreshing}
                >
                  <RefreshCw className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('knowledge.workspaceSidebar.stats.total')}</span>
                  <span className="font-semibold">32</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('knowledge.workspaceSidebar.stats.ready')}</span>
                  <span className="font-semibold">27</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('knowledge.workspaceSidebar.stats.documents')}</span>
                  <span className="font-semibold">12,840</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">{t('knowledge.workspaceSidebar.stats.chunks')}</span>
                  <span className="font-semibold">486k</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">{t('knowledge.workspaceSidebar.stats.recallRate')}</span>
                  <span>97.4%</span>
                </div>
                <Progress value={97.4} className="h-1.5 bg-emerald-100 dark:bg-emerald-400/10" />
              </div>

              <div className="text-xs text-muted-foreground">
                {t('knowledge.workspaceSidebar.stats.updatedAt', { timestamp: '2026-05-30 10:18' })}
              </div>

              <div className="mt-2 flex justify-between border-t border-border pt-2 text-xs">
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <BarChart3 className="h-3.5 w-3.5" />
                  <span>{t('knowledge.workspaceSidebar.stats.usageReport')}</span>
                </Button>
                <Button variant="ghost" size="sm" className="h-7 gap-1">
                  <ExternalLink className="h-3.5 w-3.5" />
                  <span>{t('knowledge.workspaceSidebar.stats.details')}</span>
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
