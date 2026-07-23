import {
  AlertTriangle,
  BarChart3,
  Check,
  Clock3,
  ExternalLink,
  FileText,
  ListChecks,
  MoreHorizontal,
  Plus,
  SquareStack,
  Loader2,
} from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
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
import {
  createKnowledgeBase,
  getKnowledgeWorkbench,
  getKnowledgeWorkbenchItems,
  type KnowledgeCreateRequest,
  type KnowledgeWorkbenchRow,
} from '@/services/knowledge-service'
import { toast } from 'sonner'
import { requestErrorMessage } from '@/utils/request'

type KnowledgeStatus = KnowledgeWorkbenchRow['status']

type MetricDefinition = Omit<React.ComponentProps<typeof MetricStrip>['items'][number], 'label' | 'value'> & {
  labelKey: TranslationKey
  value: string
}

const statusConfig = {
  ready: {
    labelKey: 'knowledge.workspaceDashboard.status.ready',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  indexing: {
    labelKey: 'knowledge.workspaceDashboard.status.indexing',
    className: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200',
  },
  error: {
    labelKey: 'knowledge.workspaceDashboard.status.error',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  unconfigured: {
    labelKey: 'knowledge.workspaceDashboard.status.unconfigured',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<KnowledgeStatus, { labelKey: TranslationKey; className: string }>

function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '-'
}

function formatCompactNumber(value?: number | null) {
  if (typeof value !== 'number') return '-'
  if (value >= 1000000) return `${Number((value / 1000000).toFixed(1))}m`
  if (value >= 1000) return `${Number((value / 1000).toFixed(1))}k`
  return value.toLocaleString()
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

function getMarkerClassName(row: KnowledgeWorkbenchRow) {
  if (row.status === 'error') return 'bg-red-500'
  if (row.status === 'indexing') return 'bg-amber-500'
  if (row.status === 'unconfigured') return 'bg-slate-500'
  return row.knowledge_type === 'qa' ? 'bg-emerald-500' : row.knowledge_type === 'code' ? 'bg-violet-500' : 'bg-blue-600'
}

function buildMetricItems(workbench?: Awaited<ReturnType<typeof getKnowledgeWorkbench>>): MetricDefinition[] {
  const summary = workbench?.summary
  return [
    {
      id: 'total',
      labelKey: 'knowledge.workspaceDashboard.metrics.total',
      value: formatNumber(summary?.total_knowledge_bases),
      trend: [8, 9, 10, 9, 11, 12, 12, 13, 14, 13],
      icon: SquareStack,
      tone: 'blue',
    },
    {
      id: 'ready',
      labelKey: 'knowledge.workspaceDashboard.metrics.ready',
      value: formatNumber(summary?.ready_knowledge_bases),
      trend: [7, 8, 8, 9, 10, 9, 11, 10, 12, 12],
      icon: Check,
      tone: 'green',
    },
    {
      id: 'ingested',
      labelKey: 'knowledge.workspaceDashboard.metrics.ingested',
      value: formatCompactNumber(summary?.total_documents),
      trend: [5, 7, 8, 7, 10, 12, 9, 14, 13, 16],
      icon: FileText,
      tone: 'cyan',
    },
    {
      id: 'latency',
      labelKey: 'knowledge.workspaceDashboard.metrics.latency',
      value: formatLatency(summary?.avg_latency_ms),
      trend: [14, 12, 13, 10, 9, 11, 8, 7, 8, 6],
      icon: Clock3,
      tone: 'amber',
    },
    {
      id: 'exceptions',
      labelKey: 'knowledge.workspaceDashboard.metrics.exceptions',
      value: formatNumber(summary?.recent_exceptions),
      trend: [3, 4, 3, 6, 4, 5, 7, 5, 4, 4],
      icon: AlertTriangle,
      tone: 'red',
    },
  ]
}

function KnowledgeNameCell({ row }: { row: KnowledgeWorkbenchRow }) {
  return (
    <div className="flex min-w-[270px] items-center gap-3">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-sm font-semibold text-white', getMarkerClassName(row))}>
        {row.name.trim().slice(0, 1).toUpperCase() || 'K'}
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.name}</div>
        <div className="mt-0.5 max-w-[310px] truncate text-xs text-muted-foreground">{row.description || '-'}</div>
      </div>
    </div>
  )
}

function StatusBadge({ status, label }: { status: KnowledgeStatus; label: string }) {
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{label}</Badge>
}

function HitRate({ row }: { row: KnowledgeWorkbenchRow }) {
  if (typeof row.hit_rate !== 'number') return <span className="text-muted-foreground">-</span>
  const value = row.hit_rate
  const className = value < 90
    ? 'text-red-600 dark:text-red-300'
    : value < 95
      ? 'text-orange-600 dark:text-orange-300'
      : 'text-emerald-600 dark:text-emerald-300'

  return <span className={cn('font-semibold', className)}>{formatRate(row.hit_rate)}</span>
}

function OperationButtons({ row }: { row: KnowledgeWorkbenchRow }) {
  const navigate = useNavigate()

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon-xs"
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/knowledge/${row.id}/usages`)}
      >
        <BarChart3 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        disabled={!row.action_enabled}
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/knowledge/${row.id}/document`)}
      >
        <ListChecks className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        className="border-border bg-panel text-foreground shadow-none"
        onClick={() => navigate(`/knowledge/${row.id}`)}
      >
        <ExternalLink className="h-3.5 w-3.5" />
      </Button>
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function KnowledgeBoxPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])
  const [createOpen, setCreateOpen] = useState(false)
  const [createForm, setCreateForm] = useState<KnowledgeCreateRequest>({
    name: '',
    description: '',
    knowledge_type: 'document',
    visibility: 'workspace',
  })
  const tableKeyword = search.trim()
  const pageToken = pageTokens[currentPage - 1]
  const createMutation = useMutation({
    mutationKey: ['knowledge', 'create'],
    mutationFn: (data: KnowledgeCreateRequest) => createKnowledgeBase(data, { suppressErrorToast: true }),
    onSuccess: (knowledge) => {
      setCreateOpen(false)
      navigate(`/knowledge/${knowledge.id}`)
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to create knowledge base'))
    },
  })

  const submitCreate = () => {
    const name = createForm.name.trim()
    if (!name) {
      toast.error('Knowledge base name is required')
      return
    }
    createMutation.mutate({
      ...createForm,
      name,
      description: createForm.description?.trim() || undefined,
    })
  }

  const {
    data: workbench,
    isError: isWorkbenchError,
    error: workbenchError,
    refetch: refetchWorkbench,
  } = useQuery({
    queryKey: ['knowledge', 'workbench'],
    queryFn: () => getKnowledgeWorkbench({ page_size: 1 }),
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
    queryKey: ['knowledge', 'workbench', 'items', activeTab, tableKeyword, pageToken],
    queryFn: () => getKnowledgeWorkbenchItems({
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
      { id: 'all', label: t('knowledge.workspaceDashboard.tabs.all'), count: counts?.all ?? 0 },
      { id: 'high', label: t('knowledge.workspaceDashboard.tabs.highVolume'), count: counts?.high_volume ?? 0 },
      { id: 'low-hit', label: t('knowledge.workspaceDashboard.tabs.lowHit'), count: counts?.low_hit ?? 0 },
      { id: 'slow', label: t('knowledge.workspaceDashboard.tabs.slow'), count: counts?.slow ?? 0 },
      { id: 'unconfigured', label: t('knowledge.workspaceDashboard.tabs.unconfigured'), count: counts?.unconfigured ?? 0 },
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

  const columns = useMemo<BoxDataTableColumn<KnowledgeWorkbenchRow>[]>(() => [
    {
      id: 'name',
      header: t('knowledge.workspaceDashboard.columns.knowledge'),
      render: (row) => <KnowledgeNameCell row={row} />,
    },
    {
      id: 'status',
      header: t('knowledge.workspaceDashboard.columns.status'),
      render: (row) => <StatusBadge status={row.status} label={t(statusConfig[row.status].labelKey)} />,
    },
    {
      id: 'source',
      header: t('knowledge.workspaceDashboard.columns.source'),
      render: (row) => row.content_source,
    },
    {
      id: 'documents',
      header: t('knowledge.workspaceDashboard.columns.documentsChunks'),
      cellClassName: 'font-medium text-foreground',
      render: (row) => `${formatNumber(row.document_count)} / ${formatCompactNumber(row.chunk_count)}`,
    },
    {
      id: 'todayCalls',
      header: t('knowledge.workspaceDashboard.columns.callsToday'),
      cellClassName: 'font-medium text-foreground',
      render: (row) => formatNumber(row.today_calls),
    },
    {
      id: 'hitRate',
      header: t('knowledge.workspaceDashboard.columns.hitRate'),
      render: (row) => <HitRate row={row} />,
    },
    {
      id: 'lastSync',
      header: t('knowledge.workspaceDashboard.columns.lastSync'),
      render: (row) => {
        return <span className={row.last_sync_at ? 'text-foreground/80' : 'text-muted-foreground'}>{formatTimestamp(row.last_sync_at)}</span>
      },
    },
    {
      id: 'owner',
      header: t('knowledge.workspaceDashboard.columns.owner'),
      render: (row) => row.owner || '-',
    },
    {
      id: 'actions',
      header: t('knowledge.workspaceDashboard.columns.actions'),
      render: (row) => <OperationButtons row={row} />,
    },
  ], [t])

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('knowledge.workspaceDashboard.header.title')}
        description={t('knowledge.workspaceDashboard.header.description')}
        action={(
          <Button
            className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-400"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="h-4 w-4" />
            {t('knowledge.workspaceDashboard.header.create')}
          </Button>
        )}
      />

      {isWorkbenchError || isTableError ? (
        <BoxAlert
          severity="warning"
          title={t('knowledge.workspaceDashboard.table.empty')}
          description={tableError instanceof Error ? tableError.message : workbenchError instanceof Error ? workbenchError.message : undefined}
          action={<Button variant="outline" size="sm" onClick={() => { void refetchWorkbench(); void refetchTable() }}>{t('knowledge.workspaceDashboard.toolbar.refresh')}</Button>}
        />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('knowledge.workspaceDashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('knowledge.workspaceDashboard.toolbar.searchPlaceholder')}
        filterLabel={t('knowledge.workspaceDashboard.toolbar.filter')}
        timeLabel={t('knowledge.workspaceDashboard.toolbar.allTime')}
        refreshLabel={t('knowledge.workspaceDashboard.toolbar.refresh')}
        onRefresh={() => { void refetchWorkbench(); void refetchTable() }}
      />

      <BoxDataTable
        columns={columns}
        rows={rows}
        emptyMessage={isTableLoading ? 'Loading knowledge bases...' : t('knowledge.workspaceDashboard.table.empty')}
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
          totalSuffix: t('knowledge.workspaceDashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('knowledge.workspaceDashboard.pagination.pageSizeSuffix'),
          goTo: t('knowledge.workspaceDashboard.pagination.goTo'),
          page: t('knowledge.workspaceDashboard.pagination.page'),
        }}
      />

      <Dialog open={createOpen} onOpenChange={(open) => !createMutation.isPending && setCreateOpen(open)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create Knowledge Base</DialogTitle>
            <DialogDescription>Create an empty knowledge base, then add and index documents from its detail page.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="knowledge-name">Name</Label>
              <Input
                id="knowledge-name"
                autoFocus
                value={createForm.name}
                onChange={(event) => setCreateForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="knowledge-description">Description</Label>
              <Textarea
                id="knowledge-description"
                value={createForm.description || ''}
                onChange={(event) => setCreateForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="knowledge-type">Type</Label>
                <Select
                  value={createForm.knowledge_type}
                  onValueChange={(value) => setCreateForm((current) => ({ ...current, knowledge_type: value as KnowledgeCreateRequest['knowledge_type'] }))}
                >
                  <SelectTrigger id="knowledge-type" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="document">Documents</SelectItem>
                    <SelectItem value="qa">Question and answer</SelectItem>
                    <SelectItem value="code">Code</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="knowledge-visibility">Visibility</Label>
                <Select
                  value={createForm.visibility}
                  onValueChange={(value) => setCreateForm((current) => ({ ...current, visibility: value }))}
                >
                  <SelectTrigger id="knowledge-visibility" className="w-full"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">Private</SelectItem>
                    <SelectItem value="workspace">Workspace</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" disabled={createMutation.isPending} onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button disabled={createMutation.isPending || !createForm.name.trim()} onClick={submitCreate}>
              {createMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Create Knowledge Base
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </BoxShell>
  )
}

export default KnowledgeBoxPage
