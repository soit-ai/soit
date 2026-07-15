import { useEffect, useMemo, useState } from 'react'
import { ArrowRight, Eye, MoreHorizontal, RefreshCw, Search, SlidersHorizontal } from 'lucide-react'

import {
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  MetricStrip,
} from '@/components/box'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { cn } from '@/lib/utils'
import { getTaskWorkbench, getTaskWorkbenchItems, type TaskWorkbenchRow } from '@/services/task-service'

import {
  formatTaskTime,
  metricIconForTab,
  sceneForType,
  sparkline,
  statusLabels,
  statusVariant,
  taskTabs,
  type TaskTab,
} from './task-display'

const priorityTabs: TaskTab[] = ['waiting_approval', 'failed', 'waiting_input', 'long_running']

function TaskNameCell({ row }: { row: TaskWorkbenchRow }) {
  const scene = sceneForType(row.task_type)
  const Icon = scene.icon

  return (
    <div className="flex min-w-[240px] items-center gap-3">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md border', scene.tone)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.display_name}</div>
        <div className="mt-0.5 truncate text-xs text-muted-foreground">{row.id}</div>
      </div>
    </div>
  )
}

function SceneBadge({ row }: { row: TaskWorkbenchRow }) {
  const scene = sceneForType(row.task_type)
  return <Badge variant="outline">{scene.label}</Badge>
}

function StatusBadge({ status }: { status: string }) {
  return <Badge variant={statusVariant(status) as any}>{statusLabels[status] || status}</Badge>
}

function TaskCenterPage() {
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState<TaskTab>('all')
  const [status, setStatus] = useState('all')
  const [search, setSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])

  const tableKeyword = search.trim()
  const pageToken = pageTokens[currentPage - 1]

  const {
    data: workbench,
    isError: isWorkbenchError,
    error: workbenchError,
    refetch: refetchWorkbench,
  } = useQuery({
    queryKey: ['tasks', 'workbench'],
    queryFn: () => getTaskWorkbench({ page_size: 10 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: tableData,
    isLoading: isTableLoading,
    isError: isTableError,
    error: tableError,
    refetch: refetchTable,
  } = useQuery({
    queryKey: ['tasks', 'workbench', 'items', activeTab, status, tableKeyword, dateFrom, dateTo, pageToken],
    queryFn: () =>
      getTaskWorkbenchItems({
        page_size: 10,
        page_token: pageToken,
        tab: activeTab,
        status: status === 'all' ? undefined : status,
        keyword: tableKeyword || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  useEffect(() => {
    setCurrentPage(1)
    setPageTokens([undefined])
  }, [activeTab, status, tableKeyword, dateFrom, dateTo])

  const metrics = useMemo(() => {
    const summary = workbench?.summary
    return [
      { id: 'all', label: '全部任务', value: (summary?.total_tasks ?? 0).toLocaleString(), icon: metricIconForTab('all'), tone: 'blue' as const },
      { id: 'waiting_approval', label: '待审批', value: String(summary?.waiting_approval ?? 0), icon: metricIconForTab('waiting_approval'), tone: 'amber' as const },
      { id: 'failed', label: '失败', value: String(summary?.failed ?? 0), icon: metricIconForTab('failed'), tone: 'red' as const },
      { id: 'waiting_input', label: '等待输入', value: String(summary?.waiting_input ?? 0), icon: metricIconForTab('waiting_input'), tone: 'cyan' as const },
      { id: 'running', label: '运行中', value: String(summary?.running ?? 0), icon: metricIconForTab('running'), tone: 'green' as const },
    ].map((item) => ({ ...item, trend: sparkline }))
  }, [workbench?.summary])

  const tabs = useMemo(
    () =>
      taskTabs.map((tab) => ({
        id: tab.id,
        label: tab.label,
        count: workbench?.tabs?.[tab.id] ?? 0,
      })),
    [workbench?.tabs],
  )

  const rows = tableData?.items || []
  const priorityCards = priorityTabs.map((tab) => {
    const label = taskTabs.find((item) => item.id === tab)?.label || tab
    const items = (workbench?.items || []).filter((item) => {
      if (tab === 'long_running') return false
      return item.status === tab
    })
    return {
      tab,
      label,
      count: workbench?.tabs?.[tab] ?? 0,
      icon: metricIconForTab(tab),
      items,
    }
  })

  const pages = useMemo(() => {
    const values = currentPage > 1 ? [currentPage - 1, currentPage] : [currentPage]
    if (tableData?.next_page_token) values.push(currentPage + 1)
    return values
  }, [currentPage, tableData?.next_page_token])

  const goToNextPage = () => {
    if (!tableData?.next_page_token) return
    setPageTokens((tokens) => {
      const nextTokens = tokens.slice(0, currentPage)
      nextTokens[currentPage] = tableData.next_page_token || undefined
      return nextTokens
    })
    setCurrentPage((page) => page + 1)
  }

  const goToPreviousPage = () => {
    if (currentPage <= 1) return
    setCurrentPage((page) => page - 1)
  }

  const goToPage = (page: number) => {
    if (page === currentPage + 1) goToNextPage()
    if (page === currentPage - 1) goToPreviousPage()
  }

  const columns = useMemo<BoxDataTableColumn<TaskWorkbenchRow>[]>(
    () => [
      { id: 'name', header: '任务名称', render: (row) => <TaskNameCell row={row} /> },
      { id: 'scene', header: '场景', render: (row) => <SceneBadge row={row} /> },
      { id: 'status', header: '状态', render: (row) => <StatusBadge status={row.status} /> },
      { id: 'type', header: '类型', render: (row) => <span className="font-mono text-xs">{row.task_type}</span> },
      { id: 'owner', header: '负责人', render: (row) => row.owner || '-' },
      { id: 'updated', header: '更新时间', render: (row) => formatTaskTime(row.updated_at) },
      {
        id: 'actions',
        header: '操作',
        render: (row) => (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="icon-xs" onClick={() => navigate(`/tasks/${row.id}`)}>
              <Eye className="h-3.5 w-3.5" />
            </Button>
            <Button variant="outline" size="icon-xs" onClick={() => navigate(`/tasks/processing?taskId=${row.id}`)}>
              <MoreHorizontal className="h-3.5 w-3.5" />
            </Button>
          </div>
        ),
      },
    ],
    [navigate],
  )

  return (
    <BoxShell>
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <BoxPageHeader title="任务运行中心" description="优先处理审批、失败与等待输入的运行任务" />
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center 2xl:justify-end">
          <div className="relative min-w-[260px] sm:w-[320px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务名称、ID、负责人..." className="h-10 pl-9" />
          </div>
          <Select value={status} onValueChange={setStatus}>
            <SelectTrigger className="h-10 w-[150px] bg-panel">
              <SelectValue placeholder="全部状态" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">全部状态</SelectItem>
              <SelectItem value="running">运行中</SelectItem>
              <SelectItem value="waiting_approval">待审批</SelectItem>
              <SelectItem value="waiting_input">等待输入</SelectItem>
              <SelectItem value="failed">失败</SelectItem>
              <SelectItem value="succeeded">成功</SelectItem>
            </SelectContent>
          </Select>
          <Input type="date" value={dateFrom} onChange={(event) => setDateFrom(event.target.value)} className="h-10 w-[150px]" />
          <Input type="date" value={dateTo} onChange={(event) => setDateTo(event.target.value)} className="h-10 w-[150px]" />
          <Button variant="outline" size="icon-sm" className="h-10 w-10" onClick={() => { void refetchWorkbench(); void refetchTable() }}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {isWorkbenchError || isTableError ? (
        <BoxAlert
          severity="warning"
          title="任务数据加载失败"
          description={tableError instanceof Error ? tableError.message : workbenchError instanceof Error ? workbenchError.message : undefined}
          action={<Button variant="outline" size="sm" onClick={() => { void refetchWorkbench(); void refetchTable() }}>重试</Button>}
        />
      ) : null}

      <MetricStrip items={metrics} deltaLabel="较昨日" />

      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">优先处理</h2>
            <p className="text-sm text-muted-foreground">需要重点关注的运行任务</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/tasks/processing')}>
            查看全部
            <ArrowRight className="h-4 w-4" />
          </Button>
        </div>
        <div className="grid gap-3 xl:grid-cols-4">
          {priorityCards.map((card) => {
            const Icon = card.icon
            return (
              <div key={card.tab} className="overflow-hidden rounded-lg border border-border bg-panel shadow-sm">
                <div className="flex items-center justify-between border-b border-border/70 px-4 py-3">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-primary" />
                    <span className="font-semibold">{card.label}</span>
                    <span className="text-lg font-semibold text-foreground">{card.count}</span>
                  </div>
                  <Button variant="outline" size="sm" className="h-8" onClick={() => navigate(`/tasks/processing?tab=${card.tab}`)}>处理</Button>
                </div>
                <div className="space-y-2 p-3">
                  {card.items.slice(0, 2).map((item) => (
                    <button key={item.id} type="button" className="w-full rounded-md border border-border/70 px-3 py-2 text-left hover:bg-primary/5" onClick={() => navigate(`/tasks/processing?taskId=${item.id}`)}>
                      <div className="truncate text-sm font-medium">{item.display_name}</div>
                      <div className="mt-1 flex items-center justify-between gap-2 text-xs text-muted-foreground">
                        <span>{item.task_type}</span>
                        <StatusBadge status={item.status} />
                      </div>
                    </button>
                  ))}
                  {card.items.length === 0 ? <div className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">暂无任务</div> : null}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">运行任务账本</h2>
            <p className="text-sm text-muted-foreground">完整运行任务记录与处理入口</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-10">
              <SlidersHorizontal className="h-4 w-4" />
              筛选
            </Button>
          </div>
        </div>
        <div className="flex max-w-full flex-wrap items-center gap-1 rounded-lg border border-border bg-panel p-1 shadow-sm">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveTab(tab.id as TaskTab)}
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

        <BoxDataTable columns={columns} rows={rows} emptyMessage={isTableLoading ? '正在加载任务...' : '暂无任务'} />
        <BoxPagination
          total={tableData?.total ?? 0}
          pageSize={tableData?.page_size || 10}
          currentPage={currentPage}
          pages={pages}
          hasPrevious={currentPage > 1}
          hasNext={Boolean(tableData?.next_page_token)}
          onPrevious={goToPreviousPage}
          onNext={goToNextPage}
          onPageChange={goToPage}
          labels={{ totalSuffix: '条', pageSizeSuffix: '条/页', goTo: '前往', page: '页' }}
        />
      </section>
    </BoxShell>
  )
}

export default TaskCenterPage
