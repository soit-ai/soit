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
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { getTaskWorkbench, getTaskWorkbenchItems, type TaskWorkbenchRow } from '@/services/task-service'

import {
  formatTaskTime,
  metricIconForTab,
  sceneForType,
  sparkline,
  statusLabel,
  statusVariant,
  taskTabLabel,
  taskTabs,
  type TaskTab,
} from './task-display'

const priorityTabs: TaskTab[] = ['waiting_approval', 'failed', 'waiting_input', 'long_running']

function TaskNameCell({ row }: { row: TaskWorkbenchRow }) {
  const { t } = useTranslation()
  const scene = sceneForType(t, row.task_type)
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
  const { t } = useTranslation()
  const scene = sceneForType(t, row.task_type)
  return <Badge variant="outline">{scene.label}</Badge>
}

function StatusBadge({ status }: { status: string }) {
  const { t } = useTranslation()
  return <Badge variant={statusVariant(status) as any}>{statusLabel(t, status)}</Badge>
}

function TaskCenterPage() {
  const { t } = useTranslation()
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
      { id: 'all', label: t('task.sidebar.stats.total'), value: (summary?.total_tasks ?? 0).toLocaleString(), icon: metricIconForTab('all'), tone: 'blue' as const },
      { id: 'waiting_approval', label: t('task.tabs.waiting_approval'), value: String(summary?.waiting_approval ?? 0), icon: metricIconForTab('waiting_approval'), tone: 'amber' as const },
      { id: 'failed', label: t('task.tabs.failed'), value: String(summary?.failed ?? 0), icon: metricIconForTab('failed'), tone: 'red' as const },
      { id: 'waiting_input', label: t('task.tabs.waiting_input'), value: String(summary?.waiting_input ?? 0), icon: metricIconForTab('waiting_input'), tone: 'cyan' as const },
      { id: 'running', label: t('task.tabs.running'), value: String(summary?.running ?? 0), icon: metricIconForTab('running'), tone: 'green' as const },
    ].map((item) => ({ ...item, trend: sparkline }))
  }, [workbench?.summary, t])

  const tabs = useMemo(
    () =>
      taskTabs(t).map((tab) => ({
        id: tab.id,
        label: tab.label,
        count: workbench?.tabs?.[tab.id] ?? 0,
      })),
    [workbench?.tabs, t],
  )

  const rows = tableData?.items || []
  const priorityCards = priorityTabs.map((tab) => {
    const label = taskTabLabel(t, tab)
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
      { id: 'name', header: t('task.columns.name'), render: (row) => <TaskNameCell row={row} /> },
      { id: 'scene', header: t('task.columns.scene'), render: (row) => <SceneBadge row={row} /> },
      { id: 'status', header: t('task.columns.status'), render: (row) => <StatusBadge status={row.status} /> },
      { id: 'type', header: t('task.columns.type'), render: (row) => <span className="font-mono text-xs">{row.task_type}</span> },
      { id: 'owner', header: t('task.columns.owner'), render: (row) => row.owner || '-' },
      { id: 'updated', header: t('task.columns.updated'), render: (row) => formatTaskTime(row.updated_at) },
      {
        id: 'actions',
        header: t('task.columns.actions'),
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
    [navigate, t],
  )

  return (
    <BoxShell>
      <div className="flex flex-col gap-4 2xl:flex-row 2xl:items-start 2xl:justify-between">
        <BoxPageHeader title={t('task.center.title')} description={t('task.center.description')} />
        <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center 2xl:justify-end">
          <div className="relative min-w-[260px] sm:w-[320px]">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('task.center.searchPlaceholder')} className="h-10 pl-9" />
          </div>
          <Select value={status} onValueChange={(value) => value != null && setStatus(value)}>
            <SelectTrigger className="h-10 w-[150px] bg-panel">
              <SelectValue placeholder={t('task.center.statusPlaceholder')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">{t('task.center.statusOptions.all')}</SelectItem>
              <SelectItem value="running">{t('task.center.statusOptions.running')}</SelectItem>
              <SelectItem value="waiting_approval">{t('task.center.statusOptions.waiting_approval')}</SelectItem>
              <SelectItem value="waiting_input">{t('task.center.statusOptions.waiting_input')}</SelectItem>
              <SelectItem value="failed">{t('task.center.statusOptions.failed')}</SelectItem>
              <SelectItem value="succeeded">{t('task.center.statusOptions.succeeded')}</SelectItem>
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
          title={t('task.center.errorTitle')}
          description={tableError instanceof Error ? tableError.message : workbenchError instanceof Error ? workbenchError.message : undefined}
          action={<Button variant="outline" size="sm" onClick={() => { void refetchWorkbench(); void refetchTable() }}>{t('task.center.retry')}</Button>}
        />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('task.center.deltaLabel')} />

      <section>
        <div className="mb-3 flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">{t('task.center.priorityTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('task.center.priorityDescription')}</p>
          </div>
          <Button variant="ghost" size="sm" onClick={() => navigate('/tasks/processing')}>
            {t('task.center.viewAll')}
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
                  <Button variant="outline" size="sm" className="h-8" onClick={() => navigate(`/tasks/processing?tab=${card.tab}`)}>{t('task.center.handle')}</Button>
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
                  {card.items.length === 0 ? <div className="rounded-md border border-dashed p-4 text-center text-sm text-muted-foreground">{t('task.center.emptyTasks')}</div> : null}
                </div>
              </div>
            )
          })}
        </div>
      </section>

      <section className="space-y-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <h2 className="text-base font-semibold text-foreground">{t('task.center.ledgerTitle')}</h2>
            <p className="text-sm text-muted-foreground">{t('task.center.ledgerDescription')}</p>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" className="h-10">
              <SlidersHorizontal className="h-4 w-4" />
              {t('task.center.filter')}
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

        <BoxDataTable columns={columns} rows={rows} emptyMessage={isTableLoading ? t('task.center.loading') : t('task.center.emptyTasks')} />
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
          labels={{
            totalSuffix: t('task.pagination.totalSuffix'),
            pageSizeSuffix: t('task.pagination.pageSizeSuffix'),
            goTo: t('task.pagination.goTo'),
            page: t('task.pagination.page'),
          }}
        />
      </section>
    </BoxShell>
  )
}

export default TaskCenterPage
