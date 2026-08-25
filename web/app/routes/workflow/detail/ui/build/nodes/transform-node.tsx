import React, { memo, useEffect, useState } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { RefreshCw } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const TransformNodeInfo = {
  type: 'transform-node',
  labelKey: 'workflow.detail.nodes.transform.label',
  descriptionKey: 'workflow.detail.nodes.transform.description',
  label: 'Transform',
  category: 'data',
  description: 'Transform data format or structure',
  color: 'cat-red',
  icon: 'RefreshCw',
}

export const TransformNodeDefaultData = {
  label: 'Transform',
  mapping: {},
}

// Transform node component.
const TransformNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-red' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <RefreshCw className="h-4 w-4 text-cat-red" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.transform.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.detail.nodes.transform.description')}
      </div>

      {/* Input handle. */}
      <Handle
        type="target"
        position={targetPosition}
        id="input"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-red border-2 border-background"
      />

      {/* Output handle. */}
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="w-3 h-3 bg-cat-red border-2 border-background"
      />
    </div>
  )
}

export const TransformNode = memo(TransformNodeComponent)

interface TransformPropertiesProps {
  data: any
  onChange: (data: any) => void
  onValidityChange?: (valid: boolean) => void
}

const mappingText = (mapping: unknown) => {
  if (typeof mapping !== 'object' || mapping === null || Array.isArray(mapping)) return '{}'
  return JSON.stringify(mapping, null, 2)
}

export const TransformProperties: React.FC<TransformPropertiesProps> = ({ data, onChange, onValidityChange }) => {
  const { t } = useTranslation()
  const [draft, setDraft] = useState(() => mappingText(data.mapping))
  const [invalid, setInvalid] = useState(false)

  useEffect(() => {
    setDraft(mappingText(data.mapping))
    setInvalid(false)
    onValidityChange?.(true)
  }, [data.mapping, onValidityChange])

  useEffect(() => () => onValidityChange?.(true), [onValidityChange])

  return (
    <div className="space-y-2">
      <Label htmlFor="transform-mapping">{t('workflow.detail.nodes.transform.fields.mappingLabel')}</Label>
      <Textarea
        id="transform-mapping"
        className="font-mono text-xs"
        rows={10}
        value={draft}
        aria-invalid={invalid}
        placeholder={t('workflow.detail.nodes.transform.placeholders.mapping')}
        onChange={(event) => {
          const value = event.target.value
          setDraft(value)
          try {
            const parsed = JSON.parse(value)
            if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
              setInvalid(true)
              onValidityChange?.(false)
              return
            }
            setInvalid(false)
            onValidityChange?.(true)
            onChange({ mapping: parsed })
          } catch {
            setInvalid(true)
            onValidityChange?.(false)
          }
        }}
      />
      {invalid && <p className="text-xs text-destructive">{t('workflow.detail.nodes.transform.invalidMapping')}</p>}
    </div>
  )
}
