import React, { memo } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { Variable } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const VariableAssignmentNodeInfo = {
  type: 'variable-assignment-node',
  labelKey: 'workflow.detail.nodes.variableAssignment.label',
  descriptionKey: 'workflow.detail.nodes.variableAssignment.description',
  label: 'Variable Assignment',
  category: 'data',
  description: 'Assign values to variables',
  color: 'sky-500',
  icon: 'Variable',
}

export const VariableAssignmentNodeDefaultData = {
  label: 'Variable Assignment',
  variableName: '',
  variableValue: '',
  valueType: 'string',
}

// Variable assignment node component.
const VariableAssignmentNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-sky-500' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Variable className="h-4 w-4 text-sky-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.variableAssignment.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.variableName
          ? t('workflow.detail.nodes.variableAssignment.previewVariable', { value: data.variableName as string })
          : t('workflow.detail.nodes.variableAssignment.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-sky-500 border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-sky-500 border-2 border-background"
      />
    </div>
  )
}

export const VariableAssignmentNode = memo(VariableAssignmentNodeComponent)
