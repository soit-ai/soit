import React, { memo } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { Code } from 'lucide-react'
import { useNodeHandles } from '../hooks/use-node-handles'
import { useTranslation } from '@/i18n'

export const CodeExecutionNodeInfo = {
  type: 'code-execution-node',
  label: 'Code Execution',
  labelKey: 'workflow.blocks.code',
  category: 'Tool',
  categoryKey: 'workflow.nodeLibrary.categories.tool',
  description: 'Execute custom code',
  descriptionKey: 'workflow.blocksAbout.code',
  color: 'slate-600',
  icon: 'Code',
}

export const CodeExecutionNodeDefaultData = {
  label: 'Code',
  language: 'javascript',
  code: '',
  timeout: 30000,
}

const CodeExecutionNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles();
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-slate-600' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Code className="h-4 w-4 text-slate-600" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.blocks.code')}</div>
      </div>
      
      <div className="text-xs text-muted-foreground mb-2">
        {data.language
          ? t('workflow.customNodes.code.language', { value: data.language as string })
          : t('workflow.blocksAbout.code')}
      </div>
      
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-slate-600 border-2 border-background"
      />
      
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-slate-600 border-2 border-background"
      />
    </div>
  )
}

export const CodeExecutionNode = memo(CodeExecutionNodeComponent)
