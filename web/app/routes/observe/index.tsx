import { type ComponentType, useMemo } from 'react'
import { useSearchParams } from 'react-router'
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  Clock3,
  Database,
  Gauge,
  LineChart,
  MoreHorizontal,
  RefreshCw,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  Stethoscope,
  WalletCards,
} from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart as ReLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { cn } from '@/lib/utils'
import {
  getObserveDashboard,
  type DashboardSection,
  type MetricCard,
  type ObserveBucket,
  type ObserveRange,
  type ObserveTabId,
  type TrendPoint,
} from '@/services/observe-service'

const TAB_IDS: ObserveTabId[] = ['agent_health', 'workflow_bottlenecks', 'tool_reliability', 'knowledge_quality']
const RANGES: ObserveRange[] = ['1h', '6h', '24h', '7d']
const BUCKETS: ObserveBucket[] = ['5m', '10m', '30m', '1h', '1d']

const toneClasses: Record<string, { icon: string; line: string; delta: string; soft: string }> = {
  blue: { icon: 'bg-blue-50 text-blue-600 dark:bg-blue-400/12 dark:text-blue-300', line: '#2563eb', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-blue-500' },
  green: { icon: 'bg-emerald-50 text-emerald-600 dark:bg-emerald-400/12 dark:text-emerald-300', line: '#10b981', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-emerald-500' },
  amber: { icon: 'bg-amber-50 text-amber-600 dark:bg-amber-400/12 dark:text-amber-300', line: '#f97316', delta: 'text-amber-600 dark:text-amber-300', soft: 'bg-orange-400' },
  red: { icon: 'bg-red-50 text-red-600 dark:bg-red-400/12 dark:text-red-300', line: '#ef4444', delta: 'text-red-600 dark:text-red-300', soft: 'bg-red-500' },
  cyan: { icon: 'bg-cyan-50 text-cyan-600 dark:bg-cyan-400/12 dark:text-cyan-300', line: '#06b6d4', delta: 'text-emerald-600 dark:text-emerald-300', soft: 'bg-cyan-500' },
}

const metricIcons = {
  run_count: Activity,
  failed_run_count: AlertTriangle,
  active_run_count: Stethoscope,
  pending_approvals: ShieldCheck,
  total_cost_usd: WalletCards,
} as const

const statusBadge = (status?: string) => {
  if (status === 'healthy') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'critical') return 'destructive'
  return 'outline'
}

const asNumber = (value: unknown) => (typeof value === 'number' ? value : 0)
const asString = (value: unknown) => (typeof value === 'string' ? value : value == null ? '-' : String(value))
const formatPercent = (value: unknown) => `${Math.round(asNumber(value) * 1000) / 10}%`
const formatMs = (value: unknown) => `${Math.round(asNumber(value))}ms`
const cardChrome = 'rounded-lg border-border/80 bg-panel/95 py-0 shadow-[0_8px_22px_rgba(15,23,42,0.04)] backdrop-blur-none dark:bg-panel/88 dark:shadow-none'
const dangerSurface = 'border-red-200 bg-red-50/85 text-red-700 dark:border-red-400/25 dark:bg-red-400/10 dark:text-red-200'
const infoIconSurface = 'bg-blue-50 text-blue-600 dark:bg-blue-400/12 dark:text-blue-300'

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

function MetricTile({ item }: { item: MetricCard }) {
  const tone = toneClasses[item.tone] || toneClasses.blue
  const Icon = metricIcons[item.id as keyof typeof metricIcons] || Gauge
  return (
    <Card className={cn('min-w-0 overflow-hidden', cardChrome)}>
      <CardContent className="relative flex min-h-[94px] items-center gap-4 p-4">
        <div className={cn('flex h-11 w-11 shrink-0 items-center justify-center rounded-full', tone.icon)}>
          <Icon className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="truncate text-[13px] font-semibold text-muted-foreground">{item.label}</div>
          <div className="mt-1 truncate text-[26px] font-semibold leading-none text-foreground">{item.value}</div>
          {item.delta ? <div className="mt-2 text-xs text-muted-foreground">较昨日 <span className={tone.delta}>{item.delta}</span></div> : null}
        </div>
        <div className="absolute bottom-4 right-4 hidden xl:block">
          <Sparkline values={item.trend || []} color={tone.line} />
        </div>
      </CardContent>
    </Card>
  )
}

function MiniMetric({ item }: { item: MetricCard }) {
  const tone = toneClasses[item.tone] || toneClasses.blue
  return (
    <div className="min-w-0 rounded-lg border border-border/80 bg-panel/80 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <span className={cn('h-2 w-2 rounded-full', tone.soft)} />
        <span className="truncate">{item.label}</span>
      </div>
      <div className="mt-2 truncate text-xl font-semibold leading-none">{item.value}</div>
      {item.delta ? <div className={cn('mt-2 text-xs font-medium', tone.delta)}>较昨日 {item.delta}</div> : null}
    </div>
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

function DashboardSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <Skeleton className="h-20 w-full" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, index) => <Skeleton key={index} className="h-24" />)}
      </div>
      <Skeleton className="h-[420px] w-full" />
    </div>
  )
}

function EmptyState({ section }: { section: DashboardSection }) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed bg-panel p-8 text-center">
      <Database className="h-8 w-8 text-muted-foreground" />
      <div className="mt-3 text-base font-semibold">{section.empty_state.title}</div>
      <div className="mt-1 max-w-md text-sm text-muted-foreground">{section.empty_state.description}</div>
    </div>
  )
}

function TrendChart({ data, tab }: { data: TrendPoint[]; tab: ObserveTabId }) {
  const lines = tab === 'tool_reliability'
    ? [
        { key: 'tool_count', color: '#2563eb', name: '调用数' },
        { key: 'tool_failed_count', color: '#ef4444', name: '错误数' },
      ]
    : tab === 'knowledge_quality'
      ? [
          { key: 'retrieval_count', color: '#2563eb', name: '召回数' },
          { key: 'retrieval_failed_count', color: '#ef4444', name: '失败数' },
        ]
      : [
          { key: 'run_count', color: '#2563eb', name: '运行数' },
          { key: 'failed_run_count', color: '#ef4444', name: '失败数' },
          { key: 'success_rate', color: '#06b6d4', name: '成功率' },
        ]
  return (
    <div className="h-[220px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ReLineChart data={data}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="bucket" tickFormatter={(value) => String(value).slice(11, 16)} minTickGap={24} tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }} axisLine={{ stroke: 'hsl(var(--border))' }} tickLine={{ stroke: 'hsl(var(--border))' }} />
          <YAxis tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }} width={42} axisLine={{ stroke: 'hsl(var(--border))' }} tickLine={{ stroke: 'hsl(var(--border))' }} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'hsl(var(--popover))',
              border: '1px solid hsl(var(--border))',
              borderRadius: 8,
              color: 'hsl(var(--popover-foreground))',
            }}
            labelStyle={{ color: 'hsl(var(--popover-foreground))' }}
          />
          {lines.map((line) => (
            <Line key={line.key} type="monotone" dataKey={line.key} name={line.name} stroke={line.color} strokeWidth={2} dot={false} />
          ))}
        </ReLineChart>
      </ResponsiveContainer>
    </div>
  )
}

function DonutChart({ data }: { data: Array<{ name: string; value: number; color: string }> }) {
  const total = data.reduce((sum, item) => sum + item.value, 0) || 1
  let cursor = 0
  const gradient = data.map((item) => {
    const start = cursor
    const end = cursor + (item.value / total) * 100
    cursor = end
    return `${item.color} ${start}% ${end}%`
  }).join(', ')

  return (
    <div className="flex h-[168px] w-full items-center justify-center">
      <div className="flex h-32 w-32 items-center justify-center rounded-full" style={{ background: `conic-gradient(${gradient})` }}>
        <div className="h-[76px] w-[76px] rounded-full bg-panel" />
      </div>
    </div>
  )
}

function SectionCharts({ section }: { section: DashboardSection }) {
  const trend = (section.charts.trend || []) as TrendPoint[]
  const errorDistribution = (section.charts.error_distribution || []) as Array<{ type: string; count: number }>
  const lowQualitySources = (section.charts.low_quality_sources || []) as Array<Record<string, unknown>>
  const healthDistribution = (section.charts.health_distribution || []) as Array<{ status: string; count: number }>
  const queueDistribution = (section.charts.queue_distribution || []) as Array<Record<string, unknown>>
  const alertCompression = (section.charts.alert_compression || {}) as Record<string, unknown>

  if (section.id === 'workflow_bottlenecks') {
    return (
      <div className="grid gap-3 xl:grid-cols-[1.55fr_1fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">瓶颈拓扑</CardTitle></CardHeader>
          <CardContent className="flex min-h-[168px] flex-wrap items-center gap-3 p-4">
            {queueDistribution.length ? queueDistribution.map((row, index) => (
              <div key={String(row.id)} className="flex items-center gap-3">
                <div className={cn('min-w-[116px] rounded-lg border px-4 py-3 text-center text-sm font-semibold', asNumber(row.failure_rate) > 0 ? dangerSurface : 'border-border bg-panel/80 dark:bg-panel/60')}>
                  <div className="truncate">{asString(row.stage || row.name)}</div>
                  <div className="mt-2 text-xs font-medium text-muted-foreground">{formatMs(row.avg_wait_ms)}</div>
                </div>
                {index < queueDistribution.length - 1 ? <ArrowRight className="h-4 w-4 text-muted-foreground" /> : null}
              </div>
            )) : <div className="text-sm text-muted-foreground">暂无瓶颈阶段</div>}
          </CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">排队与耗时分布</CardTitle></CardHeader>
          <CardContent className="space-y-3 p-4">
            {queueDistribution.map((row) => (
              <div key={String(row.id)} className="grid grid-cols-[120px_1fr_64px] items-center gap-3 text-sm">
                <span className="truncate text-muted-foreground">{asString(row.name)}</span>
                <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, asNumber(row.current_queue) * 8)}%` }} /></div>
                <span className="text-right font-medium">{asString(row.current_queue)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  if (section.id === 'tool_reliability') {
    return (
      <div className="grid gap-3 xl:grid-cols-[1.45fr_0.75fr_0.95fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">工具调用可靠性趋势</CardTitle></CardHeader>
          <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">错误类型分布</CardTitle></CardHeader>
          <CardContent className="p-4">
            <DonutChart data={(errorDistribution.length ? errorDistribution : [{ type: '无错误', count: 1 }]).map((item, index) => ({
              name: item.type,
              value: item.count,
              color: ['#f97316', '#2563eb', '#14b8a6', '#ef4444'][index % 4],
            }))} />
          </CardContent>
        </Card>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          {section.summary_cards.slice(0, 4).map((card) => <MiniMetric key={card.id} item={card} />)}
        </div>
      </div>
    )
  }

  if (section.id === 'knowledge_quality') {
    return (
      <div className="grid gap-3 xl:grid-cols-[1.4fr_0.8fr_1fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">知识召回质量趋势</CardTitle></CardHeader>
          <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">质量评分</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-center">
            <div className="relative my-6 flex h-36 w-36 items-center justify-center rounded-full bg-[conic-gradient(#2563eb_0_66%,#10b981_66%_100%)]">
              <div className="flex h-[112px] w-[112px] items-center justify-center rounded-full bg-panel text-center">
                <div><div className="text-3xl font-semibold">{asString(section.charts.quality_score)}</div><div className="text-xs text-muted-foreground">综合评分</div></div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">低质量来源</CardTitle></CardHeader>
          <CardContent className="space-y-3 p-4">
            {lowQualitySources.map((row, index) => (
              <div key={String(row.id)} className="grid grid-cols-[24px_1fr_52px] items-center gap-3 text-sm">
                <span className="text-muted-foreground">{index + 1}</span>
                <span className="truncate">{asString(row.name)}</span>
                <span className="text-right font-medium">{formatPercent(row.hit_rate)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="grid gap-3 xl:grid-cols-[1.5fr_0.8fr_1fr]">
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">Agent 运行与异常趋势</CardTitle></CardHeader>
        <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
      </Card>
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">健康摘要</CardTitle></CardHeader>
        <CardContent className="grid gap-3 p-4">
          <DonutChart data={(healthDistribution.length ? healthDistribution : [{ status: 'no_data', count: 1 }]).map((item, index) => ({
            name: item.status,
            value: item.count,
            color: ['#10b981', '#f97316', '#ef4444'][index % 3],
          }))} />
          <div className="grid gap-2 text-sm">
            {healthDistribution.map((item, index) => (
              <div key={item.status} className="flex items-center justify-between gap-3">
                <span className="flex min-w-0 items-center gap-2 text-muted-foreground"><span className={cn('h-2 w-2 rounded-full', ['bg-emerald-500', 'bg-orange-400', 'bg-red-500'][index % 3])} />{item.status}</span>
                <span className="font-semibold">{item.count}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">告警压缩</CardTitle></CardHeader>
        <CardContent className="space-y-4 p-4">
          <div><div className="text-3xl font-semibold">{asString(alertCompression.compressed_alerts)}</div><div className="text-sm text-muted-foreground">压缩后告警</div></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">原始告警</div><div className="text-xl font-semibold">{asString(alertCompression.raw_alerts)}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">状态</div><div className="text-xl font-semibold">收敛中</div></div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

function SectionTable({ section, onOpenRuns, onOpenDetail }: {
  section: DashboardSection
  onOpenRuns: (row: Record<string, unknown>) => void
  onOpenDetail: (row: Record<string, unknown>) => void
}) {
  if (!section.rows.length) return <EmptyState section={section} />
  const title = section.id === 'agent_health'
    ? 'Agent 健康明细'
    : section.id === 'workflow_bottlenecks'
      ? '瓶颈明细'
      : section.id === 'tool_reliability'
        ? '工具明细'
        : '知识质量明细'

  const columns = section.id === 'agent_health'
    ? ['Agent 名称', '状态', '运行数', '平均延迟', '错误率', '成功率', '最近异常', '负责人', '最近运行']
    : section.id === 'workflow_bottlenecks'
      ? ['工作流', '阶段', '当前队列', '平均等待', '失败率', '影响 Agent', '负责人']
      : section.id === 'tool_reliability'
        ? ['工具名称', '类型', '调用次数', '成功率', '平均耗时', '失败原因', '关联 Agent', '负责人']
        : ['知识库', '关联 Agent', '命中率', '无答案率', '过期片段', '最近更新', '状态', '负责人']

  const renderCells = (row: Record<string, unknown>) => {
    if (section.id === 'agent_health') {
      return [asString(row.name), <Badge key="status" variant={statusBadge(asString(row.status))}>{asString(row.status)}</Badge>, asString(row.run_count), formatMs(row.avg_latency_ms), formatPercent(row.failed_run_count && row.run_count ? asNumber(row.failed_run_count) / asNumber(row.run_count) : 0), formatPercent(row.success_rate), asString(row.last_error), asString(row.owner), asString(row.last_run_at)]
    }
    if (section.id === 'workflow_bottlenecks') {
      return [asString(row.name), asString(row.stage), asString(row.current_queue), formatMs(row.avg_wait_ms), formatPercent(row.failure_rate), Array.isArray(row.affected_agents) ? row.affected_agents.join(', ') : '-', asString(row.owner)]
    }
    if (section.id === 'tool_reliability') {
      return [asString(row.name), asString(row.type), asString(row.call_count), formatPercent(row.success_rate), formatMs(row.avg_latency_ms), Object.keys((row.failure_reason || {}) as Record<string, unknown>).join(', ') || '-', Array.isArray(row.related_agents) ? row.related_agents.join(', ') : '-', asString(row.owner)]
    }
    return [asString(row.name), Array.isArray(row.related_agents) ? row.related_agents.join(', ') : '-', formatPercent(row.hit_rate), formatPercent(row.missing_answer_rate), asString(row.expired_chunks), asString(row.last_updated), <Badge key="status" variant={statusBadge(asString(row.status))}>{asString(row.status)}</Badge>, asString(row.owner)]
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border/80 bg-panel/95">
      <div className="border-b px-4 py-3 text-[15px] font-semibold">{title}</div>
      <div className="overflow-x-auto">
        <Table className="min-w-[1040px]">
          <TableHeader>
            <TableRow className="h-9 bg-muted/60">
              {columns.map((column) => <TableHead key={column} className="h-9 px-3 text-xs font-semibold">{column}</TableHead>)}
              <TableHead className="h-9 w-[132px] px-3 text-right text-xs font-semibold">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {section.rows.map((row) => (
              <TableRow key={row.id} className="h-11">
                {renderCells(row).map((cell, index) => <TableCell key={`${row.id}-${index}`} className="px-3 py-2 text-[13px]">{cell}</TableCell>)}
                <TableCell className="px-3 py-2 text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="outline" size="icon-sm" aria-label="查看运行" onClick={() => onOpenRuns(row)}><BarChart3 className="h-4 w-4" /></Button>
                    <Button variant="outline" size="icon-sm" aria-label="查看详情" onClick={() => onOpenDetail(row)}><LineChart className="h-4 w-4" /></Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="icon-sm" aria-label="更多操作"><MoreHorizontal className="h-4 w-4" /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => onOpenRuns(row)}>查看运行</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigator.clipboard?.writeText(row.id)}>复制 ID</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}

function ObservePage() {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const tab = TAB_IDS.includes(searchParams.get('tab') as ObserveTabId) ? searchParams.get('tab') as ObserveTabId : 'agent_health'
  const range = RANGES.includes(searchParams.get('range') as ObserveRange) ? searchParams.get('range') as ObserveRange : '1h'
  const bucket = BUCKETS.includes(searchParams.get('bucket') as ObserveBucket) ? searchParams.get('bucket') as ObserveBucket : '10m'
  const q = searchParams.get('q') || ''
  const pageToken = searchParams.get('page_token') || undefined
  const pageSize = Number(searchParams.get('page_size') || 10)

  const params = useMemo(() => ({ tab, range, bucket, q, page_token: pageToken, page_size: pageSize }), [tab, range, bucket, q, pageToken, pageSize])
  const { data: dashboard, isLoading, isError, refetch } = useQuery({
    queryKey: ['observe', 'dashboard', params],
    queryFn: () => getObserveDashboard(params),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const updateParams = (patch: Record<string, string | undefined>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (!value) next.delete(key)
      else next.set(key, value)
    })
    setSearchParams(next)
  }

  const openRuns = (row?: Record<string, unknown>) => {
    const next = new URLSearchParams()
    if (row?.id) next.set('subject_id', String(row.id))
    navigate(`/observe/runs${next.toString() ? `?${next.toString()}` : ''}`)
  }

  const openDetail = (row: Record<string, unknown>) => {
    if (tab === 'agent_health') navigate(`/agents/${encodeURIComponent(String(row.id))}`)
    else if (tab === 'knowledge_quality') navigate(`/knowledge/${encodeURIComponent(String(row.id))}`)
    else openRuns(row)
  }

  return (
    <main className="flex w-full max-w-[calc(100vw-var(--root-sidebar-width)-1px)] min-w-0 flex-1 flex-col overflow-x-hidden bg-background">
      <div className="mx-auto flex w-full min-w-0 flex-1 flex-col gap-3 px-5 py-5 lg:px-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">观测工作台</h1>
            <p className="mt-1 text-sm text-muted-foreground">监控智能体运行健康、调用趋势与异常处理，保障服务稳定可靠</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" className="h-10 rounded-lg bg-panel/90" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
            <Button className="h-10 rounded-lg px-5 shadow-sm" type="button" onClick={(event) => {
              event.preventDefault()
              openRuns()
            }}>
              打开 Run Explorer
              <ArrowRight className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {isLoading ? <DashboardSkeleton /> : isError || !dashboard ? (
          <Alert variant="destructive">
            <AlertTriangle className="h-4 w-4" />
            <AlertTitle>观测数据加载失败</AlertTitle>
            <AlertDescription>
              <Button variant="outline" size="sm" onClick={() => refetch()}>重试</Button>
            </AlertDescription>
          </Alert>
        ) : (
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
              {dashboard.metric_cards.map((item) => <MetricTile key={item.id} item={item} />)}
            </div>

            {dashboard.priority_alert ? (
              <div className={cn('flex min-h-9 flex-col gap-2 rounded-lg px-4 py-2 text-sm lg:flex-row lg:items-center lg:justify-between', dangerSurface)}>
                <div className="flex flex-wrap items-center gap-x-6 gap-y-2">
                  <Badge variant="destructive">{dashboard.priority_alert.priority}</Badge>
                  <span className="font-semibold">{dashboard.priority_alert.title}</span>
                  <span>影响范围：{dashboard.priority_alert.scope}</span>
                  <span>影响 Agent：{dashboard.priority_alert.affected_agents}</span>
                  <span>持续时间：{dashboard.priority_alert.duration_label}</span>
                </div>
                <Button variant="ghost" size="sm" className="text-red-700 hover:text-red-800 dark:text-red-200 dark:hover:text-red-100" onClick={() => navigate(dashboard.priority_alert?.detail_url || '/observe/runs')}>应急处理</Button>
              </div>
            ) : null}

            <Card className={cn('overflow-hidden', cardChrome)}>
              <CardContent className="p-0">
                <Tabs value={tab} onValueChange={(value) => updateParams({ tab: value, page_token: undefined, q: undefined })}>
                  <div className="flex flex-col gap-3 border-b px-4 py-2.5 xl:flex-row xl:items-center xl:justify-between">
                    <TabsList variant="line" className="max-w-full flex-wrap justify-start">
                      {dashboard.tabs.map((item) => <TabsTrigger key={item.id} value={item.id} className="h-9 px-4 data-[state=active]:text-blue-600 dark:data-[state=active]:text-blue-300">{item.label}</TabsTrigger>)}
                    </TabsList>
                    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
                      <div className="relative min-w-[240px] sm:w-[300px]">
                        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                        <Input value={q} onChange={(event) => updateParams({ q: event.target.value, page_token: undefined })} placeholder="搜索名称" className="h-9 rounded-lg bg-panel pl-9" />
                      </div>
                      <Button variant="outline" className="h-9 rounded-lg bg-panel" type="button"><SlidersHorizontal className="h-4 w-4" />筛选</Button>
                      <select className="h-9 rounded-lg border bg-panel px-3 text-sm" value={range} onChange={(event) => updateParams({ range: event.target.value, page_token: undefined })}>
                        {RANGES.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                      <select className="h-9 rounded-lg border bg-panel px-3 text-sm" value={bucket} onChange={(event) => updateParams({ bucket: event.target.value, page_token: undefined })}>
                        {BUCKETS.map((item) => <option key={item} value={item}>{item}</option>)}
                      </select>
                      <Button variant="outline" size="icon" className="h-9 w-9 rounded-lg bg-panel" aria-label="刷新当前视图" onClick={() => refetch()}><RefreshCw className="h-4 w-4" /></Button>
                    </div>
                  </div>

                  <TabsContent value={tab} className="m-0 space-y-3 p-4">
                    <SectionCharts section={dashboard.section} />
                    {dashboard.section.id === 'knowledge_quality' ? <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-4">
                      {dashboard.section.summary_cards.map((card) => <MetricTile key={card.id} item={card} />)}
                    </div> : null}
                    <SectionTable section={dashboard.section} onOpenRuns={openRuns} onOpenDetail={openDetail} />
                    <div className="flex flex-wrap items-center justify-between gap-3 border-t pt-1 text-sm text-muted-foreground">
                      <span>共 {dashboard.section.page.total_count} 条</span>
                      <div className="flex flex-wrap items-center gap-2">
                        <select className="h-8 rounded-lg border bg-panel px-3 text-xs" value={pageSize} onChange={(event) => updateParams({ page_size: event.target.value, page_token: undefined })}>
                          <option value="10">10 条/页</option>
                          <option value="20">20 条/页</option>
                          <option value="50">50 条/页</option>
                        </select>
                        <Button variant="ghost" size="icon-sm" disabled>‹</Button>
                        <Button variant="outline" size="sm" className="h-8 min-w-8 rounded-lg px-2">1</Button>
                        <Button variant="ghost" size="sm" className="h-8 min-w-8 px-2">2</Button>
                        <Button variant="ghost" size="sm" className="h-8 min-w-8 px-2">3</Button>
                        <Button variant="ghost" size="icon-sm" disabled={!dashboard.section.page.next_page_token} onClick={() => updateParams({ page_token: dashboard.section.page.next_page_token || undefined })}>›</Button>
                        <span className="ml-3">前往</span>
                        <Input className="h-8 w-12 rounded-lg bg-panel px-2 text-center" value="1" readOnly />
                        <span>页</span>
                      </div>
                    </div>
                  </TabsContent>
                </Tabs>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </main>
  )
}

export default ObservePage
