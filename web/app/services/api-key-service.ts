import { get, patch, post, type RequestConfigWithToast } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

/** A scope is a ceiling on the key, intersected with the owner's role. */
export type ApiKeyScope = 'read' | 'write' | 'admin'

/**
 * What a key may do beyond its scopes. They apply on top of the owner's own
 * limits; on a write, null removes a limit and an omitted field keeps it.
 */
export interface ApiKeyLimits {
  rate_limit_per_minute?: number | null
  daily_request_quota?: number | null
  /** Tokens per UTC day. */
  daily_token_quota?: number | null
  /** Addresses or CIDR ranges the key is accepted from. */
  ip_allowlist?: string[] | null
  /** Model refs (`model:…` or `vmodel:…`) the key may call. */
  allowed_models?: string[] | null
  /** Tool refs the key may invoke, through the tools API, MCP or a run it starts. */
  allowed_tools?: string[] | null
  /** `metadata_only` keeps the key's calls out of run text; null follows the workspace. */
  content_capture?: 'metadata_only' | null
}

export interface ApiKeyItem extends ApiKeyLimits {
  id: string
  tenant_id: string
  workspace_id: string
  user_id: string
  name: string
  key_prefix: string
  status: string
  scopes: ApiKeyScope[]
  /** Set when the key was issued to a service principal, which it acts as. */
  principal_id?: string | null
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

export const createApiKey = (
  data: ApiKeyLimits & {
    name: string
    scopes: ApiKeyScope[]
    expires_in_days: number
    /** Issue the key to a service principal instead of the caller. */
    principal_id?: string
  },
  config?: RequestConfigWithToast,
): Promise<ApiKeyCreateResponse> => {
  return post<ApiKeyCreateResponse>('/api-keys', data, config)
}

/** Rename a key or change its limits; scopes and expiry take a new key. */
export const updateApiKey = (
  keyId: string,
  data: ApiKeyLimits & { name?: string },
  config?: RequestConfigWithToast,
): Promise<ApiKeyItem> => {
  return patch<ApiKeyItem>(`/api-keys/${keyId}`, data, config)
}

export const revokeApiKey = (
  keyId: string,
  config?: RequestConfigWithToast,
): Promise<ApiKeyItem> => {
  return post<ApiKeyItem>(`/api-keys/${keyId}/revoke`, {}, config)
}

export const rotateApiKey = (
  keyId: string,
  config?: RequestConfigWithToast,
): Promise<ApiKeyRotateResponse> => {
  return post<ApiKeyRotateResponse>(`/api-keys/${keyId}/rotate`, {}, config)
}
