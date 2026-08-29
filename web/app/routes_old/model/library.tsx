import { useEffect, useMemo, useState } from 'react'
import { AlertTriangle, Box, CheckCircle2, Clock3, MoreHorizontal, Plus, RefreshCw } from 'lucide-react'

import {
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
  MetricStrip,
} from '@/components/box'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useDrawer } from '@/hooks/use-drawer'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { getModelWorkbenchModels, listProviders } from '@/services/provider-service'

import { ModelList } from './setting/ui/model-list'
import {
  ModelNameCell,
  OperationButtons,
  StatusBadge,
  type ModelLibraryRow,
} from './ui/workbench'

function formatContext(value?: number) {
  if (!value) return '--'
  if (value >= 1000) return `${Math.round(value / 1000)}K`
  return value.toLocaleString()
}

function formatDateTime(value?: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString()
}

function formatCurrency(value?: number | null, currency?: string | null) {
  if (typeof value !== 'number') return '--'
  return `${currency || ''} ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`.trim()
}

function normalizeModelType(value?: string) {
  if (!value) return 'llm'
  const normalized = value.toLowerCase()
  if (normalized === 'llm') return 'llm'
  if (normalized === 'embedding') return 'embedding'
  if (normalized === 'rerank') return 'rerank'
  if (normalized === 'multimodal') return 'multimodal'
  return 'llm'
}

function modelTypeLabel(value?: string) {
  const normalized = normalizeModelType(value)
  if (normalized === 'embedding') return 'Embedding'
  if (normalized === 'rerank') return 'Rerank'
  if (normalized === 'multimodal') return 'Multimodal'
  return 'LLM'
}

function statusLabel(t: ReturnType<typeof useTranslation>['t'], status: ModelLibraryRow['status']) {
  if (status === 'available') return t('model.library.status.available')
  if (status === 'abnormal') return t('model.library.status.abnormal')
  return t('model.library.status.disabled')
}

function ModelLibraryPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const drawer = useDrawer()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [providerFilter, setProviderFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])
  const tableKeyword = search.trim()
  const pageToken = pageTokens[currentPage - 1]

  const workbenchQuery = useQuery({
    queryKey: ['models', 'workbench', 'models', activeTab, tableKeyword, providerFilter, statusFilter, pageToken],
    queryFn: () => getModelWorkbenchModels({
      page_size: 50,
      page_token: pageToken,
      tab: activeTab,
      keyword: tableKeyword || undefined,
      provider_id: providerFilter === 'all' ? undefined : providerFilter,
      status: statusFilter === 'all' ? undefined : statusFilter,
    }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const providersQuery = useQuery({
    queryKey: ['models', 'library', 'providers'],
    queryFn: () => listProviders(),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  useEffect(() => {
    setCurrentPage(1)
    setPageTokens([undefined])
  }, [activeTab, tableKeyword, providerFilter, statusFilter])

  const providers = providersQuery.data || []
  const providerById = useMemo(() => new Map<string, (typeof providers)[number]>(providers.map((provider) => [provider.id, provider])), [providers])

  const rows = useMemo<ModelLibraryRow[]>(() => {
    return (workbenchQuery.data?.items || []).map((model) => {
      return {
        id: model.id,
        providerId: model.provider_id,
        name: model.display_name || model.model_id,
        version: model.lifecycle_status || model.sync_status || '--',
        provider: model.provider_name,
        providerKind: model.provider_kind,
        type: modelTypeLabel(model.model_type),
        status: model.status,
        context: formatContext(model.context_window || undefined),
        price: model.unit_price === null || model.unit_price === undefined ? '--' : formatCurrency(model.unit_price, model.currency),
        todayCalls: model.today_calls.toLocaleString(),
        avgLatency: model.avg_latency_ms === null || model.avg_latency_ms === undefined ? '--' : `${model.avg_latency_ms.toLocaleString()}ms`,
        updatedAt: formatDateTime(model.updated_at),
        owner: model.owner || '--',
      }
    })
  }, [workbenchQuery.data?.items])

  const activeTabTotal = activeTab === 'all'
    ? workbenchQuery.data?.tabs.all
    : workbenchQuery.data?.tabs[activeTab as keyof NonNullable<typeof workbenchQuery.data>['tabs']]
  const filteredByControls = Boolean(tableKeyword || providerFilter !== 'all' || statusFilter !== 'all')
  const totalRows = filteredByControls ? rows.length : typeof activeTabTotal === 'number' ? activeTabTotal : rows.length
  const safePage = currentPage
  const pages = useMemo(() => {
    const values = [safePage]
    if (safePage > 1) values.unshift(safePage - 1)
    if (workbenchQuery.data?.next_page_token) values.push(safePage + 1)
    return values
  }, [safePage, workbenchQuery.data?.next_page_token])

  const disabledCount = (workbenchQuery.data?.tabs.disabled || 0) + (workbenchQuery.data?.tabs.abnormal || 0)
  const tabs = useMemo<BoxToolbarTab[]>(() => [
    { id: 'all', label: t('model.library.tabs.all'), count: workbenchQuery.data?.tabs.all ?? 0 },
    { id: 'text', label: t('model.library.tabs.text'), count: workbenchQuery.data?.tabs.text ?? 0 },
    { id: 'embedding', label: t('model.library.tabs.embedding'), count: workbenchQuery.data?.tabs.embedding ?? 0 },
    { id: 'multimodal', label: t('model.library.tabs.multimodal'), count: workbenchQuery.data?.tabs.multimodal ?? 0 },
    { id: 'rerank', label: t('model.library.tabs.rerank'), count: workbenchQuery.data?.tabs.rerank ?? 0 },
  ], [workbenchQuery.data?.tabs, t])

  const goToNextPage = () => {
    if (!workbenchQuery.data?.next_page_token) return
    setPageTokens((tokens) => {
      const nextTokens = tokens.slice(0, currentPage)
      nextTokens[currentPage] = workbenchQuery.data.next_page_token || undefined
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

  const metrics = useMemo(() => [
    {
      id: 'total',
      label: t('model.library.metrics.totalModels'),
      value: (workbenchQuery.data?.summary.total_models || 0).toLocaleString(),
      delta: `+${workbenchQuery.data?.summary.available_models || 0}`,
      trend: [8, 9, 11, 10, 12, 14, 13, 15, 14, 16],
      icon: Box,
      tone: 'blue' as const,
    },
    {
      id: 'available',
      label: t('model.library.metrics.availableModels'),
      value: (workbenchQuery.data?.summary.available_models || 0).toLocaleString(),
      delta: `-${disabledCount}`,
      trend: [6, 7, 8, 8, 9, 10, 10, 11, 12, 12],
      icon: CheckCircle2,
      tone: 'green' as const,
    },
    {
      id: 'calls',
      label: t('model.library.metrics.monthCalls'),
      value: (workbenchQuery.data?.summary.month_calls || 0).toLocaleString(),
      delta: t('model.overview.metrics.fromRuns'),
      trend: [8, 10, 9, 12, 13, 12, 15, 14, 16, 15],
      icon: MoreHorizontal,
      tone: 'blue' as const,
    },
    {
      id: 'latency',
      label: t('model.library.metrics.avgLatency'),
      value: workbenchQuery.data?.summary.avg_latency_ms ? `${workbenchQuery.data.summary.avg_latency_ms.toLocaleString()}ms` : '--',
      delta: t('model.overview.metrics.fromRuns'),
      trend: [12, 11, 10, 9, 10, 8, 7, 8, 7, 6],
      icon: Clock3,
      tone: 'amber' as const,
    },
    {
      id: 'abnormal',
      label: t('model.library.metrics.abnormalModels'),
      value: disabledCount.toLocaleString(),
      delta: disabledCount ? t('model.library.metrics.needsReview') : t('model.library.metrics.normal'),
      trend: [4, 3, 3, 2, 3, 2, 2, 1, 1, 1],
      icon: AlertTriangle,
      tone: disabledCount ? 'red' as const : 'green' as const,
    },
  ], [disabledCount, workbenchQuery.data?.summary, t])

  const openModelManagement = (row?: ModelLibraryRow) => {
    const provider = row?.providerId ? providerById.get(row.providerId) : providers[0]
    if (!provider) return
    drawer.open(
      <ModelList
        provider={provider.id}
        onSaveModel={() => { void workbenchQuery.refetch() }}
        onDeleteModel={() => { void workbenchQuery.refetch() }}
        title={row ? t('model.library.actions.editModel') : t('model.library.actions.createImport')}
      />,
      {
        direction: 'right',
        contentClassName: '!w-[680px] !max-w-[680px] h-full',
        onClose: () => { void workbenchQuery.refetch() },
      },
    )
  }

  const columns = useMemo<BoxDataTableColumn<ModelLibraryRow>[]>(() => [
    { id: 'name', header: t('model.library.columns.name'), render: (row) => <ModelNameCell row={row} /> },
    { id: 'provider', header: t('model.library.columns.provider'), render: (row) => row.provider },
    { id: 'type', header: t('model.library.columns.type'), render: (row) => row.type },
    { id: 'status', header: t('model.library.columns.status'), render: (row) => <StatusBadge status={row.status} label={statusLabel(t, row.status)} /> },
    { id: 'context', header: t('model.library.columns.context'), cellClassName: 'font-medium text-foreground', render: (row) => row.context },
    { id: 'price', header: t('model.library.columns.price'), render: (row) => row.price },
    { id: 'todayCalls', header: t('model.library.columns.todayCalls'), render: (row) => row.todayCalls },
    { id: 'latency', header: t('model.library.columns.avgLatency'), render: (row) => <span className={cn(row.avgLatency === '--' ? 'text-muted-foreground' : 'text-success-foreground')}>{row.avgLatency}</span> },
    { id: 'updatedAt', header: t('model.library.columns.updatedAt'), render: (row) => row.updatedAt },
    { id: 'owner', header: t('model.library.columns.owner'), render: (row) => row.owner },
    {
      id: 'actions',
      header: t('model.library.columns.actions'),
      render: (row) => (
        <OperationButtons
          onReport={() => navigate('/observe/runs')}
          onEdit={() => openModelManagement(row)}
        />
      ),
    },
  ], [navigate, openModelManagement, t])

  const hasError = workbenchQuery.isError || providersQuery.isError

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('model.library.title')}
        description={t('model.library.description')}
        action={(
          <Button
            type="button"
            className="h-11 gap-2 rounded-lg bg-primary px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-primary/90"
            onClick={() => openModelManagement()}
          >
            <Plus className="h-4 w-4" />
            {t('model.library.actions.createImport')}
          </Button>
        )}
      />

      {hasError ? (
        <BoxAlert severity="warning" title={t('model.common.loadFailedTitle')} description={t('model.common.loadFailedDescription')} />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('model.common.deltaLabel')} />

      {disabledCount ? (
        <BoxAlert
          severity="critical"
          badge={disabledCount}
          title={t('model.library.alert.title')}
          description={t('model.library.alert.description')}
        />
      ) : null}

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('model.library.toolbar.searchPlaceholder')}
        refreshLabel={t('model.common.refresh')}
        onRefresh={() => { void workbenchQuery.refetch(); void providersQuery.refetch() }}
        actions={(
          <>
            <Select value={providerFilter} onValueChange={(value) => value != null && setProviderFilter(value)}>
              <SelectTrigger className="h-10 w-full border-border bg-panel shadow-sm sm:w-[180px]">
                <SelectValue placeholder={t('model.library.toolbar.provider')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('model.library.toolbar.allProviders')}</SelectItem>
                {providers.map((provider) => <SelectItem key={provider.id} value={provider.id}>{provider.name}</SelectItem>)}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={(value) => value != null && setStatusFilter(value)}>
              <SelectTrigger className="h-10 w-full border-border bg-panel shadow-sm sm:w-[150px]">
                <SelectValue placeholder={t('model.library.toolbar.status')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('model.library.toolbar.allStatus')}</SelectItem>
                <SelectItem value="available">{t('model.library.status.available')}</SelectItem>
                <SelectItem value="disabled">{t('model.library.status.disabled')}</SelectItem>
                <SelectItem value="abnormal">{t('model.library.status.abnormal')}</SelectItem>
              </SelectContent>
            </Select>
          </>
        )}
      />

      <BoxDataTable columns={columns} rows={rows} emptyMessage={workbenchQuery.isLoading ? t('model.common.loading') : t('model.library.empty')} />

      <BoxPagination
        total={totalRows}
        pageSize={workbenchQuery.data?.page_size || 50}
        currentPage={safePage}
        pages={pages}
        hasPrevious={safePage > 1}
        hasNext={Boolean(workbenchQuery.data?.next_page_token)}
        onPrevious={goToPreviousPage}
        onNext={goToNextPage}
        onPageChange={goToPage}
        labels={{
          totalSuffix: t('model.common.pagination.totalSuffix'),
          pageSizeSuffix: t('model.common.pagination.pageSizeSuffix'),
          goTo: t('model.common.pagination.goTo'),
          page: t('model.common.pagination.page'),
        }}
      />
    </BoxShell>
  )
}

export default ModelLibraryPage
