import { useCallback, useEffect, useMemo, useState } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { DateRangePicker } from '@/components/ui/date-range-picker'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTranslation } from '@/i18n'
import {
  listRuns,
  getRunCostSummary,
  getRunCostByDay,
  getRunCostByProvider,
  getRunCostByModel,
  type RunResponse,
  type RunCostSummary,
  type RunCostByDay,
  type RunCostByProvider,
  type RunCostByModel,
} from '@/services/run-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'
import { useNavigate } from '@/hooks/use-navigate'
import { toast } from 'sonner'
import type { DateRange } from 'react-day-picker'
import { useSearchParams } from 'react-router'

type RunFilters = {
  status: string
  mode: string
  subjectId: string
  subjectVersionId: string
  workflowId: string
  userId: string
  dateRange: DateRange
}

const createDefaultFilters = (): RunFilters => ({
  status: 'all',
  mode: '',
  subjectId: '',
  subjectVersionId: '',
  workflowId: '',
  userId: '',
  dateRange: { from: undefined, to: undefined },
})

const toStartOfDay = (value: Date) => {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 0, 0, 0, 0)
}

const toEndOfDay = (value: Date) => {
  return new Date(value.getFullYear(), value.getMonth(), value.getDate(), 23, 59, 59, 999)
}

const buildFilters = (activeFilters: RunFilters) => {
  const params: {
    mode?: string
    status?: string
    subject_id?: string
    subject_version_id?: string
    workflow_id?: string
    user_id?: string
    started_after?: string
    started_before?: string
  } = {}
  const trimmedMode = activeFilters.mode.trim()
  if (trimmedMode) {
    params.mode = trimmedMode
  }
  const trimmedSubject = activeFilters.subjectId.trim()
  if (trimmedSubject) {
    params.subject_id = trimmedSubject
  }
  const trimmedSubjectVersion = activeFilters.subjectVersionId.trim()
  if (trimmedSubjectVersion) {
    params.subject_version_id = trimmedSubjectVersion
  }
  const trimmedWorkflow = activeFilters.workflowId.trim()
  if (trimmedWorkflow) {
    params.workflow_id = trimmedWorkflow
  }
  const trimmedUser = activeFilters.userId.trim()
  if (trimmedUser) {
    params.user_id = trimmedUser
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

const formatTimestamp = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(isoToZonedDate(value))
}

function Page() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const [filters, setFilters] = useState<RunFilters>(() => createDefaultFilters())
  const [appliedFilters, setAppliedFilters] = useState<RunFilters>(() => createDefaultFilters())
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [nextPageToken, setNextPageToken] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [costSummary, setCostSummary] = useState<RunCostSummary | null>(null)
  const [costByDay, setCostByDay] = useState<RunCostByDay[]>([])
  const [costByProvider, setCostByProvider] = useState<RunCostByProvider[]>([])
  const [costByModel, setCostByModel] = useState<RunCostByModel[]>([])
  const [loadingCost, setLoadingCost] = useState(false)

  const fetchRuns = useCallback(
    async (activeFilters: RunFilters, pageToken?: string, append?: boolean) => {
      try {
        if (append) {
          setLoadingMore(true)
        } else {
          setLoading(true)
        }
        const data = await listRuns({
          page_size: 20,
          page_token: pageToken,
          ...buildFilters(activeFilters),
        })
        const items = data.items || []
        setRuns((prev) => (append ? [...prev, ...items] : items))
        setNextPageToken(data.next_page_token ?? null)
      } catch (error) {
        toast.error(t('run.list.toast.fetchError'))
        console.error('Failed to fetch runs:', error)
      } finally {
        setLoading(false)
        setLoadingMore(false)
      }
    },
    [t]
  )

  const applyFilters = () => {
    setAppliedFilters({
      status: filters.status,
      mode: filters.mode,
      subjectId: filters.subjectId,
      subjectVersionId: filters.subjectVersionId,
      workflowId: filters.workflowId,
      userId: filters.userId,
      dateRange: { ...filters.dateRange },
    })
  }

  const resetFilters = () => {
    const nextFilters = createDefaultFilters()
    setFilters(nextFilters)
    setAppliedFilters(nextFilters)
  }

  useEffect(() => {
    fetchRuns(appliedFilters)
  }, [appliedFilters, fetchRuns])

  useEffect(() => {
    const nextFilters = createDefaultFilters()
    nextFilters.mode = searchParams.get('mode') || ''
    nextFilters.status = searchParams.get('status') || 'all'
    nextFilters.subjectId = searchParams.get('subject_id') || ''
    nextFilters.subjectVersionId = searchParams.get('subject_version_id') || ''
    nextFilters.workflowId = searchParams.get('workflow_id') || ''
    nextFilters.userId = searchParams.get('user_id') || ''
    setFilters(nextFilters)
    setAppliedFilters(nextFilters)
  }, [searchParams])

  const fetchCosts = useCallback(
    async (activeFilters: RunFilters) => {
      try {
        setLoadingCost(true)
        const params = buildFilters(activeFilters)
        const [summary, byDay, providers, models] = await Promise.all([
          getRunCostSummary(params),
          getRunCostByDay(params),
          getRunCostByProvider(params),
          getRunCostByModel(params),
        ])
        setCostSummary(summary)
        setCostByDay(byDay || [])
        setCostByProvider(providers || [])
        setCostByModel(models || [])
      } catch (error) {
        toast.error(t('run.list.toast.fetchCostError'))
        console.error('Failed to fetch run costs:', error)
      } finally {
        setLoadingCost(false)
      }
    },
    [t]
  )

  useEffect(() => {
    fetchCosts(appliedFilters)
  }, [appliedFilters, fetchCosts])

  const hasMore = Boolean(nextPageToken)

  const rows = useMemo(() => runs, [runs])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-1 flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.status.label')}</span>
              <Select value={filters.status} onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder={t('run.list.filters.status.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('run.list.filters.status.all')}</SelectItem>
                  <SelectItem value="queued">{t('run.list.filters.status.queued')}</SelectItem>
                  <SelectItem value="running">{t('run.list.filters.status.running')}</SelectItem>
                  <SelectItem value="paused">{t('run.list.filters.status.paused')}</SelectItem>
                  <SelectItem value="succeeded">{t('run.list.filters.status.succeeded')}</SelectItem>
                  <SelectItem value="failed">{t('run.list.filters.status.failed')}</SelectItem>
                  <SelectItem value="canceled">{t('run.list.filters.status.canceled')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.mode.label')}</span>
              <Input
                value={filters.mode}
                onChange={(event) => setFilters((prev) => ({ ...prev, mode: event.target.value }))}
                placeholder={t('run.list.filters.mode.placeholder')}
                className="w-full sm:w-[200px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">Subject ID</span>
              <Input
                value={filters.subjectId}
                onChange={(event) => setFilters((prev) => ({ ...prev, subjectId: event.target.value }))}
                placeholder="Filter by subject ID"
                className="w-full sm:w-[220px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.app.label')}</span>
              <Input
                value={filters.subjectVersionId}
                onChange={(event) => setFilters((prev) => ({ ...prev, subjectVersionId: event.target.value }))}
                placeholder={t('run.list.filters.app.placeholder')}
                className="w-full sm:w-[220px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.workflow.label')}</span>
              <Input
                value={filters.workflowId}
                onChange={(event) => setFilters((prev) => ({ ...prev, workflowId: event.target.value }))}
                placeholder={t('run.list.filters.workflow.placeholder')}
                className="w-full sm:w-[220px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.user.label')}</span>
              <Input
                value={filters.userId}
                onChange={(event) => setFilters((prev) => ({ ...prev, userId: event.target.value }))}
                placeholder={t('run.list.filters.user.placeholder')}
                className="w-full sm:w-[200px]"
              />
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('run.list.filters.time.label')}</span>
              <DateRangePicker
                value={filters.dateRange}
                onChange={(value) => setFilters((prev) => ({ ...prev, dateRange: value ?? createDefaultFilters().dateRange }))}
                placeholder={t('run.list.filters.time.placeholder')}
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={applyFilters} disabled={loading}>
              {t('run.list.filters.actions.apply')}
            </Button>
            <Button variant="ghost" onClick={resetFilters} disabled={loading}>
              {t('run.list.filters.actions.reset')}
            </Button>
            <Button variant="outline" onClick={() => { fetchRuns(appliedFilters); fetchCosts(appliedFilters); }} disabled={loading || loadingCost}>
              {t('run.list.actions.refresh')}
            </Button>
          </div>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.list.cost.title')}</CardTitle>
          <CardDescription>{t('run.list.cost.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {loadingCost && (
            <div className="text-sm text-muted-foreground">{t('run.list.cost.loading')}</div>
          )}
          {!loadingCost && !costSummary && (
            <div className="text-sm text-muted-foreground">{t('run.list.cost.empty')}</div>
          )}
          {!loadingCost && costSummary && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.promptTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_prompt}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.completionTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_completion}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.embeddingCount')}</div>
                <div className="text-sm font-medium">{costSummary.embedding_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.rerankCount')}</div>
                <div className="text-sm font-medium">{costSummary.rerank_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.totalMs')}</div>
                <div className="text-sm font-medium">{costSummary.ms_total}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.list.cost.storageBytes')}</div>
                <div className="text-sm font-medium">{costSummary.storage_bytes}</div>
              </div>
            </div>
          )}
          {!loadingCost && (
            <div className="grid gap-4 lg:grid-cols-3">
              <div className="space-y-2">
                <div className="text-sm font-medium">{t('run.list.cost.byDay')}</div>
                {costByDay.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('run.list.cost.empty')}</div>
                )}
                {costByDay.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('run.list.cost.date')}</TableHead>
                        <TableHead>{t('run.list.cost.promptTokens')}</TableHead>
                        <TableHead>{t('run.list.cost.completionTokens')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {costByDay.map((item) => (
                        <TableRow key={item.date}>
                          <TableCell>{item.date}</TableCell>
                          <TableCell>{item.tokens_prompt}</TableCell>
                          <TableCell>{item.tokens_completion}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">{t('run.list.cost.byProvider')}</div>
                {costByProvider.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('run.list.cost.empty')}</div>
                )}
                {costByProvider.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('run.list.cost.provider')}</TableHead>
                        <TableHead>{t('run.list.cost.promptTokens')}</TableHead>
                        <TableHead>{t('run.list.cost.completionTokens')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {costByProvider.map((item) => (
                        <TableRow key={item.provider ?? 'unknown'}>
                          <TableCell>{item.provider ?? '-'}</TableCell>
                          <TableCell>{item.tokens_prompt}</TableCell>
                          <TableCell>{item.tokens_completion}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
              <div className="space-y-2">
                <div className="text-sm font-medium">{t('run.list.cost.byModel')}</div>
                {costByModel.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('run.list.cost.empty')}</div>
                )}
                {costByModel.length > 0 && (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t('run.list.cost.model')}</TableHead>
                        <TableHead>{t('run.list.cost.promptTokens')}</TableHead>
                        <TableHead>{t('run.list.cost.completionTokens')}</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {costByModel.map((item) => (
                        <TableRow key={item.model_ref ?? 'unknown'}>
                          <TableCell>{item.model_ref ?? '-'}</TableCell>
                          <TableCell>{item.tokens_prompt}</TableCell>
                          <TableCell>{item.tokens_completion}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.list.title')}</CardTitle>
          <CardDescription>{t('run.list.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          {rows.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.list.table.empty')}</div>
          )}
          {rows.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('run.list.table.id')}</TableHead>
                  <TableHead>{t('run.list.table.mode')}</TableHead>
                  <TableHead>{t('run.list.table.app')}</TableHead>
                  <TableHead>{t('run.list.table.user')}</TableHead>
                  <TableHead>{t('run.list.table.status')}</TableHead>
                  <TableHead>{t('run.list.table.startedAt')}</TableHead>
                  <TableHead>{t('run.list.table.duration')}</TableHead>
                  <TableHead>{t('run.list.table.input')}</TableHead>
                  <TableHead className="text-right">{t('run.list.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="font-medium">{run.id}</TableCell>
                    <TableCell>{run.mode}</TableCell>
                    <TableCell>{run.subject_version_id ?? '-'}</TableCell>
                    <TableCell>{run.user_id ?? '-'}</TableCell>
                    <TableCell>{run.status}</TableCell>
                    <TableCell>{formatTimestamp(run.started_at)}</TableCell>
                    <TableCell>{run.duration_ms ? `${run.duration_ms} ms` : '-'}</TableCell>
                    <TableCell className="max-w-[200px] truncate">{run.input_summary || '-'}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="sm" onClick={() => navigate(`/observability/runs/${run.id}`)}>
                        {t('run.list.table.view')}
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          {hasMore && (
            <div className="mt-4 flex justify-center">
              <Button
                variant="outline"
                disabled={loadingMore}
                onClick={() => nextPageToken && fetchRuns(appliedFilters, nextPageToken, true)}
              >
                {t('run.list.actions.loadMore')}
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
