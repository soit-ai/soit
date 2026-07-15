import { useEffect, useMemo, useState } from 'react'
import { Eye, MoreHorizontal, RefreshCw, Search } from 'lucide-react'
import { useSearchParams } from 'react-router'
import { toast } from 'sonner'

import { BoxAlert, BoxPagination, BoxShell } from '@/components/box'
import { PageStatus } from '@/components/common/page-status'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { cn } from '@/lib/utils'
import {
  cancelTask,
  getTaskHandling,
  getTaskWorkbench,
  getTaskWorkbenchItems,
  resumeTask,
  retryTask,
  type TaskHandlingResponse,
  type TaskWorkbenchRow,
} from '@/services/task-service'

import {
  actionLabel,
  formatTaskTime,
  sceneForType,
  statusLabels,
  statusVariant,
  taskAgeLabel,
  taskTabs,
  type TaskTab,
} from './task-display'

function StatusBadge({ status }: { status: string }) {
  return <Badge variant={statusVariant(status) as any}>{statusLabels[status] || status}</Badge>
}

function TaskRowIcon({ row }: { row: TaskWorkbenchRow }) {
  const scene = sceneForType(row.task_type)
  const Icon = scene.icon
  return (
    <div className={cn('flex h-7 w-7 shrink-0 items-center justify-center rounded-md border', scene.tone)}>
      <Icon className="h-3.5 w-3.5" />
    </div>
  )
}

function HandlingDrawer({
  taskId,
  open,
  onOpenChange,
  onActionComplete,
}: {
  taskId?: string | null
  open: boolean
  onOpenChange: (open: boolean) => void
  onActionComplete: () => void
}) {
  const [action, setAction] = useState<string | null>(null)
  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', taskId, 'handling'],
    queryFn: () => getTaskHandling(taskId || ''),
    options: {
      enabled: Boolean(taskId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const handleAction = async (kind: string) => {
    if (!taskId) return
    try {
      setAction(kind)
      if (kind === 'retry') {
        await retryTask(taskId)
      } else if (kind === 'resume') {
        await resumeTask(taskId)
      } else if (kind === 'cancel') {
        await cancelTask(taskId)
      }
      toast.success(`任务${actionLabel(kind)}已提交`)
      await refetch()
      onActionComplete()
    } catch (error) {
      console.error('Failed to control task', error)
      toast.error(`任务${actionLabel(kind)}失败`)
    } finally {
      setAction(null)
    }
  }

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-[min(560px,92vw)] gap-0 overflow-hidden p-0 sm:max-w-none">
        <SheetHeader className="border-b border-border px-6 py-5">
          <SheetTitle className="text-xl">处理面板</SheetTitle>
          <SheetDescription>{data?.summary.title || taskId || '选择任务后查看处置详情'}</SheetDescription>
        </SheetHeader>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
          {isLoading ? (
            <PageStatus variant="loading" title="正在加载处置详情" description="正在读取任务上下文、事件和检查点。" />
          ) : null}

          {!isLoading && isError ? (
            <PageStatus
              variant="error"
              title="处置详情加载失败"
              description={error instanceof Error ? error.message : '无法读取该任务的处置信息。'}
              actionLabel="重试"
              onAction={() => refetch()}
            />
          ) : null}

          {!isLoading && !isError && data ? <HandlingContent data={data} action={action} onAction={handleAction} /> : null}
        </div>
      </SheetContent>
    </Sheet>
  )
}

function HandlingContent({
  data,
  action,
  onAction,
}: {
  data: TaskHandlingResponse
  action: string | null
  onAction: (kind: string) => void
}) {
  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-panel p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="truncate text-base font-semibold text-foreground">{data.summary.title}</div>
            <div className="mt-1 text-sm text-muted-foreground">{data.task.id}</div>
          </div>
          <StatusBadge status={data.summary.status} />
        </div>
        <div className="mt-4 grid gap-3 text-sm">
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">类型</span>
            <span className="font-mono text-xs">{data.summary.task_type}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">更新时间</span>
            <span>{formatTaskTime(data.summary.updated_at)}</span>
          </div>
          <div className="flex justify-between gap-3">
            <span className="text-muted-foreground">运行时长</span>
            <span>{taskAgeLabel(data.task.started_at || data.task.created_at)}</span>
          </div>
        </div>
      </section>

      {data.summary.error_message ? (
        <section className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          <div className="text-sm font-semibold">错误摘要</div>
          <div className="mt-2 text-sm">{data.summary.error_message}</div>
        </section>
      ) : null}

      <section className="rounded-lg border border-border bg-panel p-4">
        <div className="mb-3 text-sm font-semibold">运行上下文</div>
        <div className="grid gap-2 text-sm">
          <div className="flex justify-between gap-3"><span className="text-muted-foreground">Agent ID</span><span className="truncate">{data.runtime_context.agent_id || '-'}</span></div>
          <div className="flex justify-between gap-3"><span className="text-muted-foreground">Thread ID</span><span className="truncate">{data.runtime_context.thread_id || '-'}</span></div>
          <div className="flex justify-between gap-3"><span className="text-muted-foreground">Run ID</span><span className="truncate">{data.runtime_context.run_id || '-'}</span></div>
        </div>
      </section>

      <section className="flex flex-wrap gap-2">
        {data.available_actions.map((item) => (
          <Button key={item} disabled={Boolean(action)} onClick={() => onAction(item)}>
            {actionLabel(item)}
          </Button>
        ))}
        {data.available_actions.length === 0 ? <Badge variant="outline">当前状态无需处置</Badge> : null}
      </section>

      <section className="rounded-lg border border-border bg-panel p-4">
        <div className="mb-3 text-sm font-semibold">事件时间线</div>
        <div className="space-y-3">
          {data.events.map((event) => (
            <div key={event.id} className="border-l-2 border-primary/40 pl-3">
              <div className="text-sm font-medium">{event.event_type}</div>
              <div className="text-xs text-muted-foreground">{formatTaskTime(event.created_at)}</div>
            </div>
          ))}
          {data.events.length === 0 ? <div className="text-sm text-muted-foreground">暂无事件</div> : null}
        </div>
      </section>

      <section className="rounded-lg border border-border bg-panel p-4">
        <div className="mb-3 text-sm font-semibold">执行检查点</div>
        <div className="space-y-2">
          {data.checkpoints.map((checkpoint) => (
            <div key={checkpoint.id} className="flex items-center justify-between gap-3 rounded-md border border-border/70 px-3 py-2 text-sm">
              <span>#{checkpoint.checkpoint_no}</span>
              <StatusBadge status={checkpoint.status} />
            </div>
          ))}
          {data.checkpoints.length === 0 ? <div className="text-sm text-muted-foreground">暂无检查点</div> : null}
        </div>
      </section>
    </div>
  )
}

function TaskProcessingPage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const selectedTaskId = searchParams.get('taskId')
  const initialTab = (searchParams.get('tab') as TaskTab | null) || 'all'
  const [activeTab, setActiveTab] = useState<TaskTab>(initialTab)
  const [search, setSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])
  const pageToken = pageTokens[currentPage - 1]
  const keyword = search.trim()

  const {
    data: workbench,
    refetch: refetchWorkbench,
  } = useQuery({
    queryKey: ['tasks', 'workbench', 'processing'],
    queryFn: () => getTaskWorkbench({ page_size: 1 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['tasks', 'processing', activeTab, keyword, pageToken],
    queryFn: () =>
      getTaskWorkbenchItems({
        page_size: 10,
        page_token: pageToken,
        tab: activeTab,
        keyword: keyword || undefined,
      }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  useEffect(() => {
    setCurrentPage(1)
    setPageTokens([undefined])
  }, [activeTab, keyword])

  const rows = data?.items || []
  const tabs = useMemo(
    () =>
      taskTabs.map((tab) => ({
        ...tab,
        count: workbench?.tabs?.[tab.id] ?? 0,
      })),
    [workbench?.tabs],
  )

  const openTask = (taskId: string) => {
    const params = new URLSearchParams(searchParams)
    params.set('taskId', taskId)
    params.set('tab', activeTab)
    setSearchParams(params)
  }

  const closeDrawer = (open: boolean) => {
    if (open) return
    const params = new URLSearchParams(searchParams)
    params.delete('taskId')
    setSearchParams(params)
  }

  const refreshAll = () => {
    void refetch()
    void refetchWorkbench()
  }

  const pages = useMemo(() => {
    const values = currentPage > 1 ? [currentPage - 1, currentPage] : [currentPage]
    if (data?.next_page_token) values.push(currentPage + 1)
    return values
  }, [currentPage, data?.next_page_token])

  const goToNextPage = () => {
    if (!data?.next_page_token) return
    setPageTokens((tokens) => {
      const nextTokens = tokens.slice(0, currentPage)
      nextTokens[currentPage] = data.next_page_token || undefined
      return nextTokens
    })
    setCurrentPage((page) => page + 1)
  }

  const goToPreviousPage = () => {
    if (currentPage <= 1) return
    setCurrentPage((page) => page - 1)
  }

  return (
    <BoxShell>
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">任务处理</h1>
          <p className="mt-1 text-sm text-muted-foreground">从任务列表中快速定位并处理跟踪任务</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center lg:justify-end">
          <div className="relative min-w-[260px] sm:w-[320px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务名称 / ID / 负责人..." className="h-10 pl-9" />
          </div>
          <Select value={activeTab} onValueChange={(value) => setActiveTab(value as TaskTab)}>
            <SelectTrigger className="h-10 w-[150px] bg-panel">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {taskTabs.map((tab) => <SelectItem key={tab.id} value={tab.id}>{tab.label}</SelectItem>)}
            </SelectContent>
          </Select>
          <Button variant="outline" size="icon-sm" className="h-10 w-10" onClick={refreshAll}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isError ? (
        <BoxAlert
          severity="warning"
          title="任务列表加载失败"
          description={error instanceof Error ? error.message : '无法读取任务处理列表。'}
          action={<Button variant="outline" size="sm" onClick={() => refetch()}>重试</Button>}
        />
      ) : null}

      <div className="flex max-w-full flex-wrap items-center gap-1 rounded-lg border border-border bg-panel p-1 shadow-sm">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
              activeTab === tab.id && 'bg-primary/10 text-primary shadow-[inset_0_0_0_1px_rgba(37,99,235,0.18)]',
            )}
          >
            <span>{tab.label}</span>
            <span className={cn('rounded-full px-2 py-0.5 text-xs', activeTab === tab.id ? 'bg-background text-primary' : 'bg-muted text-muted-foreground')}>{tab.count}</span>
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-panel shadow-sm">
        <Table>
          <TableHeader className="bg-muted/60">
            <TableRow>
              <TableHead className="px-5">任务名称</TableHead>
              <TableHead>状态</TableHead>
              <TableHead>类型</TableHead>
              <TableHead>负责人</TableHead>
              <TableHead>更新时间</TableHead>
              <TableHead className="text-right">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="h-[62px] cursor-pointer border-border/70 hover:bg-primary/5" onClick={() => openTask(row.id)}>
                <TableCell className="px-5">
                  <div className="flex min-w-[240px] items-center gap-3">
                    <TaskRowIcon row={row} />
                    <div className="min-w-0">
                      <div className="truncate font-semibold">{row.display_name}</div>
                      <div className="mt-0.5 text-xs text-muted-foreground">ID: {row.id}</div>
                    </div>
                  </div>
                </TableCell>
                <TableCell><StatusBadge status={row.status} /></TableCell>
                <TableCell className="font-mono text-xs">{row.task_type}</TableCell>
                <TableCell>{row.owner || '-'}</TableCell>
                <TableCell>{formatTaskTime(row.updated_at)}</TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-2">
                    <Button
                      variant="outline"
                      size="icon-xs"
                      onClick={(event) => {
                        event.stopPropagation()
                        navigate(`/tasks/${row.id}`)
                      }}
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </Button>
                    <Button
                      variant="outline"
                      size="icon-xs"
                      onClick={(event) => {
                        event.stopPropagation()
                        openTask(row.id)
                      }}
                    >
                      <MoreHorizontal className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
            {!rows.length ? (
              <TableRow>
                <TableCell colSpan={6} className="h-28 text-center text-sm text-muted-foreground">
                  {isLoading ? '正在加载任务...' : '暂无任务'}
                </TableCell>
              </TableRow>
            ) : null}
          </TableBody>
        </Table>
      </div>

      <BoxPagination
        total={data?.total ?? 0}
        pageSize={data?.page_size || 10}
        currentPage={currentPage}
        pages={pages}
        hasPrevious={currentPage > 1}
        hasNext={Boolean(data?.next_page_token)}
        onPrevious={goToPreviousPage}
        onNext={goToNextPage}
        onPageChange={(page) => {
          if (page === currentPage + 1) goToNextPage()
          if (page === currentPage - 1) goToPreviousPage()
        }}
        labels={{ totalSuffix: '条', pageSizeSuffix: '条/页', goTo: '前往', page: '页' }}
      />

      <HandlingDrawer taskId={selectedTaskId} open={Boolean(selectedTaskId)} onOpenChange={closeDrawer} onActionComplete={refreshAll} />
    </BoxShell>
  )
}

export default TaskProcessingPage
