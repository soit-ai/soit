import { useMemo } from 'react'
import { AlertTriangle, Gauge, Layers3, Orbit, Wallet } from 'lucide-react'

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'
import type { Agent } from '@/services/agent-service'
import type { KnowledgeBase } from '@/services/knowledge-service'
import type { RunResponse } from '@/services/run-service'
import type { Task } from '@/services/task-service'
import type { Workflow } from '@/services/workflow-service'

import { useHomeFormatters } from '../hooks/use-home-formatters'
import type { DashboardSummary } from '../hooks/use-home-dashboard'
import { ActivitySparkline } from './activity-sparkline'

type OperationsDashboardProps = {
  summary: DashboardSummary
  agents: Agent[]
  workflows: Workflow[]
  knowledgeBases: KnowledgeBase[]
  tasks: Task[]
  runs: RunResponse[]
  isLoading: boolean
}

const percentage = (value: number, total: number) => {
  if (total <= 0) {
    return 0
  }
  return Math.round((value / total) * 100)
}

const safeDivide = (value: number, total: number) => {
  if (total <= 0) {
    return 0
  }
  return value / total
}

const startOfDay = (value: Date) => new Date(value.getFullYear(), value.getMonth(), value.getDate())

const buildActivitySeries = (timestamps: Array<string | null | undefined>, days = 7) => {
  const today = startOfDay(new Date())
  const start = new Date(today)
  start.setDate(today.getDate() - days + 1)
  const buckets = Array.from({ length: days }, () => 0)

  timestamps.forEach((timestamp) => {
    if (!timestamp) {
      return
    }

    const date = new Date(timestamp)
    if (Number.isNaN(date.getTime())) {
      return
    }

    const normalized = startOfDay(date)
    const diff = Math.floor((normalized.getTime() - start.getTime()) / 86_400_000)
    if (diff >= 0 && diff < days) {
      buckets[diff] += 1
    }
  })

  return buckets
}

const scaleToPercent = (value: number, max: number) => {
  if (max <= 0) {
    return 0
  }
  return Math.round((value / max) * 100)
}

export function OperationsDashboard({
  summary,
  agents,
  workflows,
  knowledgeBases,
  tasks,
  runs,
  isLoading,
}: OperationsDashboardProps) {
  const { t } = useTranslation()
  const { formatCompact, formatNumber } = useHomeFormatters()

  const publishRate = percentage(summary.publishedAgents, summary.agentCount)
  const workflowVersionRate = percentage(summary.versionedWorkflows, summary.workflowCount)
  const docsPerKnowledge = safeDivide(summary.totalDocuments, summary.knowledgeCount)
  const chunksPerDoc = safeDivide(summary.totalChunks, summary.totalDocuments)

  const riskTone =
    summary.failedRunCount > 0 || summary.attentionTaskCount > 2
      ? 'text-rose-600'
      : summary.activeTaskCount > 0
        ? 'text-amber-600'
        : 'text-emerald-600'

  const trendCards = useMemo(() => {
    const buildSeries = buildActivitySeries([
      ...agents.map((agent) => agent.published_at || agent.updated_at || agent.created_at),
      ...workflows.map((workflow) => workflow.updated_at || workflow.created_at),
    ])

    const knowledgeSeries = buildActivitySeries(
      knowledgeBases.map((base) => base.last_ingested_at || base.updated_at || base.created_at)
    )
    const taskSeries = buildActivitySeries(tasks.map((task) => task.updated_at || task.created_at))
    const runSeries = buildActivitySeries(runs.map((run) => run.started_at || run.created_at))

    return [
      {
        key: 'build',
        title: t('agent.home.dashboard.traceBuild'),
        value: formatNumber(buildSeries.reduce((sum, value) => sum + value, 0)),
        description: t('agent.home.dashboard.traceWindow'),
        values: buildSeries,
        lineColor: 'rgba(14, 165, 233, 0.95)',
        fillColor: 'rgba(14, 165, 233, 0.12)',
        barColor: 'rgba(14, 165, 233, 0.16)',
      },
      {
        key: 'knowledge',
        title: t('agent.home.dashboard.traceKnowledge'),
        value: formatNumber(knowledgeSeries.reduce((sum, value) => sum + value, 0)),
        description: t('agent.home.dashboard.traceWindow'),
        values: knowledgeSeries,
        lineColor: 'rgba(245, 158, 11, 0.95)',
        fillColor: 'rgba(245, 158, 11, 0.12)',
        barColor: 'rgba(245, 158, 11, 0.16)',
      },
      {
        key: 'tasks',
        title: t('agent.home.dashboard.traceTasks'),
        value: formatNumber(taskSeries.reduce((sum, value) => sum + value, 0)),
        description: t('agent.home.dashboard.traceWindow'),
        values: taskSeries,
        lineColor: 'rgba(244, 63, 94, 0.95)',
        fillColor: 'rgba(244, 63, 94, 0.12)',
        barColor: 'rgba(244, 63, 94, 0.16)',
      },
      {
        key: 'runs',
        title: t('agent.home.dashboard.traceRuns'),
        value: formatNumber(runSeries.reduce((sum, value) => sum + value, 0)),
        description: t('agent.home.dashboard.traceWindow'),
        values: runSeries,
        lineColor: 'rgba(16, 185, 129, 0.95)',
        fillColor: 'rgba(16, 185, 129, 0.12)',
        barColor: 'rgba(16, 185, 129, 0.16)',
      },
    ]
  }, [agents, knowledgeBases, runs, tasks, workflows, formatNumber, t])

  const riskMax = Math.max(summary.attentionTaskCount, summary.failedRunCount, summary.activeTaskCount, summary.draftAgents, 1)
  const tokenTotal = summary.promptTokens + summary.completionTokens
  const promptPercent = tokenTotal > 0 ? Math.round((summary.promptTokens / tokenTotal) * 100) : 0
  const completionPercent = tokenTotal > 0 ? 100 - promptPercent : 0

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3 border-b border-border/70">
        <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-muted-foreground">
          {t('agent.home.dashboard.eyebrow')}
        </div>
        <CardTitle className="text-2xl">{t('agent.home.dashboard.title')}</CardTitle>
        <CardDescription>{t('agent.home.dashboard.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="rounded-[var(--radius-2xl)] border border-border/70 bg-[linear-gradient(180deg,rgba(248,251,254,0.96)_0%,rgba(241,246,251,0.88)_100%)] p-4 dark:bg-[linear-gradient(180deg,rgba(18,28,44,0.72)_0%,rgba(18,28,44,0.56)_100%)]">
          <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-muted-foreground">
            {t('agent.home.dashboard.traceEyebrow')}
          </div>
          <div className="mt-2 text-lg font-semibold">{t('agent.home.dashboard.traceTitle')}</div>
          <div className="mt-1 text-sm text-muted-foreground">{t('agent.home.dashboard.traceDescription')}</div>

          <div className="mt-4 grid gap-3 lg:grid-cols-2 2xl:grid-cols-4">
            {trendCards.map((card) => (
              <div
                key={card.key}
                className="rounded-[26px] border border-slate-200/70 bg-white/82 p-4 dark:border-slate-800 dark:bg-slate-950/64"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground">{card.title}</div>
                    <div className="mt-2 text-2xl font-semibold">{isLoading ? '...' : card.value}</div>
                  </div>
                  <div className="text-right text-xs text-muted-foreground">{card.description}</div>
                </div>
                <ActivitySparkline
                  className="mt-4"
                  values={card.values}
                  lineColor={card.lineColor}
                  fillColor={card.fillColor}
                  barColor={card.barColor}
                />
              </div>
            ))}
          </div>
        </section>

        <div className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr_1fr]">
          <section className="rounded-[28px] border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-900/55">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium">
              <Layers3 className="h-4 w-4 text-sky-600" />
              {t('agent.home.dashboard.buildTitle')}
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t('agent.home.dashboard.publishRate')}</span>
                  <span className="font-medium">{isLoading ? '...' : `${formatNumber(publishRate)}%`}</span>
                </div>
                <Progress value={publishRate} className="h-2 bg-slate-200 dark:bg-slate-800" />
                <div className="text-xs text-muted-foreground">
                  {t('agent.home.dashboard.publishDetail', {
                    published: formatNumber(summary.publishedAgents),
                    total: formatNumber(summary.agentCount),
                  })}
                </div>
              </div>

              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{t('agent.home.dashboard.workflowCoverage')}</span>
                  <span className="font-medium">{isLoading ? '...' : `${formatNumber(workflowVersionRate)}%`}</span>
                </div>
                <Progress value={workflowVersionRate} className="h-2 bg-slate-200 dark:bg-slate-800" />
                <div className="text-xs text-muted-foreground">
                  {t('agent.home.dashboard.workflowDetail', {
                    versioned: formatNumber(summary.versionedWorkflows),
                    total: formatNumber(summary.workflowCount),
                  })}
                </div>
              </div>

              <div className="grid gap-px overflow-hidden rounded-[24px] border border-slate-200/70 bg-slate-200/70 dark:border-slate-800 dark:bg-slate-800 sm:grid-cols-2">
                <div className="bg-white/84 px-4 py-3 dark:bg-slate-950/64">
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.docsPerKnowledge')}</div>
                  <div className="mt-2 text-2xl font-semibold">{formatNumber(Math.round(docsPerKnowledge || 0))}</div>
                </div>
                <div className="bg-white/84 px-4 py-3 dark:bg-slate-950/64">
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.chunksPerDoc')}</div>
                  <div className="mt-2 text-2xl font-semibold">{formatNumber(Math.round(chunksPerDoc || 0))}</div>
                </div>
              </div>
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-900/55">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium">
              <AlertTriangle className={`h-4 w-4 ${riskTone}`} />
              {t('agent.home.dashboard.riskTitle')}
            </div>

            <div className="space-y-3">
              {[
                {
                  label: t('agent.home.dashboard.attentionTasks'),
                  value: summary.attentionTaskCount,
                  hint: t('agent.home.dashboard.attentionHint'),
                },
                {
                  label: t('agent.home.dashboard.failedRuns'),
                  value: summary.failedRunCount,
                  hint: t('agent.home.dashboard.failedHint'),
                },
                {
                  label: t('agent.home.dashboard.activeTasks'),
                  value: summary.activeTaskCount,
                  hint: t('agent.home.dashboard.activeHint'),
                },
                {
                  label: t('agent.home.dashboard.draftAgents'),
                  value: summary.draftAgents,
                  hint: t('agent.home.dashboard.draftHint'),
                },
              ].map((item) => (
                <div
                  key={item.label}
                  className="rounded-[22px] border border-slate-200/70 bg-white/82 px-3 py-3 dark:border-slate-800 dark:bg-slate-950/64"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm text-muted-foreground">{item.label}</div>
                    <div className="text-xl font-semibold">{formatNumber(item.value)}</div>
                  </div>
                  <div className="mt-2">
                    <Progress value={scaleToPercent(item.value, riskMax)} className="h-1.5 bg-slate-200 dark:bg-slate-800" />
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">{item.hint}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-slate-200/70 bg-slate-50/70 p-4 dark:border-slate-800 dark:bg-slate-900/55">
            <div className="mb-4 flex items-center gap-2 text-sm font-medium">
              <Wallet className="h-4 w-4 text-emerald-600" />
              {t('agent.home.dashboard.ledgerTitle')}
            </div>

            <div className="rounded-[24px] border border-slate-200/70 bg-white/82 p-4 dark:border-slate-800 dark:bg-slate-950/64">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{t('agent.home.dashboard.tokenSplit')}</div>
                <Orbit className="h-4 w-4 text-emerald-600" />
              </div>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                <div className="flex h-full">
                  <div className="h-full bg-emerald-500" style={{ width: `${promptPercent}%` }} />
                  <div className="h-full bg-cyan-500" style={{ width: `${completionPercent}%` }} />
                </div>
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <div>
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.promptTokens')}</div>
                  <div className="mt-1 text-xl font-semibold">{formatCompact(summary.promptTokens)}</div>
                </div>
                <div>
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.completionTokens')}</div>
                  <div className="mt-1 text-xl font-semibold">{formatCompact(summary.completionTokens)}</div>
                </div>
              </div>
            </div>

            <div className="mt-3 grid gap-px overflow-hidden rounded-[24px] border border-slate-200/70 bg-slate-200/70 dark:border-slate-800 dark:bg-slate-800 sm:grid-cols-2">
              <div className="bg-white/84 px-4 py-3 dark:bg-slate-950/64">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.runtimeMs')}</div>
                  <Gauge className="h-4 w-4 text-violet-600" />
                </div>
                <div className="mt-2 text-2xl font-semibold">{formatCompact(summary.runtimeMs)}</div>
              </div>
              <div className="bg-white/84 px-4 py-3 dark:bg-slate-950/64">
                <div className="flex items-center justify-between">
                  <div className="text-xs text-muted-foreground">{t('agent.home.dashboard.recentRuns')}</div>
                  <Gauge className="h-4 w-4 text-sky-600" />
                </div>
                <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.runCount)}</div>
              </div>
            </div>
          </section>
        </div>
      </CardContent>
    </Card>
  )
}

