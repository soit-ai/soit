import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Cpu } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Slider } from '@/components/ui/slider'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

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
  modelName: 'gpt-3.5-turbo',
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
        {t('workflow.detail.nodes.llm.fields.modelLabel')}: {data.modelName as string || 'gpt-3.5-turbo'}
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
        <Label htmlFor="modelName">{t('workflow.detail.nodes.llm.fields.modelLabel')}</Label>
        <Select
          value={data.modelName || 'gpt-3.5-turbo'}
          onValueChange={(value) => handleChange('modelName', value)}
        >
          <SelectTrigger id="modelName">
            <SelectValue placeholder={t('workflow.detail.nodes.llm.placeholders.model')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
            <SelectItem value="gpt-4">GPT-4</SelectItem>
            <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
            <SelectItem value="model:anthropic:claude-opus-4-8">Claude Opus 4.8</SelectItem>
            <SelectItem value="model:anthropic:claude-sonnet-4-6">Claude Sonnet 4.6</SelectItem>
            <SelectItem value="model:anthropic:claude-haiku-4-5-20251001">Claude Haiku 4.5</SelectItem>
            <SelectItem value="llama-3-70b">Llama 3 70B</SelectItem>
            <SelectItem value="llama-3-8b">Llama 3 8B</SelectItem>
          </SelectContent>
        </Select>
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
