import React, { memo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Handle, type NodeProps } from '@xyflow/react'
import { Wrench, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { useTranslation } from '@/i18n'
import { listRuntimeTools, type RuntimeToolItem } from '@/services/plugin-service'
import { useNodeHandles } from '../hooks/use-node-handles'

const isRecord = (value: unknown): value is Record<string, unknown> => {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

const loadWorkflowRuntimeTools = async (): Promise<RuntimeToolItem[]> => {
  const response = await listRuntimeTools()
  const tools = response?.tools
  const refs = new Set<string>()
  if (!Array.isArray(tools) || tools.some((tool) => {
    const spec = tool?.tool_spec
    const plugin = tool?.plugin
    if (
      !tool
      || typeof tool.tool_ref !== 'string'
      || !tool.tool_ref.trim()
      || typeof tool.version !== 'string'
      || !tool.version.trim()
      || (plugin !== undefined && plugin !== null && (
        !isRecord(plugin)
        || typeof plugin.name !== 'string'
        || !plugin.name.trim()
        || typeof plugin.version !== 'string'
        || !plugin.version.trim()
        || plugin.version !== tool.version
      ))
      || (spec !== undefined && spec !== null && !isRecord(spec))
      || (spec?.name !== undefined && typeof spec.name !== 'string')
      || (spec?.description !== undefined && spec.description !== null && typeof spec.description !== 'string')
      || (spec?.input_schema !== undefined && spec.input_schema !== null && !isRecord(spec.input_schema))
      || refs.has(tool.tool_ref)
    ) return true
    refs.add(tool.tool_ref)
    return false
  })) {
    throw new Error('Malformed runtime tool inventory')
  }
  return tools
}

export const ToolNodeInfo = {
  type: 'tool-node',
  labelKey: 'workflow.detail.nodes.tool.label',
  descriptionKey: 'workflow.detail.nodes.tool.description',
  label: 'Tool Call',
  category: 'tool',
  description: 'Invoke external tools or APIs',
  color: 'cat-amber',
  icon: 'Wrench',
}

export const ToolNodeDefaultData = {
  label: 'Tool Call',
  toolRef: '',
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
        <Wrench className="h-4 w-4 text-cat-amber" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.tool.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-1">
        {t('workflow.detail.nodes.tool.fields.toolLabel')}: {data.toolRef as string || t('workflow.detail.nodes.tool.unsetTool')}
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
        className="w-3 h-3 bg-cat-amber border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-amber border-2 border-background"
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
  const toolsQuery = useQuery({
    queryKey: ['workflow', 'runtime-tools'],
    queryFn: loadWorkflowRuntimeTools,
    staleTime: 5 * 60 * 1000,
    gcTime: 0,
    retry: false,
  })
  const tools = toolsQuery.data || []
  const toolRef = typeof data.toolRef === 'string' ? data.toolRef : ''
  const selectedTool = tools.find((tool) => tool.tool_ref === toolRef)
  const unavailableLabel = toolRef
    ? t('workflow.detail.nodes.tool.states.unavailable', { ref: toolRef })
    : undefined
  const selectedLabel = selectedTool?.tool_spec?.name || selectedTool?.tool_ref || unavailableLabel
  const toolState = toolsQuery.isPending ? t('workflow.detail.nodes.tool.states.loading')
    : toolsQuery.isError ? t('workflow.detail.nodes.tool.states.error')
      : tools.length === 0 ? t('workflow.detail.nodes.tool.states.empty')
        : undefined
  const toolSelectDisabled = toolsQuery.isPending || toolsQuery.isError || tools.length === 0
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
        <Label htmlFor="toolRef">{t('workflow.detail.nodes.tool.fields.toolLabel')}</Label>
        <Select
          value={toolRef}
          onValueChange={(value) => handleChange('toolRef', value)}
          disabled={toolSelectDisabled}
        >
          <SelectTrigger id="toolRef" aria-describedby="toolRef-status">
            <SelectValue placeholder={t('workflow.detail.nodes.tool.placeholders.tool')}>
              {selectedLabel}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            {toolRef && !selectedTool && (
              <SelectItem value={toolRef} disabled>{unavailableLabel}</SelectItem>
            )}
            {tools.map((tool) => (
              <SelectItem key={tool.tool_ref} value={tool.tool_ref}>
                <span>{tool.tool_spec?.name || tool.tool_ref}</span>
                <span className="ml-2 text-xs text-muted-foreground">{tool.tool_ref} · v{tool.version}</span>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <p id="toolRef-status" role="status" aria-live="polite" className="text-xs text-muted-foreground">
          {toolState || (toolRef && !selectedTool ? unavailableLabel : '')}
        </p>
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
