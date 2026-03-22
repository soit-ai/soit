import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { CircleDashed } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const VariableAggregatorNodeInfo = {
  type: 'variable-aggregator-node',
  labelKey: 'workflow.detail.nodes.variableAggregator.label',
  descriptionKey: 'workflow.detail.nodes.variableAggregator.description',
  label: 'Variable Aggregator',
  category: 'data',
  description: 'Aggregate multiple variables into a single structure',
  color: 'emerald-500',
  icon: 'CircleDashed',
}

export const VariableAggregatorNodeDefaultData = {
  label: 'Variable Aggregator',
  structure: 'object',
  variables: [],
  outputVariable: '',
}

// Variable aggregator node component.
const VariableAggregatorNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-emerald-500' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <CircleDashed className="h-4 w-4 text-emerald-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.variableAggregator.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.structure
          ? t('workflow.detail.nodes.variableAggregator.previewStructure', { value: data.structure as string })
          : t('workflow.detail.nodes.variableAggregator.description')}
      </div>

      {/* Input handles. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input-1"
        style={{ top: '30%' }}
        isConnectable={isConnectable}
        className="w-3 h-3 bg-emerald-500 border-2 border-background"
      />

      <Handle
        type="target"
        position={targetPosition}
        id="input-2"
        style={{ top: '70%' }}
        isConnectable={isConnectable}
        className="w-3 h-3 bg-emerald-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-emerald-500 border-2 border-background"
      />
    </div>
  )
}

export const VariableAggregatorNode = memo(VariableAggregatorNodeComponent)
