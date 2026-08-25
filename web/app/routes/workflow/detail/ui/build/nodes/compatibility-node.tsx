import React, { memo } from 'react'
import type { Node, NodeProps } from '@xyflow/react'
import { useTranslation } from '@/i18n'

export type CompatibilityNodeData = {
  label?: string
  originalRuntimeType: string
  originalParams: Record<string, unknown>
}

const CompatibilityNodeComponent = ({ data }: NodeProps<Node<CompatibilityNodeData>>) => {
  const { t } = useTranslation()

  return (
    <div className="min-w-56 rounded-md border border-cat-amber/20 bg-cat-amber/10 p-3">
      <div className="text-sm font-medium">{t('workflow.detail.nodes.compatibility.title')}</div>
      <div className="mt-1 font-mono text-xs">{String(data.originalRuntimeType)}</div>
      <div className="mt-2 text-xs text-muted-foreground">{t('workflow.detail.nodes.compatibility.description')}</div>
    </div>
  )
}

export const CompatibilityNode = memo(CompatibilityNodeComponent)
