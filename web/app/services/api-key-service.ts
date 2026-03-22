import { get, post } from '@/utils/request'

export interface ApiKeyItem {
  id: string
  tenant_id: string
  workspace_id: string
  user_id: string
  name: string
  key_prefix: string
  status: string
  last_used_at?: string | null
  revoked_at?: string | null
  created_at: string
  updated_at: string
}

export interface ApiKeyCreateResponse {
  api_key: string
  item: ApiKeyItem
}

export interface ApiKeyRotateResponse {
  api_key: string
  item: ApiKeyItem
}

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export const listApiKeys = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<ApiKeyItem>> => {
  return get<PaginatedResponse<ApiKeyItem>>('/api-keys', params).then(response => response.data)
}

export const createApiKey = (data: { name: string }): Promise<ApiKeyCreateResponse> => {
  return post<ApiKeyCreateResponse>('/api-keys', data).then(response => response.data)
}

export const revokeApiKey = (keyId: string): Promise<ApiKeyItem> => {
  return post<ApiKeyItem>(`/api-keys/${keyId}/revoke`, {}).then(response => response.data)
}

export const rotateApiKey = (keyId: string): Promise<ApiKeyRotateResponse> => {
  return post<ApiKeyRotateResponse>(`/api-keys/${keyId}/rotate`, {}).then(response => response.data)
}
