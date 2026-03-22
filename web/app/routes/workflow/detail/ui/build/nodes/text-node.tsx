import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { MessageSquare } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const TextNodeInfo = {
  type: 'text-node',
  labelKey: 'workflow.detail.nodes.text.label',
  descriptionKey: 'workflow.detail.nodes.text.description',
  label: 'Text Input',
  category: 'input',
  description: 'User input text',
  color: 'primary',
  icon: 'MessageSquare',
}

export const TextNodeDefaultData = {
  label: 'Text Input',
  content: '',
}

// Text input node component.
const TextNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-primary' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <MessageSquare className="h-4 w-4 text-primary" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.text.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.content
          ? t('workflow.detail.nodes.text.previewDefault', { value: data.content as string })
          : t('workflow.detail.nodes.text.previewEmpty')}
      </div>

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-primary border-2 border-background"
      />
    </div>
  )
}

export const TextNode = memo(TextNodeComponent)

interface TextPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const TextProperties: React.FC<TextPropertiesProps> = ({ data, onChange }) => {
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
          placeholder={t('workflow.detail.nodes.text.label')}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="content">{t('workflow.detail.nodes.text.fields.contentLabel')}</Label>
        <Textarea
          id="content"
          value={data.content || ''}
          onChange={(e) => handleChange('content', e.target.value)}
          placeholder={t('workflow.detail.nodes.text.placeholders.content')}
          rows={5}
        />
      </div>
    </div>
  )
}
