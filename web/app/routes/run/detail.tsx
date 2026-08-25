import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { AlertTriangle, ArrowLeft, CheckCircle2, ExternalLink, MinusCircle, RefreshCw, XCircle } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { toast } from 'sonner'
import { useNavigate } from '@/hooks/use-navigate'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'
import {
  getRunDetail,
  type RunCitation,
  type RunAuditLogResponse,
  type RunDetailResponse,
  type RunGovernanceEvidence,
  type RunGovernanceEvidenceStatus,
  type RunResponseEvent,
  type RunStepResponse,
  type RunToolCall,
} from '@/services/run-service'

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

const formatPayloadPreview = (payload?: Record<string, unknown> | null) => {
  if (!payload || Object.keys(payload).length === 0) return '-'
  try {
    const serialized = JSON.stringify(payload)
    return serialized.length > 220 ? `${serialized.slice(0, 220)}...` : serialized
  } catch {
    return '[unserializable payload]'
  }
}

const getCitationLabel = (citation: RunCitation) => {
  return citation.title || citation.doc_key || citation.source_uri || citation.document_id || citation.chunk_id || '-'
}

const getCitationSource = (citation: RunCitation) => {
  return citation.doc_key || citation.source_uri || citation.document_id || citation.chunk_id || null
}

const getEventKey = (event: RunResponseEvent) => `${event.response_id}:${event.sequence}:${event.id}`

const getAuditKey = (audit: RunAuditLogResponse, index: number) => `${audit.run_id}:${audit.step_id}:${audit.timestamp || index}`

const getAuditStatus = (audit: RunAuditLogResponse) => {
  const success = audit.response?.success
  if (typeof success === 'boolean') return success ? 'succeeded' : 'failed'
  return audit.response ? 'recorded' : '-'
}

const getWorkflowRunId = (toolCall: RunToolCall) => {
  const result = toolCall.result_json?.result
  if (!result || typeof result !== 'object' || Array.isArray(result)) return null
  const workflowRunId = (result as Record<string, unknown>).workflow_run_id
  return typeof workflowRunId === 'string' && workflowRunId ? workflowRunId : null
}

const getToolTypeKey = (toolType?: string | null) => {
  if (toolType === 'builtin' || toolType === 'workflow') return toolType
  return 'unknown'
}

const governanceStatusOrder: RunGovernanceEvidenceStatus[] = ['pass', 'warning', 'fail', 'not_applicable']

const getGovernanceStatusTone = (status: RunGovernanceEvidenceStatus) => {
  if (status === 'pass') return 'border-success/20 bg-success/12 text-success-foreground dark:border-success/30'
  if (status === 'warning') return 'border-warning/20 bg-warning/12 text-warning-foreground dark:border-warning/30'
  if (status === 'fail') return 'border-danger/20 bg-danger/12 text-danger-foreground dark:border-danger/30'
  return 'border-border bg-muted text-muted-foreground'
}

const GovernanceStatusIcon = ({ status }: { status: RunGovernanceEvidenceStatus }) => {
  if (status === 'pass') return <CheckCircle2 className="h-4 w-4" />
  if (status === 'warning') return <AlertTriangle className="h-4 w-4" />
  if (status === 'fail') return <XCircle className="h-4 w-4" />
  return <MinusCircle className="h-4 w-4" />
}

const countGovernanceEvidence = (items: RunGovernanceEvidence[]) => {
  return governanceStatusOrder.reduce<Record<RunGovernanceEvidenceStatus, number>>((acc, status) => {
    acc[status] = items.filter((item) => item.status === status).length
    return acc
  }, {
    pass: 0,
    warning: 0,
    fail: 0,
    not_applicable: 0,
  })
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
      const runDetail = await getRunDetail(runId, {
        include_steps: true,
        include_cost: true,
        include_artifacts: true,
      })
      setDetail(runDetail)
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
  const costSummary = detail?.usage_summary
  const costs = detail?.costs ?? []
  const citations = detail?.citations ?? []
  const childRuns = detail?.child_runs ?? []
  const toolCalls = detail?.tool_calls ?? []
  const responseEvents = detail?.response_events ?? []
  const audits = detail?.audits ?? []
  const governanceEvidence = detail?.governance_evidence ?? []
  const governanceCounts = countGovernanceEvidence(governanceEvidence)

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2">
          <Button variant="ghost" onClick={() => navigate('/observe/runs')}>
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
              <div className="text-sm font-medium">{run?.subject_version_id ?? '-'}</div>
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
          <CardTitle>{t('run.detail.governance.title')}</CardTitle>
          <CardDescription>{t('run.detail.governance.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {governanceEvidence.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.governance.empty')}</div>
          )}
          {governanceEvidence.length > 0 && (
            <>
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                {governanceStatusOrder.map((status) => (
                  <div key={status} className={`rounded-md border px-3 py-2 text-sm font-medium ${getGovernanceStatusTone(status)}`}>
                    {t(`run.detail.governance.counts.${status}`, { count: governanceCounts[status] })}
                  </div>
                ))}
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                {governanceEvidence.map((item) => (
                  <div key={item.key} className="rounded-md border p-3">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div className="min-w-0">
                        <div className="text-sm font-medium">{item.label}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{item.summary}</div>
                      </div>
                      <div className={`inline-flex w-fit shrink-0 items-center gap-1 rounded-full border px-2 py-1 text-xs font-medium ${getGovernanceStatusTone(item.status)}`}>
                        <GovernanceStatusIcon status={item.status} />
                        {t(`run.detail.governance.status.${item.status}`)}
                      </div>
                    </div>
                    {item.evidence_refs.length > 0 && (
                      <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                        {t('run.detail.governance.refs', { refs: item.evidence_refs.join(', ') })}
                      </div>
                    )}
                    {item.missing.length > 0 && (
                      <div className="mt-2 break-all text-xs text-destructive">
                        {t('run.detail.governance.missing', { missing: item.missing.join(', ') })}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
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
            <div className="space-y-4">
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
              {costs.length > 0 && (
                <div className="space-y-2">
                  {costs.map((cost) => (
                    <div key={cost.id} className="rounded-md border p-2 text-xs text-muted-foreground">
                      {cost.billing_basis} · {cost.billed_quantity} · {cost.model_ref || cost.tool_ref || cost.provider || '-'}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.failure.title')}</CardTitle>
          <CardDescription>{t('run.detail.failure.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="text-sm font-medium">
            {t('run.detail.failure.status', {
              status: run?.status ?? '-',
              step: run?.error_step_id ?? '-',
            })}
          </div>
          <div className="text-sm text-muted-foreground">
            {run?.error_message || t('run.detail.failure.noError')}
          </div>
          {sortedSteps.filter((step) => step.status === 'failed' || step.error_message).length > 0 && (
            <div className="space-y-2">
              {sortedSteps
                .filter((step) => step.status === 'failed' || step.error_message)
                .map((step) => (
                  <div key={step.id} className="rounded-md border p-2 text-xs text-muted-foreground">
                    {step.step_type} · {step.status} · {step.error_message || step.error_code || '-'}
                  </div>
                ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.citations.title')}</CardTitle>
          <CardDescription>{t('run.detail.citations.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {citations.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.citations.empty')}</div>
          )}
          {citations.map((citation, index) => {
            const source = getCitationSource(citation)
            return (
              <div key={`${citation.chunk_id || citation.document_id || index}`} className="rounded-md border p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="text-sm font-medium">{getCitationLabel(citation)}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('run.detail.responses.citationMeta', {
                      rank: citation.rank ?? index + 1,
                      score: typeof citation.score === 'number' ? citation.score.toFixed(2) : '-',
                    })}
                  </div>
                </div>
                {source && (
                  <div className="mt-1 break-all text-xs text-muted-foreground">
                    Source: {source}
                  </div>
                )}
                <div className="mt-1 text-xs text-muted-foreground">
                  {t('run.detail.responses.citationLocation', {
                    knowledge: citation.knowledge_id || '-',
                    chunk: citation.chunk_no ?? citation.chunk_id ?? '-',
                    page: citation.page_no ?? '-',
                  })}
                </div>
                {citation.snippet && (
                  <div className="mt-2 text-xs text-muted-foreground">{citation.snippet}</div>
                )}
              </div>
            )
          })}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.childRuns.title')}</CardTitle>
          <CardDescription>{t('run.detail.childRuns.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {childRuns.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.childRuns.empty')}</div>
          )}
          {childRuns.map((childRun) => (
            <div key={childRun.id} className="rounded-md border p-3">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div>
                  <div className="text-sm font-medium">{childRun.id}</div>
                  <div className="text-xs text-muted-foreground">
                    {childRun.mode} · {childRun.status} · {formatDuration(childRun.duration_ms)}
                  </div>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => navigate(`/observe/runs/${childRun.id}`)}
                >
                  <ExternalLink className="mr-1 h-3.5 w-3.5" />
                  {t('run.detail.responses.openWorkflowRun')}
                </Button>
              </div>
              {childRun.output_summary && (
                <div className="mt-2 text-xs text-muted-foreground">{childRun.output_summary}</div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.tools.title')}</CardTitle>
          <CardDescription>{t('run.detail.tools.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {toolCalls.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.tools.empty')}</div>
          )}
          {toolCalls.map((toolCall) => {
            const workflowRunId = getWorkflowRunId(toolCall)
            return (
              <div key={toolCall.id} className="rounded-md border p-3">
                <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                  <div className="space-y-1">
                    <div className="text-sm font-medium">{toolCall.tool_name}</div>
                    <div className="text-xs text-muted-foreground">
                      {t('run.detail.responses.toolMeta', {
                        type: t(`run.detail.responses.toolTypes.${getToolTypeKey(toolCall.tool_type)}`),
                        status: toolCall.status,
                        step: toolCall.step_id || '-',
                      })}
                    </div>
                  </div>
                  {workflowRunId && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 px-2 text-xs"
                      onClick={() => navigate(`/observe/runs/${workflowRunId}`)}
                    >
                      <ExternalLink className="mr-1 h-3.5 w-3.5" />
                      {t('run.detail.responses.openWorkflowRun')}
                    </Button>
                  )}
                </div>
                <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                  {t('run.detail.responses.toolArgs', {
                    args: formatPayloadPreview(toolCall.arguments_json),
                  })}
                </div>
                <div className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                  {t('run.detail.responses.toolResult', {
                    result: formatPayloadPreview(toolCall.result_json),
                  })}
                </div>
              </div>
            )
          })}
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
          <CardTitle>{t('run.detail.audits.title')}</CardTitle>
          <CardDescription>{t('run.detail.audits.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {audits.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.audits.empty')}</div>
          )}
          {audits.map((audit, index) => (
            <div key={getAuditKey(audit, index)} className="rounded-md border p-3">
              <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                <div className="space-y-1">
                  <div className="text-sm font-medium">{audit.gateway_type || audit.step_type}</div>
                  <div className="text-xs text-muted-foreground">
                    {t('run.detail.audits.meta', {
                      status: t(`run.detail.audits.status.${getAuditStatus(audit)}`),
                      step: audit.step_id,
                      timestamp: formatTimestamp(audit.timestamp),
                    })}
                  </div>
                  {audit.artifact_key && (
                    <div className="text-xs text-muted-foreground">
                      {t('run.detail.audits.artifact', { artifact: audit.artifact_key })}
                    </div>
                  )}
                </div>
                <div className="text-xs text-muted-foreground">
                  {audit.truncated ? t('run.detail.audits.truncated') : t('run.detail.audits.complete')}
                </div>
              </div>
              {audit.preview && (
                <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                  {t('run.detail.audits.preview', { preview: audit.preview })}
                </div>
              )}
              <div className="mt-2 grid gap-2 md:grid-cols-2">
                <div className="rounded border bg-muted/30 p-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t('run.detail.audits.requestTitle')}
                  </div>
                  <div className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                    {formatPayloadPreview(audit.request)}
                  </div>
                </div>
                <div className="rounded border bg-muted/30 p-2">
                  <div className="text-xs font-medium text-muted-foreground">
                    {t('run.detail.audits.responseTitle')}
                  </div>
                  <div className="mt-1 break-all font-mono text-[11px] text-muted-foreground">
                    {formatPayloadPreview(audit.response)}
                  </div>
                </div>
              </div>
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

      <Card>
        <CardHeader>
          <CardTitle>{t('run.detail.responses.title')}</CardTitle>
          <CardDescription>{t('run.detail.responses.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {responseEvents.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('run.detail.responses.empty')}</div>
          )}
          {responseEvents.map((event) => (
            <div key={getEventKey(event)} className="rounded-md border p-3">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-medium">{event.type}</div>
                <div className="text-xs text-muted-foreground">
                  #{event.sequence} · {formatTimestamp(event.created_at)}
                </div>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {event.source} · {event.response_id}
              </div>
              <div className="mt-2 break-all font-mono text-[11px] text-muted-foreground">
                {formatPayloadPreview(event.payload_json)}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
