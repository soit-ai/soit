import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { ArrowLeft, RefreshCw } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { toast } from 'sonner'
import { useNavigate } from '@/hooks/use-navigate'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'
import { getRunDetail, type RunDetailResponse, type RunStepResponse } from '@/services/run-service'

const formatTimestamp = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(isoToZonedDate(value))
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value} ms`
}

const getStepDuration = (step: RunStepResponse) => {
  if (!step.ended_at) return '-'
  const startedAt = new Date(step.started_at).getTime()
  const endedAt = new Date(step.ended_at).getTime()
  if (Number.isNaN(startedAt) || Number.isNaN(endedAt)) return '-'
  return `${Math.max(0, endedAt - startedAt)} ms`
}

function Page() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const { runId } = useParams<{ runId: string }>()
  const [detail, setDetail] = useState<RunDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchDetail = async () => {
    if (!runId) return
    try {
      setLoading(true)
      const data = await getRunDetail(runId, {
        include_steps: true,
        include_cost: true,
        include_artifacts: true,
      })
      setDetail(data)
    } catch (error) {
      toast.error(t('run.detail.toast.fetchError'))
      console.error('Failed to fetch run detail:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDetail()
  }, [runId])

  const sortedSteps = useMemo(() => {
    if (!detail?.steps?.length) return []
    return [...detail.steps].sort((a, b) => {
      const aTime = new Date(a.started_at).getTime()
      const bTime = new Date(b.started_at).getTime()
      if (Number.isNaN(aTime) || Number.isNaN(bTime)) return 0
      return aTime - bTime
    })
  }, [detail?.steps])

  if (!runId) {
    return (
      <div className="flex flex-1 flex-col gap-4 p-4">
        <Card>
          <CardHeader>
            <CardTitle>{t('run.detail.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground">{t('run.detail.missing')}</div>
          </CardContent>
        </Card>
      </div>
    )
  }

  const run = detail?.run
  const costSummary = detail?.cost_summary

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => navigate('/run')}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('run.detail.actions.back')}
          </Button>
          <div className="text-lg font-semibold">{t('run.detail.title')}</div>
        </div>
        <Button variant="outline" onClick={fetchDetail} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {t('run.detail.actions.refresh')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.summary.title')}</CardTitle>
          <CardDescription>{t('run.detail.summary.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.id')}</div>
              <div className="text-sm font-medium">{run?.id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.mode')}</div>
              <div className="text-sm font-medium">{run?.mode ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.app')}</div>
              <div className="text-sm font-medium">{run?.app_version_id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.trace')}</div>
              <div className="text-sm font-medium">{run?.trace_id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.user')}</div>
              <div className="text-sm font-medium">{run?.user_id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.status')}</div>
              <div className="text-sm font-medium">{run?.status ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.errorCode')}</div>
              <div className="text-sm font-medium">{run?.error_code ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.errorStep')}</div>
              <div className="text-sm font-medium">{run?.error_step_id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.startedAt')}</div>
              <div className="text-sm font-medium">{formatTimestamp(run?.started_at)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.endedAt')}</div>
              <div className="text-sm font-medium">{formatTimestamp(run?.ended_at)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('run.detail.fields.duration')}</div>
              <div className="text-sm font-medium">{formatDuration(run?.duration_ms)}</div>
            </div>
          </div>
          {run?.input_summary && (
            <div className="text-sm text-muted-foreground">
              {t('run.detail.fields.input', { input: run.input_summary })}
            </div>
          )}
          {run?.output_summary && (
            <div className="text-sm text-muted-foreground">
              {t('run.detail.fields.output', { output: run.output_summary })}
            </div>
          )}
          {run?.error_message && (
            <div className="text-sm text-destructive">
              {t('run.detail.fields.error', { error: run.error_message })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.cost.title')}</CardTitle>
          <CardDescription>{t('run.detail.cost.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          {!costSummary && (
            <div className="text-sm text-muted-foreground">{t('run.detail.cost.empty')}</div>
          )}
          {costSummary && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.promptTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_prompt}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.completionTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_completion}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.embeddingCount')}</div>
                <div className="text-sm font-medium">{costSummary.embedding_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.rerankCount')}</div>
                <div className="text-sm font-medium">{costSummary.rerank_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.totalMs')}</div>
                <div className="text-sm font-medium">{costSummary.ms_total}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('run.detail.cost.storageBytes')}</div>
                <div className="text-sm font-medium">{costSummary.storage_bytes}</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.steps.title')}</CardTitle>
          <CardDescription>{t('run.detail.steps.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {sortedSteps.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.steps.empty')}</div>
          )}
          {sortedSteps.map((step) => (
            <div key={step.id} className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{step.step_type}</div>
                <div className="text-xs text-muted-foreground">{step.status}</div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {formatTimestamp(step.started_at)} - {formatTimestamp(step.ended_at)} · {getStepDuration(step)}
              </div>
              {step.node_id && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('run.detail.steps.node', { node: step.node_id })}
                </div>
              )}
              {step.input_summary && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {t('run.detail.steps.input', { input: step.input_summary })}
                </div>
              )}
              {step.output_summary && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('run.detail.steps.output', { output: step.output_summary })}
                </div>
              )}
              {step.error_message && (
                <div className="mt-1 text-xs text-destructive">
                  {t('run.detail.steps.error', { error: step.error_message })}
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.artifacts.title')}</CardTitle>
          <CardDescription>{t('run.detail.artifacts.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {detail?.artifacts?.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.artifacts.empty')}</div>
          )}
          {detail?.artifacts?.map((artifact) => (
            <div key={artifact.id} className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{artifact.type}</div>
                <div className="text-xs text-muted-foreground">{formatTimestamp(artifact.created_at)}</div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {t('run.detail.artifacts.storageKey', { key: artifact.storage_key })}
              </div>
              {artifact.mime && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('run.detail.artifacts.mime', { mime: artifact.mime })}
                </div>
              )}
              {artifact.size_bytes !== null && artifact.size_bytes !== undefined && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('run.detail.artifacts.size', { size: artifact.size_bytes })}
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
