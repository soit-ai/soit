import React, { memo } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { Variable } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
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
  key: '',
  value: '',
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
        {data.key
          ? t('workflow.detail.nodes.variableAssignment.previewVariable', { value: data.key as string })
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

interface VariableAssignmentPropertiesProps {
  data: any
  onChange: (data: any) => void
  onValidityChange?: (valid: boolean) => void
}

const jsonValueText = (value: unknown) => JSON.stringify(value, null, 2) ?? ''

export const VariableAssignmentProperties: React.FC<VariableAssignmentPropertiesProps> = ({ data, onChange, onValidityChange }) => {
  const { t } = useTranslation()
  const [draft, setDraft] = React.useState(() => jsonValueText(data.value))
  const [invalid, setInvalid] = React.useState(false)

  React.useEffect(() => {
    setDraft(jsonValueText(data.value))
    setInvalid(false)
    onValidityChange?.(true)
  }, [data.value, onValidityChange])

  React.useEffect(() => () => onValidityChange?.(true), [onValidityChange])

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="variable-key">{t('workflow.detail.nodes.variableAssignment.fields.keyLabel')}</Label>
        <Input
          id="variable-key"
          value={typeof data.key === 'string' ? data.key : ''}
          placeholder={t('workflow.detail.nodes.variableAssignment.placeholders.key')}
          onChange={(event) => onChange({ key: event.target.value })}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="variable-value">{t('workflow.detail.nodes.variableAssignment.fields.valueLabel')}</Label>
        <Textarea
          id="variable-value"
          className="font-mono text-xs"
          rows={6}
          value={draft}
          aria-invalid={invalid}
          placeholder={t('workflow.detail.nodes.variableAssignment.placeholders.value')}
          onChange={(event) => {
            const value = event.target.value
            setDraft(value)
            try {
              const parsed = JSON.parse(value)
              setInvalid(false)
              onValidityChange?.(true)
              onChange({ value: parsed })
            } catch {
              setInvalid(true)
              onValidityChange?.(false)
            }
          }}
        />
        {invalid && <p className="text-xs text-destructive">{t('workflow.detail.nodes.variableAssignment.invalidValue')}</p>}
      </div>
    </div>
  )
}
