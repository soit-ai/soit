import { get, post } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

/** A scope is a ceiling on the key, intersected with the owner's role. */
export type ApiKeyScope = 'read' | 'write' | 'admin'

export interface ApiKeyItem {
  id: string
  tenant_id: string
  workspace_id: string
  user_id: string
  name: string
  key_prefix: string
  status: string
  scopes: ApiKeyScope[]
  expires_at?: string | null
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

export const listApiKeys = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<ApiKeyItem>> => {
  return get<PaginatedResponse<ApiKeyItem>>('/api-keys', params)
}

export const createApiKey = (data: {
  name: string
  scopes: ApiKeyScope[]
  expires_in_days: number
}): Promise<ApiKeyCreateResponse> => {
  return post<ApiKeyCreateResponse>('/api-keys', data)
}

export const revokeApiKey = (keyId: string): Promise<ApiKeyItem> => {
  return post<ApiKeyItem>(`/api-keys/${keyId}/revoke`, {})
}

export const rotateApiKey = (keyId: string): Promise<ApiKeyRotateResponse> => {
  return post<ApiKeyRotateResponse>(`/api-keys/${keyId}/rotate`, {})
}
