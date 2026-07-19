import React, { memo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Handle, type NodeProps } from '@xyflow/react'
import { Cpu } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTranslation } from '@/i18n'
import { listModels, type ModelLibraryItem } from '@/services/provider-service'
import { useNodeHandles } from '../hooks/use-node-handles'

const isModelHubRef = (value: string): boolean => {
  if (!value.startsWith('model:')) return false
  const scopedRef = value.slice('model:'.length)
  const providerSeparator = scopedRef.indexOf(':')
  if (providerSeparator < 1) return false
  const provider = scopedRef.slice(0, providerSeparator)
  const modelId = scopedRef.slice(providerSeparator + 1)
  return Boolean(provider.trim() && modelId.trim())
}

const loadWorkflowModels = async (): Promise<ModelLibraryItem[]> => {
  const models = await listModels()
  const refs = new Set<string>()
  if (!Array.isArray(models) || models.some((model) => {
    if (
      !model
      || typeof model.id !== 'string'
      || !model.id.trim()
      || typeof model.name !== 'string'
      || !model.name.trim()
      || typeof model.modelName !== 'string'
      || !isModelHubRef(model.modelName)
      || typeof model.isActive !== 'boolean'
      || refs.has(model.modelName)
    ) return true
    refs.add(model.modelName)
    return false
  })) {
    throw new Error('Malformed model inventory')
  }
  return models
}

export const LLMNodeInfo = {
  type: 'llm-node',
  labelKey: 'workflow.detail.nodes.llm.label',
  descriptionKey: 'workflow.detail.nodes.llm.description',
  label: 'LLM',
  category: 'model',
  description: 'Large language model',
  color: 'purple-500',
  icon: 'Cpu',
}

export const LLMNodeDefaultData = {
  label: 'LLM',
  modelRef: '',
  temperature: 0.7,
  maxTokens: 1000,
  topP: 1,
  systemPrompt: '',
}

// LLM node component.
const LLMNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Cpu className="h-4 w-4 text-purple-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.llm.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-1">
        {t('workflow.detail.nodes.llm.fields.modelLabel')}: {data.modelRef as string || t('workflow.detail.nodes.llm.unsetModel')}
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.detail.nodes.llm.fields.temperatureLabel')}: {data.temperature as string || '0.7'}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-purple-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-purple-500 border-2 border-background"
      />
    </div>
  )
}

export const LLMNode = memo(LLMNodeComponent)

interface LLMPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const LLMProperties: React.FC<LLMPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const modelsQuery = useQuery({
    queryKey: ['workflow', 'models'],
    queryFn: loadWorkflowModels,
    staleTime: 5 * 60 * 1000,
    gcTime: 0,
    retry: false,
  })
  const models = modelsQuery.data || []
  const modelRef = typeof data.modelRef === 'string' ? data.modelRef : ''
  const selectedModel = models.find((model) => model.modelName === modelRef)
  const unavailableLabel = modelRef
    ? t('workflow.detail.nodes.llm.states.unavailable', { ref: modelRef })
    : undefined
  const selectedLabel = selectedModel
    ? `${selectedModel.name}${selectedModel.isActive ? '' : ` (${t('workflow.detail.nodes.llm.states.disabled')})`}`
    : unavailableLabel
  const modelState = modelsQuery.isPending ? t('workflow.detail.nodes.llm.states.loading')
    : modelsQuery.isError ? t('workflow.detail.nodes.llm.states.error')
      : models.length === 0 ? t('workflow.detail.nodes.llm.states.empty')
        : undefined
  const modelSelectDisabled = modelsQuery.isPending || modelsQuery.isError || models.length === 0
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.llm.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="modelRef">{t('workflow.detail.nodes.llm.fields.modelLabel')}</Label>
        <Select
          value={modelRef}
          onValueChange={(value) => handleChange('modelRef', value)}
          disabled={modelSelectDisabled}
        >
          <SelectTrigger id="modelRef" aria-describedby="modelRef-status">
            <SelectValue placeholder={t('workflow.detail.nodes.llm.placeholders.model')}>
              {selectedLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {modelRef && !selectedModel && (
              <SelectItem value={modelRef} disabled>{unavailableLabel}</SelectItem>
            )}
            {models.map((model) => (
              <SelectItem key={model.id} value={model.modelName} disabled={!model.isActive}>
                {model.name}{model.isActive ? '' : ` (${t('workflow.detail.nodes.llm.states.disabled')})`}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p id="modelRef-status" role="status" aria-live="polite" className="text-xs text-muted-foreground">
          {modelState || (modelRef && !selectedModel ? unavailableLabel : '')}
        </p>
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="temperature">{t('workflow.detail.nodes.llm.fields.temperatureLabelWithValue', { value: data.temperature || 0.7 })}</Label>
        </div>
        <Slider
          id="temperature"
          min={0}
          max={2}
          step={0.1}
          value={[data.temperature || 0.7]}
          onValueChange={(value) => handleChange('temperature', value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="maxTokens">{t('workflow.detail.nodes.llm.fields.maxTokensLabel')}</Label>
        <Input
          id="maxTokens"
          type="number"
          value={data.maxTokens || 1000}
          onChange={(e) => handleChange('maxTokens', parseInt(e.target.value))}
          min={1}
          max={8000}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label htmlFor="topP">{t('workflow.detail.nodes.llm.fields.topPLabelWithValue', { value: data.topP || 1 })}</Label>
        </div>
        <Slider
          id="topP"
          min={0}
          max={1}
          step={0.05}
          value={[data.topP || 1]}
          onValueChange={(value) => handleChange('topP', value[0])}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="systemPrompt">{t('workflow.detail.nodes.llm.fields.systemPromptLabel')}</Label>
        <Input
          id="systemPrompt"
          value={data.systemPrompt || ''}
          onChange={(e) => handleChange('systemPrompt', e.target.value)}
          placeholder={t('workflow.detail.nodes.llm.placeholders.systemPrompt')}
        />
      </div>
    </div>
  )
}
