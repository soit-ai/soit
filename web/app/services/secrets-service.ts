import { get, post, patch, del } from '@/utils/request'

export interface Secret {
  id: string
  name: string
  description?: string | null
  secret_ref: string
  last_rotated_at?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export const listSecrets = (params?: { limit?: number; offset?: number }): Promise<Secret[]> => {
  return get<Secret[]>('/secrets', params).then(response => response.data)
}

export const getSecret = (secretId: string): Promise<Secret> => {
  return get<Secret>(`/secrets/${secretId}`).then(response => response.data)
}

export const createSecret = (data: {
  name: string
  description?: string
  value: string
}): Promise<Secret> => {
  return post<Secret>('/secrets', data).then(response => response.data)
}

export const updateSecret = (
  secretId: string,
  data: {
    name?: string
    description?: string
    value?: string
  }
): Promise<Secret> => {
  return patch<Secret>(`/secrets/${secretId}`, data).then(response => response.data)
}

export const deleteSecret = (secretId: string): Promise<void> => {
  return del(`/secrets/${secretId}`).then(response => response.data)
}

export const testSecret = (secretId: string): Promise<{ ok: boolean; message?: string | null }> => {
  return post(`/secrets/${secretId}/test`).then(response => response.data as { ok: boolean; message?: string | null })
}
