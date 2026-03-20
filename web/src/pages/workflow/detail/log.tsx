import { useCallback, useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { ChevronDown, RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { listRuns, listRunSteps, type RunResponse, type RunStepResponse } from '@/services/run-service'
import { pauseRun, replayRun, resumeRun, retryRun } from '@/services/workflow-service'
import { toast } from 'sonner'
import { useNavigate } from '@/hooks/use-navigate'

type StepFilters = {
  status: string
  stepType: string
}

type RunAction = 'pause' | 'resume' | 'retry' | 'replay'

const createDefaultFilters = (): StepFilters => ({
  status: 'all',
  stepType: '',
})

const formatDate = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString()
}

const formatDuration = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  return `${value} ms`
}

function Page() {
  const { t } = useTranslation()
  const { id: workflowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [selectedRunId, setSelectedRunId] = useState<string>('')
  const [filters, setFilters] = useState<StepFilters>(() => createDefaultFilters())
  const [appliedFilters, setAppliedFilters] = useState<StepFilters>(() => createDefaultFilters())
  const [steps, setSteps] = useState<RunStepResponse[]>([])
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [loadingSteps, setLoadingSteps] = useState(false)
  const [runActionLoading, setRunActionLoading] = useState<RunAction | null>(null)

  const fetchRuns = useCallback(async () => {
    if (!workflowId) return
    try {
      setLoadingRuns(true)
      const data = await listRuns({
        workflow_id: workflowId,
        mode: 'workflow',
        page_size: 50,
      })
      const items = data.items || []
      setRuns(items)
      if (items.length === 0) {
        setSelectedRunId('')
      } else if (!selectedRunId) {
        setSelectedRunId(items[0].id)
      } else if (!items.some((run) => run.id === selectedRunId)) {
        setSelectedRunId(items[0].id)
      }
    } catch (error) {
      toast.error(t('workflow.detail.log.toast.fetchRunsError'))
      console.error('Failed to fetch workflow runs:', error)
    } finally {
      setLoadingRuns(false)
    }
  }, [workflowId, selectedRunId, t])

  const fetchSteps = useCallback(async () => {
    if (!selectedRunId) {
      setSteps([])
      return
    }
    try {
      setLoadingSteps(true)
      const data = await listRunSteps({
        run_id: selectedRunId,
        step_type: appliedFilters.stepType.trim() || undefined,
        status: appliedFilters.status === 'all' ? undefined : appliedFilters.status,
        page_size: 200,
      })
      setSteps(data.items || [])
    } catch (error) {
      toast.error(t('workflow.detail.log.toast.fetchStepsError'))
      console.error('Failed to fetch workflow steps:', error)
    } finally {
      setLoadingSteps(false)
    }
  }, [selectedRunId, appliedFilters, t])

  useEffect(() => {
    fetchRuns()
  }, [fetchRuns])

  useEffect(() => {
    fetchSteps()
  }, [fetchSteps])

  const applyFilters = () => {
    setAppliedFilters({
      status: filters.status,
      stepType: filters.stepType,
    })
  }

  const resetFilters = () => {
    const nextFilters = createDefaultFilters()
    setFilters(nextFilters)
    setAppliedFilters(nextFilters)
  }

  const runOptions = useMemo(() => runs, [runs])
  const selectedRun = useMemo(
    () => runs.find((run) => run.id === selectedRunId) || null,
    [runs, selectedRunId]
  )
  const selectedRunStatus = (selectedRun?.status || '').toLowerCase()
  const failedStep = useMemo(() => {
    if (!selectedRun) return null
    const byErrorStepId = selectedRun.error_step_id
      ? steps.find(
          (step) =>
            step.step_id === selectedRun.error_step_id ||
            step.id === selectedRun.error_step_id ||
            step.node_id === selectedRun.error_step_id
        )
      : null
    return byErrorStepId || steps.find((step) => step.status.toLowerCase() === 'failed') || null
  }, [selectedRun, steps])

  const handleRunAction = async (action: RunAction) => {
    if (!workflowId || !selectedRun) {
      return
    }
    if ((action === 'retry' || action === 'replay') && !window.confirm(t(`workflow.detail.log.confirm.${action}`))) {
      return
    }
    try {
      setRunActionLoading(action)
      if (action === 'pause') {
        await pauseRun(workflowId, selectedRun.id)
      } else if (action === 'resume') {
        await resumeRun(workflowId, selectedRun.id)
      } else if (action === 'retry') {
        await retryRun(workflowId, selectedRun.id)
      } else {
        await replayRun(workflowId, selectedRun.id)
      }
      toast.success(t(`workflow.detail.log.toast.${action}Success`))
      await fetchRuns()
      await fetchSteps()
    } catch (error: any) {
      toast.error(error?.message || t(`workflow.detail.log.toast.${action}Error`))
      console.error(`Failed to ${action} workflow run:`, error)
    } finally {
      setRunActionLoading(null)
    }
  }

  const canPause = selectedRunStatus === 'running'
  const canResume = selectedRunStatus === 'paused'
  const canRetry = selectedRunStatus === 'failed'
  const canReplay = selectedRunStatus === 'failed' || selectedRunStatus === 'succeeded'
  const disableRunActions = loadingRuns || loadingSteps || !selectedRun

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="rounded-lg border bg-card p-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-1 flex-wrap gap-3">
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('workflow.detail.log.filters.run.label')}</span>
              <Select value={selectedRunId} onValueChange={setSelectedRunId}>
                <SelectTrigger className="w-full sm:w-[260px]">
                  <SelectValue placeholder={t('workflow.detail.log.filters.run.placeholder')} />
                </SelectTrigger>
                <SelectContent>
                  {runOptions.length === 0 && (
                    <SelectItem value="empty" disabled>
                      {t('workflow.detail.log.filters.run.empty')}
                    </SelectItem>
                  )}
                  {runOptions.map((run) => (
                    <SelectItem key={run.id} value={run.id}>
                      {run.id}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('workflow.detail.log.filters.status.label')}</span>
              <Select value={filters.status} onValueChange={(value) => setFilters((prev) => ({ ...prev, status: value }))}>
                <SelectTrigger className="w-full sm:w-[160px]">
                  <SelectValue placeholder={t('workflow.detail.log.filters.status.label')} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t('workflow.detail.log.filters.status.all')}</SelectItem>
                  <SelectItem value="queued">{t('workflow.detail.log.filters.status.queued')}</SelectItem>
                  <SelectItem value="running">{t('workflow.detail.log.filters.status.running')}</SelectItem>
                  <SelectItem value="paused">{t('workflow.detail.log.filters.status.paused')}</SelectItem>
                  <SelectItem value="succeeded">{t('workflow.detail.log.filters.status.succeeded')}</SelectItem>
                  <SelectItem value="failed">{t('workflow.detail.log.filters.status.failed')}</SelectItem>
                  <SelectItem value="skipped">{t('workflow.detail.log.filters.status.skipped')}</SelectItem>
                  <SelectItem value="canceled">{t('workflow.detail.log.filters.status.canceled')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1">
              <span className="text-xs text-muted-foreground">{t('workflow.detail.log.filters.stepType.label')}</span>
              <Input
                value={filters.stepType}
                onChange={(event) => setFilters((prev) => ({ ...prev, stepType: event.target.value }))}
                placeholder={t('workflow.detail.log.filters.stepType.placeholder')}
                className="w-full sm:w-[200px]"
              />
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="outline"
              onClick={() => handleRunAction('pause')}
              disabled={disableRunActions || !canPause || runActionLoading !== null}
            >
              {runActionLoading === 'pause'
                ? t('workflow.detail.log.actions.pausing')
                : t('workflow.detail.log.actions.pause')}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleRunAction('resume')}
              disabled={disableRunActions || !canResume || runActionLoading !== null}
            >
              {runActionLoading === 'resume'
                ? t('workflow.detail.log.actions.resuming')
                : t('workflow.detail.log.actions.resume')}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleRunAction('retry')}
              disabled={disableRunActions || !canRetry || runActionLoading !== null}
            >
              {runActionLoading === 'retry'
                ? t('workflow.detail.log.actions.retrying')
                : t('workflow.detail.log.actions.retry')}
            </Button>
            <Button
              variant="outline"
              onClick={() => handleRunAction('replay')}
              disabled={disableRunActions || !canReplay || runActionLoading !== null}
            >
              {runActionLoading === 'replay'
                ? t('workflow.detail.log.actions.replaying')
                : t('workflow.detail.log.actions.replay')}
            </Button>
            <Button variant="outline" onClick={() => { fetchRuns(); fetchSteps() }} disabled={loadingRuns || loadingSteps}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loadingRuns || loadingSteps ? 'animate-spin' : ''}`} />
              {t('workflow.detail.log.actions.refresh')}
            </Button>
          </div>
        </div>
      </div>

      {selectedRun && (
        <Card>
          <CardHeader>
            <CardTitle>{t('workflow.detail.log.runSummary.title')}</CardTitle>
            <CardDescription>{t('workflow.detail.log.runSummary.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
              <div>
                <div className="text-xs text-muted-foreground">{t('workflow.detail.log.runSummary.fields.status')}</div>
                <div className="mt-1">
                  <Badge variant="outline">{selectedRun.status}</Badge>
                </div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('workflow.detail.log.runSummary.fields.startedAt')}</div>
                <div className="text-sm font-medium">{formatDate(selectedRun.started_at)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('workflow.detail.log.runSummary.fields.endedAt')}</div>
                <div className="text-sm font-medium">{formatDate(selectedRun.ended_at)}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{t('workflow.detail.log.runSummary.fields.duration')}</div>
                <div className="text-sm font-medium">{formatDuration(selectedRun.duration_ms)}</div>
              </div>
            </div>

            {selectedRun.error_message && (
              <div className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive">
                <div className="font-medium">{t('workflow.detail.log.runSummary.errorTitle')}</div>
                <div className="mt-1 break-words">{selectedRun.error_message}</div>
                {selectedRun.error_code && (
                  <div className="mt-1 text-xs">
                    {t('workflow.detail.log.runSummary.errorCode', { code: selectedRun.error_code })}
                  </div>
                )}
              </div>
            )}

            {failedStep && (
              <div className="rounded-md border p-3 text-sm">
                <div className="font-medium">{t('workflow.detail.log.runSummary.failedStepTitle')}</div>
                <div className="mt-1 text-muted-foreground">
                  {t('workflow.detail.log.runSummary.failedStep', {
                    stepType: failedStep.step_type,
                    stepId: failedStep.step_id || failedStep.id,
                  })}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.log.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.log.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.log.empty')}</div>
          )}
          {steps.map((step) => (
            <div key={step.id} className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{step.step_type}</div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{step.status}</span>
                  <Button size="sm" variant="ghost" onClick={() => navigate(`/observability/runs/${step.run_id}`)}>
                    {t('workflow.detail.log.actions.viewRun')}
                  </Button>
                </div>
              </div>
              {step.input_summary && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {t('workflow.detail.log.fields.input', { input: step.input_summary })}
                </div>
              )}
              {step.output_summary && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('workflow.detail.log.fields.output', { output: step.output_summary })}
                </div>
              )}
              {step.error_message && (
                <div className="mt-2 text-xs text-destructive">
                  {t('workflow.detail.log.fields.error', { error: step.error_message })}
                </div>
              )}
              {step.error_details && (
                <Collapsible>
                  <CollapsibleTrigger className="mt-2 inline-flex items-center text-xs text-muted-foreground">
                    {t('workflow.detail.log.fields.errorDetails')}
                    <ChevronDown className="ml-1 h-3 w-3" />
                  </CollapsibleTrigger>
                  <CollapsibleContent className="mt-2 rounded-md bg-muted p-2 text-xs text-muted-foreground">
                    <pre className="whitespace-pre-wrap break-words">
                      {JSON.stringify(step.error_details, null, 2)}
                    </pre>
                  </CollapsibleContent>
                </Collapsible>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
