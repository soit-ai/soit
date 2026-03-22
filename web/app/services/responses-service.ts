import { get, post, sse, type SseEvent, API_BASE_URL } from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'

export interface ResponseCreateRequest {
  model?: string
  provider?: string
  thread_id?: string
  task_id?: string
  agent_id?: string
  input?: Record<string, unknown> | unknown[]
  instructions?: string
  tools?: Array<Record<string, unknown>>
  mcp_servers?: Array<Record<string, unknown>>
  response_format?: Record<string, unknown>
  context?: Record<string, unknown>
  store?: boolean
  stream?: boolean
  metadata?: Record<string, unknown>
}

export interface ResponseRead {
  id: string
  tenant_id: string
  workspace_id: string
  thread_id?: string | null
  task_id?: string | null
  agent_id?: string | null
  run_id?: string | null
  model?: string | null
  provider?: string | null
  status: string
  input_json: Record<string, unknown>
  output_json: Record<string, unknown>
  usage_json: Record<string, unknown>
  metadata_json: Record<string, unknown>
  error_code?: string | null
  error_message?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  completed_at?: string | null
  canceled_at?: string | null
}

export interface ResponseEventRead {
  id: string
  tenant_id: string
  workspace_id: string
  response_id: string
  run_id?: string | null
  thread_id?: string | null
  task_id?: string | null
  agent_id?: string | null
  sequence: number
  type: string
  source: string
  payload_json: Record<string, unknown>
  created_at: string
}

export interface ToolCallRead {
  id: string
  tenant_id: string
  workspace_id: string
  response_id: string
  run_id?: string | null
  step_id?: string | null
  thread_id?: string | null
  task_id?: string | null
  agent_id?: string | null
  tool_name: string
  tool_type: string
  status: string
  arguments_json: Record<string, unknown>
  result_json: Record<string, unknown>
  metadata_json: Record<string, unknown>
  error_code?: string | null
  error_message?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export interface ResponseTimelineItemRead {
  response: ResponseRead
  events: ResponseEventRead[]
  tool_calls: ToolCallRead[]
}

export interface RunResponseTimelineRead {
  run_id: string
  items: ResponseTimelineItemRead[]
}

export const createResponse = (data: ResponseCreateRequest): Promise<ResponseRead> => {
  return post<ResponseRead>('/responses', data).then((response) => response.data)
}

export const createStreamResponse = (
  data: ResponseCreateRequest,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, unknown> => {
  return sse(`${API_BASE_URL}/responses`, data, config)
}

export const getRunResponseTimeline = (runId: string): Promise<RunResponseTimelineRead> => {
  return get<RunResponseTimelineRead>(`/responses/by-run/${runId}`).then((response) => response.data)
}

export const cancelResponse = (responseId: string): Promise<{ status: string; response_id: string }> => {
  return post<{ status: string; response_id: string }>(`/responses/${responseId}/cancel`).then((response) => response.data)
}
