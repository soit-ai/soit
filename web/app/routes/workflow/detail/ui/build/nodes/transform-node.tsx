import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const TransformNodeInfo = {
  type: 'transform-node',
  labelKey: 'workflow.detail.nodes.transform.label',
  descriptionKey: 'workflow.detail.nodes.transform.description',
  label: 'Transform',
  category: 'tool',
  description: 'Transform data format or structure',
  color: 'rose-500',
  icon: 'RefreshCw',
}

export const TransformNodeDefaultData = {
  label: 'Transform',
  transformType: 'json',
  inputFormat: '',
  outputFormat: '',
  script: '',
}

// Transform node component.
const TransformNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-rose-500' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <RefreshCw className="h-4 w-4 text-rose-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.transform.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.transformType
          ? t('workflow.detail.nodes.transform.previewType', { value: data.transformType as string })
          : t('workflow.detail.nodes.transform.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-rose-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-rose-500 border-2 border-background"
      />
    </div>
  )
}

export const TransformNode = memo(TransformNodeComponent)
