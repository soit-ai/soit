import { get, post, del, put, patch, getFile } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface Dataset {
  id: string
  tenant_id: string
  workspace_id: string
  name: string
  type: string
  description?: string | null
  status: string
  visibility: string
  settings_json: Record<string, any>
  chunking_json: Record<string, any>
  retrieval_json: Record<string, any>
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

export interface Document {
  id: string
  tenant_id: string
  workspace_id: string
  dataset_id: string
  doc_key: string
  version: number
  is_latest: boolean
  source_type: string
  title?: string | null
  language?: string | null
  mime_type?: string | null
  filename?: string | null
  size_bytes?: number | null
  checksum?: string | null
  content_hash?: string | null
  source_uri?: string | null
  file_id?: string | null
  error_code?: string | null
  error_message?: string | null
  retry_count: number
  status: string
  parse_meta_json?: Record<string, any>
  index_meta_json?: Record<string, any>
  created_at: string
  updated_at: string
  deleted_at?: string | null
}

export interface Chunk {
  id: string
  tenant_id: string
  workspace_id: string
  dataset_id: string
  document_id: string
  document_version: number
  chunk_no: number
  chunk_key?: string | null
  text_preview?: string | null
  start_offset?: number | null
  end_offset?: number | null
  page_no?: number | null
  section_path?: string[]
  char_count?: number | null
  token_count?: number | null
  index_status: string
  created_at: string
  updated_at: string
}

export interface Index {
  id: string
  tenant_id: string
  workspace_id: string
  dataset_id: string
  name: string
  is_primary: boolean
  provider: string
  embedding_model_ref: string
  dimension: number
  metric_type: string
  status: string
  build_version: number
  doc_count: number
  chunk_count: number
  vector_count: number
  collection_name?: string | null
  partition_strategy?: string | null
  namespace?: string | null
  index_params_json?: Record<string, any> | null
  search_params_json?: Record<string, any> | null
  reranker_ref?: string | null
  filters_json?: Record<string, any> | null
  last_error_code?: string | null
  last_error_message?: string | null
  created_at: string
  updated_at: string
}

export interface IngestTask {
  id: string
  tenant_id: string
  workspace_id: string
  dataset_id: string
  document_id?: string | null
  status: string
  payload_json: Record<string, any>
  run_id?: string | null
  error_code?: string | null
  error_message?: string | null
  retry_count: number
  max_retries: number
  started_at?: string | null
  finished_at?: string | null
  created_by?: string | null
  updated_by?: string | null
  created_at: string
  updated_at: string
}

export interface DatasetRun {
  id: string
  trace_id?: string | null
  user_id?: string | null
  mode: string
  kind?: string | null
  app_version_id?: string | null
  status: string
  input_summary?: string | null
  output_summary?: string | null
  started_at: string
  ended_at?: string | null
  duration_ms?: number | null
  error_code?: string | null
  error_message?: string | null
  error_step_id?: string | null
  created_at: string
  updated_at: string
}

export interface DatasetRunCostSummary {
  tokens_prompt: number
  tokens_completion: number
  embedding_count: number
  rerank_count: number
  ms_total: number
  storage_bytes: number
}

export interface DatasetRunCostByMode extends DatasetRunCostSummary {
  mode: string
}

export interface DatasetRunCostByProvider extends DatasetRunCostSummary {
  provider?: string | null
}

export interface DatasetRunCostByModel extends DatasetRunCostSummary {
  model_ref?: string | null
}

export interface DatasetApplicationUsage {
  app_id: string
  app_name: string
  app_type: string
  app_status: string
  app_version_id: string
  app_version: number
  app_version_status: string
  app_version_created_at: string
  run_count: number
  last_run_at?: string | null
}

export interface QueryResult {
  chunk_id: string
  document_id: string
  score: number
  text: string
  snippets?: string[]
  metadata?: Record<string, any>
}

export interface QueryCitation {
  chunk_id: string
  document_id: string
  rank: number
  score: number
  dataset_id?: string | null
  doc_key?: string | null
  title?: string | null
  source_uri?: string | null
  chunk_no?: number | null
  page_no?: number | null
  section_path?: string[] | null
  snippet?: string | null
}

export interface QueryResponse {
  results: QueryResult[]
  total: number
  citations: QueryCitation[]
}

export const listDatasets = (params?: {
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Dataset>> => {
  return get<PaginatedResponse<Dataset>>('/datasets', params).then(response => response.data)
}

export const getDataset = (datasetId: string): Promise<Dataset> => {
  return get<Dataset>(`/datasets/${datasetId}`).then(response => response.data)
}

export const createDataset = (data: {
  name: string
  type: string
  description?: string
  visibility?: string
  settings_json?: Record<string, any>
  chunking_json?: Record<string, any>
  retrieval_json?: Record<string, any>
  default_embedding_model_ref?: string
  default_reranker_ref?: string
  tags?: string[]
}): Promise<Dataset> => {
  return post<Dataset>('/datasets', data).then(response => response.data)
}

export const updateDataset = (
  datasetId: string,
  data: {
    name?: string
    description?: string
    status?: string
    visibility?: string
    settings_json?: Record<string, any>
    chunking_json?: Record<string, any>
    retrieval_json?: Record<string, any>
    default_embedding_model_ref?: string
    default_reranker_ref?: string
    tags?: string[]
  }
): Promise<Dataset> => {
  return put<Dataset>(`/datasets/${datasetId}`, data).then(response => response.data)
}

export const deleteDataset = (datasetId: string): Promise<void> => {
  return del(`/datasets/${datasetId}`).then(response => response.data)
}

export const listDocuments = (
  datasetId: string,
  params?: {
    is_latest_only?: boolean
    limit?: number
    offset?: number
  }
): Promise<Document[]> => {
  return get<Document[]>(`/datasets/${datasetId}/documents`, params).then(response => response.data)
}

export const listChunks = (
  datasetId: string,
  documentId: string,
  params?: {
    limit?: number
    offset?: number
  }
): Promise<Chunk[]> => {
  return get<Chunk[]>(`/datasets/${datasetId}/documents/${documentId}/chunks`, params).then(response => response.data)
}

export const updateChunk = (
  datasetId: string,
  documentId: string,
  chunkId: string,
  data: {
    content?: string
    index_status?: 'pending' | 'indexed' | 'failed' | 'disabled'
  }
): Promise<Chunk> => {
  return patch<Chunk>(`/datasets/${datasetId}/documents/${documentId}/chunks/${chunkId}`, data).then(response => response.data)
}

export const getDocument = (datasetId: string, documentId: string): Promise<Document> => {
  return get<Document>(`/datasets/${datasetId}/documents/${documentId}`).then(response => response.data)
}

export const getDocumentContent = (
  datasetId: string,
  documentId: string
): Promise<string> => {
  return get<string>(`/datasets/${datasetId}/documents/${documentId}/content`, undefined, {
    responseType: 'text',
  }).then(response => response.data)
}

export const downloadDocument = (
  datasetId: string,
  documentId: string
) => {
  return getFile<Blob>(`/datasets/${datasetId}/documents/${documentId}/download`).then(response => response.data)
}

export interface DocumentUploadRequest {
  doc_key: string
  source_type: 'upload' | 'crawler' | 'api' | 'manual'
  source_uri?: string
  file_id?: string
  title?: string
  language?: string
  mime_type?: string
  filename?: string
  size_bytes?: number
  checksum?: string
  content_hash?: string
  access_policy_json?: Record<string, any>
  async_ingest?: boolean
  max_retries?: number
}

export const uploadDocument = async (
  datasetId: string,
  data: DocumentUploadRequest,
  file?: File
): Promise<Document> => {
  const formData = new FormData()
  formData.append('doc_key', data.doc_key)
  formData.append('source_type', data.source_type)
  if (data.source_uri) formData.append('source_uri', data.source_uri)
  if (data.file_id) formData.append('file_id', data.file_id)
  if (data.title) formData.append('title', data.title)
  if (data.language) formData.append('language', data.language)
  if (data.mime_type) formData.append('mime_type', data.mime_type)
  if (data.filename) formData.append('filename', data.filename)
  if (data.size_bytes) formData.append('size_bytes', String(data.size_bytes))
  if (data.checksum) formData.append('checksum', data.checksum)
  if (data.content_hash) formData.append('content_hash', data.content_hash)
  if (data.access_policy_json) formData.append('access_policy_json', JSON.stringify(data.access_policy_json))
  if (typeof data.async_ingest === 'boolean') formData.append('async_ingest', String(data.async_ingest))
  if (typeof data.max_retries === 'number') formData.append('max_retries', String(data.max_retries))
  if (file) formData.append('file', file)
  return post<Document>(`/datasets/${datasetId}/documents`, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  }).then(response => response.data)
}

export const deleteDocument = (datasetId: string, documentId: string): Promise<void> => {
  return del(`/datasets/${datasetId}/documents/${documentId}`).then(response => response.data)
}

export const listIngestTasks = (
  datasetId: string,
  params?: { status_filter?: string; limit?: number; offset?: number }
): Promise<IngestTask[]> => {
  return get<IngestTask[]>(`/datasets/${datasetId}/ingest-tasks`, params).then(response => response.data)
}

export const getIngestTask = (datasetId: string, taskId: string): Promise<IngestTask> => {
  return get<IngestTask>(`/datasets/${datasetId}/ingest-tasks/${taskId}`).then(response => response.data)
}

export const retryIngestTask = (datasetId: string, taskId: string): Promise<IngestTask> => {
  return post<IngestTask>(`/datasets/${datasetId}/ingest-tasks/${taskId}/retry`).then(response => response.data)
}

export const cancelIngestTask = (datasetId: string, taskId: string): Promise<IngestTask> => {
  return post<IngestTask>(`/datasets/${datasetId}/ingest-tasks/${taskId}/cancel`).then(response => response.data)
}

export const retryDocumentIngest = (
  datasetId: string,
  documentId: string,
  data?: { max_retries?: number }
): Promise<IngestTask> => {
  return post<IngestTask>(`/datasets/${datasetId}/documents/${documentId}/retry-ingest`, data).then(response => response.data)
}

export const listDocumentVersions = (datasetId: string, docKey: string): Promise<Document[]> => {
  return get<Document[]>(`/datasets/${datasetId}/documents/${docKey}/versions`).then(response => response.data)
}

export const rollbackDocumentVersion = (
  datasetId: string,
  docKey: string,
  version: number
): Promise<Document> => {
  return post<Document>(`/datasets/${datasetId}/documents/${docKey}/versions/${version}/rollback`).then(response => response.data)
}

export const queryDataset = (
  datasetId: string,
  data: {
    query: string
    top_k?: number
    index_id?: string
    filter?: Record<string, any>
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
): Promise<QueryResponse> => {
  return post<QueryResponse>(`/datasets/${datasetId}/query`, data).then(response => response.data)
}

export const listIndexes = (datasetId: string, params?: { limit?: number; offset?: number }): Promise<Index[]> => {
  return get<Index[]>(`/datasets/${datasetId}/indexes`, params).then(response => response.data)
}

export const getIndex = (datasetId: string, indexId: string): Promise<Index> => {
  return get<Index>(`/datasets/${datasetId}/indexes/${indexId}`).then(response => response.data)
}

export const createIndex = (
  datasetId: string,
  data: {
    name: string
    provider?: string
    embedding_model_ref: string
    dimension?: number
    metric_type?: string
    is_primary?: boolean
    collection_name?: string
    partition_strategy?: string
    namespace?: string
    index_params_json?: Record<string, any>
    search_params_json?: Record<string, any>
    reranker_ref?: string
    filters_json?: Record<string, any>
  }
): Promise<Index> => {
  return post<Index>(`/datasets/${datasetId}/indexes`, data).then(response => response.data)
}

export const updateIndex = (
  datasetId: string,
  indexId: string,
  data: {
    name?: string
    is_primary?: boolean
    status?: string
    search_params_json?: Record<string, any>
    reranker_ref?: string
    filters_json?: Record<string, any>
  }
): Promise<Index> => {
  return patch<Index>(`/datasets/${datasetId}/indexes/${indexId}`, data).then(response => response.data)
}

export const deleteIndex = (datasetId: string, indexId: string): Promise<void> => {
  return del(`/datasets/${datasetId}/indexes/${indexId}`).then(response => response.data)
}

export const rebuildIndex = (datasetId: string, indexId: string): Promise<Index> => {
  return post<Index>(`/datasets/${datasetId}/indexes/${indexId}/rebuild`).then(response => response.data)
}

export const listDatasetRuns = (
  datasetId: string,
  params?: {
    mode?: string
    kind?: string
    status?: string
    started_after?: string
    started_before?: string
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<DatasetRun>> => {
  return get<PaginatedResponse<DatasetRun>>(`/datasets/${datasetId}/runs`, params).then(response => response.data)
}

export const getDatasetRunCostSummary = (
  datasetId: string,
  params?: {
    mode?: string
    kind?: string
    status?: string
    started_after?: string
    started_before?: string
  }
): Promise<DatasetRunCostSummary> => {
  return get<DatasetRunCostSummary>(`/datasets/${datasetId}/runs/costs/summary`, params).then(response => response.data)
}

export const getDatasetRunCostByMode = (
  datasetId: string,
  params?: {
    mode?: string
    kind?: string
    status?: string
    started_after?: string
    started_before?: string
  }
): Promise<DatasetRunCostByMode[]> => {
  return get<DatasetRunCostByMode[]>(`/datasets/${datasetId}/runs/costs/by-mode`, params).then(response => response.data)
}

export const getDatasetRunCostByProvider = (
  datasetId: string,
  params?: {
    mode?: string
    kind?: string
    status?: string
    started_after?: string
    started_before?: string
  }
): Promise<DatasetRunCostByProvider[]> => {
  return get<DatasetRunCostByProvider[]>(`/datasets/${datasetId}/runs/costs/by-provider`, params).then(response => response.data)
}

export const getDatasetRunCostByModel = (
  datasetId: string,
  params?: {
    mode?: string
    kind?: string
    status?: string
    started_after?: string
    started_before?: string
  }
): Promise<DatasetRunCostByModel[]> => {
  return get<DatasetRunCostByModel[]>(`/datasets/${datasetId}/runs/costs/by-model`, params).then(response => response.data)
}

export const listDatasetAppUsages = (
  datasetId: string,
  params?: { limit?: number }
): Promise<DatasetApplicationUsage[]> => {
  return get<DatasetApplicationUsage[]>(`/datasets/${datasetId}/applications`, params).then(response => response.data)
}
