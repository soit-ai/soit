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
  const { runId } = useParams<{ datasetId: string; runId: string }>()
  const [detail, setDetail] = useState<RunDetailResponse | null>(null)
  const [loading, setLoading] = useState(false)

  const fetchDetail = async () => {
    if (!runId) return
    try {
      setLoading(true)
      const data = await getRunDetail(runId, {
        include_steps: true,
        include_cost: true,
        include_artifacts: false,
      })
      setDetail(data)
    } catch (error) {
      toast.error(t('dataset.runDetail.toast.fetchError'))
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
            <CardTitle>{t('dataset.runDetail.title')}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-sm text-muted-foreground">{t('dataset.runDetail.missing')}</div>
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
          <Button variant="ghost" onClick={() => navigate(-1)}>
            <ArrowLeft className="mr-2 h-4 w-4" />
            {t('dataset.runDetail.actions.back')}
          </Button>
          <div className="text-lg font-semibold">{t('dataset.runDetail.title')}</div>
        </div>
        <Button variant="outline" onClick={fetchDetail} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          {t('dataset.runDetail.actions.refresh')}
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.runDetail.summary.title')}</CardTitle>
          <CardDescription>{t('dataset.runDetail.summary.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.id')}</div>
              <div className="text-sm font-medium">{run?.id ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.mode')}</div>
              <div className="text-sm font-medium">{run?.mode ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.status')}</div>
              <div className="text-sm font-medium">{run?.status ?? '-'}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.startedAt')}</div>
              <div className="text-sm font-medium">{formatTimestamp(run?.started_at)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.endedAt')}</div>
              <div className="text-sm font-medium">{formatTimestamp(run?.ended_at)}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('dataset.runDetail.fields.duration')}</div>
              <div className="text-sm font-medium">{formatDuration(run?.duration_ms)}</div>
            </div>
          </div>
          {run?.input_summary && (
            <div className="text-sm text-muted-foreground">
              {t('dataset.runDetail.fields.input', { input: run.input_summary })}
            </div>
          )}
          {run?.output_summary && (
            <div className="text-sm text-muted-foreground">
              {t('dataset.runDetail.fields.output', { output: run.output_summary })}
            </div>
          )}
          {run?.error_message && (
            <div className="text-sm text-destructive">
              {t('dataset.runDetail.fields.error', { error: run.error_message })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.runDetail.cost.title')}</CardTitle>
          <CardDescription>{t('dataset.runDetail.cost.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          {!costSummary && (
            <div className="text-sm text-muted-foreground">{t('dataset.runDetail.cost.empty')}</div>
          )}
          {costSummary && (
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.promptTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_prompt}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.completionTokens')}</div>
                <div className="text-sm font-medium">{costSummary.tokens_completion}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.embeddingCount')}</div>
                <div className="text-sm font-medium">{costSummary.embedding_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.rerankCount')}</div>
                <div className="text-sm font-medium">{costSummary.rerank_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.totalMs')}</div>
                <div className="text-sm font-medium">{costSummary.ms_total}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('dataset.runDetail.cost.storageBytes')}</div>
                <div className="text-sm font-medium">{costSummary.storage_bytes}</div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.runDetail.steps.title')}</CardTitle>
          <CardDescription>{t('dataset.runDetail.steps.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {sortedSteps.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.runDetail.steps.empty')}</div>
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
                  {t('dataset.runDetail.steps.node', { node: step.node_id })}
                </div>
              )}
              {step.input_summary && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {t('dataset.runDetail.steps.input', { input: step.input_summary })}
                </div>
              )}
              {step.output_summary && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('dataset.runDetail.steps.output', { output: step.output_summary })}
                </div>
              )}
              {step.error_message && (
                <div className="mt-1 text-xs text-destructive">
                  {t('dataset.runDetail.steps.error', { error: step.error_message })}
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
