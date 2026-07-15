import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Bot, Plus, X } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { Switch } from '@/components/ui/switch'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const AgentNodeInfo = {
  type: 'agent-node',
  label: 'Agent',
  labelKey: 'workflow.blocks.agent',
  category: 'Model',
  categoryKey: 'workflow.nodeLibrary.categories.model',
  description: 'Agent that can plan and execute tasks',
  descriptionKey: 'workflow.customNodes.agent.description',
  color: 'blue-600',
  icon: 'Bot',
}

export const AgentNodeDefaultData = {
  label: 'Agent',
  agentType: 'react',
  model: 'gpt-4',
  systemPrompt: '',
  tools: [],
  verbose: false,
  memory: true,
}

const AgentNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-blue-600' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Bot className="h-4 w-4 text-blue-600" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.agent')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {data.agentType
          ? t('workflow.customNodes.agent.typeLabel', { value: data.agentType as string })
          : t('workflow.customNodes.agent.description')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-blue-600 border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-blue-600 border-2 border-background"
      />
    </div>
  )
}

export const AgentNode = memo(AgentNodeComponent)

interface AgentPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const AgentProperties: React.FC<AgentPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const handleChange = (field: string, value: any) => {
    onChange({
      ...data,
      [field]: value,
    })
  }

  const addTool = () => {
    const tools = [...(data.tools || []), { name: '', description: '' }]
    handleChange('tools', tools)
  }

  const removeTool = (index: number) => {
    const tools = [...(data.tools || [])]
    tools.splice(index, 1)
    handleChange('tools', tools)
  }

  const updateTool = (index: number, field: string, value: string) => {
    const tools = [...(data.tools || [])]
    tools[index] = { ...tools[index], [field]: value }
    handleChange('tools', tools)
  }

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="label">{t('workflow.customNodes.agent.form.name')}</Label>
        <Input
          id="label"
          value={data.label || ''}
          onChange={(e) => handleChange('label', e.target.value)}
          placeholder={t('workflow.blocks.agent')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="agentType">{t('workflow.customNodes.agent.form.agentType')}</Label>
        <Select
          value={data.agentType || 'react'}
          onValueChange={(value) => handleChange('agentType', value)}
        >
          <SelectTrigger id="agentType">
            <SelectValue placeholder={t('workflow.customNodes.agent.form.agentTypePlaceholder')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="react">ReAct</SelectItem>
            <SelectItem value="reflexion">Reflexion</SelectItem>
            <SelectItem value="plan-and-execute">{t('workflow.customNodes.agent.form.agentTypes.planAndExecute')}</SelectItem>
            <SelectItem value="autonomous">{t('workflow.customNodes.agent.form.agentTypes.autonomous')}</SelectItem>
            <SelectItem value="custom">{t('workflow.customNodes.agent.form.agentTypes.custom')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="model">{t('workflow.customNodes.agent.form.model')}</Label>
        <Select
          value={data.model || 'gpt-4'}
          onValueChange={(value) => handleChange('model', value)}
        >
          <SelectTrigger id="model">
            <SelectValue placeholder={t('workflow.customNodes.agent.form.modelPlaceholder')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="gpt-4">GPT-4</SelectItem>
            <SelectItem value="gpt-4-turbo">GPT-4 Turbo</SelectItem>
            <SelectItem value="gpt-3.5-turbo">GPT-3.5 Turbo</SelectItem>
            <SelectItem value="model:anthropic:claude-sonnet-4-6">Claude Sonnet 4.6</SelectItem>
            <SelectItem value="custom">{t('workflow.customNodes.agent.form.modelCustom')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {data.model === 'custom' && (
        <div className="space-y-2">
          <Label htmlFor="customModel">{t('workflow.customNodes.agent.form.customModel')}</Label>
          <Input
            id="customModel"
            value={data.customModel || ''}
            onChange={(e) => handleChange('customModel', e.target.value)}
            placeholder={t('workflow.customNodes.agent.form.customModelPlaceholder')}
          />
        </div>
      )}

      <div className="space-y-2">
        <Label htmlFor="systemPrompt">{t('workflow.customNodes.agent.form.systemPrompt')}</Label>
        <Textarea
          id="systemPrompt"
          value={data.systemPrompt || ''}
          onChange={(e) => handleChange('systemPrompt', e.target.value)}
          placeholder={t('workflow.customNodes.agent.form.systemPromptPlaceholder')}
          rows={4}
        />
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <Label>{t('workflow.customNodes.agent.form.tools')}</Label>
          <Button 
            type="button" 
            variant="outline" 
            size="sm" 
            onClick={addTool}
            className="h-8 px-2"
          >
            <Plus className="h-4 w-4 mr-1" />
            {t('workflow.customNodes.agent.form.addTool')}
          </Button>
        </div>

        <div className="space-y-3 mt-2">
          {(data.tools || []).map((tool: any, index: number) => (
            <div key={index} className="flex items-start gap-2 p-2 border rounded-md bg-muted/20">
              <div className="flex-1 space-y-2">
                <Input
                  value={tool.name}
                  onChange={(e) => updateTool(index, 'name', e.target.value)}
                  placeholder={t('workflow.customNodes.agent.form.toolNamePlaceholder')}
                  className="h-8"
                />
                <Textarea
                  value={tool.description}
                  onChange={(e) => updateTool(index, 'description', e.target.value)}
                  placeholder={t('workflow.customNodes.agent.form.toolDescriptionPlaceholder')}
                  className="min-h-[60px] text-xs"
                />
              </div>
              <Button 
                type="button" 
                variant="ghost" 
                size="icon" 
                onClick={() => removeTool(index)}
                className="h-8 w-8"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="verbose"
          checked={data.verbose || false}
          onCheckedChange={(checked) => handleChange('verbose', checked)}
        />
        <Label htmlFor="verbose">{t('workflow.customNodes.agent.form.verbose')}</Label>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="memory"
          checked={data.memory || true}
          onCheckedChange={(checked) => handleChange('memory', checked)}
        />
        <Label htmlFor="memory">{t('workflow.customNodes.agent.form.memory')}</Label>
      </div>
    </div>
  )
}
