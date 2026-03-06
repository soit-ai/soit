import { get, post, del, patch, sse, type SseEvent, API_BASE_URL } from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant' | 'tool'
  content: string
  metadata?: Record<string, any>
}

export interface ChatCompletionRequest {
  conversation_id?: string
  parent_message_id?: string
  messages: ChatMessage[]
  model?: string
  temperature?: number
  max_tokens?: number
  top_p?: number
  stream?: boolean
  history_limit?: number
  title?: string
  metadata?: Record<string, any>
  stream_chunk_size?: number
}

export interface Conversation {
  id: string
  title?: string | null
  status: string
  metadata_json?: Record<string, any> | null
  system_prompt?: string | null
  default_model_ref?: string | null
  default_temperature?: number | null
  default_max_tokens?: number | null
  default_top_p?: number | null
  message_count: number
  last_message_at?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

type ConversationPayload = Conversation & {
  metadata?: Record<string, any> | null
}

export interface Message {
  id: string
  conversation_id: string
  parent_id?: string | null
  role: string
  content: string
  model_ref?: string | null
  tokens_prompt?: number | null
  tokens_completion?: number | null
  finish_reason?: string | null
  run_id?: string | null
  created_by?: string | null
  metadata_json?: Record<string, any> | null
  created_at: string
}

export interface ChatCompletionResponse {
  run_id: string
  conversation_id: string
  message: Message
  model: string
  tokens_prompt: number
  tokens_completion: number
  finish_reason?: string | null
}

export const listConversations = (params?: {
  page_token?: string
  page_size?: number
  status?: 'active' | 'archived'
}): Promise<PaginatedResponse<Conversation>> => {
  return get('/chat/conversations', params).then(response => response.data)
}

const normalizeConversation = (item: ConversationPayload): Conversation => {
  if (item.metadata_json !== undefined) {
    return item
  }
  return {
    ...item,
    metadata_json: item.metadata ?? null,
  }
}

export const listHistory = (params?: {
  page_token?: string
  page_size?: number
  status?: 'active' | 'archived'
}): Promise<PaginatedResponse<Conversation>> => {
  return get('/chat/history', params).then((response) => {
    const payload = response.data as PaginatedResponse<ConversationPayload>
    return {
      ...payload,
      items: (payload.items || []).map(normalizeConversation),
    }
  })
}

export const getConversation = (conversationId: string): Promise<Conversation> => {
  return get(`/chat/conversations/${conversationId}`).then(response => response.data)
}

export const createConversation = (data: {
  title?: string
  status?: 'active' | 'archived'
  metadata?: Record<string, any>
  system_prompt?: string
  default_model_ref?: string
  default_temperature?: number
  default_max_tokens?: number
  default_top_p?: number
}): Promise<Conversation> => {
  return post('/chat/conversations', data).then(response => response.data)
}

export const updateConversation = (
  conversationId: string,
  data: {
    title?: string
    status?: 'active' | 'archived'
    metadata?: Record<string, any>
    system_prompt?: string
    default_model_ref?: string
    default_temperature?: number
    default_max_tokens?: number
    default_top_p?: number
  }
): Promise<Conversation> => {
  return patch(`/chat/conversations/${conversationId}`, data).then((response) => response.data)
}

export const deleteConversation = (conversationId: string): Promise<void> => {
  return del(`/chat/conversations/${conversationId}`).then(response => response.data)
}

export const deleteHistory = (conversationId: string): Promise<void> => {
  return del(`/chat/history/${conversationId}`).then(response => response.data)
}

export const listMessages = (params: {
  conversation_id: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Message>> => {
  const { conversation_id, ...query } = params
  return get(`/chat/conversations/${conversation_id}/messages`, query).then(response => response.data)
}

export const createChatCompletion = (data: ChatCompletionRequest): Promise<ChatCompletionResponse> => {
  return post('/chat/completions', data).then(response => response.data)
}

export const createStreamChatCompletion = (
  data: ChatCompletionRequest,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, any> => {
  return sse(`${API_BASE_URL}/chat/stream`, data, config)
}
