import { del, get, post, type RequestConfigWithToast } from '@/utils/request'

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  workspace_id?: string
  /** Renews the access token without a password. Returned once per rotation. */
  refresh_token?: string | null
}

export interface UserSession {
  id: string
  workspace_id?: string | null
  status: string
  user_agent?: string | null
  ip_address?: string | null
  created_at: string
  last_seen_at: string
  expires_at: string
  /** True for the session making the request. */
  current: boolean
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


/**
 * Exchange a refresh token for a new access token.
 *
 * The refresh token rotates on every use: the response carries the next one,
 * and presenting a spent token ends the session. Kept quiet because the caller
 * is the interceptor, which decides whether a failure means "sign in again".
 */
export const authRefresh = (refreshToken: string): Promise<TokenResponse> => {
  return post<TokenResponse>(`/refresh`, { refresh_token: refreshToken }, quiet)
}

export const listSessions = (): Promise<UserSession[]> => {
  return get<UserSession[]>(`/me/sessions`)
}

export const revokeSession = (
  sessionId: string,
  config?: RequestConfigWithToast,
): Promise<UserSession> => {
  return del<UserSession>(`/me/sessions/${sessionId}`, undefined, config)
}

export const revokeAllSessions = (
  keepCurrent = true,
  config?: RequestConfigWithToast,
): Promise<{ revoked: number }> => {
  return post<{ revoked: number }>(
    `/me/sessions/revoke-all`,
    undefined,
    { ...config, params: { keep_current: keepCurrent } },
  )
}
