import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { GitBranch } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const ConditionalNodeInfo = {
  type: 'conditional-node',
  label: 'Conditional',
  labelKey: 'workflow.blocks.if-else',
  category: 'Flow',
  categoryKey: 'workflow.nodeLibrary.categories.flow',
  description: 'Branch based on conditions',
  descriptionKey: 'workflow.blocksAbout.if-else',
  color: 'amber-600',
  icon: 'GitBranch',
}

export const ConditionalNodeDefaultData = {
  label: 'Conditional',
  conditions: [],
  defaultPath: '',
}

const ConditionalNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-amber-600' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <GitBranch className="h-4 w-4 text-amber-600" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.if-else')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.blocksAbout.if-else')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-amber-600 border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output-true"
        style={{ top: '30%' }}
        isConnectable={isConnectable}
        className="w-3 h-3 bg-amber-600 border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output-false"
        style={{ top: '70%' }}
        isConnectable={isConnectable}
        className="w-3 h-3 bg-amber-600 border-2 border-background"
      />
    </div>
  )
}

export const ConditionalNode = memo(ConditionalNodeComponent)
