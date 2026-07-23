export type JsonRecord = Record<string, any>

export interface ModelArchitectureConfig {
  modality?: string
  input_modalities?: string[]
  output_modalities?: string[]
  tokenizer?: string
}

export interface ModelCapabilityMatrixEntry {
  catalog?: boolean | null
  diagnostics?: boolean | null
  runtime?: boolean | null
  merged?: boolean | null
  user_override?: string
}

export type ModelCapabilityMatrixConfig = Record<string, ModelCapabilityMatrixEntry>

export interface ModelParameterConfig {
  max_input_files?: number
  max_image_count?: number
  max_audio_seconds?: number
  max_video_seconds?: number
  supported_parameters?: string[]
  default_parameters?: JsonRecord
}

export interface ModelPricingConfig {
  currency?: string
  pricing_source?: string
  prompt?: { amount?: number; unit?: string }
  completion?: { amount?: number; unit?: string }
  image?: { amount?: number; unit?: string; enabled?: boolean }
  request?: { amount?: number; unit?: string }
  override_policy?: JsonRecord
  estimate?: JsonRecord
}

export interface ModelDiagnosticsConfig {
  last_test_status?: string
  last_test_at?: string
  last_test_error?: string
  test_mode?: string
  test_prompt?: string
  timeout_ms?: number
  support?: JsonRecord
  runtime_stats?: JsonRecord
  override_reason?: string
}

export interface ModelConfig {
  id: string
  providerId: string
  providerKind: string
  modelId: string
  displayName?: string
  description?: string
  capabilities?: string[]
  capabilitiesJson?: JsonRecord
  contextWindow?: number
  maxOutputTokens?: number
  lifecycle?: string
  status?: 'active' | 'disabled' | 'error' | string
  enabled: boolean
  source: 'platform' | 'local' | 'catalog' | 'manual' | 'override' | string
  platformModelId?: string
  lastSyncedAt?: string
  architecture?: ModelArchitectureConfig
  capabilityMatrix?: ModelCapabilityMatrixConfig
  parameterConfig?: ModelParameterConfig
  pricing?: ModelPricingConfig
  diagnostics?: ModelDiagnosticsConfig
  rawMeta?: JsonRecord
  userOverridesJson?: JsonRecord
  syncStatus: string
  userOverrides?: string[]
  config?: JsonRecord
  createdAt: string
  updatedAt: string
}

export interface ProviderConfig {
  id: string
  adapterBackend: 'native' | 'litellm'
  slug?: string
  name: string
  kind: string
  baseUrl?: string
  credentialSecretId?: string
  status: 'active' | 'disabled' | 'error'
  lastSyncedAt?: string
  lastHealthcheckAt?: string
  lastHealthcheckError?: string
  syncPolicy?: {
    auto_sync?: boolean
    interval_minutes?: number
    recreate_deleted?: boolean
    default_enabled?: boolean
    catalog_supported?: boolean
    include_models?: string[]
    exclude_models?: string[]
  }
  connectionConfig?: {
    api_version?: string
    timeout_ms?: number
    retry_policy?: {
      max_retries?: number
      backoff?: string
      retryable_status_codes?: number[]
    }
    rate_limit?: {
      rpm?: number
      tpm?: number
      concurrency?: number
    }
  }
  authConfig?: {
    auth_type?: 'api_key' | 'bearer' | 'azure_ad' | 'custom_header'
    secret_bindings?: Record<string, string>
  }
  runtimeConfig?: {
    diagnostics_supported?: Record<string, boolean>
    runtime_support?: Record<string, boolean>
    litellm_provider?: string
    litellm_params?: JsonRecord
  }
  governanceConfig?: {
    currency?: string
    pricing_source?: 'catalog' | 'manual' | 'unknown' | string
    egress_policy?: {
      allow_external?: boolean
      allowed_domains?: string[]
    }
    data_policy?: {
      files?: boolean
      images?: boolean
      audio?: boolean
      video?: boolean
      sensitive_data?: string
    }
    log_level?: string
    trace_enabled?: boolean
  }
  source?: 'builtin' | 'plugin' | 'template'
  templateId?: string
  pluginId?: string
  pluginName?: string
  pluginVersion?: string
  metadata?: {
    modelHints?: string[]
  }
  createdAt?: string
  updatedAt?: string
}

export interface ModelListProps {
  onSaveModel: (model: ModelConfig) => void
  onDeleteModel: (id: string) => void
  provider: string
  title?: string
}

export interface ModelFormProps {
  model: ModelConfig
  onSave: (e: React.FormEvent) => void
  onCancel: () => void
  onChange: (model: ModelConfig) => void
  title?: string
}

export interface ModelItemProps {
  model: ModelConfig
  onEdit: (model: ModelConfig) => void
  onDelete: (id: string) => void
  onToggleActive?: (id: string, enabled: boolean) => void
}

export const MODEL_CAPABILITIES = [
  { 
    labelKey: 'model.capabilities.textProcessing.label',
    value: 'text_processing',
    descriptionKey: 'model.capabilities.textProcessing.description',
  },
  { 
    labelKey: 'model.capabilities.speechProcessing.label',
    value: 'speech_processing',
    descriptionKey: 'model.capabilities.speechProcessing.description',
  },
  { 
    labelKey: 'model.capabilities.imageProcessing.label',
    value: 'image_processing',
    descriptionKey: 'model.capabilities.imageProcessing.description',
  },
  { 
    labelKey: 'model.capabilities.contentAudit.label',
    value: 'content_audit',
    descriptionKey: 'model.capabilities.contentAudit.description',
  },
  { 
    labelKey: 'model.capabilities.knowledgeRetrieval.label',
    value: 'knowledge_retrieval',
    descriptionKey: 'model.capabilities.knowledgeRetrieval.description',
  },
  { 
    labelKey: 'model.capabilities.dialogueGeneration.label',
    value: 'dialogue_generation',
    descriptionKey: 'model.capabilities.dialogueGeneration.description',
  },
] as const
