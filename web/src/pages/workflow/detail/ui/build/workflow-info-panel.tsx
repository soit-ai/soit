import React from 'react'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'
import { useTranslation } from '@/i18n'

interface WorkflowInfoPanelProps {
  workflowName: string
  workflowDescription: string
  setWorkflowName: (name: string) => void
  setWorkflowDescription: (description: string) => void
}

const WorkflowInfoPanel: React.FC<WorkflowInfoPanelProps> = ({
  workflowName,
  workflowDescription,
  setWorkflowName,
  setWorkflowDescription
}) => {
  const { t } = useTranslation()
  return (
    <div className="mb-4">
      <h3 className="text-sm font-medium mb-2">{t('workflow.build.info.title')}</h3>
      <Input
        placeholder={t('workflow.build.info.namePlaceholder')}
        value={workflowName}
        onChange={(e) => setWorkflowName(e.target.value)}
        className="mb-2"
      />
      <Input
        placeholder={t('workflow.build.info.descriptionPlaceholder')}
        value={workflowDescription}
        onChange={(e) => setWorkflowDescription(e.target.value)}
        className="mb-2"
      />
    </div>
  )
}

export default WorkflowInfoPanel
