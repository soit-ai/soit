import { get, put } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
  has_next?: boolean
}

export interface EgressPolicy {
  scope: string
  allowlist: string[]
  blocklist: string[]
}

export interface EgressPolicyAudit {
  id: string
  tenant_id: string
  workspace_id?: string | null
  scope: string
  allowlist: string[]
  blocklist: string[]
  created_by?: string | null
  created_at: string
}

export interface UsagePolicy {
  llm_rate_limit_per_minute?: number | null
  tool_rate_limit_per_minute?: number | null
  llm_daily_quota?: number | null
  tool_daily_quota?: number | null
}

export const getWorkspaceEgressPolicy = (): Promise<EgressPolicy> => {
  return get<EgressPolicy>('/security/egress/workspace').then(response => response.data)
}

export const updateWorkspaceEgressPolicy = async (data: Pick<EgressPolicy, 'allowlist' | 'blocklist'>): Promise<EgressPolicy> => {
  return put<EgressPolicy>('/security/egress/workspace', data).then(response => response.data)
}

export const listEgressPolicyAudits = (params?: {
  scope?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<EgressPolicyAudit>> => {
  return get<PaginatedResponse<EgressPolicyAudit>>('/security/egress/audits', params).then(response => response.data)
}

export const getWorkspaceUsagePolicy = (): Promise<UsagePolicy> => {
  return get<UsagePolicy>('/security/limits/workspace').then(response => response.data)
}

export const updateWorkspaceUsagePolicy = async (data: UsagePolicy): Promise<UsagePolicy> => {
  return put<UsagePolicy>('/security/limits/workspace', data).then(response => response.data)
}
