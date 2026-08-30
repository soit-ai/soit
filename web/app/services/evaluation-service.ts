import { get } from '@/utils/request'

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
