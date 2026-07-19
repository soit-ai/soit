import { get, patch, post } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type FeedbackCategory = 'bug' | 'feature' | 'performance' | 'usability' | 'other'
export type FeedbackPriority = 'low' | 'medium' | 'high' | 'critical'
export type FeedbackStatus = 'open' | 'in_progress' | 'resolved' | 'closed'

export interface FeedbackContext {
  page_path?: string | null
  app_version?: string | null
  browser?: string | null
  os?: string | null
}

export interface ProductFeedback {
  id: string
  tenant_id?: string
  workspace_id?: string
  title: string
  description: string
  category: FeedbackCategory
  priority: FeedbackPriority
  status: FeedbackStatus
  context_json?: FeedbackContext | null
  created_by: string
  updated_by?: string | null
  resolved_by?: string | null
  resolution_note?: string | null
  resolved_at?: string | null
  created_at: string
  updated_at: string
}

export interface FeedbackSummary {
  total: number
  by_status: Record<FeedbackStatus, number>
  by_category: Record<FeedbackCategory, number>
  by_priority: Record<FeedbackPriority, number>
}

export interface CreateFeedbackPayload {
  title: string
  description: string
  category: FeedbackCategory
  priority: FeedbackPriority
  context?: FeedbackContext
}

export interface UpdateFeedbackPayload {
  status?: FeedbackStatus
  priority?: FeedbackPriority
  resolution_note?: string
}

export interface ListFeedbackParams {
  scope?: 'mine' | 'workspace'
  status?: FeedbackStatus
  category?: FeedbackCategory
  priority?: FeedbackPriority
  q?: string
  page_token?: string
  page_size?: number
}

export const createFeedback = (payload: CreateFeedbackPayload): Promise<ProductFeedback> => {
  return post<ProductFeedback>('/feedback', payload)
}

export const listFeedback = (
  params: ListFeedbackParams = {},
): Promise<PaginatedResponse<ProductFeedback>> => {
  return get<PaginatedResponse<ProductFeedback>>('/feedback', params)
}

export const getFeedbackSummary = (scope: 'mine' | 'workspace'): Promise<FeedbackSummary> => {
  return get<FeedbackSummary>('/feedback/summary', { scope })
}

export const updateFeedback = (
  feedbackId: string,
  payload: UpdateFeedbackPayload,
): Promise<ProductFeedback> => {
  return patch<ProductFeedback>(`/feedback/${feedbackId}`, payload)
}
