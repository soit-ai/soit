import { useEffect, useRef, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'
import { toast } from 'sonner'
import { getRunDetail, type RunDetailResponse, type RunStepResponse } from '@/services/run-service'
import { useNavigate } from '@/hooks/use-navigate'
import { streamWorkflowExecution } from '@/services/workflow-service'

type MonitorStep = {
  id: string
  step_type?: string
  status?: string
  input_summary?: string | null
  output_summary?: string | null
}

function Page() {
  const { t } = useTranslation()
  const { id: workflowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [inputsText, setInputsText] = useState('{\n}')
  const [runId, setRunId] = useState<string | null>(null)
  const [status, setStatus] = useState<string>(t('workflow.detail.monitor.status.idle'))
  const [steps, setSteps] = useState<MonitorStep[]>([])
  const [executing, setExecuting] = useState(false)
  const [runDetail, setRunDetail] = useState<RunDetailResponse | null>(null)
  const streamControllerRef = useRef<AbortController | null>(null)
  const runIdRef = useRef<string | null>(null)

  const mapStatus = (value?: string | null) => {
    if (!value) return null
    if (['started', 'compiled', 'queued', 'running'].includes(value)) {
      return t('workflow.detail.monitor.status.running')
    }
    if (['succeeded', 'completed'].includes(value)) {
      return t('workflow.detail.monitor.status.completed')
    }
    if (['failed', 'canceled'].includes(value)) {
      return t('workflow.detail.monitor.status.failed')
    }
    return value
  }

  const stopStream = () => {
    if (streamControllerRef.current) {
      streamControllerRef.current.abort()
      streamControllerRef.current = null
    }
  }

  const resetState = () => {
    stopStream()
    setRunId(null)
    runIdRef.current = null
    setSteps([])
    setRunDetail(null)
    setStatus(t('workflow.detail.monitor.status.idle'))
    setExecuting(false)
  }

  useEffect(() => {
    return () => {
      stopStream()
    }
  }, [])

  const updateRunStateFromDetail = (detail: RunDetailResponse) => {
    setRunDetail(detail)
    setStatus((prev) => mapStatus(detail.run?.status) || prev)
    setSteps(
      (detail.steps || []).map((step: RunStepResponse) => ({
        id: step.id,
        step_type: step.step_type,
        status: step.status,
        input_summary: step.input_summary,
        output_summary: step.output_summary,
      }))
    )
  }

  const fetchRunDetail = async (targetRunId?: string) => {
    const activeRunId = targetRunId || runIdRef.current
    if (!activeRunId) return
    try {
      const detail = await getRunDetail(activeRunId, {
        include_steps: true,
        include_artifacts: false,
        include_cost: true,
      })
      updateRunStateFromDetail(detail)
    } catch (error) {
      toast.error(t('workflow.detail.monitor.toast.fetchDetailError'))
    }
  }

  const updateRunId = (nextRunId: string) => {
    runIdRef.current = nextRunId
    setRunId(nextRunId)
  }

  const startRun = async () => {
    if (!workflowId) return
    let inputs: Record<string, unknown> = {}
    try {
      inputs = inputsText.trim() ? JSON.parse(inputsText) : {}
    } catch (error) {
      toast.error(t('workflow.detail.monitor.toast.invalidJson'))
      return
    }

    resetState()
    setStatus(t('workflow.detail.monitor.status.running'))
    setExecuting(true)

    try {
      const controller = new AbortController()
      streamControllerRef.current = controller
      const token = localStorage.getItem('token') || ''
      const workspaceId = localStorage.getItem('workspace_id') || ''
      const headers: Record<string, string> = {}
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }
      if (workspaceId) {
        headers['X-Workspace-Id'] = workspaceId
      }
      const stream = streamWorkflowExecution(workflowId, inputs, {
        signal: controller.signal,
        headers,
      })

      for await (const event of stream) {
        if (!event) continue
        let payload: any = null
        try {
          payload = event.data ? JSON.parse(event.data) : null
        } catch (parseError) {
          payload = null
        }

        if (event.event === 'start' && payload?.run_id) {
          updateRunId(payload.run_id)
          const mappedStatus = mapStatus(payload.status)
          if (mappedStatus) {
            setStatus(mappedStatus)
          }
          continue
        }

        if (event.event === 'step' && payload?.step_id) {
          setSteps((prev) => {
            const index = prev.findIndex((item) => item.id === payload.step_id)
            const nextStep = {
              id: payload.step_id,
              step_type: payload.step_type,
              status: payload.status,
              input_summary: payload.input_summary,
              output_summary: payload.output_summary,
            }
            if (index === -1) {
              return [...prev, nextStep]
            }
            const next = [...prev]
            next[index] = { ...next[index], ...nextStep }
            return next
          })
          continue
        }

        if (event.event === 'run' && payload?.run_id) {
          updateRunId(payload.run_id)
          const mappedStatus = mapStatus(payload.status)
          if (mappedStatus) {
            setStatus(mappedStatus)
          }
          continue
        }

        if (event.event === 'complete') {
          if (payload?.run_id) {
            updateRunId(payload.run_id)
          }
          const mappedStatus = mapStatus(payload?.status) || t('workflow.detail.monitor.status.completed')
          setStatus(mappedStatus)
          await fetchRunDetail(payload?.run_id)
          break
        }

        if (event.event === 'error') {
          setStatus(t('workflow.detail.monitor.status.failed'))
          toast.error(t('workflow.detail.monitor.toast.executeError'))
          break
        }
      }
    } catch (error) {
      if (!streamControllerRef.current?.signal.aborted) {
        setStatus(t('workflow.detail.monitor.status.failed'))
        toast.error(t('workflow.detail.monitor.toast.executeError'))
      }
    } finally {
      setExecuting(false)
      streamControllerRef.current = null
    }
  }

  const refreshRun = async () => {
    await fetchRunDetail()
  }

  const costSummary = runDetail?.usage_summary

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.monitor.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.monitor.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div>
            <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.inputs.label')}</div>
            <Textarea
              value={inputsText}
              onChange={(event) => setInputsText(event.target.value)}
              placeholder={t('workflow.detail.monitor.inputs.placeholder')}
              className="mt-2 min-h-[120px]"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={startRun} disabled={executing}>
              {t('workflow.detail.monitor.actions.start')}
            </Button>
            <Button variant="outline" onClick={resetState} disabled={executing}>
              {t('workflow.detail.monitor.actions.reset')}
            </Button>
            <Button variant="ghost" onClick={refreshRun} disabled={!runId || executing}>
              {t('workflow.detail.monitor.actions.refresh')}
            </Button>
            {runId && (
              <Button variant="ghost" onClick={() => navigate(`/observe/runs/${runId}`)}>
                {t('workflow.detail.monitor.actions.viewRun')}
              </Button>
            )}
          </div>
          <div className="text-sm">
            <span className="text-muted-foreground">{t('workflow.detail.monitor.status.label')} </span>
            <span className="font-medium">{status}</span>
          </div>
          {runId && (
            <div className="text-xs text-muted-foreground">
              {t('workflow.detail.monitor.status.runId', { runId })}
            </div>
          )}
        </CardContent>
      </Card>

      {costSummary && (
        <Card>
          <CardHeader>
            <CardTitle>{t('workflow.detail.monitor.cost.title')}</CardTitle>
            <CardDescription>{t('workflow.detail.monitor.cost.description')}</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.promptTokens')}</div>
              <div className="text-sm font-medium">{costSummary.tokens_prompt}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.completionTokens')}</div>
              <div className="text-sm font-medium">{costSummary.tokens_completion}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.embeddingCount')}</div>
              <div className="text-sm font-medium">{costSummary.embedding_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.rerankCount')}</div>
              <div className="text-sm font-medium">{costSummary.rerank_count}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.totalMs')}</div>
              <div className="text-sm font-medium">{costSummary.ms_total}</div>
            </div>
            <div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.monitor.cost.storageBytes')}</div>
              <div className="text-sm font-medium">{costSummary.storage_bytes}</div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.monitor.steps.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.monitor.steps.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {steps.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.monitor.steps.empty')}</div>
          )}
          {steps.map((step) => (
            <div key={step.id} className="rounded-md border p-3">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{step.step_type || step.id}</div>
                <div className="text-xs text-muted-foreground">{step.status}</div>
              </div>
              {step.input_summary && (
                <div className="mt-2 text-xs text-muted-foreground">
                  {t('workflow.detail.monitor.steps.input', { input: step.input_summary })}
                </div>
              )}
              {step.output_summary && (
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('workflow.detail.monitor.steps.output', { output: step.output_summary })}
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
