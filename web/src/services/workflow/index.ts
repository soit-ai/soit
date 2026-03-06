import { get, post, put, del, sse, type SseEvent, API_BASE_URL } from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface Workflow {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  description?: string | null
  current_version_id?: string | null
  metadata_json?: Record<string, any> | null
  created_at: string
  updated_at: string
}

export interface WorkflowVersion {
  id: string
  tenant_id: string
  workspace_id: string
  workflow_id: string
  graph_json: Record<string, any>
  created_by: string
  created_at: string
}

export interface WorkflowRunControlResponse {
  run_id: string
  status?: string
  [key: string]: any
}

export const listWorkflows = (params?: { page_token?: string; page_size?: number }): Promise<PaginatedResponse<Workflow>> => {
  return get('/workflows', params).then((response) => response.data)
}

export const getWorkflow = (workflowId: string): Promise<Workflow> => {
  return get(`/workflows/${workflowId}`).then((response) => response.data)
}

export const createWorkflow = (data: { name: string; description?: string }): Promise<Workflow> => {
  return post('/workflows', data).then((response) => response.data)
}

export const updateWorkflow = (
  workflowId: string,
  data: { name?: string; description?: string; metadata_json?: Record<string, any> }
): Promise<Workflow> => {
  return put(`/workflows/${workflowId}`, data).then((response) => response.data)
}

export const deleteWorkflow = (workflowId: string): Promise<void> => {
  return del(`/workflows/${workflowId}`).then(() => undefined)
}

export const createWorkflowVersion = (
  workflowId: string,
  data: { graph_json: Record<string, any>; created_by: string }
): Promise<WorkflowVersion> => {
  return post(`/workflows/${workflowId}/versions`, data).then((response) => response.data)
}

export const listWorkflowVersions = (
  workflowId: string,
  params?: { page_token?: string; page_size?: number }
): Promise<PaginatedResponse<WorkflowVersion>> => {
  return get(`/workflows/${workflowId}/versions`, params).then((response) => response.data)
}

export const getCurrentWorkflowVersion = (workflowId: string): Promise<WorkflowVersion> => {
  return get(`/workflows/${workflowId}/version/current`).then((response) => response.data)
}

export const publishWorkflowVersion = (workflowId: string, versionId: string): Promise<Workflow> => {
  return post(`/workflows/${workflowId}/publish`, { version_id: versionId }).then((response) => response.data)
}

export const executeWorkflow = (workflowId: string, inputs: Record<string, any>): Promise<any> => {
  return post(`/workflows/${workflowId}/execute`, inputs).then((response) => response.data)
}

export const streamWorkflowExecution = (
  workflowId: string,
  inputs: Record<string, any>,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, any> => {
  return sse(`${API_BASE_URL}/sse/execution`, { workflow_id: workflowId, inputs }, config)
}

export const exportWorkflowDsl = (
  workflowId: string,
  params?: { version_id?: string; format?: 'json' | 'yaml' }
): Promise<{ dsl: Record<string, any> | string; format: string }> => {
  return get(`/workflows/${workflowId}/dsl`, params).then((response) => response.data)
}

export const importWorkflowDsl = (
  workflowId: string,
  data: { dsl: Record<string, any> | string; created_by: string; format?: 'json' | 'yaml' }
): Promise<WorkflowVersion> => {
  return post(`/workflows/${workflowId}/dsl`, data).then((response) => response.data)
}

const mapRunControlError = (error: any): Error => {
  const status = error?.response?.status
  const detail = error?.response?.data?.detail || error?.response?.data?.message || error?.message
  if (status === 409 || status === 422) {
    return new Error(detail || 'Run status does not allow this action')
  }
  if (status === 404) {
    return new Error(detail || 'Run not found')
  }
  if (status === 401 || status === 403) {
    return new Error(detail || 'You do not have permission to control this run')
  }
  return new Error(detail || 'Failed to control workflow run')
}

export const pauseRun = (workflowId: string, runId: string): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/pause`)
    .then((response) => response.data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const resumeRun = (workflowId: string, runId: string): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/resume`)
    .then((response) => response.data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const retryRun = (
  workflowId: string,
  runId: string,
  data?: Record<string, any>
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/retry`, data)
    .then((response) => response.data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const replayRun = (
  workflowId: string,
  runId: string,
  data?: Record<string, any>
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/replay`, data)
    .then((response) => response.data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}
