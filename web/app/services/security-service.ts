import { get, put } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

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
  return get<EgressPolicy>('/security/egress/workspace')
}

export const updateWorkspaceEgressPolicy = async (data: Pick<EgressPolicy, 'allowlist' | 'blocklist'>): Promise<EgressPolicy> => {
  return put<EgressPolicy>('/security/egress/workspace', data)
}

export const listEgressPolicyAudits = (params?: {
  scope?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<EgressPolicyAudit>> => {
  return get<PaginatedResponse<EgressPolicyAudit>>('/security/egress/audits', params)
}

export interface EgressBlockRow {
  id: string
  domain?: string | null
  resource_ref?: string | null
  reason?: string | null
  url?: string | null
  actor_user_id?: string | null
  trace_id?: string | null
  created_at: string
}

export interface EgressBlockSummary {
  since?: string | null
  until?: string | null
  total: number
  /** Distinct callers refused: what the governance panel calls agents. */
  subjects: number
  domains: number
  recent: EgressBlockRow[]
}

/**
 * Outbound requests the policy refused. Distinct from
 * `listEgressPolicyAudits`, which records changes to the policy itself.
 */
export const getEgressBlockSummary = (params?: {
  since?: string
  until?: string
}): Promise<EgressBlockSummary> => {
  return get<EgressBlockSummary>('/security/egress/blocks', params)
}

export const getWorkspaceUsagePolicy = (): Promise<UsagePolicy> => {
  return get<UsagePolicy>('/security/limits/workspace')
}

export const updateWorkspaceUsagePolicy = async (data: UsagePolicy): Promise<UsagePolicy> => {
  return put<UsagePolicy>('/security/limits/workspace', data)
}
