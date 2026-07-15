import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  Braces,
  Clock3,
  Database,
  FileText,
  MessageCircle,
  MoreHorizontal,
  Network,
  Plus,
  ShieldCheck,
  Store,
  TrendingUp,
  Workflow,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  MetricStrip,
  type MetricStripItem,
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
import {
  createAgent,
  getAgentWorkbench,
  getAgentWorkbenchItems,
  type AgentWorkbenchCapability,
  type AgentWorkbenchRow,
} from '@/services/agent-service'

type AgentStatus = AgentWorkbenchRow['status']
type AbilityTone = 'blue' | 'emerald' | 'orange' | 'red' | 'violet'
type AgentAction = 'chat' | 'disabled'

interface AgentAbility {
  id: string
  label: string
  icon: typeof FileText
  tone: AbilityTone
}

type MetricDefinition = Omit<MetricStripItem, 'label' | 'value'> & {
  labelKey: TranslationKey
  value: string
}

const statusConfig = {
  running: {
    labelKey: 'agent.dashboard.status.running',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  configuring: {
    labelKey: 'agent.dashboard.status.configuring',
    className: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200',
  },
  abnormal: {
    labelKey: 'agent.dashboard.status.abnormal',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  unconfigured: {
    labelKey: 'agent.dashboard.status.unconfigured',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<AgentStatus, { labelKey: TranslationKey; className: string }>

const abilityToneClassNameMap = {
  blue: 'border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  orange: 'border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200',
  red: 'border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  violet: 'border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-400/10 dark:text-violet-200',
} satisfies Record<AbilityTone, string>

const capabilityIconMap: Record<string, typeof FileText> = {
  model: Braces,
  knowledge: Database,
  tool: Network,
  workflow: Workflow,
  skill: FileText,
  plugin: Store,
}

const capabilityToneMap: Record<string, AbilityTone> = {
  model: 'orange',
  knowledge: 'emerald',
  tool: 'blue',
  workflow: 'violet',
  skill: 'blue',
  plugin: 'red',
}

function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '-'
}

function formatLatency(value?: number | null) {
  return typeof value === 'number' ? `${value.toLocaleString()}ms` : '-'
}

function formatRate(value?: number | null) {
  return typeof value === 'number' ? `${value.toFixed(value % 1 === 0 ? 0 : 1)}%` : '-'
}

function formatTimestamp(value?: string | null) {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

function capabilityToAbility(capability: AgentWorkbenchCapability): AgentAbility {
  const type = capability.type || 'tool'
  return {
    id: `${type}:${capability.target_key || capability.target_id || capability.label}`,
    label: capability.label,
    icon: capabilityIconMap[type] || Network,
    tone: capabilityToneMap[type] || 'blue',
  }
}

function buildMetricItems(workbench?: Awaited<ReturnType<typeof getAgentWorkbench>>): MetricDefinition[] {
  const summary = workbench?.summary
  return [
    {
      id: 'running',
      labelKey: 'agent.dashboard.metrics.running',
      value: formatNumber(summary?.running_agents),
      trend: [5, 8, 8, 10, 6, 7, 5, 7, 6, 5],
      icon: Bot,
      tone: 'green',
    },
    {
      id: 'today',
      labelKey: 'agent.dashboard.metrics.todayCalls',
      value: formatNumber(summary?.today_calls),
      trend: [5, 6, 8, 7, 9, 13, 10, 9, 9, 8],
      icon: TrendingUp,
      tone: 'blue',
    },
    {
      id: 'latency',
      labelKey: 'agent.dashboard.metrics.avgLatency',
      value: formatLatency(summary?.avg_latency_ms),
      trend: [7, 7, 8, 7, 10, 9, 13, 10, 8, 8],
      icon: Clock3,
      tone: 'amber',
    },
    {
      id: 'success',
      labelKey: 'agent.dashboard.metrics.successRate',
      value: formatRate(summary?.success_rate),
      trend: [8, 11, 11, 10, 12, 10, 10, 11, 9, 12],
      icon: ShieldCheck,
      tone: 'green',
    },
    {
      id: 'exceptions',
      labelKey: 'agent.dashboard.metrics.pendingExceptions',
      value: formatNumber(summary?.pending_exceptions),
      trend: [3, 5, 4, 4, 3, 3, 3, 2, 3, 3],
      icon: AlertTriangle,
      tone: 'red',
    },
  ]
}

function AgentNameCell({ row }: { row: AgentWorkbenchRow }) {
  return (
    <div className="flex min-w-[245px] items-center gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-blue-600 text-white">
        <Bot className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.name}</div>
        <div className="mt-0.5 max-w-[300px] truncate text-xs text-muted-foreground">{row.description || '-'}</div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: AgentStatus }) {
  const { t } = useTranslation()
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{t(config.labelKey)}</Badge>
}

function AbilityIcons({ capabilities }: { capabilities: AgentWorkbenchCapability[] }) {
  const abilities = capabilities.map(capabilityToAbility)
  if (!abilities.length) return <span className="text-muted-foreground">-</span>

  return (
    <div className="flex min-w-[110px] items-center gap-2">
      {abilities.slice(0, 4).map((ability) => {
        const Icon = ability.icon
        return (
          <span
            key={ability.id}
            title={ability.label}
            className={cn('flex h-7 w-7 items-center justify-center rounded-md border', abilityToneClassNameMap[ability.tone])}
          >
            <Icon className="h-3.5 w-3.5" />
          </span>
        )
      })}
    </div>
  )
}

function RecentException({ value }: { value: number }) {
  const { t } = useTranslation()
  if (!value) return <span className="text-muted-foreground">-</span>

  const variantClassName =
    value >= 3
      ? 'border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200'
      : 'border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200'

  return (
    <Badge className={cn('rounded-md border px-2 py-1', variantClassName)}>
      {t('agent.dashboard.table.exceptionCount', { count: String(value) })}
    </Badge>
  )
}

function OperationButtons({ row }: { row: AgentWorkbenchRow }) {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const action: AgentAction = row.action_enabled ? 'chat' : 'disabled'

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon-xs"
        disabled={action === 'disabled'}
        aria-label={t('agent.dashboard.table.chatAction')}
        title={t('agent.dashboard.table.chatAction')}
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/chat/${row.id}`)}
      >
        <MessageCircle className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        aria-label={t('agent.dashboard.table.reportAction')}
        title={t('agent.dashboard.table.reportAction')}
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/observe/runs?subject_id=${row.id}`)}
      >
        <BarChart3 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        aria-label={t('agent.dashboard.table.moreAction')}
        title={t('agent.dashboard.table.moreAction')}
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/agents/${row.id}`)}
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function AgentBoxPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftDescription, setDraftDescription] = useState('')
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
    queryKey: ['agents', 'workbench'],
    queryFn: () => getAgentWorkbench({ page_size: 1 }),
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
    queryKey: ['agents', 'workbench', 'items', activeTab, tableKeyword, pageToken],
    queryFn: () => getAgentWorkbenchItems({
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

  const createMutation = useMutation({
    mutationKey: ['agents', 'create'],
    mutationFn: () =>
      createAgent({
        name: draftName.trim(),
        description: draftDescription.trim() || undefined,
        visibility: 'private',
      }),
    onSuccess: (agent) => {
      setDraftName('')
      setDraftDescription('')
      setDialogOpen(false)
      void refetchWorkbench()
      void refetchTable()
      toast.success(t('agent.workspace.created', { name: agent.name }))
      navigate(`/agents/${agent.id}`)
    },
    onError: (mutationError: any) => {
      toast.error(mutationError?.message || t('agent.workspace.createFailed'))
    },
  })

  const toolbarTabs = useMemo<BoxToolbarTab[]>(() => {
    const counts = workbench?.tabs
    return [
      { id: 'all', label: t('agent.dashboard.tabs.all'), count: counts?.all ?? 0 },
      { id: 'high', label: t('agent.dashboard.tabs.highCalls'), count: counts?.high_calls ?? 0 },
      { id: 'low-success', label: t('agent.dashboard.tabs.lowSuccess'), count: counts?.low_success ?? 0 },
      { id: 'long-latency', label: t('agent.dashboard.tabs.longLatency'), count: counts?.long_latency ?? 0 },
      { id: 'unconfigured', label: t('agent.dashboard.tabs.unconfigured'), count: counts?.unconfigured ?? 0 },
    ]
  }, [t, workbench?.tabs])

  const rows = tableData?.items || []
  const activeTabTotal = toolbarTabs.find((tab) => tab.id === activeTab)?.count
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

  const columns = useMemo<BoxDataTableColumn<AgentWorkbenchRow>[]>(() => [
    {
      id: 'name',
      header: t('agent.dashboard.table.name'),
      render: (row) => <AgentNameCell row={row} />,
    },
    {
      id: 'status',
      header: t('agent.dashboard.table.status'),
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      id: 'abilities',
      header: t('agent.dashboard.table.abilities'),
      render: (row) => <AbilityIcons capabilities={row.capabilities} />,
    },
    {
      id: 'todayCalls',
      header: t('agent.dashboard.table.todayCalls'),
      cellClassName: 'font-semibold text-foreground',
      render: (row) => formatNumber(row.today_calls),
    },
    {
      id: 'avgLatency',
      header: t('agent.dashboard.table.avgLatency'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(
          row.status === 'abnormal'
            ? 'text-red-600 dark:text-red-300'
            : row.avg_latency_ms && row.avg_latency_ms >= 300
              ? 'text-orange-600 dark:text-orange-300'
              : row.avg_latency_ms
                ? 'text-emerald-600 dark:text-emerald-300'
                : 'text-muted-foreground',
        )}
        >
          {formatLatency(row.avg_latency_ms)}
        </span>
      ),
    },
    {
      id: 'successRate',
      header: t('agent.dashboard.table.successRate'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(
          row.status === 'abnormal'
            ? 'text-red-600 dark:text-red-300'
            : row.success_rate !== null && row.success_rate !== undefined && row.success_rate < 98
              ? 'text-orange-600 dark:text-orange-300'
              : row.success_rate !== null && row.success_rate !== undefined
                ? 'text-emerald-600 dark:text-emerald-300'
                : 'text-muted-foreground',
        )}
        >
          {formatRate(row.success_rate)}
        </span>
      ),
    },
    {
      id: 'recentException',
      header: t('agent.dashboard.table.recentException'),
      render: (row) => row.status === 'unconfigured'
        ? <Badge className="rounded-md border border-border bg-muted px-2 py-1 text-muted-foreground">{t('agent.dashboard.status.unconfigured')}</Badge>
        : <RecentException value={row.recent_exception_count} />,
    },
    {
      id: 'owner',
      header: t('agent.dashboard.table.owner'),
      render: (row) => row.owner || '-',
    },
    {
      id: 'lastRun',
      header: t('agent.dashboard.table.lastRun'),
      render: (row) => (
        <span className={row.last_run_at ? 'text-foreground/80' : 'text-muted-foreground'}>
          {formatTimestamp(row.last_run_at)}
        </span>
      ),
    },
    {
      id: 'actions',
      header: t('agent.dashboard.table.actions'),
      render: (row) => <OperationButtons row={row} />,
    },
  ], [t])

  const metricItems = useMemo(
    () => buildMetricItems(workbench).map(({ labelKey, ...metric }) => ({ ...metric, label: t(labelKey) })),
    [t, workbench],
  )

  const canCreate = draftName.trim().length > 0 && !createMutation.isPending
  const emptyMessage = isTableLoading ? t('agent.workspace.loadingDescription') : t('agent.dashboard.table.empty')

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('agent.dashboard.title')}
        description={t('agent.dashboard.description')}
        action={(
          <Button
            type="button"
            className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700"
            onClick={() => setDialogOpen(true)}
          >
            <Plus className="h-4 w-4" />
            {t('agent.dashboard.create.action')}
          </Button>
        )}
      />

      {isWorkbenchError || isTableError ? (
        <BoxAlert
          severity="warning"
          title={t('agent.workspace.errorTitle')}
          description={tableError instanceof Error ? tableError.message : workbenchError instanceof Error ? workbenchError.message : t('agent.workspace.errorDescription')}
          action={<Button variant="outline" size="sm" onClick={() => { void refetchWorkbench(); void refetchTable() }}>{t('agent.workspace.retry')}</Button>}
        />
      ) : null}

      <MetricStrip items={metricItems} deltaLabel={t('agent.dashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={toolbarTabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('agent.dashboard.toolbar.searchPlaceholder')}
        filterLabel={t('agent.dashboard.toolbar.filter')}
        timeLabel={t('agent.dashboard.toolbar.time')}
        refreshLabel={t('agent.dashboard.toolbar.refresh')}
        onRefresh={() => { void refetchWorkbench(); void refetchTable() }}
      />

      <BoxDataTable
        columns={columns}
        rows={rows}
        emptyMessage={emptyMessage}
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
          totalSuffix: t('agent.dashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('agent.dashboard.pagination.pageSizeSuffix'),
          goTo: t('agent.dashboard.pagination.goTo'),
          page: t('agent.dashboard.pagination.page'),
        }}
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('agent.dashboard.create.title')}</DialogTitle>
            <DialogDescription>{t('agent.dashboard.create.description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              placeholder={t('agent.workspace.namePlaceholder')}
              autoFocus
            />
            <Input
              value={draftDescription}
              onChange={(event) => setDraftDescription(event.target.value)}
              placeholder={t('agent.workspace.descriptionPlaceholder')}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              {t('agent.dashboard.create.cancel')}
            </Button>
            <Button
              type="button"
              disabled={!canCreate}
              onClick={() => createMutation.mutate(undefined)}
            >
              <Plus className="h-4 w-4" />
              {createMutation.isPending ? t('agent.dashboard.create.submitting') : t('agent.dashboard.create.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </BoxShell>
  )
}

export default AgentBoxPage
