import { del, get, post, put, sse, type SseEvent, API_BASE_URL } from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

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
    plugin_refs?: string[]
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

export interface AgentRunMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  metadata?: Record<string, unknown>
}

export interface AgentRunRequest {
  messages: AgentRunMessage[]
  thread_id?: string
  thread_title?: string
  rag_top_k?: number
  rag_strategy?: 'system_message' | 'planner_context'
  memory_query?: string
  context_window_messages?: number
  context_window_chars?: number
}

export const listAgents = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Agent>> => {
  return get<PaginatedResponse<Agent>>('/agents', params).then((response) => response.data)
}

export const getAgent = (agentId: string): Promise<Agent> => {
  return get<Agent>(`/agents/${agentId}`).then((response) => response.data)
}

export const createAgent = (data: AgentCreateRequest): Promise<Agent> => {
  return post<Agent>('/agents', data).then((response) => response.data)
}

export const updateAgent = (agentId: string, data: AgentUpdateRequest): Promise<Agent> => {
  return put<Agent>(`/agents/${agentId}`, data).then((response) => response.data)
}

export const deleteAgent = (agentId: string): Promise<void> => {
  return del(`/agents/${agentId}`).then((response) => response.data)
}

export const listAgentVersions = (
  agentId: string,
  params?: {
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<AgentVersion>> => {
  return get<PaginatedResponse<AgentVersion>>(`/agents/${agentId}/versions`, params).then((response) => response.data)
}

export const createAgentVersion = (
  agentId: string,
  data: AgentVersionCreateRequest
): Promise<AgentVersion> => {
  return post<AgentVersion>(`/agents/${agentId}/versions`, data).then((response) => response.data)
}

export const listAgentReleases = (
  agentId: string,
  params?: {
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<AgentRelease>> => {
  return get<PaginatedResponse<AgentRelease>>(`/agents/${agentId}/releases`, params).then((response) => response.data)
}

export const listAgentBindings = (
  agentId: string,
  params?: {
    version_id?: string
  }
): Promise<AgentBinding[]> => {
  return get<AgentBinding[]>(`/agents/${agentId}/bindings`, params).then((response) => response.data)
}

export const publishAgentVersion = (
  agentId: string,
  data: AgentPublishRequest
): Promise<Agent> => {
  return post<Agent>(`/agents/${agentId}/publish`, data).then((response) => response.data)
}

export const streamAgentExecution = (
  agentId: string,
  data: AgentRunRequest,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, unknown> => {
  return sse(`${API_BASE_URL}/agents/${agentId}/stream`, data, config)
}
