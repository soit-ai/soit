import { del, get, patch, post } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface Thread {
  id: string
  tenant_id: string
  workspace_id: string
  agent_id?: string | null
  title?: string | null
  status: string
  thread_type: string
  source?: string | null
  owner_user_id?: string | null
  summary?: string | null
  system_prompt?: string | null
  default_model_ref?: string | null
  default_temperature?: number | null
  default_max_tokens?: number | null
  default_top_p?: number | null
  context_window?: number | null
  max_history_messages?: number | null
  max_history_chars?: number | null
  message_count: number
  last_message_at?: string | null
  last_user_message_at?: string | null
  last_assistant_message_at?: string | null
  archived_at?: string | null
  pinned_at?: string | null
  knowledge_config_json: Record<string, any>
  tool_config_json: Record<string, any>
  metadata_json: Record<string, any>
  latest_run_id?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

export interface ThreadMessage {
  id: string
  tenant_id: string
  workspace_id: string
  thread_id: string
  run_id?: string | null
  task_id?: string | null
  response_id?: string | null
  parent_message_id?: string | null
  sequence_no: number
  role: string
  content: string
  message_type: string
  status: string
  content_json: Record<string, any>
  summary?: string | null
  model_ref?: string | null
  tokens_prompt?: number | null
  tokens_completion?: number | null
  finish_reason?: string | null
  citations_json: Array<Record<string, any>>
  attachments_json: Array<Record<string, any>>
  tool_calls_json: Array<Record<string, any>>
  error_code?: string | null
  error_message?: string | null
  metadata_json: Record<string, any>
  created_by?: string | null
  created_at: string
  edited_at?: string | null
  deleted_at?: string | null
}

export interface ThreadDetail {
  thread: Thread
  messages: ThreadMessage[]
}

export const createThread = (data?: {
  agent_id?: string
  title?: string
  thread_type?: string
  source?: string
  summary?: string
  system_prompt?: string
  default_model_ref?: string
  default_temperature?: number
  default_max_tokens?: number
  default_top_p?: number
  context_window?: number
  max_history_messages?: number
  max_history_chars?: number
  knowledge_config_json?: Record<string, any>
  tool_config_json?: Record<string, any>
  owner_user_id?: string
  metadata_json?: Record<string, any>
}): Promise<Thread> => {
  return post<Thread>('/threads', data || {}).then((response) => response.data)
}

export const listThreads = (params?: {
  page_token?: string
  page_size?: number
  status?: string
  agent_id?: string
}): Promise<PaginatedResponse<Thread>> => {
  return get<PaginatedResponse<Thread>>('/threads', params).then((response) => response.data)
}

export const getThread = (threadId: string): Promise<ThreadDetail> => {
  return get<ThreadDetail>(`/threads/${threadId}`).then((response) => response.data)
}

export const updateThread = (
  threadId: string,
  data: {
    title?: string
    status?: string
    thread_type?: string
    source?: string
    summary?: string
    system_prompt?: string
    default_model_ref?: string
    default_temperature?: number
    default_max_tokens?: number
    default_top_p?: number
    context_window?: number
    max_history_messages?: number
    max_history_chars?: number
    knowledge_config_json?: Record<string, any>
    tool_config_json?: Record<string, any>
    pinned_at?: string | null
    metadata_json?: Record<string, any>
  }
): Promise<Thread> => {
  return patch<Thread>(`/threads/${threadId}`, data).then((response) => response.data)
}

export const deleteThread = (threadId: string): Promise<void> => {
  return del(`/threads/${threadId}`).then((response) => response.data)
}
