import { get, post, patch, del, type RequestConfigWithToast } from '@/utils/request'

export interface Secret {
  id: string
  name: string
  description?: string | null
  last_rotated_at?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export const listSecrets = (params?: { limit?: number; offset?: number }): Promise<Secret[]> => {
  return get<Secret[]>('/secrets', params)
}

export interface SecretResolutionSummary {
  since?: string | null
  until?: string | null
  total: number
  /** Distinct secrets resolved at least once in the window. */
  secrets: number
}

/**
 * How often secrets were handed to governed callers. Counted from the audit
 * ledger, which records that a resolution happened and never its value.
 */
export const getSecretResolutionSummary = (params?: {
  since?: string
  until?: string
}): Promise<SecretResolutionSummary> => {
  return get<SecretResolutionSummary>('/secrets/resolutions/summary', params)
}

export const getSecret = (secretId: string): Promise<Secret> => {
  return get<Secret>(`/secrets/${secretId}`)
}

export const createSecret = (
  data: {
    name: string
    description?: string
    value: string
  },
  config?: RequestConfigWithToast,
): Promise<Secret> => {
  return post<Secret>('/secrets', data, config)
}

export const updateSecret = (
  secretId: string,
  data: {
    name?: string
    description?: string
    value?: string
  },
  config?: RequestConfigWithToast,
): Promise<Secret> => {
  return patch<Secret>(`/secrets/${secretId}`, data, config)
}

export const deleteSecret = (
  secretId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/secrets/${secretId}`, undefined, config)
}

export const testSecret = (
  secretId: string,
  config?: RequestConfigWithToast,
): Promise<{ ok: boolean; message?: string | null }> => {
  return post<{ ok: boolean; message?: string | null }>(`/secrets/${secretId}/test`, undefined, config)
}
