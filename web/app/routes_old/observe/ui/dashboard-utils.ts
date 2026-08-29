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
  blue: { icon: 'bg-cat-blue/12 text-cat-blue', line: 'var(--cat-blue)', delta: 'text-success-foreground', soft: 'bg-cat-blue' },
  green: { icon: 'bg-cat-green/12 text-cat-green', line: 'var(--cat-green)', delta: 'text-success-foreground', soft: 'bg-cat-green' },
  amber: { icon: 'bg-cat-amber/12 text-cat-amber', line: 'var(--cat-amber)', delta: 'text-warning-foreground', soft: 'bg-cat-amber' },
  red: { icon: 'bg-cat-red/12 text-cat-red', line: 'var(--cat-red)', delta: 'text-danger-foreground', soft: 'bg-cat-red' },
  cyan: { icon: 'bg-cat-cyan/12 text-cat-cyan', line: 'var(--cat-cyan)', delta: 'text-success-foreground', soft: 'bg-cat-cyan' },
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
export const dangerSurface = 'border-danger/20 bg-danger/12 text-danger-foreground dark:border-danger/25'
export const infoIconSurface = 'bg-primary/12 text-primary'
