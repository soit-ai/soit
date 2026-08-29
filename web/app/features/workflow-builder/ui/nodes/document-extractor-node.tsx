import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { FileText } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const DocumentExtractorNodeInfo = {
  type: 'document-extractor-node',
  labelKey: 'workflow.detail.nodes.documentExtractor.label',
  descriptionKey: 'workflow.detail.nodes.documentExtractor.description',
  label: 'Document Extractor',
  category: 'data',
  description: 'Extract information from documents',
  color: 'cat-green',
  icon: 'FileText',
}

export const DocumentExtractorNodeDefaultData = {
  label: 'Document Extractor',
  documentId: '',
  extractionType: 'text',
  outputFormat: 'json',
  extractionRules: [],
}

// Document extractor node component.
const DocumentExtractorNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-green' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <FileText className="h-4 w-4 text-cat-green" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.documentExtractor.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {data.outputFormat
          ? t('workflow.detail.nodes.documentExtractor.previewOutput', { value: data.outputFormat as string })
          : t('workflow.detail.nodes.documentExtractor.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-green border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-green border-2 border-background"
      />
    </div>
  )
}

export const DocumentExtractorNode = memo(DocumentExtractorNodeComponent)
