import { get, post } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface Task {
  id: string
  tenant_id: string
  workspace_id: string
  agent_id?: string | null
  thread_id?: string | null
  run_id?: string | null
  task_type: string
  status: string
  input_json: Record<string, unknown>
  output_json: Record<string, unknown>
  progress_json: Record<string, unknown>
  error_code?: string | null
  error_message?: string | null
  started_at?: string | null
  finished_at?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export interface TaskEvent {
  id: string
  tenant_id: string
  workspace_id: string
  task_id: string
  event_type: string
  payload_json: Record<string, unknown>
  created_at: string
}

export interface TaskCheckpoint {
  id: string
  tenant_id: string
  workspace_id: string
  task_id: string
  checkpoint_no: number
  status: string
  payload_json: Record<string, unknown>
  created_at: string
}

export interface TaskDetail {
  task: Task
  checkpoints: TaskCheckpoint[]
  events: TaskEvent[]
  available_actions: Array<'retry' | 'resume' | 'cancel' | string>
}

export interface TaskControlResponse {
  task: Task
  action: string
}

export interface TaskWorkbenchSummary {
  total_tasks: number
  waiting_approval: number
  failed: number
  waiting_input: number
  long_running: number
  running: number
  today_created: number
  today_completed: number
  updated_at: string
}

export interface TaskWorkbenchTabs {
  all: number
  waiting_approval: number
  failed: number
  waiting_input: number
  long_running: number
  running: number
}

export interface TaskWorkbenchRow {
  id: string
  tenant_id: string
  workspace_id: string
  display_name: string
  task_type: string
  status: string
  agent_id?: string | null
  thread_id?: string | null
  run_id?: string | null
  owner?: string | null
  error_code?: string | null
  error_message?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface TaskWorkbenchResponse {
  summary: TaskWorkbenchSummary
  tabs: TaskWorkbenchTabs
  items: TaskWorkbenchRow[]
  total: number
  next_page_token?: string | null
  page_size: number
}

export interface TaskWorkbenchItemsResponse {
  items: TaskWorkbenchRow[]
  total: number
  next_page_token?: string | null
  page_size: number
}

export interface TaskHandlingResponse {
  task: Task
  summary: {
    title: string
    status: string
    task_type: string
    error_code?: string | null
    error_message?: string | null
    updated_at: string
  }
  runtime_context: {
    agent_id?: string | null
    thread_id?: string | null
    run_id?: string | null
  }
  available_actions: Array<'retry' | 'resume' | 'cancel' | string>
  events: TaskEvent[]
  checkpoints: TaskCheckpoint[]
}

export const listTasks = (params?: {
  status?: string
  task_type?: string
  agent_id?: string
  thread_id?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Task>> => {
  return get<PaginatedResponse<Task>>('/tasks', params)
}

export const getTask = (taskId: string): Promise<TaskDetail> => {
  return get<TaskDetail>(`/tasks/${taskId}`)
}

export const getTaskWorkbench = (params?: {
  page_token?: string
  page_size?: number
}): Promise<TaskWorkbenchResponse> => {
  return get<TaskWorkbenchResponse>('/tasks/workbench', params)
}

export const getTaskWorkbenchItems = (params?: {
  tab?: string
  keyword?: string
  status?: string
  date_from?: string
  date_to?: string
  page_token?: string
  page_size?: number
}): Promise<TaskWorkbenchItemsResponse> => {
  return get<TaskWorkbenchItemsResponse>('/tasks/workbench/items', params)
}

export const getTaskHandling = (taskId: string): Promise<TaskHandlingResponse> => {
  return get<TaskHandlingResponse>(`/tasks/${taskId}/handling`)
}

export const cancelTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/cancel`, {})
}

export const resumeTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/resume`, {})
}

export const retryTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/retry`, {})
}
