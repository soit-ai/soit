import React, { memo } from 'react'
import { Handle, type NodeProps } from '@xyflow/react'
import { LogIn } from 'lucide-react'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const InputNodeInfo = {
  type: 'input-node',
  labelKey: 'workflow.detail.nodes.input.label',
  descriptionKey: 'workflow.detail.nodes.input.description',
  label: 'Input',
  category: 'input',
  description: 'Validated workflow invocation input',
  color: 'emerald-500',
  icon: 'LogIn',
}

export const InputNodeDefaultData = {
  label: 'Input',
  description: 'Validated workflow invocation input',
}

const InputNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition } = useNodeHandles()

  return (
    <div className={`min-w-[180px] rounded-md border bg-card p-3 shadow-sm ${selected ? 'border-emerald-500' : 'border-border'}`}>
      <div className="mb-2 flex items-center gap-2">
        <LogIn className="h-4 w-4 text-emerald-500" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.input.label')}</div>
      </div>
      <div className="mb-2 text-xs text-muted-foreground">
        {t('workflow.detail.nodes.input.description')}
      </div>
      <Handle
        type="source"
        position={sourcePosition}
        id="output"
        isConnectable={isConnectable}
        className="h-3 w-3 border-2 border-background bg-emerald-500"
      />
    </div>
  )
}

export const InputNode = memo(InputNodeComponent)

interface InputPropertiesProps {
  data: any
  onChange: (data: any) => void
}

export const InputProperties: React.FC<InputPropertiesProps> = ({ data, onChange }) => {
  const { t } = useTranslation()
  const select = Array.isArray(data.select) && data.select.every((value: unknown) => typeof value === 'string')
    ? data.select
    : []
  const serializedSelect = select.join('\n')
  const [selectDraft, setSelectDraft] = React.useState(serializedSelect)

  React.useEffect(() => {
    setSelectDraft(serializedSelect)
  }, [serializedSelect])

  return (
    <div className="space-y-2">
      <Label htmlFor="input-select">{t('workflow.detail.nodes.input.fields.selectLabel')}</Label>
      <Textarea
        id="input-select"
        value={selectDraft}
        rows={5}
        placeholder={t('workflow.detail.nodes.input.placeholders.select')}
        onChange={(event) => {
          const nextDraft = event.target.value
          setSelectDraft(nextDraft)
          const values = nextDraft
            .split('\n')
            .map((value) => value.trim())
            .filter(Boolean)
          onChange({ select: values.length ? values : undefined })
        }}
      />
      <p className="text-xs text-muted-foreground">{t('workflow.detail.nodes.input.fields.selectHelp')}</p>
    </div>
  )
}
