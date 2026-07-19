import { type ComponentType, type KeyboardEvent } from 'react'
import { Link } from 'react-router'
import {
  Activity,
  AlertTriangle,
  Clock3,
  Gauge,
  ShieldCheck,
  Stethoscope,
  WalletCards,
} from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import type { MetricCard, WorkspaceObserveDashboard } from '@/services/observe-service'

import {
  cardChrome,
  dangerSurface,
  formatDurationShort,
  formatRunSubject,
  infoIconSurface,
  statusBadge,
  toneClasses,
} from './dashboard-utils'

const metricIcons = {
  run_count: Activity,
  failed_run_count: AlertTriangle,
  active_run_count: Stethoscope,
  pending_approvals: ShieldCheck,
  total_cost_usd: WalletCards,
} as const

function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (!values.length) return null
  const min = Math.min(...values)
  const max = Math.max(...values)
  const range = max - min || 1
  const width = 96
  const height = 28
  const step = values.length > 1 ? width / (values.length - 1) : width
  const path = values.map((value, index) => {
    const x = Number((index * step).toFixed(2))
    const y = Number((height - ((value - min) / range) * height).toFixed(2))
    return `${index === 0 ? 'M' : 'L'} ${x} ${y}`
  }).join(' ')
  return (
    <svg className="h-8 w-24" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <path d={path} fill="none" stroke={color} strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
    </svg>
  )
}

export function MetricTile({ item, onOpenRun }: { item: MetricCard; onOpenRun?: (url: string) => void }) {
  const tone = toneClasses[item.tone] || toneClasses.blue
  const Icon = metricIcons[item.id as keyof typeof metricIcons] || Gauge
  const detailUrl = typeof item.detail_url === 'string' && item.detail_url ? item.detail_url : null
  const openDetail = () => {
    if (detailUrl) onOpenRun?.(detailUrl)
  }
  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!detailUrl) return
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      openDetail()
    }
  }
  return (
    <Card
      className={cn(
        'min-w-0 overflow-hidden',
        cardChrome,
        detailUrl ? 'cursor-pointer transition hover:border-blue-300 hover:shadow-[0_10px_26px_rgba(37,99,235,0.10)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring' : null,
      )}
      role={detailUrl ? 'button' : undefined}
      tabIndex={detailUrl ? 0 : undefined}
      aria-label={detailUrl ? `打开运行详情：${item.label}` : undefined}
      onClick={openDetail}
      onKeyDown={handleKeyDown}
    >
      <CardContent className="relative flex min-h-[94px] items-center gap-4 p-4">
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-full', tone.icon)}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-semibold text-muted-foreground">{item.label}</div>
          <div className="mt-1 truncate text-[26px] font-semibold leading-none text-foreground">{item.value}</div>
          {item.delta ? <div className="mt-2 text-xs text-muted-foreground">较昨日 <span className={tone.delta}>{item.delta}</span></div> : null}
          {item.run_id ? <div className="mt-1 truncate text-xs font-medium text-muted-foreground">{item.run_id}</div> : null}
        </div>
        <div className="absolute bottom-4 right-4 hidden xl:block">
          <Sparkline values={item.trend || []} color={tone.line} />
        </div>
      </CardContent>
    </Card>
  )
}

function OverviewItem({
  icon: Icon,
  iconClassName,
  label,
  value,
  meta,
}: {
  icon: ComponentType<{ className?: string }>
  iconClassName: string
  label: string
  value: string
  meta?: string
}) {
  return (
    <div className="flex min-w-0 items-center gap-4 px-4 py-3 sm:px-5">
      <div className={cn('flex h-10 w-10 shrink-0 items-center justify-center rounded-full', iconClassName)}>
        <Icon className="h-5 w-5" />
      </div>
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold text-muted-foreground">{label}</div>
        <div className="mt-1 truncate text-[24px] font-semibold leading-none text-foreground">{value}</div>
        {meta ? <div className="mt-1 truncate text-xs font-medium text-muted-foreground">{meta}</div> : null}
      </div>
    </div>
  )
}

type DashboardSummaryProps = {
  dashboard: WorkspaceObserveDashboard
  onOpenRun: (url?: string | null) => void
  onOpenAlert: (url?: string | null) => void
}

export function DashboardSummary({
  dashboard,
  onOpenRun,
  onOpenAlert,
}: DashboardSummaryProps) {
  return (
    <>
      <section className="grid overflow-hidden rounded-lg border border-border/80 bg-panel/95 shadow-[0_8px_22px_rgba(15,23,42,0.04)] lg:grid-cols-2 xl:grid-cols-4">
        <OverviewItem
          icon={ShieldCheck}
          iconClassName="bg-emerald-50 text-emerald-600 dark:bg-emerald-400/12 dark:text-emerald-300"
          label="工作区健康"
          value={`${dashboard.overview.workspace_health_score}%`}
          meta={dashboard.overview.workspace_health_status === 'healthy' ? '健康' : dashboard.overview.workspace_health_status === 'warning' ? '警告' : '需要关注'}
        />
        <OverviewItem
          icon={AlertTriangle}
          iconClassName="bg-red-50 text-red-600 dark:bg-red-400/12 dark:text-red-300"
          label="活动告警"
          value={String(dashboard.overview.active_alert_count)}
          meta={dashboard.overview.active_alert_count > 0 ? '需要关注' : '无活动告警'}
        />
        <OverviewItem
          icon={Activity}
          iconClassName={infoIconSurface}
          label="采样状态"
          value={`${Math.round(dashboard.overview.sampling_rate * 100)}%`}
          meta={dashboard.overview.sampling_status}
        />
        <OverviewItem
          icon={Clock3}
          iconClassName={infoIconSurface}
          label="最近刷新"
          value="刚刚"
          meta={dashboard.overview.refreshed_at}
        />
      </section>

      <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-5">
        {dashboard.metric_cards.map((item) => <MetricTile key={item.id} item={item} onOpenRun={onOpenRun} />)}
      </div>

      {dashboard.recent_runs.length ? (
        <section className="overflow-hidden rounded-lg border border-border/80 bg-panel/95 px-4 py-3 shadow-[0_8px_22px_rgba(15,23,42,0.04)]">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <div className="text-[15px] font-semibold">最近应用运行</div>
            <Link to="/observe/runs?include_observe_summary=true" className="text-xs font-medium text-blue-600 hover:underline dark:text-blue-300">查看全部运行</Link>
          </div>
          <div className="flex gap-2 overflow-x-auto pb-1">
            {dashboard.recent_runs.slice(0, 6).map((run) => (
              <Button
                key={run.run_id}
                variant="outline"
                className="h-auto min-w-[260px] justify-start rounded-lg bg-panel px-3 py-2 text-left"
                type="button"
                aria-label={`打开运行详情：${run.run_id}`}
                onClick={() => onOpenRun(run.detail_url)}
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <Badge variant={statusBadge(run.status)}>{run.status}</Badge>
                    <span className="truncate text-sm font-semibold">{run.run_id}</span>
                  </div>
                  <div className="mt-1 truncate text-xs text-muted-foreground">
                    {formatRunSubject(run)} · {formatDurationShort(run.duration_ms)} · ${run.cost_usd.toFixed(2)}
                  </div>
                  {run.observe_summary ? (
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[11px] font-medium text-muted-foreground">
                      <span>步骤 {run.observe_summary.step_count}</span>
                      <span>工具 {run.observe_summary.tool_call_count}</span>
                      <span>引用 {run.observe_summary.citation_count}</span>
                      <span>审计 {run.observe_summary.audit_count}</span>
                    </div>
                  ) : null}
                  {run.failure_reason ? <div className="mt-1 truncate text-xs text-red-600 dark:text-red-300">{run.failure_reason}</div> : null}
                </div>
              </Button>
            ))}
          </div>
        </section>
      ) : (
        <section className="rounded-lg border border-dashed bg-panel px-4 py-5 text-sm text-muted-foreground">
          当前 24h 内没有应用运行数据。质量门禁命令不会自动写入 Observe；请通过企业 MVP demo 或应用操作产生 Agent、Workflow、Knowledge 运行后再查看。
          <Link to="/observe/runs?include_observe_summary=true" className="ml-2 font-medium text-blue-600 hover:underline dark:text-blue-300">打开 Run Explorer</Link>
        </section>
      )}

      {dashboard.priority_alert ? (
        <div className={cn('flex min-h-9 flex-col gap-2 rounded-lg px-4 py-2 text-sm lg:flex-row lg:items-center lg:justify-between', dangerSurface)}>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
            <Badge variant="destructive">{dashboard.priority_alert.priority}</Badge>
            <span className="font-semibold">{dashboard.priority_alert.title}</span>
            <span>影响范围：{dashboard.priority_alert.scope}</span>
            <span>影响 Agent：{dashboard.priority_alert.affected_agents}</span>
            <span>持续时间：{dashboard.priority_alert.duration_label}</span>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="text-red-700 hover:text-red-800 dark:text-red-200 dark:hover:text-red-100"
            onClick={() => onOpenAlert(dashboard.priority_alert?.detail_url)}
          >
            应急处理
          </Button>
        </div>
      ) : null}
    </>
  )
}
