import request, { del, get, patch, post, type RequestConfigWithToast } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

import { filenameOf, saveBlob } from './ledger-service'

export interface RegressionReport {
  id: string
  tenant_id: string
  workspace_id: string
  subject_kind: string
  subject_id: string
  subject_version_id: string
  passed: boolean
  /** The dataset this report ran, at the revision it ran. */
  dataset: string
  dataset_revision: number
  /** The comparable report it was measured against, if there was one. */
  baseline_report_id?: string | null
  /** Cases that passed in the baseline and fail here. */
  regressed_case_ids_json: string[]
  fixed_case_ids_json: string[]
  summary_json: {
    total?: number
    passed?: number
    failed?: number
    regressed?: number
    fixed?: number
    /** Present when the cases ran on another model; such a report is no baseline. */
    model_ref?: string
    [key: string]: unknown
  }
  metrics_json: {
    avg_latency_ms?: number
    total_cost_amount?: number
    [key: string]: unknown
  }
  case_results_json: RegressionCaseResult[]
  created_by?: string | null
  created_at: string
}

/** One case's outcome in a report. */
export interface RegressionCaseResult {
  case_id: string
  name: string
  passed: boolean
  run_id?: string | null
  latency_ms?: number
  cost?: { amount?: number; currency?: string }
  failure_reasons?: string[]
  error?: string
  judge?: { score?: number; reasoning?: string; model?: string; min_score?: number; error?: string }
}

/** A report without its per-case results, as lists return it. */
export type RegressionReportSummary = Omit<RegressionReport, 'case_results_json'>

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

export const getRegressionTrend = (
  params: {
    subject_kind: string
    subject_id: string
    dataset?: string
    limit?: number
  },
  config?: RequestConfigWithToast,
): Promise<RegressionTrend> => {
  return get<RegressionTrend>('/evaluations/regression-reports/trend', params, config)
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

// ---------------------------------------------------------------------------
// Datasets: named, versioned sets of cases an agent is evaluated against.
// ---------------------------------------------------------------------------

/** What a case must satisfy; at least one key. See `kernel/specs/v1/dataset_case_spec`. */
export interface ExpectedFeatures {
  minimum_output_terms?: string[]
  max_latency_ms?: number
  max_cost_amount?: number
  llm_judge?: { rubric: string; min_score?: number; model?: string }
  [key: string]: unknown
}

export interface DatasetLatestReport {
  id: string
  passed: boolean
  total: number
  passed_count: number
  pass_rate?: number | null
  dataset_revision: number
  subject_version_id: string
  /** Set when the cases ran on a model other than the version's own. */
  model_ref?: string | null
  created_at: string
}

export interface Dataset {
  id: string
  subject_kind: string
  subject_id: string
  name: string
  description: string
  revision: number
  status: 'active' | 'archived'
  case_count: number
  latest_report?: DatasetLatestReport | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface DatasetCase {
  id: string
  name: string
  /** Text sent to the agent, or an object stored as given (for example `messages`). */
  input: string | Record<string, unknown>
  expected_features_json: ExpectedFeatures
  dataset: string
  /** The dataset revision that last touched this case. */
  dataset_revision: number
  /** Empty for cases written or imported directly rather than frozen from a run. */
  source_run_id?: string | null
  created_by?: string | null
  created_at: string
}

export interface DatasetVersion {
  id: string
  dataset_id: string
  revision: number
  case_count: number
  content_hash: string
  changes: { added: number; removed: number; changed: number }
  note: string
  created_by?: string | null
  created_at: string
}

export interface DatasetVersionDetail extends DatasetVersion {
  snapshot: Array<{
    name: string
    input: string | Record<string, unknown>
    expected_features: ExpectedFeatures
  }>
}

export const listDatasets = (
  params?: { subject_id?: string; status?: 'active' | 'archived' | ''; limit?: number; offset?: number },
  config?: RequestConfigWithToast,
): Promise<Dataset[]> => get<Dataset[]>('/evaluations/datasets', params, config)

export const getDataset = (datasetId: string, config?: RequestConfigWithToast): Promise<Dataset> =>
  get<Dataset>(`/evaluations/datasets/${datasetId}`, undefined, config)

export const createDataset = (
  data: { subject_id: string; name: string; description?: string },
  config?: RequestConfigWithToast,
): Promise<Dataset> => post<Dataset>('/evaluations/datasets', { subject_kind: 'agent', ...data }, config)

export const updateDataset = (
  datasetId: string,
  data: { description?: string; status?: 'active' | 'archived' },
  config?: RequestConfigWithToast,
): Promise<Dataset> => patch<Dataset>(`/evaluations/datasets/${datasetId}`, data, config)

export const listDatasetCases = (
  datasetId: string,
  params?: { q?: string; page_token?: string; page_size?: number; with_total?: boolean },
  config?: RequestConfigWithToast,
): Promise<PaginatedResponse<DatasetCase>> =>
  get<PaginatedResponse<DatasetCase>>(`/evaluations/datasets/${datasetId}/cases`, params, config)

export interface DatasetCaseInput {
  name: string
  input: string | Record<string, unknown>
  expected_features: ExpectedFeatures
  note?: string
}

export const addDatasetCase = (
  datasetId: string,
  data: DatasetCaseInput,
  config?: RequestConfigWithToast,
): Promise<DatasetCase> => post<DatasetCase>(`/evaluations/datasets/${datasetId}/cases`, data, config)

export const updateDatasetCase = (
  datasetId: string,
  caseId: string,
  data: Partial<DatasetCaseInput>,
  config?: RequestConfigWithToast,
): Promise<DatasetCase> =>
  patch<DatasetCase>(`/evaluations/datasets/${datasetId}/cases/${caseId}`, data, config)

/** Takes the case out of the dataset; answers with the dataset at its new revision. */
export const removeDatasetCase = (
  datasetId: string,
  caseId: string,
  config?: RequestConfigWithToast,
): Promise<Dataset> =>
  del<Dataset>(`/evaluations/datasets/${datasetId}/cases/${caseId}`, undefined, config)

/** What the server accepts in one import. */
export const IMPORT_MAX_LINES = 1000
export const IMPORT_MAX_BYTES = 2 * 1024 * 1024

/** Adds the cases of a JSONL file, all or none; a bad line fails the whole import. */
export const importDatasetCases = (
  datasetId: string,
  data: { content: string; note?: string },
  config?: RequestConfigWithToast,
): Promise<{ imported: number; dataset: Dataset }> =>
  post(`/evaluations/datasets/${datasetId}/import`, data, config)

/** One line the server refused, from a failed import response. */
export interface ImportLineError {
  line?: number
  message: string
}

/** Every refused line of a failed import, with the line numbers the server counted. */
export function importLineErrors(error: unknown): ImportLineError[] {
  const details = (
    error as { response?: { data?: { details?: { errors?: unknown; names?: unknown } } } } | null
  )?.response?.data?.details
  if (!details) return []
  // Case names that already exist in the dataset are refused as a group, with
  // the names rather than line numbers.
  if (Array.isArray(details.names)) {
    return details.names.map((name: unknown) => ({ message: String(name) }))
  }
  if (!Array.isArray(details.errors)) return []
  return details.errors.map((item: { line?: unknown; message?: unknown }) => ({
    line: typeof item.line === 'number' ? item.line : undefined,
    message: String(item.message ?? ''),
  }))
}

/** Downloads the dataset as JSONL, in the format import reads. */
export async function exportDatasetCases(datasetId: string, fallbackName: string): Promise<string> {
  const config: RequestConfigWithToast = { responseType: 'blob', suppressErrorToast: true }
  const response = await request.get<Blob>(`/evaluations/datasets/${datasetId}/export`, config)
  const filename = filenameOf(
    response.headers?.['content-disposition'],
    `soit-dataset-${fallbackName}.jsonl`,
  )
  saveBlob(response.data, filename)
  return filename
}

export const listDatasetVersions = (
  datasetId: string,
  params?: { limit?: number; offset?: number },
  config?: RequestConfigWithToast,
): Promise<DatasetVersion[]> =>
  get<DatasetVersion[]>(`/evaluations/datasets/${datasetId}/versions`, params, config)

export const getDatasetVersion = (
  datasetId: string,
  revision: number,
  config?: RequestConfigWithToast,
): Promise<DatasetVersionDetail> =>
  get<DatasetVersionDetail>(
    `/evaluations/datasets/${datasetId}/versions/${revision}`,
    undefined,
    config,
  )

// ---------------------------------------------------------------------------
// Reports and runs
// ---------------------------------------------------------------------------

export const listReports = (
  params?: {
    subject_kind?: string
    subject_id?: string
    dataset?: string
    passed?: boolean
    page_token?: string
    page_size?: number
    with_total?: boolean
  },
  config?: RequestConfigWithToast,
): Promise<PaginatedResponse<RegressionReportSummary>> =>
  get<PaginatedResponse<RegressionReportSummary>>('/evaluations/reports', params, config)

export const getReport = (
  reportId: string,
  config?: RequestConfigWithToast,
): Promise<RegressionReport> =>
  get<RegressionReport>(`/evaluations/reports/${reportId}`, undefined, config)

/**
 * Every case runs before this answers, so it is given far longer than the
 * default request timeout.
 */
export const EVALUATION_RUN_TIMEOUT_MS = 30 * 60 * 1000

/** Runs a dataset on an agent version now and answers with the recorded report. */
export const runEvaluation = (
  data: {
    subject_id: string
    dataset: string
    subject_version_id?: string
    model_ref?: string
    max_cases?: number
  },
  config?: RequestConfigWithToast,
): Promise<RegressionReport> =>
  post<RegressionReport>(
    '/evaluations/run',
    { subject_kind: 'agent', ...data },
    { timeout: EVALUATION_RUN_TIMEOUT_MS, ...config },
  )
