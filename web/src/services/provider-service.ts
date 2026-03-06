import { get, post, patch, del } from '@/utils/request'
import type { ModelConfig } from '@/pages/model/setting/ui/types'
import type { ProviderConfig } from '@/pages/model/setting/ui/provider-types'

interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

interface ModelResponse {
  id: string
  name: string
  provider: string
  model_ref: string
  description?: string | null
  capabilities_json?: Record<string, any> | null
  config_json?: Record<string, any> | null
  metadata_json?: Record<string, any> | null
  created_at: string
  updated_at: string
}

interface ProviderResponse {
  id: string
  kind: string
  name: string
  base_url?: string | null
  credential_ref?: string | null
  status: string
  sync_policy_json?: Record<string, any> | null
  last_healthcheck_at?: string | null
  last_healthcheck_error?: string | null
  created_at: string
  updated_at: string
}

const SYNC_POLICY_KEYS = ['auto_sync', 'interval_minutes', 'recreate_deleted', 'default_enabled'] as const

const splitProviderSyncPolicy = (syncPolicyJson?: Record<string, any> | null) => {
  const syncPolicy: Record<string, any> = {}
  const meta: Record<string, any> = {}
  const source = syncPolicyJson || {}

  Object.entries(source).forEach(([key, value]) => {
    if ((SYNC_POLICY_KEYS as readonly string[]).includes(key)) {
      syncPolicy[key] = value
      return
    }
    meta[key] = value
  })

  return {
    syncPolicy,
    meta,
  }
}

const buildProviderSyncPolicyPayload = (data: ProviderConfig) => {
  const base = data.syncPolicy || {}
  const meta = {
    _source: data.source,
    _template_id: data.templateId,
    _plugin_id: data.pluginId,
    _plugin_name: data.pluginName,
    _plugin_version: data.pluginVersion,
    _model_hints: data.metadata?.modelHints,
  }

  return {
    ...base,
    ...Object.fromEntries(Object.entries(meta).filter(([, value]) => value !== undefined && value !== null && value !== '')),
  }
}

interface ProviderModelResponse {
  id: string
  provider_id: string
  provider_kind: string
  model_id: string
  display_name?: string | null
  description?: string | null
  capabilities_json?: Record<string, any> | null
  config_json?: Record<string, any> | null
  context_window?: number | null
  max_output_tokens?: number | null
  lifecycle?: string | null
  raw_meta?: Record<string, any> | null
  enabled: boolean
  source: string
  platform_model_id?: string | null
  sync_status: string
  user_overrides_json?: Record<string, any> | null
  last_synced_at?: string | null
  created_at: string
  updated_at: string
}

export type ModelLibraryItem = {
  id: string
  name: string
  modelName: string
  modelType: string
  provider: string
  description?: string
  contextLength?: number
  capabilities?: string[]
  isActive: boolean
  createdAt: string
  updatedAt: string
}

const mapLibraryModel = (model: ModelResponse): ModelLibraryItem => {
  const capabilities = model.capabilities_json || {}
  const config = model.config_json || {}
  const metadata = model.metadata_json || {}
  return {
    id: model.id,
    name: model.name,
    modelName: model.model_ref,
    modelType: (capabilities.model_type as string) || 'llm',
    provider: model.provider,
    description: model.description || undefined,
    contextLength: config.contextLength,
    capabilities: (capabilities.capabilities as string[]) || [],
    isActive: metadata.isActive !== false,
    createdAt: model.created_at,
    updatedAt: model.updated_at,
  }
}

const mapProviderToConfig = (provider: ProviderResponse): ProviderConfig => {
  const { syncPolicy, meta } = splitProviderSyncPolicy(provider.sync_policy_json)

  return {
    id: provider.id,
    name: provider.name,
    kind: provider.kind as ProviderConfig['kind'],
    baseUrl: provider.base_url || '',
    credentialRef: provider.credential_ref || '',
    status: provider.status as ProviderConfig['status'],
    syncPolicy,
    source: (meta._source as ProviderConfig['source']) || 'builtin',
    templateId: (meta._template_id as string) || undefined,
    pluginId: (meta._plugin_id as string) || undefined,
    pluginName: (meta._plugin_name as string) || undefined,
    pluginVersion: (meta._plugin_version as string) || undefined,
    metadata: {
      modelHints: Array.isArray(meta._model_hints) ? meta._model_hints : undefined,
    },
    createdAt: provider.created_at,
    updatedAt: provider.updated_at,
  }
}

const mapProviderModelToConfig = (model: ProviderModelResponse): ModelConfig => {
  const capabilities = model.capabilities_json || {}
  return {
    id: model.id,
    providerId: model.provider_id,
    providerKind: model.provider_kind,
    modelId: model.model_id,
    displayName: model.display_name || '',
    description: model.description || '',
    capabilities: (capabilities.capabilities as string[]) || [],
    contextWindow: model.context_window || undefined,
    maxOutputTokens: model.max_output_tokens || undefined,
    lifecycle: model.lifecycle || undefined,
    enabled: model.enabled,
    source: model.source as ModelConfig['source'],
    syncStatus: model.sync_status,
    userOverrides: (model.user_overrides_json?.fields as string[]) || [],
    config: model.config_json || {},
    createdAt: model.created_at,
    updatedAt: model.updated_at,
  }
}

const mapConfigToCreatePayload = (data: Partial<ModelConfig>) => {
  return {
    model_id: data.modelId || '',
    display_name: data.displayName || undefined,
    description: data.description || undefined,
    capabilities_json: data.capabilities ? { capabilities: data.capabilities } : undefined,
    config_json: data.config || undefined,
    context_window: data.contextWindow,
    max_output_tokens: data.maxOutputTokens,
    lifecycle: data.lifecycle,
    raw_meta: undefined,
    enabled: data.enabled ?? true,
  }
}

const mapConfigToUpdatePayload = (data: Partial<ModelConfig>) => {
  return {
    display_name: data.displayName,
    description: data.description,
    capabilities_json: data.capabilities ? { capabilities: data.capabilities } : undefined,
    config_json: data.config,
    context_window: data.contextWindow,
    max_output_tokens: data.maxOutputTokens,
    lifecycle: data.lifecycle,
    enabled: data.enabled,
  }
}

export async function listProviders() {
  const response = await get<PaginatedResponse<ProviderResponse>>('/modelhub/providers', { page_size: 200 }).then(response => response.data)
  return (response?.items || []).map(mapProviderToConfig)
}

export async function listModels(params?: { provider?: string }) {
  const response = await get<PaginatedResponse<ModelResponse>>('/models', {
    page_size: 200,
    ...(params?.provider ? { provider: params.provider } : {}),
  }).then(response => response.data)
  return (response?.items || []).map(mapLibraryModel)
}

export async function getProvider(id: string) {
  const providers = await listProviders()
  const provider = providers.find((item) => item.id === id)
  if (!provider) {
    throw new Error('Provider not found')
  }
  return provider
}

export async function createProvider(data: ProviderConfig) {
  const payload = {
    name: data.name,
    kind: data.kind,
    base_url: data.baseUrl || undefined,
    credential_ref: data.credentialRef || undefined,
    status: data.status,
    sync_policy_json: buildProviderSyncPolicyPayload(data),
  }
  const response = await post<ProviderResponse>('/modelhub/providers', payload).then(response => response.data)
  return mapProviderToConfig(response as ProviderResponse)
}

export async function updateProvider(id: string, data: ProviderConfig) {
  const payload = {
    name: data.name,
    kind: data.kind,
    base_url: data.baseUrl || undefined,
    credential_ref: data.credentialRef || undefined,
    status: data.status,
    sync_policy_json: buildProviderSyncPolicyPayload(data),
  }
  const response = await patch<ProviderResponse>(`/modelhub/providers/${id}`, payload).then(response => response.data)
  return mapProviderToConfig(response as ProviderResponse)
}

export async function deleteProvider(id: string) {
  await del(`/modelhub/providers/${id}`)
}

export async function listProviderModels(providerId: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>(
    `/modelhub/providers/${providerId}/models`,
    { page_size: 200 }
  ).then(response => response.data)
  return (response?.items || []).map(mapProviderModelToConfig)
}

export async function getProviderModel(providerId: string, modelId: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>(
    `/modelhub/providers/${providerId}/models`,
    { page_size: 200 }
  ).then(response => response.data)
  const model = (response.items || []).find((item) => item.id === modelId)
  if (!model) {
    throw new Error('Model not found')
  }
  return mapProviderModelToConfig(model)
}

export async function createProviderModel(providerId: string, data: Partial<ModelConfig>) {
  const payload = mapConfigToCreatePayload(data)
  const response = await post<ProviderModelResponse>(`/modelhub/providers/${providerId}/models`, payload).then(response => response.data)
  return mapProviderModelToConfig(response as ProviderModelResponse)
}

export async function updateProviderModel(providerId: string, modelId: string, data: Partial<ModelConfig>) {
  const payload = mapConfigToUpdatePayload(data)
  const response = await patch<ProviderModelResponse>(`/modelhub/providers/${providerId}/models/${modelId}`, payload).then(response => response.data)
  return mapProviderModelToConfig(response as ProviderModelResponse)
}

export async function deleteProviderModel(providerId: string, modelId: string) {
  await del(`/modelhub/providers/${providerId}/models/${modelId}`)
}

export async function syncFromPlatform(providerId: string, includeModelIds?: string[]) {
  const payload = includeModelIds ? { include_model_ids: includeModelIds } : undefined
  const response = await post(`/modelhub/providers/${providerId}/sync-from-platform`, payload).then(response => response.data)
  return response
}

export async function healthCheck(providerId: string) {
  const response = await post(`/modelhub/providers/${providerId}/healthcheck`).then(response => response.data)
  return response
}

export async function listSyncJobs(providerId: string) {
  const response = await get<PaginatedResponse<any>>(`/modelhub/providers/${providerId}/sync-jobs`, {
    page_size: 50,
  }).then(response => response.data)
  return response.items || []
}

export async function listPlatformModels(providerKind: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>('/modelhub/platform-models', {
    provider_kind: providerKind,
    page_size: 200,
  }).then(response => response.data)
  return (response?.items || []).map(mapProviderModelToConfig)
}

export async function testModelConnection(providerId: string, modelId: string, input: string, type: 'chat' | 'embeddings') {
  const endpoint = type === 'chat' ? '/modelhub/test/chat' : '/modelhub/test/embeddings'
  const response = await post(endpoint, {
    provider_id: providerId,
    model_id: modelId,
    input,
  }).then(response => response.data)
  return response
}
