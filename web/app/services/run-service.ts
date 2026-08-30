import { get } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface RunResponse {
  id: string
  trace_id?: string | null
  request_id?: string | null
  parent_run_id?: string | null
  source_run_id?: string | null
  attempt_no: number
  user_id?: string | null
  mode: string
  kind?: string | null
  subject_kind?: string | null
  subject_id?: string | null
  subject_version_id?: string | null
  status: string
  input_summary?: string | null
  output_summary?: string | null
  started_at: string
  ended_at?: string | null
  duration_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  error_step_id?: string | null
  created_at: string
  updated_at: string
  observe_summary?: RunObserveSummary | null
}

export interface RunObserveSummary {
  step_count: number
  tool_call_count: number
  child_run_count: number
  response_event_count: number
  citation_count: number
  audit_count: number
  cost_entry_count: number
}

export interface RunChargeSummary {
  entry_count: number
  /** Amounts are decimal strings, keyed by currency code. */
  amounts: Record<string, string>
}

export interface RunCostSummary {
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
  request_count?: number
  vector_count?: number
  /** Money spent under the same filters; empty when nothing was priced. */
  charges?: RunChargeSummary
}

export interface RunCostByMode {
  mode: string
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
}

export interface RunCostByDay {
  date: string
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
}

export interface RunCostByProvider {
  provider?: string | null
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
}

export interface RunCostByModel {
  model_ref?: string | null
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
}

export interface RunStepResponse {
  id: string
  run_id: string
  trace_id?: string | null
  step_id?: string | null
  step_type: string
  node_id?: string | null
  status: string
  input_summary?: string | null
  output_summary?: string | null
  metrics_json?: Record<string, unknown> | null
  error_code?: string | null
  error_message?: string | null
  error_details?: Record<string, unknown> | null
  started_at: string
  ended_at?: string | null
  created_at: string
}

export interface RunArtifactResponse {
  id: string
  run_id: string
  step_id?: string | null
  type: string
  storage_key: string
  mime?: string | null
  size_bytes?: number | null
  sha256?: string | null
  meta_json?: Record<string, unknown> | null
  created_at: string
}

export interface RunCostEntryResponse {
  id: string
  run_id: string
  step_id?: string | null
  tenant_id: string
  workspace_id: string
  currency?: string | null
  amount?: string | null
  pricing_snapshot_json: Record<string, unknown>
  billing_basis: string
  billed_quantity: string
  source_ref?: string | null
  provider?: string | null
  model_ref?: string | null
  tool_ref?: string | null
  source_port?: string | null
  operation?: string | null
  prompt_tokens?: number | null
  completion_tokens?: number | null
  total_tokens?: number | null
  latency_ms?: number | null
  request_count?: number | null
  embedding_count?: number | null
  rerank_count?: number | null
  vector_count?: number | null
  storage_bytes?: number | null
  created_at: string
}

export interface RunResponseEvent {
  id: string
  tenant_id: string
  workspace_id: string
  response_id: string
  run_id?: string | null
  thread_id?: string | null
  task_id?: string | null
  agent_id?: string | null
  sequence: number
  type: string
  source: string
  payload_json: Record<string, unknown>
  created_at: string
}

export interface RunToolCall {
  id: string
  tenant_id: string
  workspace_id: string
  response_id: string
  run_id?: string | null
  step_id?: string | null
  thread_id?: string | null
  task_id?: string | null
  agent_id?: string | null
  tool_name: string
  tool_type: string
  status: string
  arguments_json: Record<string, unknown>
  result_json: Record<string, unknown>
  metadata_json: Record<string, unknown>
  error_code?: string | null
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface RunCitation {
  chunk_id?: string | null
  document_id?: string | null
  knowledge_id?: string | null
  title?: string | null
  doc_key?: string | null
  source_uri?: string | null
  rank?: number | null
  score?: number | null
  chunk_no?: number | null
  page_no?: number | null
  snippet?: string | null
  [key: string]: unknown
}

export type RunGovernanceEvidenceStatus = 'pass' | 'fail' | 'warning' | 'not_applicable'

export interface RunGovernanceEvidence {
  key: string
  status: RunGovernanceEvidenceStatus
  label: string
  summary: string
  evidence_refs: string[]
  missing: string[]
}

export interface RunDetailResponse {
  run: RunResponse
  steps: RunStepResponse[]
  artifacts: RunArtifactResponse[]
  usage_summary?: RunCostSummary | null
  charge_summary?: RunChargeSummary | null
  costs: RunCostEntryResponse[]
  response_events: RunResponseEvent[]
  tool_calls: RunToolCall[]
  citations: RunCitation[]
  audits: RunAuditLogResponse[]
  child_runs: RunResponse[]
  governance_evidence: RunGovernanceEvidence[]
}

export interface RunAuditLogResponse {
  audit_id?: string | null
  run_id: string
  step_id: string
  step_type: string
  trace_id?: string | null
  outcome?: string | null
  evidence_artifact_id?: string | null
  gateway_type?: string | null
  request?: Record<string, unknown> | null
  response?: Record<string, unknown> | null
  timestamp?: string | null
  truncated: boolean
  preview?: string | null
  artifact_key?: string | null
}

export const listRuns = (params?: {
  mode?: string
  kind?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  trace_id?: string
  user_id?: string
  started_after?: string
  started_before?: string
  include_observe_summary?: boolean
  has_tool_call?: boolean
  has_citation?: boolean
  has_audit?: boolean
  page_token?: string
  page_size?: number
  with_total?: boolean
}): Promise<PaginatedResponse<RunResponse>> => {
  return get<PaginatedResponse<RunResponse>>('/runs', params)
}

export interface RunWindowSummary {
  since?: string | null
  until?: string | null
  total: number
  succeeded: number
  failed: number
  running: number
  /** Succeeded over settled runs; null while nothing has settled. */
  pass_rate?: number | null
  charges?: RunChargeSummary
}

export const getRunWindowSummary = (params?: {
  since?: string
  until?: string
  include_sandbox?: boolean
}): Promise<RunWindowSummary> => {
  return get<RunWindowSummary>('/runs/summary/window', params)
}

export interface RunToolInvocation {
  tool_ref?: string | null
  provider?: string | null
  invocations: number
  ms_total: number
}

/**
 * Governed tool invocations per tool inside a window, busiest first. Counted
 * from the cost ledger the tool path already writes, so a tool with no calls
 * in the window is absent rather than reported as zero.
 */
export const listToolInvocations = (params?: {
  since?: string
  until?: string
  include_sandbox?: boolean
}): Promise<RunToolInvocation[]> => {
  return get<RunToolInvocation[]>('/runs/tools/invocations', params)
}

export const getRunCostSummary = (params?: {
  mode?: string
  kind?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostSummary> => {
  return get<RunCostSummary>('/runs/costs/summary', params)
}

export const getRunCostByMode = (params?: {
  mode?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  started_after?: string
  started_before?: string
  kind?: string
}): Promise<RunCostByMode[]> => {
  return get<RunCostByMode[]>('/runs/costs/by-mode', params)
}

export const getRunCostByDay = (params?: {
  mode?: string
  kind?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByDay[]> => {
  return get<RunCostByDay[]>('/runs/costs/by-day', params)
}

export const getRunCostByProvider = (params?: {
  mode?: string
  kind?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByProvider[]> => {
  return get<RunCostByProvider[]>('/runs/costs/by-provider', params)
}

export const getRunCostByModel = (params?: {
  mode?: string
  kind?: string
  subject_kind?: string
  subject_id?: string
  subject_version_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByModel[]> => {
  return get<RunCostByModel[]>('/runs/costs/by-model', params)
}

export const getRunDetail = (
  runId: string,
  params?: {
    include_steps?: boolean
    include_artifacts?: boolean
    include_cost?: boolean
  }
): Promise<RunDetailResponse> => {
  return get<RunDetailResponse>(`/runs/${runId}`, params)
}

/** Every run that shares a trace id — the console's trace-detail root query. */
export const listRunsByTrace = (
  traceId: string,
  params?: { page_token?: string; page_size?: number },
): Promise<PaginatedResponse<RunResponse>> => {
  return get<PaginatedResponse<RunResponse>>(`/runs/trace/${traceId}`, params)
}

export interface RunStepMetric {
  step_type: string
  status: string
  count: number
  avg_latency_ms?: number | null
  min_latency_ms?: number | null
  max_latency_ms?: number | null
}

export const getRunStepMetrics = (params?: {
  run_id?: string
  step_type?: string
  started_after?: string
  started_before?: string
}): Promise<RunStepMetric[]> => {
  return get<RunStepMetric[]>('/runs/steps/metrics', params)
}

export const listRunSteps = (params?: {
  run_id?: string
  trace_id?: string
  step_id?: string
  step_type?: string
  status?: string
  node_id?: string
  started_after?: string
  started_before?: string
  ended_after?: string
  ended_before?: string
  page_token?: string
  page_size?: number
  with_total?: boolean
}): Promise<PaginatedResponse<RunStepResponse>> => {
  return get<PaginatedResponse<RunStepResponse>>('/runs/steps', params)
}

export const listRunAudits = (params: {
  run_id?: string
  step_id?: string
  step_type?: string
  gateway_type?: string
  since?: string
  until?: string
  page_token?: string
  page_size?: number
  with_total?: boolean
}): Promise<PaginatedResponse<RunAuditLogResponse>> => {
  return get<PaginatedResponse<RunAuditLogResponse>>('/runs/audits', params)
}
