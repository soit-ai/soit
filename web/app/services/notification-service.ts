import { del, get, patch, post, put, type RequestConfigWithToast } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface NotificationAction {
  target?: string | null
  route?: string | null
  params?: Record<string, any> | null
  deeplink?: string | null
  resource_ref?: string | null
}

export interface Notification {
  id: string
  tenant_id: string
  workspace_id: string
  user_id: string
  type: string
  severity?: string | null
  status: string
  title: string
  content?: string | null
  source_module?: string | null
  action?: NotificationAction | null
  meta?: Record<string, any> | null
  read_at?: string | null
  archived_at?: string | null
  created_at: string
  updated_at: string
}

export interface NotificationUnreadCount {
  count: number
}

export interface NotificationBulkResult {
  updated: number
}

export type NotificationDeliveryMode = 'in_app' | 'in_app_email' | 'in_app_all'
export type NotificationEndpointKind = 'email' | 'webhook' | 'slack' | 'teams' | 'discord' | 'telegram' | 'other'

export interface NotificationPreference {
  id: string
  delivery_mode: NotificationDeliveryMode
  categories: Record<string, boolean>
  quiet_hours_enabled: boolean
  quiet_hours_start: string
  quiet_hours_end: string
  timezone: string
  created_at: string
  updated_at: string
}

export type NotificationPreferenceUpdate = Omit<NotificationPreference, 'id' | 'created_at' | 'updated_at'>

export interface NotificationEndpoint {
  id: string
  name: string
  kind: NotificationEndpointKind
  display_target: string
  status: 'active' | 'disabled'
  created_at: string
  updated_at: string
}

export interface NotificationEndpointCreate {
  name: string
  kind: NotificationEndpointKind
  url: string
}

export interface NotificationDelivery {
  id: string
  notification_id: string
  endpoint_id: string
  status: 'queued' | 'sending' | 'sent' | 'failed'
  attempt_count: number
  available_at: string
  last_error?: string | null
  sent_at?: string | null
  created_at: string
  updated_at: string
}

type NotificationListParams = {
  page_token?: string
  page_size?: number
  status?: string
  type?: string
  severity?: string
  source_module?: string
  include_archived?: boolean
}

const unwrapResponse = <T>(payload: any): T => {
  if (payload && typeof payload === 'object' && 'data' in payload) {
    return payload.data as T
  }
  return payload as T
}

export const listNotifications = async (params?: NotificationListParams): Promise<PaginatedResponse<Notification>> => {
  const data = await get('/notifications', params)
  return unwrapResponse<PaginatedResponse<Notification>>(data)
}

export const getNotificationUnreadCount = async (
  config?: RequestConfigWithToast,
): Promise<NotificationUnreadCount> => {
  const data = await get('/notifications/unread-count', undefined, config)
  return unwrapResponse<NotificationUnreadCount>(data)
}

export const markNotificationRead = async (notificationId: string): Promise<Notification> => {
  const data = await post(`/notifications/${notificationId}/read`)
  return unwrapResponse<Notification>(data)
}

export const markNotificationsRead = async (payload: { ids?: string[]; all?: boolean }): Promise<NotificationBulkResult> => {
  const data = await post('/notifications/read', payload)
  return unwrapResponse<NotificationBulkResult>(data)
}

export const archiveNotification = async (notificationId: string): Promise<Notification> => {
  const data = await post(`/notifications/${notificationId}/archive`)
  return unwrapResponse<Notification>(data)
}

export const getNotificationPreferences = async (): Promise<NotificationPreference> => {
  return unwrapResponse<NotificationPreference>(await get('/notifications/preferences'))
}

export const updateNotificationPreferences = async (
  payload: NotificationPreferenceUpdate,
  config?: RequestConfigWithToast,
): Promise<NotificationPreference> => {
  return unwrapResponse<NotificationPreference>(
    await put('/notifications/preferences', payload, config),
  )
}

export const listNotificationEndpoints = async (): Promise<NotificationEndpoint[]> => {
  return unwrapResponse<NotificationEndpoint[]>(await get('/notifications/endpoints'))
}

export const createNotificationEndpoint = async (
  payload: NotificationEndpointCreate,
  config?: RequestConfigWithToast,
): Promise<NotificationEndpoint> => {
  return unwrapResponse<NotificationEndpoint>(
    await post('/notifications/endpoints', payload, config),
  )
}

export const updateNotificationEndpoint = async (
  endpointId: string,
  payload: Partial<NotificationEndpointCreate> & { status?: 'active' | 'disabled' },
  config?: RequestConfigWithToast,
): Promise<NotificationEndpoint> => {
  return unwrapResponse<NotificationEndpoint>(
    await patch(`/notifications/endpoints/${endpointId}`, payload, config),
  )
}

export const deleteNotificationEndpoint = async (
  endpointId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  await del(`/notifications/endpoints/${endpointId}`, undefined, config)
}

export const testNotificationEndpoint = async (
  endpointId: string,
  config?: RequestConfigWithToast,
): Promise<NotificationDelivery> => {
  return unwrapResponse<NotificationDelivery>(
    await post(`/notifications/endpoints/${endpointId}/test`, undefined, config),
  )
}

export const listNotificationDeliveries = async (notificationId: string): Promise<NotificationDelivery[]> => {
  return unwrapResponse<NotificationDelivery[]>(await get(`/notifications/${notificationId}/deliveries`))
}
