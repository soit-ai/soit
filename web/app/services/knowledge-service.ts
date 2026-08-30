import request, { del, get, post, put, patch, type RequestConfigWithToast } from '@/utils/request'
import type { RunCostByMode, RunCostSummary, RunResponse } from './run-service'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface KnowledgeBase {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  description?: string | null
  status: string
  visibility: string
  knowledge_type: string
  settings_json: Record<string, unknown>
  chunking_json: Record<string, unknown>
  retrieval_json: Record<string, unknown>
  default_embedding_model_ref?: string | null
  default_reranker_ref?: string | null
  default_index_id?: string | null
  doc_count: number
  chunk_count: number
  last_ingested_at?: string | null
  last_indexed_at?: string | null
  tags?: string[] | null
  created_at: string
  updated_at: string
}

export interface KnowledgeCreateRequest {
  name: string
  description?: string
  knowledge_type?: 'document' | 'qa' | 'code' | 'graph' | 'other'
  visibility?: string
  settings_json?: Record<string, unknown>
  chunking_json?: Record<string, unknown>
  retrieval_json?: Record<string, unknown>
  default_embedding_model_ref?: string
  default_reranker_ref?: string
  tags?: string[]
}

export interface KnowledgeUpdateRequest extends Partial<KnowledgeCreateRequest> {
  status?: string
}

export interface KnowledgeDocument {
  id: string
  tenant_id: string
  workspace_id: string
  knowledge_id: string
  doc_key: string
  version: number
  is_latest: boolean
  source_kind: string
  title?: string | null
  language?: string | null
  mime_type?: string | null
  filename?: string | null
  size_bytes?: number | null
  source_uri?: string | null
  status: string
  created_at: string
  updated_at: string
  checksum?: string | null
  content_hash?: string | null
  file_id?: string | null
  error_code?: string | null
  error_message?: string | null
  retry_count?: number
  parse_meta_json?: Record<string, unknown>
  index_meta_json?: Record<string, unknown>
  deleted_at?: string | null
}

export interface KnowledgeChunk {
  id: string
  tenant_id: string
  workspace_id: string
  knowledge_id: string
  document_id: string
  document_version: number
  chunk_no: number
  chunk_key?: string | null
  text_preview?: string | null
  start_offset?: number | null
  end_offset?: number | null
  page_no?: number | null
  section_path: string[]
  char_count?: number | null
  token_count?: number | null
  index_status: string
  created_at: string
  updated_at: string
}

export interface KnowledgeChunkUpdateRequest {
  content?: string
  index_status?: 'pending' | 'indexed' | 'failed' | 'disabled'
}

export interface KnowledgeIndex {
  id: string
  tenant_id: string
  workspace_id: string
  knowledge_id: string
  name: string
  is_primary: boolean
  provider: string
  embedding_model_ref: string
  dimension: number
  metric_type: string
  status: string
  build_version: number
  last_build_at?: string | null
  last_run_id?: string | null
  doc_count: number
  chunk_count: number
  vector_count: number
  last_error_code?: string | null
  last_error_message?: string | null
  created_at: string
  updated_at: string
}

export interface KnowledgeIndexCreateRequest {
  name: string
  provider?: string
  embedding_model_ref: string
  dimension?: number
  metric_type?: string
  is_primary?: boolean
}

export interface KnowledgeIndexUpdateRequest {
  name?: string
  is_primary?: boolean
  embedding_model_ref?: string
  dimension?: number
  metric_type?: string
  status?: string
}

export interface KnowledgeIngestTask {
  id: string
  tenant_id: string
  workspace_id: string
  knowledge_id: string
  document_id?: string | null
  status: string
  run_id?: string | null
  error_code?: string | null
  error_message?: string | null
  max_retries: number
  retry_count: number
  payload_json: Record<string, unknown>
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
  started_at?: string | null
  finished_at?: string | null
}

export interface KnowledgeQueryRequest {
  query: string
  top_k?: number
  index_id?: string
  filter?: Record<string, unknown>
  use_rerank?: boolean
  reranker_ref?: string
  strategy?: 'vector' | 'multi_index' | 'keyword' | 'hybrid'
  index_ids?: string[]
  keyword_top_k?: number
  keyword_candidate_limit?: number
  keyword_min_score?: number
  hybrid_alpha?: number
  include_snippets?: boolean
  snippet_length?: number
  max_snippets?: number
}

export interface KnowledgeQueryResult {
  chunk_id: string
  document_id: string
  score: number
  text: string
  snippets: string[]
  metadata: Record<string, unknown>
}

export interface KnowledgeQueryCitation {
  chunk_id: string
  document_id: string
  rank: number
  score: number
  knowledge_id?: string | null
  doc_key?: string | null
  title?: string | null
  source_uri?: string | null
  chunk_no?: number | null
  page_no?: number | null
  section_path?: string[] | null
  snippet?: string | null
}

export interface KnowledgeQueryResponse {
  results: KnowledgeQueryResult[]
  total: number
  citations: KnowledgeQueryCitation[]
}

export interface KnowledgeDocumentUploadRequest {
  doc_key: string
  source_kind: string
  source_uri?: string
  file_id?: string
  title?: string
  language?: string
  mime_type?: string
  filename?: string
  size_bytes?: number
  checksum?: string
  content_hash?: string
  access_policy_json?: Record<string, unknown>
  async_ingest?: boolean
  max_retries?: number
}

export interface KnowledgeUsage {
  resource_id: string
  resource_name: string
  resource_kind: string
  resource_status: string
  resource_version_id: string
  resource_version: number
  resource_version_status: string
  resource_version_created_at: string
  run_count: number
  last_run_at?: string | null
}

export interface KnowledgeWorkbenchSummary {
  total_knowledge_bases: number
  ready_knowledge_bases: number
  total_documents: number
  total_chunks: number
  today_calls: number
  avg_latency_ms?: number | null
  hit_rate?: number | null
  recent_exceptions: number
  updated_at: string
}

export interface KnowledgeWorkbenchTabs {
  all: number
  high_volume: number
  low_hit: number
  slow: number
  unconfigured: number
}

export interface KnowledgeWorkbenchRow {
  id: string
  name: string
  description?: string | null
  status: 'ready' | 'indexing' | 'error' | 'unconfigured'
  knowledge_type: string
  content_source: string
  document_count: number
  chunk_count: number
  today_calls: number
  avg_latency_ms?: number | null
  hit_rate?: number | null
  recent_exception_count: number
  owner?: string | null
  last_sync_at?: string | null
  action_enabled: boolean
  updated_at: string
}

export interface KnowledgeWorkbenchResponse {
  summary: KnowledgeWorkbenchSummary
  tabs: KnowledgeWorkbenchTabs
  items: KnowledgeWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export interface KnowledgeWorkbenchItemsResponse {
  items: KnowledgeWorkbenchRow[]
  next_page_token?: string | null
  page_size: number
}

export const listKnowledgeBases = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<KnowledgeBase>> => {
  return get<PaginatedResponse<KnowledgeBase>>('/knowledge', params)
}

export const getKnowledgeWorkbench = (params?: {
  page_token?: string
  page_size?: number
}): Promise<KnowledgeWorkbenchResponse> => {
  return get<KnowledgeWorkbenchResponse>('/knowledge/workbench', params)
}

export const getKnowledgeWorkbenchItems = (params?: {
  tab?: string
  keyword?: string
  page_token?: string
  page_size?: number
}): Promise<KnowledgeWorkbenchItemsResponse> => {
  return get<KnowledgeWorkbenchItemsResponse>('/knowledge/workbench/items', params)
}

export const getKnowledgeBase = (knowledgeId: string): Promise<KnowledgeBase> => {
  return get<KnowledgeBase>(`/knowledge/${knowledgeId}`)
}

export const createKnowledgeBase = (
  data: KnowledgeCreateRequest,
  config?: RequestConfigWithToast,
): Promise<KnowledgeBase> => {
  return post<KnowledgeBase>('/knowledge', data, config)
}

export const updateKnowledgeBase = (
  knowledgeId: string,
  data: KnowledgeUpdateRequest,
  config?: RequestConfigWithToast,
): Promise<KnowledgeBase> => {
  return put<KnowledgeBase>(`/knowledge/${knowledgeId}`, data, config)
}

export const deleteKnowledgeBase = (
  knowledgeId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/knowledge/${knowledgeId}`, undefined, config).then(() => undefined)
}

export const listKnowledgeDocuments = (
  knowledgeId: string,
  params?: { limit?: number; offset?: number }
): Promise<KnowledgeDocument[]> => {
  return get<KnowledgeDocument[]>(`/knowledge/${knowledgeId}/documents`, params)
}

export const listKnowledgeRuns = (
  knowledgeId: string,
  params?: { page_token?: string; page_size?: number }
): Promise<PaginatedResponse<RunResponse>> => {
  return get<PaginatedResponse<RunResponse>>(`/knowledge/${knowledgeId}/runs`, params)
}

export const getKnowledgeRunCostSummary = (knowledgeId: string): Promise<RunCostSummary> => {
  return get<RunCostSummary>(`/knowledge/${knowledgeId}/runs/costs/summary`)
}

export const getKnowledgeRunCostByMode = (knowledgeId: string): Promise<RunCostByMode[]> => {
  return get<RunCostByMode[]>(`/knowledge/${knowledgeId}/runs/costs/by-mode`)
}

export const listKnowledgeUsages = (knowledgeId: string): Promise<KnowledgeUsage[]> => {
  return get<KnowledgeUsage[]>(`/knowledge/${knowledgeId}/usages`)
}

export const listKnowledgeIndexes = (
  knowledgeId: string,
  params?: { limit?: number; offset?: number }
): Promise<KnowledgeIndex[]> => {
  return get<KnowledgeIndex[]>(`/knowledge/${knowledgeId}/indexes`, params)
}

export const createKnowledgeIndex = (
  knowledgeId: string,
  data: KnowledgeIndexCreateRequest
): Promise<KnowledgeIndex> => {
  return post<KnowledgeIndex>(`/knowledge/${knowledgeId}/indexes`, data)
}

export const updateKnowledgeIndex = (
  knowledgeId: string,
  indexId: string,
  data: KnowledgeIndexUpdateRequest
): Promise<KnowledgeIndex> => {
  return patch<KnowledgeIndex>(`/knowledge/${knowledgeId}/indexes/${indexId}`, data)
}

export const deleteKnowledgeIndex = (knowledgeId: string, indexId: string): Promise<void> => {
  return del(`/knowledge/${knowledgeId}/indexes/${indexId}`).then(() => undefined)
}

export const rebuildKnowledgeIndex = (
  knowledgeId: string,
  indexId: string,
  config?: RequestConfigWithToast,
): Promise<KnowledgeIndex> => {
  return post<KnowledgeIndex>(`/knowledge/${knowledgeId}/indexes/${indexId}/rebuild`, undefined, config)
}

export const uploadKnowledgeDocument = async (
  knowledgeId: string,
  data: KnowledgeDocumentUploadRequest,
  file?: File
): Promise<KnowledgeDocument> => {
  const formData = new FormData()
  formData.append('doc_key', data.doc_key)
  formData.append('source_kind', data.source_kind)
  if (data.source_uri) formData.append('source_uri', data.source_uri)
  if (data.file_id) formData.append('file_id', data.file_id)
  if (data.title) formData.append('title', data.title)
  if (data.language) formData.append('language', data.language)
  if (data.mime_type) formData.append('mime_type', data.mime_type)
  if (data.filename) formData.append('filename', data.filename)
  if (data.size_bytes !== undefined) formData.append('size_bytes', String(data.size_bytes))
  if (data.checksum) formData.append('checksum', data.checksum)
  if (data.content_hash) formData.append('content_hash', data.content_hash)
  if (data.access_policy_json) formData.append('access_policy_json', JSON.stringify(data.access_policy_json))
  formData.append('async_ingest', String(data.async_ingest ?? true))
  formData.append('max_retries', String(data.max_retries ?? 1))
  if (file) formData.append('file', file)
  const response = await post<KnowledgeDocument>(`/knowledge/${knowledgeId}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return response
}

export const getKnowledgeDocument = (knowledgeId: string, documentId: string): Promise<KnowledgeDocument> => {
  return get<KnowledgeDocument>(`/knowledge/${knowledgeId}/documents/${documentId}`)
}

export const getKnowledgeDocumentContent = async (knowledgeId: string, documentId: string): Promise<string> => {
  const response = await request.get(`/knowledge/${knowledgeId}/documents/${documentId}/content`, {
    responseType: 'text',
  })
  return response.data
}

export const downloadKnowledgeDocument = (knowledgeId: string, documentId: string) => {
  return request.get(`/knowledge/${knowledgeId}/documents/${documentId}/download`, {
    responseType: 'blob',
  })
}

export const listKnowledgeDocumentVersions = (knowledgeId: string, docKey: string): Promise<KnowledgeDocument[]> => {
  return get<KnowledgeDocument[]>(`/knowledge/${knowledgeId}/documents/${docKey}/versions`)
}

export const rollbackKnowledgeDocumentVersion = (
  knowledgeId: string,
  docKey: string,
  version: number
): Promise<KnowledgeDocument> => {
  return post<KnowledgeDocument>(`/knowledge/${knowledgeId}/documents/${docKey}/versions/${version}/rollback`)
}

export const deleteKnowledgeDocument = (
  knowledgeId: string,
  documentId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/knowledge/${knowledgeId}/documents/${documentId}`, undefined, config).then(
    () => undefined,
  )
}

export const listKnowledgeChunks = (
  knowledgeId: string,
  documentId: string,
  params?: { limit?: number; offset?: number }
): Promise<KnowledgeChunk[]> => {
  return get<KnowledgeChunk[]>(`/knowledge/${knowledgeId}/documents/${documentId}/chunks`, params)
}

export const updateKnowledgeChunk = (
  knowledgeId: string,
  documentId: string,
  chunkId: string,
  data: KnowledgeChunkUpdateRequest,
  config?: RequestConfigWithToast,
): Promise<KnowledgeChunk> => {
  return patch<KnowledgeChunk>(
    `/knowledge/${knowledgeId}/documents/${documentId}/chunks/${chunkId}`,
    data,
    config,
  )
}

export const listKnowledgeIngestTasks = (
  knowledgeId: string,
  params?: { status_filter?: string; limit?: number; offset?: number }
): Promise<KnowledgeIngestTask[]> => {
  return get<KnowledgeIngestTask[]>(`/knowledge/${knowledgeId}/ingest-tasks`, params)
}

export const getKnowledgeIngestTask = (knowledgeId: string, taskId: string): Promise<KnowledgeIngestTask> => {
  return get<KnowledgeIngestTask>(`/knowledge/${knowledgeId}/ingest-tasks/${taskId}`)
}

export const retryKnowledgeIngestTask = (
  knowledgeId: string,
  taskId: string,
  config?: RequestConfigWithToast,
): Promise<KnowledgeIngestTask> => {
  return post<KnowledgeIngestTask>(
    `/knowledge/${knowledgeId}/ingest-tasks/${taskId}/retry`,
    undefined,
    config,
  )
}

export const cancelKnowledgeIngestTask = (
  knowledgeId: string,
  taskId: string,
  config?: RequestConfigWithToast,
): Promise<KnowledgeIngestTask> => {
  return post<KnowledgeIngestTask>(
    `/knowledge/${knowledgeId}/ingest-tasks/${taskId}/cancel`,
    undefined,
    config,
  )
}

export const retryKnowledgeDocumentIngest = (
  knowledgeId: string,
  documentId: string,
  maxRetries = 1
): Promise<KnowledgeIngestTask> => {
  return post<KnowledgeIngestTask>(`/knowledge/${knowledgeId}/documents/${documentId}/retry-ingest`, undefined, {
    params: { max_retries: maxRetries },
  })
}

export interface KnowledgeRetrievalSummary {
  since?: string | null
  until?: string | null
  score_threshold: number
  queries: number
  hits: number
  zero_hits: number
  /** Hits over queries; null when nothing was queried in the window. */
  hit_rate?: number | null
  zero_hit_rate?: number | null
}

/**
 * Retrieval quality for one knowledge base, read from the retrieval steps each
 * query already writes. No query text is stored to produce it.
 */
export const getKnowledgeRetrievalSummary = (
  knowledgeId: string,
  params?: { since?: string; until?: string; score_threshold?: number },
): Promise<KnowledgeRetrievalSummary> => {
  return get<KnowledgeRetrievalSummary>(`/knowledge/${knowledgeId}/retrieval/summary`, params)
}

export const queryKnowledge = (
  knowledgeId: string,
  data: KnowledgeQueryRequest
): Promise<KnowledgeQueryResponse> => {
  return post<KnowledgeQueryResponse>(`/knowledge/${knowledgeId}/query`, data)
}
