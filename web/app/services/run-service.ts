import { get } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface RunResponse {
  id: string
  trace_id?: string | null
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
}

export interface RunCostSummary {
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
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

export interface RunDetailResponse {
  run: RunResponse
  steps: RunStepResponse[]
  artifacts: RunArtifactResponse[]
  cost_summary?: RunCostSummary | null
}

export interface RunAuditLogResponse {
  run_id: string
  step_id: string
  step_type: string
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
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  trace_id?: string
  user_id?: string
  started_after?: string
  started_before?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<RunResponse>> => {
  return get<PaginatedResponse<RunResponse>>('/runs', params).then(response => response.data)
}

export const getRunCostSummary = (params?: {
  mode?: string
  kind?: string
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostSummary> => {
  return get<RunCostSummary>('/runs/costs/summary', params).then(response => response.data)
}

export const getRunCostByMode = (params?: {
  mode?: string
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  started_after?: string
  started_before?: string
  kind?: string
}): Promise<RunCostByMode[]> => {
  return get<RunCostByMode[]>('/runs/costs/by-mode', params).then(response => response.data)
}

export const getRunCostByDay = (params?: {
  mode?: string
  kind?: string
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByDay[]> => {
  return get<RunCostByDay[]>('/runs/costs/by-day', params).then(response => response.data)
}

export const getRunCostByProvider = (params?: {
  mode?: string
  kind?: string
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByProvider[]> => {
  return get<RunCostByProvider[]>('/runs/costs/by-provider', params).then(response => response.data)
}

export const getRunCostByModel = (params?: {
  mode?: string
  kind?: string
  subject_id?: string
  subject_version_id?: string
  workflow_id?: string
  status?: string
  started_after?: string
  started_before?: string
}): Promise<RunCostByModel[]> => {
  return get<RunCostByModel[]>('/runs/costs/by-model', params).then(response => response.data)
}

export const getRunDetail = (
  runId: string,
  params?: {
    include_steps?: boolean
    include_artifacts?: boolean
    include_cost?: boolean
  }
): Promise<RunDetailResponse> => {
  return get<RunDetailResponse>(`/runs/${runId}`, params).then(response => response.data)
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
}): Promise<PaginatedResponse<RunStepResponse>> => {
  return get<PaginatedResponse<RunStepResponse>>('/runs/steps', params).then(response => response.data)
}

export const listRunAudits = (params: {
  run_id: string
  step_id?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<RunAuditLogResponse>> => {
  return get<PaginatedResponse<RunAuditLogResponse>>('/runs/audits', params).then(response => response.data)
}
