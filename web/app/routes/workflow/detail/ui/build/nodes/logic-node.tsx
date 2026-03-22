import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { GitMerge } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const LogicNodeInfo = {
  type: 'logic-node',
  label: 'Logic',
  labelKey: 'workflow.customNodes.logic.label',
  category: 'Tool',
  categoryKey: 'workflow.nodeLibrary.categories.tool',
  description: 'Perform logical operations and evaluation',
  descriptionKey: 'workflow.customNodes.logic.description',
  color: 'blue-400',
  icon: 'GitMerge',
}

export const LogicNodeDefaultData = {
  label: 'Logic',
  operation: 'AND',
  conditions: [],
}

const LogicNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-blue-400' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <GitMerge className="h-4 w-4 text-blue-400" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.customNodes.logic.label')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {data.operation
          ? t('workflow.customNodes.logic.operation', { value: data.operation as string })
          : t('workflow.customNodes.logic.description')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-blue-400 border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-blue-400 border-2 border-background"
      />
    </div>
  )
}

export const LogicNode = memo(LogicNodeComponent)
