import { Activity, AlertTriangle, ClipboardList, Home, RefreshCw, Wrench } from 'lucide-react'
import type React from 'react'
import { Link } from 'react-router'

import { Button, buttonVariants } from '@/components/ui/button'
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
import { useQuery } from '@/hooks/use-query'
import { cn } from '@/lib/utils'
import { getTaskWorkbench } from '@/services/task-service'

const primaryItems = [
  { id: 'center', label: '任务中心', url: '/tasks', icon: Home, disabled: false },
  { id: 'processing', label: '任务处理', url: '/tasks/processing', icon: Wrench, disabled: false },
]

const managementItems = [
  { id: 'library', label: '任务库', url: '/tasks?view=library', icon: ClipboardList, disabled: true },
  { id: 'history', label: '运行记录', url: '/tasks?view=history', icon: Activity, disabled: true },
  { id: 'exceptions', label: '异常处理', url: '/tasks?view=exceptions', icon: AlertTriangle, disabled: true },
]

export function TaskSidebar({
  activeTab = 'center',
  ...props
}: { activeTab?: string } & React.ComponentProps<typeof Sidebar>) {
  const { setOpen } = useSidebar()
  const { data, isFetching, refetch } = useQuery({
    queryKey: ['tasks', 'workbench', 'sidebar'],
    queryFn: () => getTaskWorkbench({ page_size: 1 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const summary = data?.summary
  const total = summary?.total_tasks || 0
  const attention = (summary?.failed || 0) + (summary?.waiting_input || 0) + (summary?.waiting_approval || 0)
  const attentionRate = total ? Math.min((attention / total) * 100, 100) : 0

  const renderItem = (item: (typeof primaryItems)[number] | (typeof managementItems)[number]) => {
    const Icon = item.icon
    const isActive = activeTab === item.id

    return (
      <Tooltip key={item.id}>
        <TooltipTrigger asChild>
          {item.disabled ? (
            <Button
              variant={isActive ? 'secondary' : 'ghost'}
              className="relative w-full justify-start gap-2 opacity-50"
              disabled
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Button>
          ) : (
            <Link
              to={item.url}
              aria-current={isActive ? 'page' : undefined}
              onClick={() => setOpen(false)}
              className={cn(
                buttonVariants({ variant: isActive ? 'secondary' : 'ghost' }),
                'relative w-full justify-start gap-2',
              )}
            >
              <Icon className="h-4 w-4" />
              <span>{item.label}</span>
            </Link>
          )}
        </TooltipTrigger>
        <TooltipContent side="right">
          <p>{item.label}</p>
        </TooltipContent>
      </Tooltip>
    )
  }

  return (
    <Sidebar className="hidden flex-1 md:flex" {...props}>
      <SidebarHeader className="mt-0">
        <div className="mb-2 flex w-full items-center justify-between px-2">
          <div className="text-lg font-semibold text-foreground">Task</div>
          <SidebarTrigger className="-mr-1" />
        </div>
        <SidebarInput placeholder="搜索任务..." className="mx-2 w-auto" />
      </SidebarHeader>

      <SidebarContent>
        <ScrollArea className="flex-1 overflow-auto">
          <div className="w-full">
            <div className="px-2 py-2">
              <div className="space-y-1 animate-in fade-in-50 duration-100">
                {primaryItems.map(renderItem)}
              </div>
            </div>

            <div className="px-2 py-2">
              <h2 className="mb-2 px-2 text-sm font-semibold tracking-tight text-muted-foreground">管理</h2>
              <div className="space-y-1">{managementItems.map(renderItem)}</div>
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
                  <ClipboardList className="mr-2 h-5 w-5 text-primary" />
                  <h3 className="font-semibold">任务统计</h3>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-6 w-6"
                  onClick={() => refetch()}
                  disabled={isFetching}
                >
                  <RefreshCw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
                </Button>
              </div>

              <div className="grid grid-cols-2 gap-2 text-sm">
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">全部任务</span>
                  <span className="font-semibold">{total.toLocaleString()}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">运行中</span>
                  <span className="font-semibold">{summary?.running ?? 0}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">需处理</span>
                  <span className="font-semibold">{attention}</span>
                </div>
                <div className="flex flex-col">
                  <span className="text-xs text-muted-foreground">今日新增</span>
                  <span className="font-semibold">{summary?.today_created ?? 0}</span>
                </div>
              </div>

              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">处理压力</span>
                  <span>{attention}</span>
                </div>
                <Progress value={attentionRate} className="h-1.5 bg-orange-100 dark:bg-orange-400/10" />
              </div>

              <div className="text-xs text-muted-foreground">
                更新时间：{summary?.updated_at ? new Date(summary.updated_at).toLocaleString('zh-CN', { hour12: false }) : '-'}
              </div>
            </div>
          </div>
        </div>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
