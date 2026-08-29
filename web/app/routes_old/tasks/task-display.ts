import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  FileQuestion,
  PlayCircle,
  ShieldAlert,
  Timer,
  Workflow,
} from 'lucide-react'

import type { TFunction } from '@/i18n/types'
import type { Task, TaskWorkbenchRow } from '@/services/task-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

export type TaskTab = 'all' | 'waiting_approval' | 'failed' | 'waiting_input' | 'long_running' | 'running'

export const taskTabIds: TaskTab[] = [
  'all',
  'waiting_approval',
  'failed',
  'waiting_input',
  'long_running',
  'running',
]

export const taskTabLabel = (t: TFunction, tab: TaskTab) => t(`task.tabs.${tab}`)

export const taskTabs = (t: TFunction): Array<{ id: TaskTab; label: string }> =>
  taskTabIds.map((id) => ({ id, label: taskTabLabel(t, id) }))

export const statusLabel = (t: TFunction, status: string) => {
  switch (status) {
    case 'queued':
      return t('task.status.queued')
    case 'preparing':
      return t('task.status.preparing')
    case 'running':
      return t('task.status.running')
    case 'retrying':
      return t('task.status.retrying')
    case 'waiting_input':
      return t('task.status.waiting_input')
    case 'waiting_approval':
      return t('task.status.waiting_approval')
    case 'paused':
      return t('task.status.paused')
    case 'succeeded':
      return t('task.status.succeeded')
    case 'failed':
      return t('task.status.failed')
    case 'canceled':
      return t('task.status.canceled')
    case 'expired':
      return t('task.status.expired')
    default:
      return status
  }
}

export const statusVariant = (status: string) => {
  if (status === 'failed') return 'destructive'
  if (status === 'succeeded') return 'success'
  if (status === 'waiting_input') return 'info'
  if (status === 'waiting_approval') return 'warning'
  if (['running', 'preparing', 'queued', 'retrying'].includes(status)) return 'success'
  return 'outline'
}

export const sceneForType = (t: TFunction, taskType: string) => {
  if (taskType === 'agent.execute' || taskType === 'agent.stream') {
    return { label: t('task.scene.agentExecute'), icon: Bot, tone: 'text-success-foreground bg-success/12 border-success/20' }
  }
  if (taskType === 'wf_step') {
    return { label: t('task.scene.workflowNode'), icon: Workflow, tone: 'text-primary bg-primary/12 border-primary/20' }
  }
  if (taskType === 'approval_gate') {
    return { label: t('task.scene.approval'), icon: ShieldAlert, tone: 'text-warning-foreground bg-warning/12 border-warning/20' }
  }
  return { label: t('task.scene.other'), icon: FileQuestion, tone: 'text-muted-foreground bg-muted border-border' }
}

export const metricIconForTab = (tab: TaskTab) => {
  switch (tab) {
    case 'waiting_approval':
      return ShieldAlert
    case 'failed':
      return AlertTriangle
    case 'waiting_input':
      return FileQuestion
    case 'long_running':
      return Timer
    case 'running':
      return PlayCircle
    default:
      return CheckCircle2
  }
}

export const actionLabel = (t: TFunction, action: string) => {
  if (action === 'retry') return t('task.actions.retry')
  if (action === 'resume') return t('task.actions.resume')
  if (action === 'cancel') return t('task.actions.cancel')
  return action
}

export const rowTitle = (row: TaskWorkbenchRow | Task) => {
  return 'display_name' in row ? row.display_name : row.input_json?.title?.toString() || row.task_type
}

export const formatTaskTime = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(isoToZonedDate(value))
}

export const taskAgeLabel = (t: TFunction, value?: string | null) => {
  if (!value) return '-'
  const diff = Date.now() - new Date(value).getTime()
  if (diff < 0) return '-'
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return t('task.age.minutes', { minutes })
  const hours = Math.floor(minutes / 60)
  return t('task.age.hoursMinutes', { hours, minutes: minutes % 60 })
}

export const sparkline = [8, 10, 9, 12, 11, 15, 10, 13, 9, 11]
