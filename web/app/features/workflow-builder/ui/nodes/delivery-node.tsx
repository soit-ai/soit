import React, { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'
import { Send } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNodeHandles } from '../hooks/use-node-handles'

export const DeliveryNodeInfo = {
  type: 'delivery-node',
  labelKey: 'workflow.detail.nodes.delivery.label',
  descriptionKey: 'workflow.detail.nodes.delivery.description',
  label: 'Delivery',
  category: 'flow',
  description: 'Pass data to the next node',
  color: 'cat-green',
  icon: 'Send',
}

export const DeliveryNodeDefaultData = {
  label: 'Delivery',
  message: '',
  deliveryType: 'direct',
}

// Delivery node component.
const DeliveryNodeComponent = ({ data, isConnectable, selected }: NodeProps) => {
  const { t } = useTranslation()
  const { sourcePosition, targetPosition } = useNodeHandles()
  return (
    <div className={`p-3 rounded-md border ${selected ? 'border-cat-green' : 'border-border'} bg-card shadow-sm min-w-[180px]`}>
      <div className="flex items-center gap-2 mb-2">
        <Send className="h-4 w-4 text-cat-green" />
        <div className="text-sm font-medium">{data.label as string || t('workflow.detail.nodes.delivery.label')}</div>
      </div>

      <div className="text-xs text-muted-foreground mb-2">
        {t('workflow.detail.nodes.delivery.description')}
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

export const DeliveryNode = memo(DeliveryNodeComponent)
