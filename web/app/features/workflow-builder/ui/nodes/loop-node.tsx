import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Repeat } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const LoopNodeInfo = {
  type: 'loop-node',
  label: 'Loop',
  labelKey: 'workflow.blocks.iteration',
  category: 'Flow',
  categoryKey: 'workflow.nodeLibrary.categories.flow',
  description: 'Loop through operations',
  descriptionKey: 'workflow.blocksAbout.iteration',
  color: 'cat-purple',
  icon: 'Repeat',
}

export const LoopNodeDefaultData = {
  label: 'Loop',
  iterationVariable: '',
  maxIterations: 10,
  exitCondition: '',
}

const LoopNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-purple' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Repeat className="h-4 w-4 text-cat-purple" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.iteration')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {data.maxIterations
          ? t('workflow.customNodes.loop.maxIterations', { value: data.maxIterations })
          : t('workflow.blocksAbout.iteration')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-purple border-2 border-background"
      />
      
      <Handle
        type="source"
        position={Position.Bottom}
        id="loop-body"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-purple border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-purple border-2 border-background"
      />
    </div>
  )
}

export const LoopNode = memo(LoopNodeComponent)
