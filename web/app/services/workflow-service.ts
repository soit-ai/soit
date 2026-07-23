import {
  get,
  post,
  put,
  del,
  sse,
  type RequestConfigWithToast,
  type SseEvent,
  API_BASE_URL,
} from '@/utils/request'
import type { FetchEventSourceInit } from '@microsoft/fetch-event-source'
import type { PaginatedResponse } from '@/types/api'
import { isAxiosError } from 'axios'

export type { PaginatedResponse } from '@/types/api'

const suppressErrorToastConfig: RequestConfigWithToast = { suppressErrorToast: true }

export interface Workflow {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  description?: string | null
  summary?: string | null
  status: string
  visibility: string
  icon_url?: string | null
  category?: string | null
  tags?: string[] | null
  owner_user_id?: string | null
  current_version_id?: string | null
  published_version_id?: string | null
  metadata_json?: Record<string, any> | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  deleted_at?: string | null
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

export interface WorkflowNodeCapability {
  type: string
  ui_type: string
  category: string
  executable: boolean
}

export interface WorkflowCapabilitiesResponse {
  capabilities: WorkflowNodeCapability[]
  builder_node_types: string[]
  compatibility_node_types: string[]
}

export interface WorkflowRelease {
  id: string
  workflow_id: string
  version_id: string
  action: string
  scope: string
  status: string
  from_version_id?: string | null
  to_version_id: string
  notes?: string | null
  rollback_of_publish_id?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface WorkflowRunControlResponse {
  run_id: string
  status?: string
  [key: string]: any
}

export interface WorkflowPreviewResponse {
  run_id: string
  workflow_version_id: string
  output: Record<string, unknown>
}

export interface WorkflowWorkbenchSummary {
  total_workflows: number
  published_workflows: number
  running_workflows: number
  today_runs: number
  avg_latency_ms?: number | null
  success_rate?: number | null
  recent_exceptions: number
  updated_at: string
}

export interface WorkflowWorkbenchTabs {
  all: number
  high_volume: number
  publishing: number
  abnormal: number
  draft: number
}

export interface WorkflowWorkbenchRow {
  id: string
  name: string
  description?: string | null
  summary?: string | null
  status: 'running' | 'publishing' | 'abnormal' | 'draft'
  linked_agents: string[]
  linked_agent_count: number
  today_runs: number
  avg_latency_ms?: number | null
  success_rate?: number | null
  recent_exception_count: number
  owner?: string | null
  last_run_at?: string | null
  action_enabled: boolean
  updated_at: string
}

export interface WorkflowWorkbenchResponse {
  summary: WorkflowWorkbenchSummary
  tabs: WorkflowWorkbenchTabs
  items: WorkflowWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export interface WorkflowWorkbenchItemsResponse {
  items: WorkflowWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export const listWorkflows = (params?: { page_token?: string; page_size?: number }): Promise<PaginatedResponse<Workflow>> => {
  return get('/workflows', params)
}

export const getWorkflowWorkbench = (params?: { page_token?: string; page_size?: number }): Promise<WorkflowWorkbenchResponse> => {
  return get('/workflows/workbench', params)
}

export const getWorkflowWorkbenchItems = (params?: {
  tab?: string
  keyword?: string
  page_token?: string
  page_size?: number
}): Promise<WorkflowWorkbenchItemsResponse> => {
  return get('/workflows/workbench/items', params)
}

export const getWorkflow = (
  workflowId: string,
  config?: RequestConfigWithToast,
): Promise<Workflow> => {
  return get(`/workflows/${workflowId}`, undefined, config)
}

export const getWorkflowCapabilities = (): Promise<WorkflowCapabilitiesResponse> => {
  return get('/workflows/capabilities')
}

export const createWorkflow = (data: {
  name: string
  description?: string
  summary?: string
  visibility?: string
  icon_url?: string
  category?: string
  tags?: string[]
}, config?: RequestConfigWithToast): Promise<Workflow> => {
  return post('/workflows', data, config)
}

export const createTicketTriageWorkflow = (data?: {
  name?: string
}, config?: RequestConfigWithToast): Promise<Workflow> => {
  return post('/workflows/templates/ticket-triage', data || {}, config)
}

export const updateWorkflow = (
  workflowId: string,
  data: {
    name?: string
    description?: string
    summary?: string
    status?: string
    visibility?: string
    icon_url?: string
    category?: string
    tags?: string[]
    metadata_json?: Record<string, any>
  },
  config?: RequestConfigWithToast,
): Promise<Workflow> => {
  return put(`/workflows/${workflowId}`, data, config)
}

export const deleteWorkflow = (
  workflowId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/workflows/${workflowId}`, undefined, config).then(() => undefined)
}

export const createWorkflowVersion = (
  workflowId: string,
  data: { graph_json: Record<string, unknown> },
  config?: RequestConfigWithToast,
): Promise<WorkflowVersion> => {
  return post(`/workflows/${workflowId}/versions`, data, config)
}

export const listWorkflowVersions = (
  workflowId: string,
  params?: { page_token?: string; page_size?: number }
): Promise<PaginatedResponse<WorkflowVersion>> => {
  return get(`/workflows/${workflowId}/versions`, params)
}

export const listWorkflowReleases = (
  workflowId: string,
  params?: { page_token?: string; page_size?: number }
): Promise<PaginatedResponse<WorkflowRelease>> => {
  return get(`/workflows/${workflowId}/releases`, params)
}

export const getCurrentWorkflowVersion = (workflowId: string): Promise<WorkflowVersion> => {
  return get(`/workflows/${workflowId}/version/current`)
}

export const getCurrentWorkflowVersionOrNull = async (
  workflowId: string,
): Promise<WorkflowVersion | null> => {
  try {
    return await get<WorkflowVersion>(
      `/workflows/${workflowId}/version/current`,
      undefined,
      suppressErrorToastConfig,
    )
  } catch (error) {
    if (isAxiosError(error) && error.response?.status === 404) {
      return null
    }
    throw error
  }
}

export const publishWorkflowVersion = (workflowId: string, versionId: string): Promise<Workflow> => {
  return post(`/workflows/${workflowId}/publish`, { version_id: versionId })
}

export const executeWorkflow = (workflowId: string, inputs: Record<string, any>): Promise<any> => {
  return post(`/workflows/${workflowId}/execute`, inputs)
}

export const previewWorkflowVersion = (
  workflowId: string,
  versionId: string,
  inputs: Record<string, unknown>,
  config?: RequestConfigWithToast,
): Promise<WorkflowPreviewResponse> => {
  return post(`/workflows/${workflowId}/versions/${versionId}/preview`, { inputs }, config)
}

export const streamWorkflowExecution = (
  workflowId: string,
  inputs: Record<string, any>,
  config?: FetchEventSourceInit
): AsyncGenerator<SseEvent, void, any> => {
  return sse(`${API_BASE_URL}/workflows/${workflowId}/stream`, { inputs }, config)
}

export const exportWorkflowDsl = (
  workflowId: string,
  params?: { version_id?: string; format?: 'json' | 'yaml' }
): Promise<{ dsl: Record<string, any> | string; format: string }> => {
  return get(`/workflows/${workflowId}/dsl`, params)
}

export const importWorkflowDsl = (
  workflowId: string,
  data: { dsl: Record<string, unknown> | string; format?: 'json' | 'yaml' }
): Promise<WorkflowVersion> => {
  return post(`/workflows/${workflowId}/dsl`, data)
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
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const resumeRun = (workflowId: string, runId: string): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/resume`)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const cancelRun = (
  workflowId: string,
  runId: string,
  data?: { reason?: string }
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/cancel`, data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const failRun = (
  workflowId: string,
  runId: string,
  data?: { error_code?: string; error_message?: string }
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/fail`, data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const retryRun = (
  workflowId: string,
  runId: string,
  data?: Record<string, any>
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/retry`, data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}

export const replayRun = (
  workflowId: string,
  runId: string,
  data?: Record<string, any>
): Promise<WorkflowRunControlResponse> => {
  return post(`/workflows/${workflowId}/runs/${runId}/replay`, data)
    .catch((error) => Promise.reject(mapRunControlError(error)))
}
