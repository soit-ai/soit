import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Wrench, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const ToolNodeInfo = {
  type: 'tool-node',
  labelKey: 'workflow.detail.nodes.tool.label',
  descriptionKey: 'workflow.detail.nodes.tool.description',
  label: 'Tool Call',
  category: 'tool',
  description: 'Invoke external tools or APIs',
  color: 'amber-500',
  icon: 'Wrench',
}

export const ToolNodeDefaultData = {
  label: 'Tool Call',
  toolName: '',
  description: '',
  parameters: {},
}

// Tool call node component.
const ToolNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Wrench className="h-4 w-4 text-amber-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.tool.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-1">
        {t('workflow.detail.nodes.tool.fields.toolLabel')}: {data.toolName as string || t('workflow.detail.nodes.tool.unsetTool')}
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.description ? data.description as string : t('workflow.detail.nodes.tool.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-amber-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-amber-500 border-2 border-background"
      />
    </div>
  )
}

export const ToolNode = memo(ToolNodeComponent)

interface ToolPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const ToolProperties: React.FC<ToolPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const addParameter = () => {
    const parameters = { ...(data.parameters || {}) }
    parameters[`param${Object.keys(parameters).length + 1}`] = ''
    handleChange('parameters', parameters)
  }

  const removeParameter = (key: string) => {
    const parameters = { ...(data.parameters || {}) }
    delete parameters[key]
    handleChange('parameters', parameters)
  }

  const updateParameterKey = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return

    const parameters = { ...(data.parameters || {}) }
    const value = parameters[oldKey]
    delete parameters[oldKey]
    parameters[newKey] = value
    handleChange('parameters', parameters)
  }

  const updateParameterValue = (key: string, value: string) => {
    const parameters = { ...(data.parameters || {}) }
    parameters[key] = value
    handleChange('parameters', parameters)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.detail.nodes.common.nameLabel')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.detail.nodes.tool.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="toolName">{t('workflow.detail.nodes.tool.fields.toolLabel')}</Label>
        <Select
          value={data.toolName || ''}
          onValueChange={(value) => handleChange('toolName', value)}
        >
          <SelectTrigger id="toolName">
            <SelectValue placeholder={t('workflow.detail.nodes.tool.placeholders.tool')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="search">{t('workflow.detail.nodes.tool.tools.search')}</SelectItem>
            <SelectItem value="calculator">{t('workflow.detail.nodes.tool.tools.calculator')}</SelectItem>
            <SelectItem value="weather">{t('workflow.detail.nodes.tool.tools.weather')}</SelectItem>
            <SelectItem value="calendar">{t('workflow.detail.nodes.tool.tools.calendar')}</SelectItem>
            <SelectItem value="custom">{t('workflow.detail.nodes.tool.tools.custom')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="description">{t('workflow.detail.nodes.common.descriptionLabel')}</Label>
        <Textarea
          id="description"
          value={data.description || ''}
          onChange={(e) => handleChange('description', e.target.value)}
          placeholder={t('workflow.detail.nodes.tool.placeholders.description')}
          rows={3}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('workflow.detail.nodes.tool.fields.parametersLabel')}</Label>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={addParameter}
            className="h-8 px-2"
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('workflow.detail.nodes.tool.actions.addParameter')}
          </Button>
        </div>

        <div className="space-y-3 mt-2">
          {Object.entries(data.parameters || {}).map(([key, value]: [string, any], index: number) => (
            <div key={index} className="flex items-start gap-2 p-2 border rounded-md bg-muted/20">
              <div className="flex-1 space-y-2">
                <Input
                  value={key}
                  onChange={(e) => updateParameterKey(key, e.target.value)}
                  placeholder={t('workflow.detail.nodes.tool.placeholders.parameterName')}
                  className="h-8"
                />
                <Input
                  value={value}
                  onChange={(e) => updateParameterValue(key, e.target.value)}
                  placeholder={t('workflow.detail.nodes.tool.placeholders.parameterValue')}
                  className="h-8"
                />
              </div>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                onClick={() => removeParameter(key)}
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
