import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { MessageSquare, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const PromptNodeInfo = {
  type: 'prompt-node',
  labelKey: 'workflow.detail.nodes.prompt.label',
  descriptionKey: 'workflow.detail.nodes.prompt.description',
  label: 'Prompt',
  category: 'input',
  description: 'Preset prompt template',
  color: 'blue-500',
  icon: 'MessageSquare',
}

export const PromptNodeDefaultData = {
  label: 'Prompt',
  template: '',
  variables: [],
}

// Prompt node component.
const PromptNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="h-4 w-4 text-blue-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.prompt.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.template ? (
          <div className="max-h-16 overflow-hidden text-ellipsis">
            {(data.template as string).length > 100
              ? `${(data.template as string).substring(0, 100)}...`
              : (data.template as string)}
          </div>
        ) : t('workflow.detail.nodes.prompt.previewEmpty')}
      </div>

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-blue-500 border-2 border-background"
      />
    </div>
  )
}

export const PromptNode = memo(PromptNodeComponent)

interface PromptPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const PromptProperties: React.FC<PromptPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const addVariable = () => {
    const variables = [...(data.variables || []), { name: '', description: '' }]
    handleChange('variables', variables)
  }

  const removeVariable = (index: number) => {
    const variables = [...(data.variables || [])]
    variables.splice(index, 1)
    handleChange('variables', variables)
  }

  const updateVariable = (index: number, field: string, value: string) => {
    const variables = [...(data.variables || [])]
    variables[index] = { ...variables[index], [field]: value }
    handleChange('variables', variables)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.prompt.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="template">{t('workflow.detail.nodes.prompt.fields.templateLabel')}</Label>
        <Textarea
          id="template"
          value={data.template || ''}
          onChange={(e) => handleChange('template', e.target.value)}
          placeholder={t('workflow.detail.nodes.prompt.placeholders.template')}
          rows={8}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('workflow.detail.nodes.prompt.fields.variablesLabel')}</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addVariable}
            className="h-8 px-2"
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('workflow.detail.nodes.prompt.actions.addVariable')}
          </Button>
        </div>

        <div className="space-y-3 mt-2">
          {(data.variables || []).map((variable: any, index: number) => (
            <div key={index} className="flex items-start gap-2 p-2 border rounded-md bg-muted/20">
              <div className="flex-1 space-y-2">
                <Input
                  value={variable.name}
                  onChange={(e) => updateVariable(index, 'name', e.target.value)}
                  placeholder={t('workflow.detail.nodes.prompt.placeholders.variableName')}
                  className="h-8"
                />
                <Input
                  value={variable.description}
                  onChange={(e) => updateVariable(index, 'description', e.target.value)}
                  placeholder={t('workflow.detail.nodes.prompt.placeholders.variableDescription')}
                  className="h-8"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeVariable(index)}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
