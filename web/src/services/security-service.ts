import { get, put } from '@/utils/request'

export interface UsagePolicy {
  llm_rate_limit_per_minute?: number | null
  tool_rate_limit_per_minute?: number | null
  llm_daily_quota?: number | null
  tool_daily_quota?: number | null
}

export const getWorkspaceUsagePolicy = (): Promise<UsagePolicy> => {
  return get<UsagePolicy>('/security/limits/workspace').then(response => response.data)
}

export const updateWorkspaceUsagePolicy = async (data: UsagePolicy): Promise<UsagePolicy> => {
  return put<UsagePolicy>('/security/limits/workspace', data).then(response => response.data)
}
