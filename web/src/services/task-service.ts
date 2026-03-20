import { get, post } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

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
}

export interface TaskControlResponse {
  task: Task
  action: string
}

export const listTasks = (params?: {
  status?: string
  task_type?: string
  agent_id?: string
  thread_id?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Task>> => {
  return get<PaginatedResponse<Task>>('/tasks', params).then((response) => response.data)
}

export const getTask = (taskId: string): Promise<TaskDetail> => {
  return get<TaskDetail>(`/tasks/${taskId}`).then((response) => response.data)
}

export const cancelTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/cancel`, {}).then((response) => response.data)
}

export const resumeTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/resume`, {}).then((response) => response.data)
}

export const retryTask = (taskId: string): Promise<TaskControlResponse> => {
  return post<TaskControlResponse>(`/tasks/${taskId}/retry`, {}).then((response) => response.data)
}
