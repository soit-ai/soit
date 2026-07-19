import type {
  ObserveBucket,
  ObserveRange,
  ObserveTabId,
  RecentRun,
} from '@/services/observe-service'

export const OBSERVE_TAB_IDS: ObserveTabId[] = [
  'agent_health',
  'workflow_bottlenecks',
  'tool_reliability',
  'knowledge_quality',
]

export const OBSERVE_RANGES: ObserveRange[] = ['1h', '6h', '24h', '7d']

export const OBSERVE_BUCKETS: ObserveBucket[] = ['5m', '10m', '30m', '1h', '1d']

export const toneClasses: Record<string, { icon: string; line: string; delta: string; soft: string }> = {
  blue: { icon: 'bg-blue-50 text-blue-600 dark:bg-blue-400/12 dark:text-blue-300', line: '#2563eb', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-blue-500' },
  green: { icon: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-400/12 dark:text-emerald-300', line: '#10b981', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-emerald-500' },
  amber: { icon: 'bg-amber-50 text-amber-600 dark:bg-amber-400/12 dark:text-amber-300', line: '#f97316', delta: 'text-amber-600 dark:text-amber-300', soft: 'bg-orange-400' },
  red: { icon: 'bg-red-50 text-red-600 dark:bg-red-400/12 dark:text-red-300', line: '#ef4444', delta: 'text-red-600 dark:text-red-300', soft: 'bg-red-500' },
  cyan: { icon: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-400/12 dark:text-cyan-300', line: '#06b6d4', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-cyan-500' },
}

export const statusBadge = (status?: string) => {
  if (status === 'healthy') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'destructive'
  return 'outline'
}

export const asNumber = (value: unknown) => (typeof value === 'number' ? value : 0)

export const asString = (value: unknown) => (
  typeof value === 'string' ? value : value == null ? '-' : String(value)
)

export const formatPercent = (value: unknown) => `${Math.round(asNumber(value) * 1000) / 10}%`

export const formatMs = (value: unknown) => `${Math.round(asNumber(value))}ms`

export const formatDurationShort = (value?: number | null) => {
  if (value === null || value === undefined) return '-'
  if (value >= 1000) return `${Math.round(value / 10) / 100}s`
  return `${Math.round(value)}ms`
}

export const formatRunSubject = (
  run: Pick<RecentRun, 'mode' | 'subject_id' | 'subject_kind' | 'kind'>,
) => {
  const subject = run.subject_id || run.subject_kind || run.kind || 'run'
  return `${run.mode || run.kind || 'run'} · ${subject}`
}

export const cardChrome = 'rounded-lg border-border/80 bg-panel/95 py-0 shadow-[0_8px_22px_rgba(15,23,42,0.04)] backdrop-blur-none dark:bg-panel/88 dark:shadow-none'
export const dangerSurface = 'border-red-200 bg-red-50/85 text-red-700 dark:border-red-400/25 dark:bg-red-400/10 dark:text-red-200'
export const infoIconSurface = 'bg-blue-50 text-blue-600 dark:bg-blue-400/12 dark:text-blue-300'
