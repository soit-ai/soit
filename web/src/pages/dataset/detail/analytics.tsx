import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useParams } from 'react-router'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useNavLayout } from '@/components/layout/nav-layout'
import { PageHeader } from './ui/analytics/page-header'
import { getDataset, type Dataset } from '@/services/dataset-service'
import {
  getRunCostSummary,
  getRunCostByMode,
  getRunCostByProvider,
  getRunCostByModel,
  listRuns,
  type RunResponse,
  type RunCostSummary,
  type RunCostByMode,
  type RunCostByProvider,
  type RunCostByModel,
} from '@/services/run-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'
import { useNavigate } from '@/hooks/use-navigate'
import type { DateRange } from 'react-day-picker'

type AnalyticsFilters = {
  status: string
  mode: string
  dateRange: DateRange
}

const createDefaultFilters = (): AnalyticsFilters => ({
  status: 'all',
  mode: '',
  dateRange: { from: undefined, to: undefined },
})

const toStartOfDay = (value: Date) => {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 0, 0, 0, 0)
}

const toEndOfDay = (value: Date) => {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 23, 59, 59, 999)
}

const cloneDateRange = (range: DateRange): DateRange => ({
  from: range?.from,
  to: range?.to,
})

const buildSharedFilters = (activeFilters: AnalyticsFilters) => {
  const params: {
    mode?: string
    status?: string
    started_after?: string
    started_before?: string
  } = {}
  const trimmedMode = activeFilters.mode.trim()
  if (trimmedMode) {
    params.mode = trimmedMode
  }
  if (activeFilters.status !== 'all') {
    params.status = activeFilters.status
  }
  if (activeFilters.dateRange?.from) {
    params.started_after = toStartOfDay(activeFilters.dateRange.from).toISOString()
  }
  if (activeFilters.dateRange?.to) {
    params.started_before = toEndOfDay(activeFilters.dateRange.to).toISOString()
  }
  return params
}

const buildModeSummaryFilters = (activeFilters: AnalyticsFilters) => {
  const params: {
    status?: string
    started_after?: string
    started_before?: string
  } = {}
  if (activeFilters.status !== 'all') {
    params.status = activeFilters.status
  }
  if (activeFilters.dateRange?.from) {
    params.started_after = toStartOfDay(activeFilters.dateRange.from).toISOString()
  }
  if (activeFilters.dateRange?.to) {
    params.started_before = toEndOfDay(activeFilters.dateRange.to).toISOString()
  }
  return params
}

function Page() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const navigate = useNavigate()
  const [dataset, setDataset] = useState<Dataset | null>(null)
  const [costSummary, setCostSummary] = useState<RunCostSummary | null>(null)
  const [costByMode, setCostByMode] = useState<RunCostByMode[]>([])
  const [costByProvider, setCostByProvider] = useState<RunCostByProvider[]>([])
  const [costByModel, setCostByModel] = useState<RunCostByModel[]>([])
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loading, setLoading] = useState(false)
  const [filters, setFilters] = useState<AnalyticsFilters>(() => createDefaultFilters())
  const [appliedFilters, setAppliedFilters] = useState<AnalyticsFilters>(() => createDefaultFilters())

  const { setHeaderContent } = useNavLayout()

  const fetchData = useCallback(async (activeFilters: AnalyticsFilters) => {
    if (!datasetId) return
    const sharedFilters = buildSharedFilters(activeFilters)
    const modeSummaryFilters = buildModeSummaryFilters(activeFilters)
    try {
      setLoading(true)
      const [datasetData, costData, costModeData, costProviderData, costModelData, runsData] = await Promise.all([
        getDataset(datasetId),
        getRunCostSummary({ app_version_id: datasetId, ...sharedFilters }),
        getRunCostByMode({ app_version_id: datasetId, ...modeSummaryFilters, ...(sharedFilters.mode ? { mode: sharedFilters.mode } : {}) }),
        getRunCostByProvider({ app_version_id: datasetId, ...sharedFilters }),
        getRunCostByModel({ app_version_id: datasetId, ...sharedFilters }),
        listRuns({ app_version_id: datasetId, page_size: 20, ...sharedFilters }),
      ])
      setDataset(datasetData)
      setCostSummary(costData)
      setCostByMode(costModeData)
      setCostByProvider(costProviderData)
      setCostByModel(costModelData)
      setRuns(runsData.items || [])
    } catch (error) {
      toast.error(t('dataset.analytics.toast.fetchError'))
      console.error('Failed to load analytics data:', error)
    } finally {
      setLoading(false)
    }
  }, [datasetId, t])

  const applyFilters = () => {
    setAppliedFilters({
      status: filters.status,
      mode: filters.mode,
      dateRange: cloneDateRange(filters.dateRange),
    })
  }

  const resetFilters = () => {
    const nextFilters = createDefaultFilters()
    setFilters(nextFilters)
    setAppliedFilters(nextFilters)
  }

  const handleRefresh = useCallback(() => {
    fetchData(appliedFilters)
  }, [fetchData, appliedFilters])

  useEffect(() => {
    setHeaderContent(<PageHeader title={t('dataset.analytics.header.title')} onRefresh={handleRefresh} />)
    return () => setHeaderContent(null)
  }, [setHeaderContent, t, handleRefresh])

  useEffect(() => {
    fetchData(appliedFilters)
  }, [datasetId, appliedFilters, fetchData])

  const runCounts = useMemo(() => {
    return runs.reduce(
      (acc, run) => {
        acc.total += 1
        acc[run.mode] = (acc[run.mode] || 0) + 1
        return acc
      },
      { total: 0 } as Record<string, number>
    )
  }, [runs])

  const visibleCostByMode = useMemo(() => {
    const activeMode = appliedFilters.mode.trim()
    if (!activeMode) return costByMode
    return costByMode.filter((item) => item.mode === activeMode)
  }, [appliedFilters.mode, costByMode])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-1 flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('dataset.analytics.filters.status.label')}</span>
              <Select value={filters.status} onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder={t('dataset.analytics.filters.status.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('dataset.analytics.filters.status.all')}</SelectItem>
                  <SelectItem value="queued">{t('dataset.analytics.filters.status.queued')}</SelectItem>
                  <SelectItem value="running">{t('dataset.analytics.filters.status.running')}</SelectItem>
                  <SelectItem value="paused">{t('dataset.analytics.filters.status.paused')}</SelectItem>
                  <SelectItem value="succeeded">{t('dataset.analytics.filters.status.succeeded')}</SelectItem>
                  <SelectItem value="failed">{t('dataset.analytics.filters.status.failed')}</SelectItem>
                  <SelectItem value="canceled">{t('dataset.analytics.filters.status.canceled')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('dataset.analytics.filters.mode.label')}</span>
              <Input
                value={filters.mode}
                onChange={(event) => setFilters((prev) => ({ ...prev, mode: event.target.value }))}
                placeholder={t('dataset.analytics.filters.mode.placeholder')}
                className="w-full sm:w-[200px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('dataset.analytics.filters.time.label')}</span>
              <DateRangePicker
                value={filters.dateRange}
                onChange={(value) => setFilters((prev) => ({ ...prev, dateRange: value ?? createDefaultFilters().dateRange }))}
                placeholder={t('dataset.analytics.filters.time.placeholder')}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={applyFilters} disabled={loading}>
              {t('dataset.analytics.filters.actions.apply')}
            </Button>
            <Button variant="ghost" onClick={resetFilters} disabled={loading}>
              {t('dataset.analytics.filters.actions.reset')}
            </Button>
          </div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('dataset.analytics.cards.documents')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{dataset?.doc_count ?? 0}</div>
            <p className="text-xs text-muted-foreground">
              {t('dataset.analytics.cards.chunks', { count: dataset?.chunk_count ?? 0 })}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('dataset.analytics.cards.runs')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{runCounts.total}</div>
            <p className="text-xs text-muted-foreground">{t('dataset.analytics.cards.recentRuns')}</p>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('dataset.analytics.cards.promptTokens')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{costSummary?.tokens_prompt ?? 0}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">{t('dataset.analytics.cards.completionTokens')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{costSummary?.tokens_completion ?? 0}</div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.analytics.mode.title')}</CardTitle>
          <CardDescription>{t('dataset.analytics.mode.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {visibleCostByMode.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.analytics.mode.empty')}</div>
          )}
          {visibleCostByMode.map((item) => (
            <div key={item.mode} className="flex items-center justify-between border-b pb-2">
              <div className="text-sm font-medium">{item.mode}</div>
              <div className="text-xs text-muted-foreground">
                {t('dataset.analytics.mode.tokens', { prompt: item.tokens_prompt, completion: item.tokens_completion })}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>{t('dataset.analytics.provider.title')}</CardTitle>
            <CardDescription>{t('dataset.analytics.provider.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {costByProvider.length === 0 && (
              <div className="text-sm text-muted-foreground">{t('dataset.analytics.provider.empty')}</div>
            )}
            {costByProvider.map((item) => {
              const providerLabel = item.provider || t('dataset.analytics.provider.unknown')
              return (
                <div key={providerLabel} className="flex items-center justify-between border-b pb-2">
                  <div className="text-sm font-medium">{providerLabel}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('dataset.analytics.provider.tokens', { prompt: item.tokens_prompt, completion: item.tokens_completion })}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('dataset.analytics.model.title')}</CardTitle>
            <CardDescription>{t('dataset.analytics.model.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-2">
            {costByModel.length === 0 && (
              <div className="text-sm text-muted-foreground">{t('dataset.analytics.model.empty')}</div>
            )}
            {costByModel.map((item) => {
              const modelLabel = item.model_ref || t('dataset.analytics.model.unknown')
              return (
                <div key={modelLabel} className="flex items-center justify-between border-b pb-2">
                  <div className="text-sm font-medium">{modelLabel}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('dataset.analytics.model.tokens', { prompt: item.tokens_prompt, completion: item.tokens_completion })}
                  </div>
                </div>
              )
            })}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.analytics.recent.title')}</CardTitle>
          <CardDescription>{t('dataset.analytics.recent.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {runs.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.analytics.recent.empty')}</div>
          )}
          {runs.map((run) => (
            <div key={run.id} className="border-b pb-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{run.mode}</div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{run.status}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => datasetId && navigate(`/dataset/${datasetId}/runs/${run.id}`)}
                    disabled={!datasetId}
                  >
                    {t('dataset.analytics.recent.view')}
                  </Button>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">{run.started_at}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
