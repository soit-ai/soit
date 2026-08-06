import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  FileText,
  MoreHorizontal,
  Play,
  Plus,
  RotateCw,
  ShieldCheck,
  TrendingUp,
  Workflow,
  Loader2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  MetricStrip,
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
} from '@/components/box'
import { useNavigate } from '@/hooks/use-navigate'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import { createWorkflow, getWorkflowWorkbench, getWorkflowWorkbenchItems, type WorkflowWorkbenchRow } from '@/services/workflow-service'
import { toast } from 'sonner'
import { requestErrorMessage } from '@/utils/request'

type WorkflowStatus = WorkflowWorkbenchRow['status']

type MetricDefinition = Omit<React.ComponentProps<typeof MetricStrip>['items'][number], 'label' | 'value'> & {
  labelKey: TranslationKey
  value: string
}

const statusConfig = {
  running: {
    labelKey: 'workflow.workspaceDashboard.status.running',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  publishing: {
    labelKey: 'workflow.workspaceDashboard.status.publishing',
    className: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  },
  abnormal: {
    labelKey: 'workflow.workspaceDashboard.status.incident',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  draft: {
    labelKey: 'workflow.workspaceDashboard.status.draft',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<WorkflowStatus, { labelKey: TranslationKey; className: string }>

function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '-'
}

function formatLatency(value?: number | null) {
  if (typeof value !== 'number') return '-'
  return value >= 1000 ? `${Number((value / 1000).toFixed(1))}s` : `${value.toLocaleString()}ms`
}

function formatRate(value?: number | null) {
  return typeof value === 'number' ? `${value.toFixed(value % 1 === 0 ? 0 : 1)}%` : '-'
}

function formatTimestamp(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function buildMetricItems(workbench?: Awaited<ReturnType<typeof getWorkflowWorkbench>>): MetricDefinition[] {
  const summary = workbench?.summary
  return [
    {
      id: 'running',
      labelKey: 'workflow.workspaceDashboard.metrics.running',
      value: formatNumber(summary?.running_workflows),
      trend: [4, 6, 5, 8, 6, 10, 5, 6, 4, 7, 5],
      icon: Play,
      tone: 'green',
    },
    {
      id: 'today',
      labelKey: 'workflow.workspaceDashboard.metrics.today',
      value: formatNumber(summary?.today_runs),
      trend: [8, 7, 9, 8, 12, 10, 14, 9, 10, 8],
      icon: TrendingUp,
      tone: 'blue',
    },
    {
      id: 'latency',
      labelKey: 'workflow.workspaceDashboard.metrics.latency',
      value: formatLatency(summary?.avg_latency_ms),
      trend: [7, 8, 7, 10, 8, 9, 15, 9, 11, 10],
      icon: Clock3,
      tone: 'amber',
    },
    {
      id: 'success',
      labelKey: 'workflow.workspaceDashboard.metrics.success',
      value: formatRate(summary?.success_rate),
      trend: [9, 8, 10, 9, 12, 13, 10, 11, 9, 13],
      icon: ShieldCheck,
      tone: 'green',
    },
    {
      id: 'exceptions',
      labelKey: 'workflow.workspaceDashboard.metrics.exceptions',
      value: formatNumber(summary?.recent_exceptions),
      trend: [3, 5, 4, 8, 5, 4, 6, 3, 4, 3],
      icon: AlertTriangle,
      tone: 'red',
    },
  ]
}

function WorkflowNameCell({ row }: { row: WorkflowWorkbenchRow }) {
  const Icon = row.status === 'draft' ? FileText : row.status === 'abnormal' ? AlertTriangle : Workflow
  const iconClassName =
    row.status === 'abnormal'
      ? 'bg-red-500'
      : row.status === 'draft'
        ? 'bg-slate-500'
        : row.status === 'publishing'
          ? 'bg-blue-500'
          : 'bg-emerald-500'

  const navigate = useNavigate()
  return (
    <button
      type="button"
      className="flex min-w-[230px] cursor-pointer items-center gap-3 text-left"
      onClick={() => navigate(`/workflow/${row.id}/build`)}
    >
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white', iconClassName)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground hover:underline">{row.name}</div>
        <div className="mt-0.5 max-w-[280px] truncate text-xs text-muted-foreground">{row.summary || row.description || '-'}</div>
      </div>
    </button>
  )
}

function StatusBadge({ status, label }: { status: WorkflowStatus; label: string }) {
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{label}</Badge>
}

function AgentAvatars({ agents, total }: { agents: string[]; total: number }) {
  if (!agents.length && total === 0) return <span className="text-muted-foreground">-</span>

  return (
    <AvatarGroup>
      {agents.slice(0, 3).map((agent, index) => (
        <Avatar key={`${agent}-${index}`} size="sm" className="border border-background bg-muted">
          <AvatarFallback className={cn('text-[10px] font-semibold text-white', index % 2 === 0 ? 'bg-slate-700 dark:bg-slate-500' : 'bg-blue-600 dark:bg-blue-500')}>
            {agent}
          </AvatarFallback>
        </Avatar>
      ))}
      {total > agents.length ? <AvatarGroupCount className="size-6 text-xs">+{total - agents.length}</AvatarGroupCount> : null}
    </AvatarGroup>
  )
}

function OperationButtons({ row }: { row: WorkflowWorkbenchRow }) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon-xs"
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/observe/runs?subject_kind=workflow&subject_id=${row.id}&mode=workflow`)}
      >
        <BarChart3 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        disabled={!row.action_enabled}
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/workflow/${row.id}/build`)}
      >
        {row.action_enabled ? <Play className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/workflow/${row.id}/publish`)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function WorkflowBoxPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])
  const tableKeyword = search.trim()
  const pageToken = pageTokens[currentPage - 1]
  const createMutation = useMutation({
    mutationKey: ['workflows', 'create'],
    mutationFn: () => createWorkflow(
      {
        name: 'Untitled workflow',
        description: '',
        visibility: 'private',
      },
      { suppressErrorToast: true },
    ),
    onSuccess: (workflow) => {
      navigate(`/workflow/${workflow.id}/build`)
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to create workflow'))
    },
  })

  const {
    data: workbench,
    isError: isWorkbenchError,
    error: workbenchError,
    refetch: refetchWorkbench,
  } = useQuery({
    queryKey: ['workflows', 'workbench'],
    queryFn: () => getWorkflowWorkbench({ page_size: 1 }),
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
    queryKey: ['workflows', 'workbench', 'items', activeTab, tableKeyword, pageToken],
    queryFn: () => getWorkflowWorkbenchItems({
      page_size: 50,
      page_token: pageToken,
      tab: activeTab,
      keyword: tableKeyword || undefined,
    }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  useEffect(() => {
    setCurrentPage(1)
    setPageTokens([undefined])
  }, [activeTab, tableKeyword])

  const metrics = useMemo(() => buildMetricItems(workbench).map((item) => ({
    ...item,
    label: t(item.labelKey),
  })), [t, workbench])

  const tabs = useMemo<BoxToolbarTab[]>(() => {
    const counts = workbench?.tabs
    return [
      { id: 'all', label: t('workflow.workspaceDashboard.tabs.all'), count: counts?.all ?? 0 },
      { id: 'high', label: t('workflow.workspaceDashboard.tabs.highVolume'), count: counts?.high_volume ?? 0 },
      { id: 'publishing', label: t('workflow.workspaceDashboard.tabs.publishing'), count: counts?.publishing ?? 0 },
      { id: 'abnormal', label: t('workflow.workspaceDashboard.tabs.incidents'), count: counts?.abnormal ?? 0 },
      { id: 'draft', label: t('workflow.workspaceDashboard.tabs.drafts'), count: counts?.draft ?? 0 },
    ]
  }, [t, workbench?.tabs])

  const rows = tableData?.items || []
  const activeTabTotal = tabs.find((tab) => tab.id === activeTab)?.count
  const totalRows = tableKeyword ? rows.length : typeof activeTabTotal === 'number' ? activeTabTotal : rows.length
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
    if (page === currentPage) return
    if (page === currentPage + 1) {
      goToNextPage()
      return
    }
    if (page === currentPage - 1) {
      goToPreviousPage()
    }
  }

  const columns = useMemo<BoxDataTableColumn<WorkflowWorkbenchRow>[]>(() => [
    {
      id: 'name',
      header: t('workflow.workspaceDashboard.columns.workflow'),
      render: (row) => <WorkflowNameCell row={row} />,
    },
    {
      id: 'status',
      header: t('workflow.workspaceDashboard.columns.status'),
      render: (row) => <StatusBadge status={row.status} label={t(statusConfig[row.status].labelKey)} />,
    },
    {
      id: 'agents',
      header: t('workflow.workspaceDashboard.columns.linkedAgent'),
      render: (row) => <AgentAvatars agents={row.linked_agents} total={row.linked_agent_count} />,
    },
    {
      id: 'todayRuns',
      header: t('workflow.workspaceDashboard.columns.runsToday'),
      cellClassName: 'font-semibold text-foreground',
      render: (row) => formatNumber(row.today_runs),
    },
    {
      id: 'avgLatency',
      header: t('workflow.workspaceDashboard.columns.avgLatency'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(row.status === 'abnormal' ? 'text-red-600 dark:text-red-300' : row.avg_latency_ms && row.avg_latency_ms >= 2000 ? 'text-orange-600 dark:text-orange-300' : row.avg_latency_ms ? 'text-emerald-600 dark:text-emerald-300' : 'text-muted-foreground')}>
          {formatLatency(row.avg_latency_ms)}
        </span>
      ),
    },
    {
      id: 'successRate',
      header: t('workflow.workspaceDashboard.columns.successRate'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(row.status === 'abnormal' ? 'text-orange-600 dark:text-orange-300' : row.success_rate !== null && row.success_rate !== undefined ? 'text-emerald-600 dark:text-emerald-300' : 'text-muted-foreground')}>
          {formatRate(row.success_rate)}
        </span>
      ),
    },
    {
      id: 'recentException',
      header: t('workflow.workspaceDashboard.columns.recentIncident'),
      render: (row) => row.recent_exception_count ? (
        <Badge className="rounded-md border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200">
          {row.recent_exception_count} incidents
        </Badge>
      ) : <span className="text-muted-foreground">-</span>,
    },
    {
      id: 'owner',
      header: t('workflow.workspaceDashboard.columns.owner'),
      render: (row) => row.owner || '-',
    },
    {
      id: 'lastRun',
      header: t('workflow.workspaceDashboard.columns.lastRun'),
      render: (row) => <span className={row.last_run_at ? 'text-foreground/80' : 'text-muted-foreground'}>{formatTimestamp(row.last_run_at)}</span>,
    },
    {
      id: 'actions',
      header: t('workflow.workspaceDashboard.columns.actions'),
      render: (row) => <OperationButtons row={row} />,
    },
  ], [t])

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('workflow.workspaceDashboard.header.title')}
        description={t('workflow.workspaceDashboard.header.description')}
        action={(
          <Button
            className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700"
            disabled={createMutation.isPending}
            onClick={() => createMutation.mutate(undefined)}
          >
            {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {t('workflow.workspaceDashboard.header.create')}
          </Button>
        )}
      />

      {isWorkbenchError || isTableError ? (
        <BoxAlert
          severity="warning"
          title={t('workflow.workspaceDashboard.table.empty')}
          description={tableError instanceof Error ? tableError.message : workbenchError instanceof Error ? workbenchError.message : undefined}
          action={<Button variant="outline" size="sm" onClick={() => { void refetchWorkbench(); void refetchTable() }}>{t('workflow.workspaceDashboard.toolbar.refresh')}</Button>}
        />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('workflow.workspaceDashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('workflow.workspaceDashboard.toolbar.searchPlaceholder')}
        filterLabel={t('workflow.workspaceDashboard.toolbar.filter')}
        timeLabel={t('workflow.workspaceDashboard.toolbar.allTime')}
        refreshLabel={t('workflow.workspaceDashboard.toolbar.refresh')}
        onRefresh={() => { void refetchWorkbench(); void refetchTable() }}
      />

      <BoxDataTable
        columns={columns}
        rows={rows}
        emptyMessage={isTableLoading ? 'Loading workflows...' : t('workflow.workspaceDashboard.table.empty')}
      />

      <BoxPagination
        total={totalRows}
        pageSize={tableData?.page_size || 50}
        currentPage={currentPage}
        pages={pages}
        hasPrevious={currentPage > 1}
        hasNext={Boolean(tableData?.next_page_token)}
        onPrevious={goToPreviousPage}
        onNext={goToNextPage}
        onPageChange={goToPage}
        labels={{
          totalSuffix: t('workflow.workspaceDashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('workflow.workspaceDashboard.pagination.pageSizeSuffix'),
          goTo: t('workflow.workspaceDashboard.pagination.goTo'),
          page: t('workflow.workspaceDashboard.pagination.page'),
        }}
      />
    </BoxShell>
  )
}

export default WorkflowBoxPage
