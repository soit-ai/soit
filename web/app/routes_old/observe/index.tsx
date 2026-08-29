import { useMemo } from 'react'
import { useSearchParams } from 'react-router'
import { AlertTriangle } from 'lucide-react'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  getObserveDashboard,
  type ObserveBucket,
  type ObserveRange,
  type ObserveTabId,
} from '@/services/observe-service'

import { DashboardHeader } from './ui/dashboard-header'
import { DashboardSection } from './ui/dashboard-section'
import { DashboardSkeleton } from './ui/dashboard-skeleton'
import { DashboardSummary } from './ui/dashboard-summary'
import {
  OBSERVE_BUCKETS,
  OBSERVE_RANGES,
  OBSERVE_TAB_IDS,
} from './ui/dashboard-utils'

function ObservePage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = OBSERVE_TAB_IDS.includes(searchParams.get('tab') as ObserveTabId)
    ? searchParams.get('tab') as ObserveTabId
    : 'agent_health'
  const range = OBSERVE_RANGES.includes(searchParams.get('range') as ObserveRange)
    ? searchParams.get('range') as ObserveRange
    : '24h'
  const bucket = OBSERVE_BUCKETS.includes(searchParams.get('bucket') as ObserveBucket)
    ? searchParams.get('bucket') as ObserveBucket
    : '10m'
  const q = searchParams.get('q') || ''
  const pageToken = searchParams.get('page_token') || undefined
  const pageSize = Number(searchParams.get('page_size') || 10)

  const params = useMemo(
    () => ({
      tab,
      range,
      bucket,
      q,
      page_token: pageToken,
      page_size: pageSize,
    }),
    [tab, range, bucket, q, pageToken, pageSize],
  )
  const { data: dashboard, isLoading, isError, refetch } = useQuery({
    queryKey: ['observe', 'dashboard', params],
    queryFn: () => getObserveDashboard(params),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const updateParams = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) next.delete(key)
      else next.set(key, value)
    })
    setSearchParams(next)
  }

  const openRunDetail = (url?: string | null) => {
    if (url) navigate(url)
  }

  const openRuns = (row?: Record<string, unknown>) => {
    if (typeof row?.detail_url === 'string' && row.detail_url) {
      navigate(row.detail_url)
      return
    }
    const next = new URLSearchParams()
    if (row?.id) next.set('subject_id', String(row.id))
    navigate(`/observe/runs${next.toString() ? `?${next.toString()}` : ''}`)
  }

  const openDetail = (row: Record<string, unknown>) => {
    if (tab === 'agent_health') navigate(`/agents/${encodeURIComponent(String(row.id))}`)
    else if (tab === 'knowledge_quality') navigate(`/knowledge/${encodeURIComponent(String(row.id))}`)
    else openRuns(row)
  }

  const runExplorerUrl = searchParams.get('nosider')
    ? '/observe/runs?include_observe_summary=true&nosider=true'
    : '/observe/runs?include_observe_summary=true'

  return (
    <main className="flex w-full max-w-[calc(100vw-var(--root-sidebar-width)-1px)] min-w-0 flex-1 flex-col overflow-x-hidden bg-background">
      <div className="mx-auto flex w-full min-w-0 flex-1 flex-col gap-3 px-5 py-5 lg:px-7">
        <DashboardHeader
          isLoading={isLoading}
          runExplorerUrl={runExplorerUrl}
          onRefresh={() => void refetch()}
        />

        {isLoading ? <DashboardSkeleton /> : isError || !dashboard ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>{t('observe.error.title')}</AlertTitle>
            <AlertDescription>
              <Button variant="outline" size="sm" onClick={() => void refetch()}>{t('observe.error.retry')}</Button>
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <DashboardSummary
              dashboard={dashboard}
              onOpenRun={openRunDetail}
              onOpenAlert={(url) => navigate(url || '/observe/runs')}
            />
            <DashboardSection
              tab={tab}
              range={range}
              bucket={bucket}
              q={q}
              pageSize={pageSize}
              pageToken={pageToken}
              tabs={dashboard.tabs}
              section={dashboard.section}
              onUpdateParams={updateParams}
              onRefresh={() => void refetch()}
              onOpenRuns={openRuns}
              onOpenDetail={openDetail}
            />
          </>
        )}
      </div>
    </main>
  )
}

export default ObservePage
