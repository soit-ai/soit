import { get, post, patch, del, type RequestConfigWithToast } from '@/utils/request'
import type { ModelConfig } from '@/routes/model/setting/ui/types'
import type { ProviderConfig } from '@/routes/model/setting/ui/types'
import type { PaginatedResponse } from '@/types/api'

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
  adapter_backend: 'native' | 'litellm'
  slug?: string | null
  kind: string
  name: string
  base_url?: string | null
  credential_secret_id?: string | null
  status: string
  sync_policy_json?: Record<string, any> | null
  connection_config_json?: Record<string, any> | null
  auth_config_json?: Record<string, any> | null
  runtime_config_json?: Record<string, any> | null
  governance_config_json?: Record<string, any> | null
  last_synced_at?: string | null
  last_healthcheck_at?: string | null
  last_healthcheck_error?: string | null
  created_at: string
  updated_at: string
}

export interface ProviderSupportStatus {
  provider_kind: string
  display_name: string
  support_status: 'supported' | 'unavailable' | 'unsupported'
  configured: boolean
  provider_count: number
  configured_provider_ids: string[]
  chat_supported: boolean
  embeddings_supported: boolean
  catalog_supported: boolean
  notes?: string | null
}

export interface AdapterBackendSupport {
  adapter_backend: 'native' | 'litellm'
  display_name: string
  available: boolean
  install_hint?: string | null
}

export interface ProviderPreset {
  provider_kind: string
  display_name: string
  default_adapter_backend: 'native' | 'litellm'
  supported_adapter_backends: Array<'native' | 'litellm'>
  litellm_provider: string
  requires_base_url: boolean
  credential_optional: boolean
}

interface ProviderSupportMatrixResponse {
  providers: ProviderSupportStatus[]
  adapter_backends: AdapterBackendSupport[]
  provider_presets: ProviderPreset[]
}

const normalizeCapabilitySupport = (value: unknown): boolean | null => {
  if (typeof value === 'boolean') return value
  if (typeof value !== 'string') return null
  const normalized = value.toLowerCase()
  if (['true', 'supported', 'trusted', 'passed', 'callable', 'enabled'].includes(normalized)) return true
  if (['false', 'unsupported', 'failed', 'unavailable', 'disabled'].includes(normalized)) return false
  return null
}

const normalizeModelCapabilityMatrix = (matrix: Record<string, any> | null | undefined) => {
  return Object.fromEntries(Object.entries(matrix || {}).map(([key, rawValue]) => {
    const entry = typeof rawValue === 'boolean' ? { catalog: rawValue } : (rawValue || {})
    const catalog = normalizeCapabilitySupport(entry.catalog)
    const diagnostics = normalizeCapabilitySupport(entry.diagnostics)
    const runtime = normalizeCapabilitySupport(entry.runtime)
    const userOverride = entry.user_override || 'auto'
    let merged: boolean | null
    if (userOverride === 'force_on') merged = true
    else if (userOverride === 'force_off') merged = false
    else if (userOverride === 'enable_after_diagnostics') merged = diagnostics === true
    else merged = diagnostics ?? runtime ?? catalog ?? (typeof entry.merged === 'boolean' ? entry.merged : null)
    return [key, {
      catalog,
      diagnostics,
      runtime,
      merged,
      user_override: userOverride,
    }]
  }))
}

export interface ModelWorkbenchSummary {
  total_models: number
  available_models: number
  total_providers: number
  online_providers: number
  month_calls: number
  month_tokens: number
  month_cost_amount: number
  currency?: string | null
  avg_latency_ms?: number | null
  abnormal_models: number
  updated_at: string
}

export interface ModelWorkbenchModelTabs {
  all: number
  text: number
  embedding: number
  multimodal: number
  rerank: number
  disabled: number
  abnormal: number
}

export interface ModelWorkbenchProviderTabs {
  all: number
  online: number
  disabled: number
  error: number
}

export interface ModelWorkbenchModelRow {
  id: string
  provider_id: string
  provider_slug: string
  provider_name: string
  provider_kind: string
  model_id: string
  display_name?: string | null
  description?: string | null
  model_type: string
  status: 'available' | 'disabled' | 'abnormal'
  context_window?: number | null
  max_output_tokens?: number | null
  lifecycle_status?: string | null
  sync_status: string
  source: string
  month_calls: number
  today_calls: number
  month_tokens: number
  month_cost_amount: number
  currency?: string | null
  avg_latency_ms?: number | null
  recent_exception_count: number
  last_run_at?: string | null
  last_synced_at?: string | null
  updated_at: string
  owner?: string | null
  region?: string | null
  unit_price?: number | null
  action_enabled: boolean
}

export interface ModelWorkbenchProviderRow {
  id: string
  name: string
  kind: string
  status: 'online' | 'disabled' | 'error'
  available_models: number
  total_models: number
  model_types: string[]
  month_calls: number
  month_tokens: number
  month_cost_amount: number
  currency?: string | null
  avg_latency_ms?: number | null
  recent_exception_count: number
  availability?: number | null
  last_sync_at?: string | null
  last_healthcheck_at?: string | null
  updated_at: string
  owner?: string | null
  region?: string | null
  quota_used?: number | null
  quota_limit?: number | null
  quota_percent?: number | null
}

export interface ModelWorkbenchTrendPoint {
  date: string
  calls: number
  tokens: number
  cost_amount: number
  avg_latency_ms?: number | null
}

export interface ModelWorkbenchCostShareRow {
  id: string
  label: string
  provider_kind?: string | null
  value: number
  currency?: string | null
}

export interface ModelWorkbenchQuotaReminderRow {
  id: string
  label: string
  status: 'normal' | 'warning'
  quota_used?: number | null
  quota_limit?: number | null
  quota_percent?: number | null
  remaining_quota?: number | null
}

export interface ModelWorkbenchOverviewResponse {
  summary: ModelWorkbenchSummary
  model_tabs: ModelWorkbenchModelTabs
  provider_tabs: ModelWorkbenchProviderTabs
  trend: ModelWorkbenchTrendPoint[]
  cost_share: ModelWorkbenchCostShareRow[]
  top_models: ModelWorkbenchModelRow[]
  top_providers: ModelWorkbenchProviderRow[]
  quota_reminders: ModelWorkbenchQuotaReminderRow[]
}

export interface ModelWorkbenchModelsResponse {
  summary: ModelWorkbenchSummary
  tabs: ModelWorkbenchModelTabs
  items: ModelWorkbenchModelRow[]
  next_page_token?: string | null
  page_size: number
}

export interface ModelWorkbenchProvidersResponse {
  summary: ModelWorkbenchSummary
  tabs: ModelWorkbenchProviderTabs
  items: ModelWorkbenchProviderRow[]
  next_page_token?: string | null
  page_size: number
}

const SYNC_POLICY_KEYS = [
  'auto_sync',
  'interval_minutes',
  'recreate_deleted',
  'default_enabled',
  'catalog_supported',
  'include_models',
  'exclude_models',
] as const

const MODEL_CAPABILITY_KEYS = [
  'chat',
  'streaming',
  'embedding',
  'vision',
  'file_input',
  'audio_input',
  'video_input',
  'image_output',
  'tool_calling',
  'structured_outputs',
  'reasoning',
  'rerank',
] as const

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
  model_ref: string
  display_name?: string | null
  description?: string | null
  capabilities_json?: Record<string, any> | null
  config_json?: Record<string, any> | null
  architecture_json?: Record<string, any> | null
  capability_matrix_json?: Record<string, any> | null
  parameter_config_json?: Record<string, any> | null
  pricing_json?: Record<string, any> | null
  diagnostics_json?: Record<string, any> | null
  context_window?: number | null
  max_output_tokens?: number | null
  status: string
  lifecycle_status?: string | null
  raw_meta?: Record<string, any> | null
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
  providerName?: string
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
    adapterBackend: provider.adapter_backend,
    slug: provider.slug || provider.kind,
    name: provider.name,
    kind: provider.kind as ProviderConfig['kind'],
    baseUrl: provider.base_url || '',
    credentialSecretId: provider.credential_secret_id || '',
    status: provider.status as ProviderConfig['status'],
    lastSyncedAt: provider.last_synced_at || undefined,
    lastHealthcheckAt: provider.last_healthcheck_at || undefined,
    lastHealthcheckError: provider.last_healthcheck_error || undefined,
    syncPolicy,
    connectionConfig: provider.connection_config_json || {},
    authConfig: provider.auth_config_json || {},
    runtimeConfig: provider.runtime_config_json || {},
    governanceConfig: provider.governance_config_json || {},
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
  const capabilityList = Array.isArray(capabilities.capabilities)
    ? (capabilities.capabilities as string[])
    : MODEL_CAPABILITY_KEYS.filter((key) => capabilities[key] === true)
  return {
    id: model.id,
    providerId: model.provider_id,
    providerKind: model.provider_kind,
    modelId: model.model_id,
    displayName: model.display_name || '',
    description: model.description || '',
    capabilities: capabilityList,
    capabilitiesJson: capabilities,
    contextWindow: model.context_window || undefined,
    maxOutputTokens: model.max_output_tokens || undefined,
    lifecycle: model.lifecycle_status || undefined,
    status: model.status,
    enabled: model.status === 'active',
    source: model.source as ModelConfig['source'],
    platformModelId: model.platform_model_id || undefined,
    lastSyncedAt: model.last_synced_at || undefined,
    architecture: model.architecture_json || {},
    capabilityMatrix: normalizeModelCapabilityMatrix(model.capability_matrix_json),
    parameterConfig: model.parameter_config_json || {},
    pricing: model.pricing_json || {},
    diagnostics: model.diagnostics_json || {},
    rawMeta: model.raw_meta || {},
    userOverridesJson: model.user_overrides_json || {},
    syncStatus: model.sync_status,
    userOverrides: (model.user_overrides_json?.fields as string[]) || [],
    config: model.config_json || {},
    createdAt: model.created_at,
    updatedAt: model.updated_at,
  }
}

const buildModelCapabilitiesPayload = (data: Partial<ModelConfig>) => {
  const payload: Record<string, any> = {
    ...(data.capabilitiesJson || {}),
  }
  const selected = new Set<string>(data.capabilities || [])

  Object.entries(data.capabilityMatrix || {}).forEach(([key, value]) => {
    if (value?.merged === true) {
      selected.add(key)
    }
    if (value?.merged === false) {
      selected.delete(key)
    }
  })

  payload.capabilities = Array.from(selected)
  MODEL_CAPABILITY_KEYS.forEach((key) => {
    payload[key] = selected.has(key)
  })
  return payload
}

const mapConfigToCreatePayload = (data: Partial<ModelConfig>) => {
  return {
    model_id: data.modelId || '',
    display_name: data.displayName || undefined,
    description: data.description || undefined,
    capabilities_json: data.capabilities || data.capabilityMatrix || data.capabilitiesJson
      ? buildModelCapabilitiesPayload(data)
      : undefined,
    config_json: data.config || undefined,
    architecture_json: data.architecture,
    capability_matrix_json: data.capabilityMatrix,
    parameter_config_json: data.parameterConfig,
    pricing_json: data.pricing,
    diagnostics_json: data.diagnostics,
    context_window: data.contextWindow,
    max_output_tokens: data.maxOutputTokens,
    lifecycle_status: data.lifecycle,
    source: data.source,
    platform_model_id: data.platformModelId,
    last_synced_at: data.lastSyncedAt,
    status: data.status || (data.enabled === false ? 'disabled' : 'active'),
    raw_meta: data.rawMeta,
    user_overrides_json: data.userOverridesJson,
  }
}

const mapConfigToUpdatePayload = (data: Partial<ModelConfig>) => {
  return {
    display_name: data.displayName,
    description: data.description,
    capabilities_json: data.capabilities || data.capabilityMatrix || data.capabilitiesJson
      ? buildModelCapabilitiesPayload(data)
      : undefined,
    config_json: data.config,
    architecture_json: data.architecture,
    capability_matrix_json: data.capabilityMatrix,
    parameter_config_json: data.parameterConfig,
    pricing_json: data.pricing,
    diagnostics_json: data.diagnostics,
    context_window: data.contextWindow,
    max_output_tokens: data.maxOutputTokens,
    lifecycle_status: data.lifecycle,
    source: data.source,
    platform_model_id: data.platformModelId,
    last_synced_at: data.lastSyncedAt,
    raw_meta: data.rawMeta,
    user_overrides_json: data.userOverridesJson,
    status: data.status ?? (data.enabled === undefined ? undefined : (data.enabled ? 'active' : 'disabled')),
  }
}

export async function listProviders() {
  const response = await get<PaginatedResponse<ProviderResponse>>('/modelhub/providers', { page_size: 200 })
  return (response?.items || []).map(mapProviderToConfig)
}

export async function getProviderSupportMatrix() {
  const response = await get<ProviderSupportMatrixResponse>('/modelhub/providers/support-matrix')
  return {
    providers: response.providers || [],
    adapterBackends: response.adapter_backends || [],
    providerPresets: response.provider_presets || [],
  }
}

export async function getModelWorkbenchOverview() {
  return get<ModelWorkbenchOverviewResponse>('/modelhub/workbench/overview')
}

export async function getModelWorkbenchModels(params?: {
  page_token?: string
  page_size?: number
  tab?: string
  keyword?: string
  provider_id?: string
  status?: string
  model_type?: string
}) {
  return get<ModelWorkbenchModelsResponse>('/modelhub/workbench/models', params)
}

export async function getModelWorkbenchProviders(params?: {
  page_token?: string
  page_size?: number
  tab?: string
  keyword?: string
  status?: string
  model_type?: string
}) {
  return get<ModelWorkbenchProvidersResponse>('/modelhub/workbench/providers', params)
}

export async function listModels(params?: { provider?: string }) {
  const response = await getModelWorkbenchModels({
    page_size: 200,
    ...(params?.provider ? { provider_id: params.provider } : {}),
  })
  return (response?.items || []).map((model): ModelLibraryItem => ({
    id: model.id,
    name: model.display_name || model.model_id,
    modelName: `model:${model.provider_slug}:${model.model_id}`,
    modelType: model.model_type,
    provider: model.provider_slug,
    providerName: model.provider_name || model.provider_slug,
    description: model.description || undefined,
    contextLength: model.context_window || undefined,
    capabilities: [],
    isActive: model.status === 'available',
    createdAt: model.updated_at,
    updatedAt: model.updated_at,
  }))
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
    adapter_backend: data.adapterBackend,
    slug: data.slug || data.kind,
    name: data.name,
    kind: data.kind,
    base_url: data.baseUrl || undefined,
    credential_secret_id: data.credentialSecretId || undefined,
    status: data.status,
    sync_policy_json: buildProviderSyncPolicyPayload(data),
    connection_config_json: data.connectionConfig || undefined,
    auth_config_json: data.authConfig || undefined,
    runtime_config_json: data.runtimeConfig || undefined,
    governance_config_json: data.governanceConfig || undefined,
  }
  const response = await post<ProviderResponse>('/modelhub/providers', payload)
  return mapProviderToConfig(response as ProviderResponse)
}

export async function updateProvider(id: string, data: ProviderConfig) {
  const payload = {
    adapter_backend: data.adapterBackend,
    slug: data.slug || data.kind,
    name: data.name,
    kind: data.kind,
    base_url: data.baseUrl || undefined,
    credential_secret_id: data.credentialSecretId || undefined,
    status: data.status,
    sync_policy_json: buildProviderSyncPolicyPayload(data),
    connection_config_json: data.connectionConfig || undefined,
    auth_config_json: data.authConfig || undefined,
    runtime_config_json: data.runtimeConfig || undefined,
    governance_config_json: data.governanceConfig || undefined,
  }
  const response = await patch<ProviderResponse>(`/modelhub/providers/${id}`, payload)
  return mapProviderToConfig(response as ProviderResponse)
}

export async function deleteProvider(id: string, config?: RequestConfigWithToast) {
  await del(`/modelhub/providers/${id}`, undefined, config)
}

export async function listProviderModels(providerId: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>(
    `/modelhub/providers/${providerId}/models`,
    { page_size: 200 }
  )
  return (response?.items || []).map(mapProviderModelToConfig)
}

export async function getProviderModel(providerId: string, modelId: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>(
    `/modelhub/providers/${providerId}/models`,
    { page_size: 200 }
  )
  const model = (response.items || []).find((item) => item.id === modelId)
  if (!model) {
    throw new Error('Model not found')
  }
  return mapProviderModelToConfig(model)
}

export async function createProviderModel(providerId: string, data: Partial<ModelConfig>) {
  const payload = mapConfigToCreatePayload(data)
  const response = await post<ProviderModelResponse>(`/modelhub/providers/${providerId}/models`, payload)
  return mapProviderModelToConfig(response as ProviderModelResponse)
}

export async function updateProviderModel(providerId: string, modelId: string, data: Partial<ModelConfig>) {
  const payload = mapConfigToUpdatePayload(data)
  const response = await patch<ProviderModelResponse>(`/modelhub/providers/${providerId}/models/${modelId}`, payload)
  return mapProviderModelToConfig(response as ProviderModelResponse)
}

export async function deleteProviderModel(
  providerId: string,
  modelId: string,
  config?: RequestConfigWithToast,
) {
  await del(`/modelhub/providers/${providerId}/models/${modelId}`, undefined, config)
}

export async function syncFromPlatform(providerId: string, includeModelIds?: string[]) {
  const payload = includeModelIds ? { include_model_ids: includeModelIds } : undefined
  const response = await post(`/modelhub/providers/${providerId}/sync-from-platform`, payload)
  return response
}

export async function healthCheck(providerId: string) {
  const response = await post(`/modelhub/providers/${providerId}/healthcheck`)
  return response
}

export async function listSyncJobs(providerId: string) {
  const response = await get<PaginatedResponse<any>>(`/modelhub/providers/${providerId}/sync-jobs`, {
    page_size: 50,
  })
  return response.items || []
}

export async function listPlatformModels(providerKind: string) {
  const response = await get<PaginatedResponse<ProviderModelResponse>>('/modelhub/platform-models', {
    provider_kind: providerKind,
    page_size: 200,
  })
  return (response?.items || []).map(mapProviderModelToConfig)
}

export async function testModelConnection(
  providerId: string,
  modelId: string,
  input: string,
  type: 'chat' | 'embeddings',
  config?: RequestConfigWithToast,
) {
  const endpoint = type === 'chat' ? '/modelhub/test/chat' : '/modelhub/test/embeddings'
  const response = await post(
    endpoint,
    {
      provider_id: providerId,
      model_id: modelId,
      input,
    },
    config,
  )
  return response
}
