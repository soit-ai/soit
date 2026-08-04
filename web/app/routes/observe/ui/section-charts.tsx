import { useEffect, useRef, useState } from 'react'
import { ArrowRight } from 'lucide-react'
import {
  CartesianGrid,
  Line,
  LineChart as ReLineChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import type {
  DashboardSection,
  MetricCard,
  ObserveTabId,
  TrendPoint,
} from '@/services/observe-service'

import {
  cardChrome,
  dangerSurface,
  formatMs,
  formatPercent,
  toneClasses,
} from './dashboard-utils'

function useMeasuredChartWidth() {
  const ref = useRef<HTMLDivElement | null>(null)
  const [width, setWidth] = useState(0)

  useEffect(() => {
    const element = ref.current
    if (!element) return

    const updateWidth = () => {
      setWidth(Math.max(1, Math.floor(element.getBoundingClientRect().width)))
    }
    updateWidth()

    const observer = new ResizeObserver(updateWidth)
    observer.observe(element)
    return () => observer.disconnect()
  }, [])

  return { ref, width }
}

function MiniMetric({ item }: { item: MetricCard }) {
  const { t } = useTranslation()
  const tone = toneClasses[item.tone] || toneClasses.blue
  return (
    <div className="min-w-0 rounded-lg border border-border/80 bg-panel/80 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
        <span className={cn('h-2 w-2 rounded-full', tone.soft)} />
        <span className="truncate">{item.label}</span>
      </div>
      <div className="mt-2 truncate text-xl font-semibold leading-none">{item.value}</div>
      {item.delta ? <div className={cn('mt-2 text-xs font-medium', tone.delta)}>{t('observe.metric.deltaVsYesterday')} {item.delta}</div> : null}
    </div>
  )
}

function TrendChart({ data, tab }: { data: TrendPoint[]; tab: ObserveTabId }) {
  const { t } = useTranslation()
  const { ref, width } = useMeasuredChartWidth()
  const lines = tab === 'tool_reliability'
    ? [
        { key: 'tool_count', color: '#2563eb', name: t('observe.charts.series.calls') },
        { key: 'tool_failed_count', color: '#ef4444', name: t('observe.charts.series.errors') },
      ]
    : tab === 'knowledge_quality'
      ? [
          { key: 'retrieval_count', color: '#2563eb', name: t('observe.charts.series.retrievals') },
          { key: 'retrieval_failed_count', color: '#ef4444', name: t('observe.charts.series.failures') },
        ]
      : [
          { key: 'run_count', color: '#2563eb', name: t('observe.charts.series.runs') },
          { key: 'failed_run_count', color: '#ef4444', name: t('observe.charts.series.failures') },
          { key: 'success_rate', color: '#06b6d4', name: t('observe.charts.series.successRate') },
        ]
  return (
    <div ref={ref} className="h-[220px] min-w-[1px] w-full overflow-hidden">
      {width > 0 ? (
        <ReLineChart data={data} width={width} height={220}>
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
      ) : null}
    </div>
  )
}

type DonutDatum = {
  name: string
  value: number
  color: string
}

function DonutChart({
  data,
  legendLabel,
}: {
  data: DonutDatum[]
  legendLabel: string
}) {
  const { t } = useTranslation()
  const normalizedData = data.map((item) => ({
    ...item,
    value: Number.isFinite(item.value) ? Math.max(0, item.value) : 0,
  }))
  const hasData = normalizedData.some((item) => item.value > 0)
  const items = hasData
    ? normalizedData
    : [{ name: t('observe.charts.noData'), value: 0, color: '#94a3b8' }]
  const total = items.reduce((sum, item) => sum + item.value, 0)
  let cursor = 0
  const gradient = hasData
    ? items.map((item) => {
        const start = cursor
        const end = cursor + (item.value / total) * 100
        cursor = end
        return `${item.color} ${start}% ${end}%`
      }).join(', ')
    : `${items[0].color} 0% 100%`

  return (
    <div className="grid min-h-[168px] gap-3">
      <div className="flex items-center justify-center" aria-hidden="true">
        <div className="flex h-28 w-28 items-center justify-center rounded-full" style={{ background: `conic-gradient(${gradient})` }}>
          <div className="h-[68px] w-[68px] rounded-full bg-panel" />
        </div>
      </div>
      <ul aria-label={legendLabel} className="grid max-h-24 gap-1.5 overflow-y-auto text-xs">
        {items.map((item) => {
          const percentage = total > 0 ? Math.round((item.value / total) * 100) : 0
          return (
            <li key={item.name} className="flex min-w-0 items-center gap-2">
              <span className="h-2 w-2 shrink-0 rounded-full" style={{ backgroundColor: item.color }} aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate" title={item.name}>{item.name}</span>
              <span className="shrink-0 font-medium">{item.value} · {percentage}%</span>
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function SectionCharts({ section }: { section: DashboardSection }) {
  const { t } = useTranslation()

  if (section.id === 'workflow_bottlenecks') {
    const { queue_distribution: queueDistribution } = section.charts
    return (
      <div className="grid gap-3 xl:grid-cols-[1.55fr_1fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.bottleneckTopology')}</CardTitle></CardHeader>
          <CardContent className="flex min-h-[168px] flex-wrap items-center gap-3 p-4">
            {queueDistribution.length ? queueDistribution.map((row, index) => (
              <div key={String(row.id)} className="flex items-center gap-3">
                <div className={cn('min-w-[116px] rounded-lg border px-4 py-3 text-center text-sm font-semibold', row.failure_rate > 0 ? dangerSurface : 'border-border bg-panel/80 dark:bg-panel/60')}>
                  <div className="truncate">{row.stage || row.name}</div>
                  <div className="mt-2 text-xs font-medium text-muted-foreground">{formatMs(row.avg_wait_ms)}</div>
                </div>
                {index < queueDistribution.length - 1 ? <ArrowRight className="h-4 w-4 text-muted-foreground" /> : null}
              </div>
            )) : <div className="text-sm text-muted-foreground">{t('observe.charts.noBottleneckStage')}</div>}
          </CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.queueDistribution')}</CardTitle></CardHeader>
          <CardContent className="space-y-3 p-4">
            {queueDistribution.map((row) => (
              <div key={String(row.id)} className="grid grid-cols-[120px_1fr_64px] items-center gap-3 text-sm">
                <span className="truncate text-muted-foreground">{row.name}</span>
                <div className="h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, row.current_queue * 8)}%` }} /></div>
                <span className="text-right font-medium">{row.current_queue}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  if (section.id === 'tool_reliability') {
    const { error_distribution: errorDistribution, trend } = section.charts
    return (
      <div className="grid gap-3 xl:grid-cols-[1.45fr_0.75fr_0.95fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.toolReliabilityTrend')}</CardTitle></CardHeader>
          <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.errorTypeDistribution')}</CardTitle></CardHeader>
          <CardContent className="p-4">
            <DonutChart
              legendLabel={t('observe.charts.errorTypeDistributionLegend')}
              data={errorDistribution.map((item, index) => ({
                name: item.type,
                value: item.count,
                color: ['#f97316', '#2563eb', '#14b8a6', '#ef4444'][index % 4],
              }))}
            />
          </CardContent>
        </Card>
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-1">
          {section.summary_cards.slice(0, 4).map((card) => <MiniMetric key={card.id} item={card} />)}
        </div>
      </div>
    )
  }

  if (section.id === 'knowledge_quality') {
    const {
      low_quality_sources: lowQualitySources,
      quality_score: qualityScore,
      trend,
    } = section.charts
    return (
      <div className="grid gap-3 xl:grid-cols-[1.4fr_0.8fr_1fr]">
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.knowledgeQualityTrend')}</CardTitle></CardHeader>
          <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.qualityScore')}</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-center">
            <div className="relative my-6 flex h-36 w-36 items-center justify-center rounded-full bg-[conic-gradient(#2563eb_0_66%,#10b981_66%_100%)]">
              <div className="flex h-[112px] w-[112px] items-center justify-center rounded-full bg-panel text-center">
                <div><div className="text-3xl font-semibold">{qualityScore}</div><div className="text-xs text-muted-foreground">{t('observe.charts.overallScore')}</div></div>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className={cardChrome}>
          <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.lowQualitySources')}</CardTitle></CardHeader>
          <CardContent className="space-y-3 p-4">
            {lowQualitySources.map((row, index) => (
              <div key={String(row.id)} className="grid grid-cols-[24px_1fr_52px] items-center gap-3 text-sm">
                <span className="text-muted-foreground">{index + 1}</span>
                <span className="truncate">{row.name}</span>
                <span className="text-right font-medium">{formatPercent(row.hit_rate)}</span>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  const {
    alert_compression: alertCompression,
    health_distribution: healthDistribution,
    trend,
  } = section.charts

  return (
    <div className="grid gap-3 xl:grid-cols-[1.5fr_0.8fr_1fr]">
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.agentRunTrend')}</CardTitle></CardHeader>
        <CardContent className="p-4"><TrendChart data={trend} tab={section.id} /></CardContent>
      </Card>
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.healthSummary')}</CardTitle></CardHeader>
        <CardContent className="grid gap-3 p-4">
          <DonutChart
            legendLabel={t('observe.charts.healthSummaryLegend')}
            data={healthDistribution.map((item) => ({
              name: item.status,
              value: item.count,
              color: {
                healthy: '#10b981',
                warning: '#f97316',
                critical: '#ef4444',
                unknown: '#64748b',
              }[item.status],
            }))}
          />
        </CardContent>
      </Card>
      <Card className={cardChrome}>
        <CardHeader className="border-b px-4 py-3"><CardTitle className="text-[15px]">{t('observe.charts.alertCompression')}</CardTitle></CardHeader>
        <CardContent className="space-y-4 p-4">
          <div><div className="text-3xl font-semibold">{alertCompression.compressed_alerts}</div><div className="text-sm text-muted-foreground">{t('observe.charts.compressedAlerts')}</div></div>
          <div className="grid grid-cols-2 gap-3">
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">{t('observe.charts.rawAlerts')}</div><div className="text-xl font-semibold">{alertCompression.raw_alerts}</div></div>
            <div className="rounded-lg border p-3"><div className="text-xs text-muted-foreground">{t('observe.charts.status')}</div><div className="text-xl font-semibold">{t('observe.charts.converging')}</div></div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
