import { post, type RequestConfigWithToast } from '@/utils/request'

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

// The auth forms render the failure inline, next to the fields it concerns.
// Letting the global handler also raise a toast reports one rejection twice.
const quiet: RequestConfigWithToast = { suppressErrorToast: true }

export const authLogin = (data: LoginRequest): Promise<TokenResponse> => {
  return post<TokenResponse>(`/login`, data, quiet)
}

export const authRegister = (data: RegisterRequest): Promise<TokenResponse> => {
  const { tenant_name, ...payload } = data
  const config: RequestConfigWithToast = tenant_name
    ? { ...quiet, params: { tenant_name } }
    : quiet
  return post<TokenResponse>(`/register`, payload, config)
}
