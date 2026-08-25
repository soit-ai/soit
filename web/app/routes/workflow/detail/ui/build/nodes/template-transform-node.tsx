import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { FileCode } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const TemplateTransformNodeInfo = {
  type: 'template-transform-node',
  label: 'Template Transform',
  labelKey: 'workflow.blocks.template-transform',
  category: 'Tool',
  categoryKey: 'workflow.nodeLibrary.categories.tool',
  description: 'Transform data with a template',
  descriptionKey: 'workflow.blocksAbout.template-transform',
  color: 'cat-pink',
  icon: 'FileCode',
}

export const TemplateTransformNodeDefaultData = {
  label: 'Template',
  template: '',
  inputFormat: '',
  outputFormat: '',
}

const TemplateTransformNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-pink' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <FileCode className="h-4 w-4 text-cat-pink" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.template-transform')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.blocksAbout.template-transform')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-pink border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-pink border-2 border-background"
      />
    </div>
  )
}

export const TemplateTransformNode = memo(TemplateTransformNodeComponent)
