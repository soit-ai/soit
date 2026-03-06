import { get, post, put, del } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface Bot {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  description?: string | null
  status: string
  visibility: string
  tags?: string[] | null
  current_version_id?: string | null
  published_version_id?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

export interface BotVersion {
  id: string
  bot_id: string
  version: string
  status: string
  system_prompt?: string | null
  model_ref?: string | null
  temperature?: number | null
  max_tokens?: number | null
  top_p?: number | null
  tool_refs?: string[] | null
  metadata_json?: Record<string, any> | null
  display_version?: string | null
  triggers?: Record<string, any> | null
  channels?: Record<string, any> | null
  limits?: Record<string, any> | null
  created_by?: string | null
  created_at: string
}

export interface BotExecuteResponse {
  run_id: string
  output: string
  model: string
  tokens_prompt: number
  tokens_completion: number
  finish_reason?: string | null
}

export interface BotRunSummary {
  id: string
  bot_id: string
  status: string
  mode: string
  user_id?: string | null
  message_count?: number
  input_summary?: string | null
  output_summary?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export interface BotLogEntry {
  id: string
  run_id: string
  step_id?: string | null
  level: 'info' | 'warning' | 'error'
  message: string
  code?: string | null
  status?: string | null
  created_at?: string | null
  details?: Record<string, any> | null
}

export interface BotMetricsPoint {
  bucket: string
  runs_total: number
  runs_succeeded: number
  runs_failed: number
  tokens_prompt: number
  tokens_completion: number
  avg_latency_ms?: number | null
}

export interface BotMetrics {
  runs_total: number
  runs_succeeded: number
  runs_failed: number
  success_rate: number
  avg_latency_ms?: number | null
  tokens_prompt: number
  tokens_completion: number
  active_users: number
  usage_distribution: Array<{ name: string; value: number }>
  resource_usage: {
    cpu_percent?: number
    memory_percent?: number
    network_percent?: number
    storage_percent?: number
    ms_total?: number
    storage_bytes?: number
  }
  points: BotMetricsPoint[]
}

export const listBots = (params?: { page_token?: string; page_size?: number }): Promise<PaginatedResponse<Bot>> => {
  return get<PaginatedResponse<Bot>>('/bots', params).then(response => response.data)
}

export const getBot = (botId: string): Promise<Bot> => {
  return get<Bot>(`/bots/${botId}`).then(response => response.data)
}

export const createBot = (data: {
  name: string
  description?: string
  visibility?: 'private' | 'workspace' | 'tenant' | 'public'
  tags?: string[]
}): Promise<Bot> => {
  return post<Bot>('/bots', data).then(response => response.data)
}

export const updateBot = (
  botId: string,
  data: {
    name?: string
    description?: string
    status?: 'active' | 'archived' | 'disabled'
    visibility?: 'private' | 'workspace' | 'tenant' | 'public'
    tags?: string[]
  }
): Promise<Bot> => {
  return put<Bot>(`/bots/${botId}`, data).then(response => response.data)
}

export const deleteBot = (botId: string): Promise<void> => {
  return del(`/bots/${botId}`).then(response => response.data)
}

export const listBotVersions = (
  botId: string,
  params?: { page_token?: string; page_size?: number }
): Promise<PaginatedResponse<BotVersion>> => {
  return get<PaginatedResponse<BotVersion>>(`/bots/${botId}/versions`, params).then(response => response.data)
}

export const createBotVersion = (
  botId: string,
  data: {
    version?: string
    system_prompt?: string
    model_ref?: string
    temperature?: number
    max_tokens?: number
    top_p?: number
    tool_refs?: string[]
    metadata_json?: Record<string, any>
    triggers?: Record<string, any>
    channels?: Record<string, any>
    limits?: Record<string, any>
  }
): Promise<BotVersion> => {
  return post<BotVersion>(`/bots/${botId}/versions`, data).then(response => response.data)
}

export const getBotVersion = (botId: string, versionId: string): Promise<BotVersion> => {
  return get<BotVersion>(`/bots/${botId}/versions/${versionId}`).then(response => response.data)
}

export const updateBotVersion = (
  botId: string,
  versionId: string,
  data: {
    system_prompt?: string
    model_ref?: string
    temperature?: number
    max_tokens?: number
    top_p?: number
    tool_refs?: string[]
    metadata_json?: Record<string, any>
    triggers?: Record<string, any>
    channels?: Record<string, any>
    limits?: Record<string, any>
  }
): Promise<BotVersion> => {
  return put<BotVersion>(`/bots/${botId}/versions/${versionId}`, data).then(response => response.data)
}

export const publishBotVersion = (botId: string, versionId: string): Promise<Bot> => {
  return post<Bot>(`/bots/${botId}/publish`, { version_id: versionId }).then(response => response.data)
}

export const executeBot = (
  botId: string,
  data: { messages: Array<{ role: string; content: string }>; version_id?: string }
): Promise<BotExecuteResponse> => {
  return post<BotExecuteResponse>(`/bots/${botId}/execute`, data).then(response => response.data)
}

export const executeBotTrigger = (
  botId: string,
  trigger: 'webhook' | 'schedule' | 'event',
  data: { event_payload: Record<string, any>; version_id?: string; messages?: Array<{ role: string; content: string }> }
): Promise<BotExecuteResponse> => {
  return post<BotExecuteResponse>(`/bots/${botId}/execute/${trigger}`, data).then(response => response.data)
}

export const listBotRuns = (
  botId: string,
  params?: {
    page_token?: string
    page_size?: number
    status?: string
    started_after?: string
    started_before?: string
  }
): Promise<PaginatedResponse<BotRunSummary>> => {
  return get<PaginatedResponse<BotRunSummary>>(`/bots/${botId}/runs`, params).then(response => response.data)
}

export const getBotRun = (botId: string, runId: string): Promise<Record<string, any>> => {
  return get<Record<string, any>>(`/bots/${botId}/runs/${runId}`).then(response => response.data)
}

export const listBotLogs = (
  botId: string,
  params?: {
    page_token?: string
    page_size?: number
    status?: string
    level?: string
    started_after?: string
    started_before?: string
  }
): Promise<PaginatedResponse<BotLogEntry>> => {
  return get<PaginatedResponse<BotLogEntry>>(`/bots/${botId}/logs`, params).then(response => response.data)
}

export const getBotMetrics = (
  botId: string,
  params?: { range_key?: '24h' | '7d' | '30d' | '90d' }
): Promise<BotMetrics> => {
  return get<BotMetrics>(`/bots/${botId}/metrics`, params).then(response => response.data)
}
