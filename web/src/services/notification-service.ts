import { get, post } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

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

export const getNotificationUnreadCount = async (): Promise<NotificationUnreadCount> => {
  const data = await get('/notifications/unread-count')
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
