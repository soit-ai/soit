import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { BotMessageSquare } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'
import type { TranslationKey } from '@/i18n/types'

export const OutputNodeInfo = {
  type: 'output-node',
  labelKey: 'workflow.detail.nodes.output.label',
  descriptionKey: 'workflow.detail.nodes.output.description',
  label: 'Output',
  category: 'output',
  description: 'Workflow output result',
  color: 'green-500',
  icon: 'BotMessageSquare',
}

export const OutputNodeDefaultData = {
  label: 'Output',
  format: 'text',
  destination: 'ui',
  saveHistory: true,
  streaming: false,
}

// Output node component.
const OutputNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <BotMessageSquare className="h-4 w-4 text-green-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.output.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.detail.nodes.output.fields.formatLabel')}: {t(`workflow.detail.nodes.output.formats.${data.format || 'text'}` as TranslationKey)}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-green-500 border-2 border-background"
      />
    </div>
  )
}

export const OutputNode = memo(OutputNodeComponent)

interface OutputPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const OutputProperties: React.FC<OutputPropertiesProps> = ({ data, onChange }) => {
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
          placeholder={t('workflow.detail.nodes.output.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="format">{t('workflow.detail.nodes.output.fields.formatLabel')}</Label>
        <Select
          value={data.format || 'text'}
          onValueChange={(value) => handleChange('format', value)}
        >
          <SelectTrigger id="format">
            <SelectValue placeholder={t('workflow.detail.nodes.output.placeholders.format')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="text">{t('workflow.detail.nodes.output.formats.text')}</SelectItem>
            <SelectItem value="json">{t('workflow.detail.nodes.output.formats.json')}</SelectItem>
            <SelectItem value="markdown">{t('workflow.detail.nodes.output.formats.markdown')}</SelectItem>
            <SelectItem value="html">{t('workflow.detail.nodes.output.formats.html')}</SelectItem>
            <SelectItem value="csv">{t('workflow.detail.nodes.output.formats.csv')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="destination">{t('workflow.detail.nodes.output.fields.destinationLabel')}</Label>
        <Select
          value={data.destination || 'ui'}
          onValueChange={(value) => handleChange('destination', value)}
        >
          <SelectTrigger id="destination">
            <SelectValue placeholder={t('workflow.detail.nodes.output.placeholders.destination')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="ui">{t('workflow.detail.nodes.output.destinations.ui')}</SelectItem>
            <SelectItem value="api">{t('workflow.detail.nodes.output.destinations.api')}</SelectItem>
            <SelectItem value="file">{t('workflow.detail.nodes.output.destinations.file')}</SelectItem>
            <SelectItem value="database">{t('workflow.detail.nodes.output.destinations.database')}</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {data.destination === 'api' && (
        <div className="space-y-2">
          <Label htmlFor="webhookUrl">{t('workflow.detail.nodes.output.fields.webhookLabel')}</Label>
          <Input
            id="webhookUrl"
            value={data.webhookUrl || ''}
            onChange={(e) => handleChange('webhookUrl', e.target.value)}
            placeholder={t('workflow.detail.nodes.output.placeholders.webhook')}
          />
        </div>
      )}

      {data.destination === 'file' && (
        <div className="space-y-2">
          <Label htmlFor="filePath">{t('workflow.detail.nodes.output.fields.filePathLabel')}</Label>
          <Input
            id="filePath"
            value={data.filePath || ''}
            onChange={(e) => handleChange('filePath', e.target.value)}
            placeholder={t('workflow.detail.nodes.output.placeholders.filePath')}
          />
        </div>
      )}

      <div className="flex items-center space-x-2">
        <Switch
          id="saveHistory"
          checked={data.saveHistory ?? true}
          onCheckedChange={(checked) => handleChange('saveHistory', checked)}
        />
        <Label htmlFor="saveHistory">{t('workflow.detail.nodes.output.fields.saveHistoryLabel')}</Label>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="streaming"
          checked={data.streaming || false}
          onCheckedChange={(checked) => handleChange('streaming', checked)}
        />
        <Label htmlFor="streaming">{t('workflow.detail.nodes.output.fields.streamingLabel')}</Label>
      </div>
    </div>
  )
}
