export interface ModelConfig {
  id: string
  providerId: string
  providerKind: string
  modelId: string
  displayName?: string
  description?: string
  capabilities?: string[]
  contextWindow?: number
  maxOutputTokens?: number
  lifecycle?: string
  enabled: boolean
  source: 'platform' | 'local'
  syncStatus: string
  userOverrides?: string[]
  config?: Record<string, any>
  createdAt: string
  updatedAt: string
}

export interface ProviderConfig {
  id: string
  name: string
  kind: 'openai' | 'anthropic' | 'gemini' | 'openai_compat'
  baseUrl?: string
  credentialRef?: string
  status: 'active' | 'disabled' | 'error'
  lastHealthcheckAt?: string
  lastHealthcheckError?: string
  syncPolicy?: {
    auto_sync?: boolean
    interval_minutes?: number
    recreate_deleted?: boolean
    default_enabled?: boolean
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
    labelKey: 'system.model.capabilities.textProcessing.label',
    value: 'text_processing',
    descriptionKey: 'system.model.capabilities.textProcessing.description',
  },
  { 
    labelKey: 'system.model.capabilities.speechProcessing.label',
    value: 'speech_processing',
    descriptionKey: 'system.model.capabilities.speechProcessing.description',
  },
  { 
    labelKey: 'system.model.capabilities.imageProcessing.label',
    value: 'image_processing',
    descriptionKey: 'system.model.capabilities.imageProcessing.description',
  },
  { 
    labelKey: 'system.model.capabilities.contentAudit.label',
    value: 'content_audit',
    descriptionKey: 'system.model.capabilities.contentAudit.description',
  },
  { 
    labelKey: 'system.model.capabilities.knowledgeRetrieval.label',
    value: 'knowledge_retrieval',
    descriptionKey: 'system.model.capabilities.knowledgeRetrieval.description',
  },
  { 
    labelKey: 'system.model.capabilities.dialogueGeneration.label',
    value: 'dialogue_generation',
    descriptionKey: 'system.model.capabilities.dialogueGeneration.description',
  },
] as const
