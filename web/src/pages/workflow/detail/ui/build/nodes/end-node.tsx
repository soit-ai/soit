import React, { memo } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { Square } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const EndNodeInfo = {
  type: 'end-node',
  label: 'End',
  labelKey: 'workflow.blocks.end',
  category: 'Flow',
  categoryKey: 'workflow.nodeLibrary.categories.flow',
  description: 'Workflow end point',
  descriptionKey: 'workflow.blocksAbout.end',
  color: 'red-500',
  icon: 'Square',
}

export const EndNodeDefaultData = {
  label: 'End',
  status: 'success',
  message: '',
}

const EndNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-red-500' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Square className="h-4 w-4 text-red-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.end')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {data.status
          ? t('workflow.customNodes.end.status', { value: data.status as string })
          : t('workflow.blocksAbout.end')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-red-500 border-2 border-background"
      />
    </div>
  )
}

export const EndNode = memo(EndNodeComponent)
