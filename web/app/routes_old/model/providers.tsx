import { useEffect, useMemo, useState } from 'react'
import { Building2, CheckCircle2, Cuboid, Plus, RefreshCw, WalletCards } from 'lucide-react'
import { toast } from 'sonner'

import {
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
  MetricStrip,
  BoxAlert,
} from '@/components/box'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useDrawer } from '@/hooks/use-drawer'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createProvider,
  getModelWorkbenchProviders,
  healthCheck,
  listProviders,
  syncFromPlatform,
  updateProvider,
} from '@/services/provider-service'
import type { ProviderConfig } from '@/features/model-config/types'

import { SettingSheet } from './setting'
import {
  OperationButtons,
  ProviderNameCell,
  QuotaProgress,
  StatusBadge,
  TypeBadges,
  type ProviderTableRow,
} from './ui/workbench'

function formatDateTime(value?: string) {
  if (!value) return '--'
  return new Date(value).toLocaleString()
}

function formatCurrency(value?: number | null, currency?: string | null) {
  if (typeof value !== 'number') return '--'
  return `${currency || ''} ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`.trim()
}

function statusLabel(t: ReturnType<typeof useTranslation>['t'], status: ProviderTableRow['status']) {
  if (status === 'online') return t('model.providers.status.online')
  if (status === 'error') return t('model.providers.status.error')
  return t('model.providers.status.disabled')
}

function ModelProvidersPage() {
  const { t } = useTranslation()
  const drawer = useDrawer()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [regionFilter, setRegionFilter] = useState('all')
  const [modelTypeFilter, setModelTypeFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageTokens, setPageTokens] = useState<Array<string | undefined>>([undefined])
  const tableKeyword = search.trim()
  const pageToken = pageTokens[currentPage - 1]

  const providersQuery = useQuery({
    queryKey: ['models', 'providers', 'providers'],
    queryFn: () => listProviders(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const workbenchQuery = useQuery({
    queryKey: ['models', 'workbench', 'providers', activeTab, tableKeyword, statusFilter, modelTypeFilter, pageToken],
    queryFn: () => getModelWorkbenchProviders({
      page_size: 50,
      page_token: pageToken,
      tab: activeTab,
      keyword: tableKeyword || undefined,
      status: statusFilter === 'all' ? undefined : statusFilter,
      model_type: modelTypeFilter === 'all' ? undefined : modelTypeFilter,
    }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  useEffect(() => {
    setCurrentPage(1)
    setPageTokens([undefined])
  }, [activeTab, tableKeyword, statusFilter, regionFilter, modelTypeFilter])

  const providers = providersQuery.data || []

  const rows = useMemo<ProviderTableRow[]>(() => {
    return (workbenchQuery.data?.items || []).map((provider) => {
      return {
        id: provider.id,
        name: provider.name,
        kind: provider.kind,
        status: provider.status,
        availableModels: provider.available_models,
        modelTypes: provider.model_types,
        region: provider.region || '--',
        monthCalls: provider.month_calls.toLocaleString(),
        monthCost: formatCurrency(provider.month_cost_amount, provider.currency),
        quotaLabel: provider.quota_used === null || provider.quota_used === undefined || provider.quota_limit === null || provider.quota_limit === undefined
          ? '-- / --'
          : `${provider.quota_used.toLocaleString()} / ${provider.quota_limit.toLocaleString()}`,
        quotaPercent: provider.quota_percent || 0,
        availability: provider.availability === null || provider.availability === undefined ? '--' : `${provider.availability}%`,
        lastSync: formatDateTime(provider.last_sync_at || provider.last_healthcheck_at || provider.updated_at),
        owner: provider.owner || '--',
      }
    })
  }, [workbenchQuery.data?.items])

  const activeTabTotal = activeTab === 'all'
    ? workbenchQuery.data?.tabs.all
    : workbenchQuery.data?.tabs[activeTab as keyof NonNullable<typeof workbenchQuery.data>['tabs']]
  const filteredByControls = Boolean(tableKeyword || statusFilter !== 'all' || regionFilter !== 'all' || modelTypeFilter !== 'all')
  const totalRows = filteredByControls ? rows.length : typeof activeTabTotal === 'number' ? activeTabTotal : rows.length
  const safePage = currentPage
  const pages = useMemo(() => {
    const values = [safePage]
    if (safePage > 1) values.unshift(safePage - 1)
    if (workbenchQuery.data?.next_page_token) values.push(safePage + 1)
    return values
  }, [safePage, workbenchQuery.data?.next_page_token])

  const tabs = useMemo<BoxToolbarTab[]>(() => [
    { id: 'all', label: t('model.providers.tabs.all'), count: workbenchQuery.data?.tabs.all ?? 0 },
    { id: 'online', label: t('model.providers.tabs.enabled'), count: workbenchQuery.data?.tabs.online ?? 0 },
    { id: 'disabled', label: t('model.providers.tabs.disabled'), count: workbenchQuery.data?.tabs.disabled ?? 0 },
    { id: 'error', label: t('model.providers.tabs.error'), count: workbenchQuery.data?.tabs.error ?? 0 },
  ], [workbenchQuery.data?.tabs, t])

  const onlineProviders = workbenchQuery.data?.summary.online_providers || 0
  const summary = workbenchQuery.data?.summary
  const metrics = useMemo(() => [
    {
      id: 'connected',
      label: t('model.providers.metrics.connectedProviders'),
      value: (summary?.total_providers || 0).toLocaleString(),
      delta: `+${onlineProviders}`,
      trend: [4, 5, 5, 6, 6, 7, 7, 8, 8, 8],
      icon: Building2,
      tone: 'blue' as const,
    },
    {
      id: 'online',
      label: t('model.providers.metrics.onlineProviders'),
      value: onlineProviders.toLocaleString(),
      delta: `-${(summary?.total_providers || 0) - onlineProviders}`,
      trend: [3, 4, 5, 5, 5, 6, 6, 6, 7, 7],
      icon: CheckCircle2,
      tone: 'green' as const,
    },
    {
      id: 'models',
      label: t('model.providers.metrics.availableModels'),
      value: (summary?.available_models || 0).toLocaleString(),
      delta: `+${summary?.total_models || 0}`,
      trend: [8, 9, 10, 12, 13, 15, 16, 18, 19, 20],
      icon: Cuboid,
      tone: 'blue' as const,
    },
    {
      id: 'calls',
      label: t('model.providers.metrics.monthCalls'),
      value: (summary?.month_calls || 0).toLocaleString(),
      delta: t('model.overview.metrics.fromRuns'),
      trend: [8, 9, 11, 10, 13, 14, 13, 16, 15, 17],
      icon: RefreshCw,
      tone: 'cyan' as const,
    },
    {
      id: 'cost',
      label: t('model.providers.metrics.monthCost'),
      value: formatCurrency(summary?.month_cost_amount, summary?.currency),
      delta: t('model.overview.metrics.fromRuns'),
      trend: [5, 6, 6, 8, 7, 9, 10, 11, 12, 13],
      icon: WalletCards,
      tone: 'amber' as const,
    },
  ], [onlineProviders, summary, t])

  const reload = () => {
    void providersQuery.refetch()
    void workbenchQuery.refetch()
  }

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

  const openProviderForm = (provider?: ProviderConfig) => {
    const currentProvider: ProviderConfig = provider || {
      id: '',
      adapterBackend: 'native',
      slug: '',
      name: '',
      kind: 'openai',
      status: 'active',
      baseUrl: '',
      credentialSecretId: '',
      syncPolicy: {
        auto_sync: false,
        interval_minutes: 360,
        recreate_deleted: false,
        default_enabled: true,
        catalog_supported: true,
        include_models: [],
        exclude_models: [],
      },
      connectionConfig: {
        timeout_ms: 30000,
        retry_policy: { max_retries: 3, backoff: 'exponential' },
        rate_limit: { concurrency: 16 },
      },
      authConfig: {
        auth_type: 'bearer',
      },
      runtimeConfig: {
        diagnostics_supported: { healthcheck: true, chat: true, embedding: false },
        runtime_support: { chat: true, stream: true, embedding: false, image: false, audio: false, video: false, rerank: false },
      },
      governanceConfig: {
        currency: 'USD',
        pricing_source: 'unknown',
        egress_policy: { allow_external: true, allowed_domains: [] },
        data_policy: { files: false, images: false, audio: false, video: false, sensitive_data: 'deny' },
        log_level: 'summary',
        trace_enabled: true,
      },
    }

    drawer.open(
      <SettingSheet
        item={currentProvider}
        index={0}
        onSave={async (data) => {
          if (provider?.id) {
            await updateProvider(provider.id, { ...provider, ...data })
          } else {
            await createProvider({ ...currentProvider, ...data })
          }
          reload()
        }}
      />,
      {
        direction: 'right',
        contentClassName: '!w-[760px] !max-w-[760px] h-full',
        onClose: reload,
      },
    )
  }

  const handleHealthCheck = async (row: ProviderTableRow) => {
    try {
      await healthCheck(row.id)
      toast.success(t('model.providers.toast.healthSuccess'))
      reload()
    } catch (error) {
      toast.error(t('model.providers.toast.healthFailed'))
      console.error('Provider health check failed:', error)
    }
  }

  const handleSync = async (row: ProviderTableRow) => {
    try {
      await syncFromPlatform(row.id)
      toast.success(t('model.providers.toast.syncSuccess'))
      reload()
    } catch (error) {
      toast.error(t('model.providers.toast.syncFailed'))
      console.error('Provider sync failed:', error)
    }
  }

  const columns = useMemo<BoxDataTableColumn<ProviderTableRow>[]>(() => [
    { id: 'provider', header: t('model.providers.columns.provider'), render: (row) => <ProviderNameCell row={row} /> },
    { id: 'status', header: t('model.providers.columns.status'), render: (row) => <StatusBadge status={row.status} label={statusLabel(t, row.status)} /> },
    { id: 'models', header: t('model.providers.columns.availableModels'), cellClassName: 'font-semibold text-foreground', render: (row) => row.availableModels },
    { id: 'types', header: t('model.providers.columns.modelTypes'), render: (row) => <TypeBadges values={row.modelTypes} /> },
    { id: 'region', header: t('model.providers.columns.region'), render: (row) => row.region },
    { id: 'monthCalls', header: t('model.providers.columns.monthCalls'), render: (row) => row.monthCalls },
    { id: 'monthCost', header: t('model.providers.columns.monthCost'), render: (row) => row.monthCost },
    { id: 'quota', header: t('model.providers.columns.quota'), render: (row) => <QuotaProgress label={row.quotaLabel} value={row.quotaPercent} /> },
    { id: 'availability', header: t('model.providers.columns.availability'), cellClassName: 'font-semibold text-success-foreground', render: (row) => row.availability },
    { id: 'lastSync', header: t('model.providers.columns.lastSync'), render: (row) => row.lastSync },
    { id: 'owner', header: t('model.providers.columns.owner'), render: (row) => row.owner },
    {
      id: 'actions',
      header: t('model.providers.columns.actions'),
      render: (row) => {
        const provider = providers.find((item) => item.id === row.id)
        return (
          <OperationButtons
            onRefresh={() => { void handleHealthCheck(row) }}
            onEdit={provider ? () => openProviderForm(provider) : undefined}
            onMore={() => { void handleSync(row) }}
          />
        )
      },
    },
  ], [providers, t])

  const hasError = providersQuery.isError || workbenchQuery.isError

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('model.providers.title')}
        description={t('model.providers.description')}
        action={(
          <Button
            type="button"
            className="h-11 gap-2 rounded-lg bg-primary px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-primary/90"
            onClick={() => openProviderForm()}
          >
            <Plus className="h-4 w-4" />
            {t('model.providers.actions.addProvider')}
          </Button>
        )}
      />

      {hasError ? (
        <BoxAlert severity="warning" title={t('model.common.loadFailedTitle')} description={t('model.common.loadFailedDescription')} />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('model.common.deltaLabel')} />

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('model.providers.toolbar.searchPlaceholder')}
        refreshLabel={t('model.common.refresh')}
        onRefresh={reload}
        actions={(
          <>
            <Select value={statusFilter} onValueChange={(value) => value != null && setStatusFilter(value)}>
              <SelectTrigger className="h-10 w-full border-border bg-panel shadow-sm sm:w-[130px]">
                <SelectValue placeholder={t('model.providers.toolbar.status')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('model.providers.toolbar.allStatus')}</SelectItem>
                <SelectItem value="online">{t('model.providers.status.online')}</SelectItem>
                <SelectItem value="disabled">{t('model.providers.status.disabled')}</SelectItem>
                <SelectItem value="error">{t('model.providers.status.error')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={regionFilter} onValueChange={(value) => value != null && setRegionFilter(value)}>
              <SelectTrigger className="h-10 w-full border-border bg-panel shadow-sm sm:w-[130px]">
                <SelectValue placeholder={t('model.providers.toolbar.region')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('model.providers.toolbar.allRegions')}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={modelTypeFilter} onValueChange={(value) => value != null && setModelTypeFilter(value)}>
              <SelectTrigger className="h-10 w-full border-border bg-panel shadow-sm sm:w-[150px]">
                <SelectValue placeholder={t('model.providers.toolbar.modelType')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t('model.providers.toolbar.allTypes')}</SelectItem>
                <SelectItem value="llm">LLM</SelectItem>
                <SelectItem value="embedding">Embedding</SelectItem>
              </SelectContent>
            </Select>
          </>
        )}
      />

      <BoxDataTable columns={columns} rows={rows} emptyMessage={workbenchQuery.isLoading ? t('model.common.loading') : t('model.providers.empty')} />

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

export default ModelProvidersPage
