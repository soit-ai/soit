import { del, get, post, put, sse, type SseEvent, API_BASE_URL } from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface Agent {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  description?: string | null
  status: string
  visibility: string
  icon_url?: string | null
  category?: string | null
  is_public: boolean
  featured: boolean
  downloads_count: number
  rating?: number | null
  reviews_count: number
  published_at?: string | null
  tags?: string[] | null
  current_version_id?: string | null
  published_version_id?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

export interface AgentVersion {
  id: string
  agent_id: string
  version: number
  status: string
  spec_schema: string
  spec_json: Record<string, unknown>
  checksum?: string | null
  created_by?: string | null
  created_at: string
}

export interface AgentRelease {
  id: string
  agent_id: string
  version_id: string
  action: string
  scope: string
  status: string
  from_version_id?: string | null
  to_version_id: string
  notes?: string | null
  rollback_of_publish_id?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface AgentVersionCreateRequest {
  system_prompt?: string
  temperature?: number
  max_iterations?: number
  max_tool_calls?: number
  max_llm_calls?: number
  max_failures?: number
  max_runtime_seconds?: number
  max_tokens_total?: number
  max_cost?: number
  cost_currency?: string
  memory_strategy?: string
  memory_top_k?: number
  verify?: boolean
  failure_strategy?: string
  bindings?: {
    model_ref?: string
    knowledge_refs?: string[]
    tool_refs?: string[]
    workflow_refs?: string[]
    skill_refs?: string[]
  }
}

export interface AgentBinding {
  id: string
  agent_id: string
  agent_version_id?: string | null
  binding_type: string
  target_id?: string | null
  target_key?: string | null
  config_json: Record<string, unknown>
  sort_order: number
  created_at: string
  updated_at: string
}

export interface AgentWorkbenchSummary {
  total_agents: number
  configured_agents: number
  running_agents: number
  today_calls: number
  avg_latency_ms?: number | null
  success_rate?: number | null
  pending_exceptions: number
  updated_at: string
}

export interface AgentWorkbenchTabs {
  all: number
  high_calls: number
  low_success: number
  long_latency: number
  unconfigured: number
}

export interface AgentWorkbenchCapability {
  type: string
  target_id?: string | null
  target_key?: string | null
  label: string
}

export interface AgentWorkbenchRow {
  id: string
  name: string
  description?: string | null
  status: 'running' | 'configuring' | 'abnormal' | 'unconfigured'
  capabilities: AgentWorkbenchCapability[]
  today_calls: number
  avg_latency_ms?: number | null
  success_rate?: number | null
  recent_exception_count: number
  owner?: string | null
  last_run_at?: string | null
  action_enabled: boolean
  updated_at: string
}

export interface AgentWorkbenchResponse {
  summary: AgentWorkbenchSummary
  tabs: AgentWorkbenchTabs
  items: AgentWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export interface AgentWorkbenchItemsResponse {
  items: AgentWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export interface AgentCreateRequest {
  name: string
  description?: string
  visibility?: string
  icon_url?: string
  category?: string
  is_public?: boolean
  featured?: boolean
  tags?: string[]
}

export interface AgentUpdateRequest {
  name?: string
  description?: string
  status?: string
  visibility?: string
  icon_url?: string
  category?: string
  is_public?: boolean
  featured?: boolean
  tags?: string[]
}

export interface AgentPublishRequest {
  version_id: string
}

export interface AgentRunRequest {
  input: string
  thread_id?: string
  request_id?: string
}

export interface AgentCancelResponse {
  run_id: string
  status: string
  task_ids: string[]
  response_ids: string[]
}

export const listAgents = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Agent>> => {
  return get<PaginatedResponse<Agent>>('/agents', params)
}

export const getAgent = (agentId: string): Promise<Agent> => {
  return get<Agent>(`/agents/${agentId}`)
}

export const getAgentWorkbench = (params?: {
  page_token?: string
  page_size?: number
}): Promise<AgentWorkbenchResponse> => {
  return get<AgentWorkbenchResponse>('/agents/workbench', params)
}

export const getAgentWorkbenchItems = (params?: {
  tab?: string
  keyword?: string
  page_token?: string
  page_size?: number
}): Promise<AgentWorkbenchItemsResponse> => {
  return get<AgentWorkbenchItemsResponse>('/agents/workbench/items', params)
}

export const createAgent = (data: AgentCreateRequest): Promise<Agent> => {
  return post<Agent>('/agents', data)
}

export const updateAgent = (agentId: string, data: AgentUpdateRequest): Promise<Agent> => {
  return put<Agent>(`/agents/${agentId}`, data)
}

export const deleteAgent = (agentId: string): Promise<void> => {
  return del(`/agents/${agentId}`)
}

export const listAgentVersions = (
  agentId: string,
  params?: {
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<AgentVersion>> => {
  return get<PaginatedResponse<AgentVersion>>(`/agents/${agentId}/versions`, params)
}

export const createAgentVersion = (
  agentId: string,
  data: AgentVersionCreateRequest
): Promise<AgentVersion> => {
  return post<AgentVersion>(`/agents/${agentId}/versions`, data)
}

export const listAgentReleases = (
  agentId: string,
  params?: {
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<AgentRelease>> => {
  return get<PaginatedResponse<AgentRelease>>(`/agents/${agentId}/releases`, params)
}

export const listAgentBindings = (
  agentId: string,
  params?: {
    version_id?: string
  }
): Promise<AgentBinding[]> => {
  return get<AgentBinding[]>(`/agents/${agentId}/bindings`, params)
}

export const publishAgentVersion = (
  agentId: string,
  data: AgentPublishRequest
): Promise<Agent> => {
  return post<Agent>(`/agents/${agentId}/publish`, data)
}

export const streamAgentExecution = (
  agentId: string,
  data: AgentRunRequest,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, unknown> => {
  return sse(`${API_BASE_URL}/agents/${agentId}/stream`, data, config)
}

export const cancelAgentExecution = (
  agentId: string,
  runId: string
): Promise<AgentCancelResponse> => {
  return post<AgentCancelResponse>(`/agents/${agentId}/runs/${runId}/cancel`, {})
}
