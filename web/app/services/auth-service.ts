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

export interface MfaChallenge {
  mfa_required: true
  mfa_token: string
  expires_in: number
}

/** A sign-in either completes or stops at the second factor. */
export type LoginResult = TokenResponse | MfaChallenge

export function isMfaChallenge(result: LoginResult): result is MfaChallenge {
  return (result as MfaChallenge).mfa_required === true
}

export interface MfaStatus {
  enabled: boolean
  pending: boolean
  confirmed_at?: string | null
  last_used_at?: string | null
  recovery_codes_remaining: number
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

export const authLogin = (data: LoginRequest): Promise<LoginResult> => {
  return post<LoginResult>(`/login`, data, quiet)
}

/** Finish a sign-in that stopped at the second factor. */
export const authCompleteMfaLogin = (
  mfaToken: string,
  code: string,
): Promise<TokenResponse> => {
  return post<TokenResponse>(`/login/mfa`, { mfa_token: mfaToken, code }, quiet)
}

export const getMfaStatus = (config?: RequestConfigWithToast): Promise<MfaStatus> => {
  return get<MfaStatus>(`/me/mfa`, undefined, config)
}

/** Begins enrolment. The secret comes back once and is never returned again. */
export const startMfaEnrolment = (
  config?: RequestConfigWithToast,
): Promise<{ secret: string; provisioning_uri: string }> => {
  return post<{ secret: string; provisioning_uri: string }>(`/me/mfa/setup`, undefined, config)
}

export const confirmMfaEnrolment = (
  code: string,
  config?: RequestConfigWithToast,
): Promise<{ recovery_codes: string[] }> => {
  return post<{ recovery_codes: string[] }>(`/me/mfa/confirm`, { code }, config)
}

export const regenerateMfaRecoveryCodes = (
  code: string,
  config?: RequestConfigWithToast,
): Promise<{ recovery_codes: string[] }> => {
  return post<{ recovery_codes: string[] }>(`/me/mfa/recovery-codes`, { code }, config)
}

/** POST, not DELETE: the password belongs in a body, never in a query string. */
export const disableMfa = (
  password: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return post<void>(`/me/mfa/disable`, { password }, config)
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
