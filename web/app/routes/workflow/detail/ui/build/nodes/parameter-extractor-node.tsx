import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { SlidersHorizontal } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const ParameterExtractorNodeInfo = {
  type: 'parameter-extractor-node',
  label: 'Parameter Extractor',
  labelKey: 'workflow.blocks.parameter-extractor',
  category: 'Data',
  categoryKey: 'workflow.nodeLibrary.categories.data',
  description: 'Extract parameters from inputs',
  descriptionKey: 'workflow.blocksAbout.parameter-extractor',
  color: 'cat-teal',
  icon: 'SlidersHorizontal',
}

export const ParameterExtractorNodeDefaultData = {
  label: 'Parameter Extractor',
  parameters: [],
  defaultValues: {},
}

const ParameterExtractorNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-teal' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <SlidersHorizontal className="h-4 w-4 text-cat-teal" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.parameter-extractor')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.blocksAbout.parameter-extractor')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-teal border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-teal border-2 border-background"
      />
    </div>
  )
}

export const ParameterExtractorNode = memo(ParameterExtractorNodeComponent)
