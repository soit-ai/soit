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

import type { Task, TaskWorkbenchRow } from '@/services/task-service'

export type TaskTab = 'all' | 'waiting_approval' | 'failed' | 'waiting_input' | 'long_running' | 'running'

export const taskTabs: Array<{ id: TaskTab; label: string }> = [
  { id: 'all', label: '全部' },
  { id: 'waiting_approval', label: '待审批' },
  { id: 'failed', label: '失败' },
  { id: 'waiting_input', label: '等待输入' },
  { id: 'long_running', label: '长时间运行' },
  { id: 'running', label: '运行中' },
]

export const statusLabels: Record<string, string> = {
  queued: '排队中',
  preparing: '准备中',
  running: '运行中',
  retrying: '重试中',
  waiting_input: '等待输入',
  waiting_approval: '待审批',
  paused: '已暂停',
  succeeded: '成功',
  failed: '失败',
  canceled: '已取消',
  expired: '已过期',
}

export const statusVariant = (status: string) => {
  if (status === 'failed') return 'destructive'
  if (status === 'succeeded') return 'success'
  if (status === 'waiting_input') return 'info'
  if (status === 'waiting_approval') return 'warning'
  if (['running', 'preparing', 'queued', 'retrying'].includes(status)) return 'success'
  return 'outline'
}

export const sceneForType = (taskType: string) => {
  if (taskType === 'agent.execute' || taskType === 'agent.stream') {
    return { label: 'Agent 执行', icon: Bot, tone: 'text-emerald-600 bg-emerald-50 border-emerald-100' }
  }
  if (taskType === 'wf_step') {
    return { label: '工作流节点', icon: Workflow, tone: 'text-blue-600 bg-blue-50 border-blue-100' }
  }
  if (taskType === 'approval_gate') {
    return { label: '审批任务', icon: ShieldAlert, tone: 'text-orange-600 bg-orange-50 border-orange-100' }
  }
  return { label: '其他运行任务', icon: FileQuestion, tone: 'text-slate-600 bg-slate-50 border-slate-100' }
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

export const actionLabel = (action: string) => {
  if (action === 'retry') return '重试'
  if (action === 'resume') return '恢复'
  if (action === 'cancel') return '取消'
  return action
}

export const rowTitle = (row: TaskWorkbenchRow | Task) => {
  return 'display_name' in row ? row.display_name : row.input_json?.title?.toString() || row.task_type
}

export const formatTaskTime = (value?: string | null) => {
  if (!value) return '-'
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

export const taskAgeLabel = (value?: string | null) => {
  if (!value) return '-'
  const diff = Date.now() - new Date(value).getTime()
  if (diff < 0) return '-'
  const minutes = Math.floor(diff / 60000)
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  return `${hours} 小时 ${minutes % 60} 分钟`
}

export const sparkline = [8, 10, 9, 12, 11, 15, 10, 13, 9, 11]
