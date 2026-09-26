import { get, post, type RequestConfigWithToast } from '@/utils/request'

export interface RegressionReport {
  id: string
  tenant_id: string
  workspace_id: string
  subject_kind: string
  subject_id: string
  subject_version_id: string
  passed: boolean
  summary_json: {
    total?: number
    passed?: number
    failed?: number
    [key: string]: unknown
  }
  metrics_json: {
    avg_latency_ms?: number
    avg_cost_amount?: number
    [key: string]: unknown
  }
  case_results_json: Array<Record<string, unknown>>
  created_by?: string | null
  created_at: string
}

export const getLatestRegressionReport = (params: {
  subject_kind: string
  subject_id: string
  subject_version_id?: string
}): Promise<RegressionReport> => {
  return get<RegressionReport>('/evaluations/regression-reports/latest', params)
}

/** One regression report, reduced to what a trend line needs. */
export interface RegressionTrendPoint {
  report_id: string
  subject_version_id: string
  dataset: string
  dataset_revision: number
  created_at: string
  passed: boolean
  total: number
  passed_count: number
  pass_rate?: number | null
  /** Cases that passed in the baseline and fail here: what this change broke. */
  regressed: number
  fixed: number
  avg_latency_ms?: number | null
  total_cost_amount?: number | null
}

export interface RegressionTrend {
  subject_kind: string
  subject_id: string
  dataset?: string | null
  points: RegressionTrendPoint[]
}

export const getRegressionTrend = (params: {
  subject_kind: string
  subject_id: string
  dataset?: string
  limit?: number
}): Promise<RegressionTrend> => {
  return get<RegressionTrend>('/evaluations/regression-reports/trend', params)
}

/** Pass rate, latency and cost of one side of a model replay. */
export interface ModelReplaySide {
  total: number
  passed: number
  failed: number
  pass_rate: number | null
  avg_latency_ms: number
  total_cost_amount: number
  errors: number
}

export interface ModelReplayCaseSide {
  passed: boolean
  latency_ms: number
  cost_amount: number
  run_id: string | null
  failure_reasons: string[]
}

export interface ModelReplaySubject {
  agent_id: string
  agent_name: string
  version_id: string
  dataset: string
  dataset_revision: number
  /** The model the published version binds: the baseline side. */
  baseline_model_ref: string | null
  baseline: ModelReplaySide
  candidate: ModelReplaySide
  /** Cases that pass on the current model and fail on the candidate. */
  regressed: string[]
  fixed: string[]
  cases: Array<{
    case_id: string
    name: string
    baseline: ModelReplayCaseSide
    candidate: ModelReplayCaseSide
  }>
}

export interface ModelReplayTotals {
  baseline: ModelReplaySide
  candidate: ModelReplaySide
  /** Candidate minus baseline. */
  delta: {
    pass_rate: number | null
    avg_latency_ms: number | null
    total_cost_amount: number | null
  }
  regressed: number
  fixed: number
  skipped: Array<{ agent_id: string; agent_name: string; reason: string }>
}

export interface ModelReplaySummary {
  id: string
  model_ref: string
  case_count: number
  totals: ModelReplayTotals
  created_by?: string | null
  created_at: string
}

export interface ModelReplay extends ModelReplaySummary {
  subjects: ModelReplaySubject[]
}

/**
 * Every case runs twice before this answers, so it is given far longer than
 * the default request timeout.
 */
export const MODEL_REPLAY_TIMEOUT_MS = 30 * 60 * 1000

export const createModelReplay = (
  data: { model_ref: string; agent_ids?: string[]; dataset?: string; max_cases?: number },
  config?: RequestConfigWithToast,
): Promise<ModelReplay> => {
  return post<ModelReplay>('/evaluations/model-replays', data, {
    timeout: MODEL_REPLAY_TIMEOUT_MS,
    ...config,
  })
}

export const listModelReplays = (config?: RequestConfigWithToast): Promise<ModelReplaySummary[]> => {
  return get<ModelReplaySummary[]>('/evaluations/model-replays', undefined, config)
}

export const getModelReplay = (
  replayId: string,
  config?: RequestConfigWithToast,
): Promise<ModelReplay> => {
  return get<ModelReplay>(`/evaluations/model-replays/${replayId}`, undefined, config)
}
