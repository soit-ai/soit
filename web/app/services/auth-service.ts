import { post } from '@/utils/request'

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  workspace_id?: string
}

export interface RegisterRequest {
  email: string
  password: string
  name: string
  tenant_name?: string
}

export const authLogin = (data: LoginRequest): Promise<TokenResponse> => {
  return post<TokenResponse>(`/login`, data)
}

export const authRegister = (data: RegisterRequest): Promise<TokenResponse> => {
  const { tenant_name, ...payload } = data
  return post<TokenResponse>(`/register`, payload, tenant_name ? { params: { tenant_name } } : undefined)
}
