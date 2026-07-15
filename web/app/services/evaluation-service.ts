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
