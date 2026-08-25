import { Activity, AlertTriangle, ArrowRight, Bot, Database, RefreshCw, Sparkles, Waypoints } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'

import { useHomeFormatters } from '../hooks/use-home-formatters'
import type { DashboardSummary } from '../hooks/use-home-dashboard'

type HomeHeroProps = {
  summary: DashboardSummary
  isRefreshing: boolean
  partialFailure: boolean
  isInitialError?: boolean
  onRefresh: () => void
}

export function HomeHero({ summary, isRefreshing, partialFailure, isInitialError = false, onRefresh }: HomeHeroProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { formatNumber, formatCompact } = useHomeFormatters()

  const publishRate = summary.agentCount > 0 ? Math.round((summary.publishedAgents / summary.agentCount) * 100) : 0
  const knowledgeDensity = summary.knowledgeCount > 0 ? Math.round(summary.totalDocuments / summary.knowledgeCount) : 0
  const totalTokens = summary.promptTokens + summary.completionTokens

  const railMetrics = [
    {
      label: t('agent.home.hero.publishRate'),
      value: `${formatNumber(publishRate)}%`,
    },
    {
      label: t('agent.home.hero.knowledgeDensity'),
      value: formatNumber(knowledgeDensity),
    },
    {
      label: t('agent.home.hero.totalTokens'),
      value: formatCompact(totalTokens),
    },
    {
      label: t('agent.home.hero.activeRuntime'),
      value: formatNumber(summary.activeTaskCount),
    },
  ]

  const signalPanels = [
    {
      label: t('agent.home.hero.signalBuild'),
      value: formatNumber(summary.publishedAgents),
      meta: `${formatNumber(summary.agentCount)} ${t('agent.home.hero.agentsUnit')} / ${formatNumber(summary.workflowCount)} ${t('agent.home.hero.workflowsUnit')}`,
      icon: Bot,
      tone: 'text-primary',
    },
    {
      label: t('agent.home.hero.signalKnowledge'),
      value: formatCompact(summary.totalDocuments),
      meta: `${formatCompact(summary.totalChunks)} ${t('agent.home.hero.chunksUnit')}`,
      icon: Database,
      tone: 'text-warning-foreground',
    },
    {
      label: t('agent.home.hero.signalRuntime'),
      value: formatNumber(summary.activeTaskCount),
      meta: `${formatNumber(summary.failedRunCount)} ${t('agent.home.hero.failedRuns')}`,
      icon: Waypoints,
      tone: 'text-success-foreground',
    },
    {
      label: t('agent.home.hero.totalTokens'),
      value: formatCompact(totalTokens),
      meta: t('agent.home.hero.runtimeMs', { count: formatCompact(summary.runtimeMs) }),
      icon: Activity,
      tone: 'text-primary',
    },
  ]

  return (
    <section className="animate-in fade-in slide-in-from-top-2 duration-500">
      <div className="relative overflow-hidden rounded-[calc(var(--radius-2xl)+0.5rem)] border border-border/70 bg-[linear-gradient(145deg,rgba(255,255,255,0.84)_0%,rgba(246,249,252,0.94)_44%,rgba(236,244,252,0.98)_100%)] p-5 shadow-[0_28px_80px_rgba(15,23,42,0.08)] md:p-6 xl:p-7 dark:bg-[linear-gradient(145deg,rgba(14,20,34,0.92)_0%,rgba(17,26,42,0.94)_44%,rgba(11,34,54,0.96)_100%)]">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_12%_16%,rgba(14,165,233,0.16),transparent_24%),radial-gradient(circle_at_84%_12%,rgba(59,130,246,0.12),transparent_20%),linear-gradient(rgba(15,23,42,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(15,23,42,0.045)_1px,transparent_1px)] [background-size:auto,auto,28px_28px,28px_28px] opacity-70 dark:bg-[radial-gradient(circle_at_12%_16%,rgba(34,211,238,0.16),transparent_24%),radial-gradient(circle_at_84%_12%,rgba(96,165,250,0.14),transparent_20%),linear-gradient(rgba(255,255,255,0.04)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.04)_1px,transparent_1px)]" />

        <div className="relative grid gap-3 border-b border-border/60 pb-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="flex flex-wrap items-center gap-3">
            <Badge variant="outline" className="bg-panel/78 text-foreground">
              {t('agent.home.hero.badge')}
            </Badge>
            <Badge className="bg-primary/10 text-primary">
              {t('agent.home.hero.mode')}
            </Badge>
            <span className="text-[11px] uppercase tracking-[0.24em] text-muted-foreground">
              {t('agent.home.hero.commandRail')}
            </span>
            {partialFailure && !isInitialError && (
              <Badge variant="destructive" className="gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5" />
                {t('agent.home.hero.partialFailure')}
              </Badge>
            )}
          </div>

          {isInitialError && (
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-[var(--radius-lg)] border border-destructive/40 bg-destructive/10 px-4 py-3">
              <div className="flex items-center gap-2 text-sm font-medium text-destructive">
                <AlertTriangle className="h-4 w-4" />
                {t('agent.home.hero.loadFailedTitle')}
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-1.5"
                disabled={isRefreshing}
                onClick={onRefresh}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
                {t('agent.home.hero.loadFailedRetry')}
              </Button>
            </div>
          )}

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {railMetrics.map((metric) => (
              <div
                key={metric.label}
                className="rounded-[var(--radius-lg)] border border-border/70 bg-elevated/72 px-3 py-2.5 shadow-[0_10px_20px_rgba(15,23,42,0.05)]"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">{metric.label}</div>
                <div className="mt-1 text-base font-semibold text-foreground">{metric.value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.2fr)_390px] xl:items-stretch">
          <div className="rounded-[var(--radius-2xl)] border border-border/70 bg-panel/84 p-5 shadow-[0_16px_36px_rgba(15,23,42,0.06)] backdrop-blur-md">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
              <div className="space-y-4">
                <div className="max-w-3xl space-y-3">
                  <div className="text-[11px] font-semibold uppercase tracking-[0.24em] text-primary/80">
                    Workspace Pulse
                  </div>
                  <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-foreground md:text-5xl">
                    {t('agent.home.hero.title')}
                  </h1>
                  <p className="max-w-2xl text-sm leading-7 text-muted-foreground md:text-[15px]">
                    {t('agent.home.hero.description')}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button onClick={() => navigate('/agents')}>
                    <Bot className="mr-2 h-4 w-4" />
                    {t('agent.home.hero.ctaAgents')}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => navigate('/workflow')}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {t('agent.home.hero.ctaWorkflow')}
                  </Button>
                  <Button
                    variant="ghost"
                    onClick={() => navigate('/observe/runs')}
                  >
                    {t('agent.home.hero.ctaRuns')}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="grid gap-2.5 text-xs text-muted-foreground sm:grid-cols-3 lg:grid-cols-1">
                <span className="rounded-full border border-border/70 bg-elevated/72 px-3 py-2">
                  {t('agent.home.hero.runtimeMs', { count: formatCompact(summary.runtimeMs) })}
                </span>
                <span className="rounded-full border border-border/70 bg-elevated/72 px-3 py-2">
                  {t('agent.home.hero.attentionTasks', { count: formatNumber(summary.attentionTaskCount) })}
                </span>
                <span className="rounded-full border border-border/70 bg-elevated/72 px-3 py-2">
                  {t('agent.home.hero.promptTokens', {
                    prompt: formatCompact(summary.promptTokens),
                    completion: formatCompact(summary.completionTokens),
                  })}
                </span>
              </div>
            </div>

            <div className="mt-5">
              <div className="mb-3 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted-foreground">
                {t('agent.home.hero.signalStrip')}
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {signalPanels.map((panel) => {
                  const Icon = panel.icon

                  return (
                    <div
                      key={panel.label}
                      className="rounded-[var(--radius-xl)] border border-border/70 bg-elevated/74 px-4 py-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.2em] text-muted-foreground">
                            {panel.label}
                          </div>
                          <div className="mt-2 text-2xl font-semibold text-foreground">{panel.value}</div>
                        </div>
                        <div className="rounded-[0.875rem] border border-border/70 bg-panel/78 p-2.5">
                          <Icon className={`h-4 w-4 ${panel.tone}`} />
                        </div>
                      </div>
                      <div className="mt-3 text-sm text-muted-foreground">{panel.meta}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="rounded-[var(--radius-2xl)] border border-inverse-border bg-[linear-gradient(180deg,rgba(16,24,38,0.96)_0%,rgba(14,30,46,0.92)_100%)] p-5 text-white shadow-[0_22px_48px_rgba(2,6,23,0.28)] ">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-inverse-muted-foreground">
                  {t('agent.home.hero.controlDeck')}
                </div>
                <div className="mt-1 text-lg font-medium">{t('agent.home.hero.controlDeckTitle')}</div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="border-transparent text-white hover:bg-inverse-panel"
                disabled={isRefreshing}
                onClick={onRefresh}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-[var(--radius-lg)] border border-inverse-border bg-inverse-panel p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-inverse-muted-foreground">{t('agent.home.hero.publishing')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.publishedAgents)}</div>
                  </div>
                  <Bot className="h-5 w-5 text-brand-blue-300" />
                </div>
                <div className="mt-2 text-sm text-inverse-muted-foreground">{t('agent.home.hero.publishingShort')}</div>
              </div>

              <div className="rounded-[var(--radius-lg)] border border-inverse-border bg-inverse-panel p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-inverse-muted-foreground">{t('agent.home.hero.retrieval')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.knowledgeCount)}</div>
                  </div>
                  <Database className="h-5 w-5 text-warning-foreground" />
                </div>
                <div className="mt-2 text-sm text-inverse-muted-foreground">{t('agent.home.hero.retrievalShort')}</div>
              </div>

              <div className="rounded-[var(--radius-lg)] border border-inverse-border bg-inverse-panel p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-inverse-muted-foreground">{t('agent.home.hero.execution')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.runCount)}</div>
                  </div>
                  <Waypoints className="h-5 w-5 text-brand-teal-300" />
                </div>
                <div className="mt-2 text-sm text-inverse-muted-foreground">{t('agent.home.hero.executionShort')}</div>
              </div>

              <div className="rounded-[var(--radius-lg)] border border-inverse-border bg-inverse-panel p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-inverse-muted-foreground">{t('agent.home.hero.totalTokens')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatCompact(totalTokens)}</div>
                  </div>
                  <Activity className="h-5 w-5 text-primary" />
                </div>
                <div className="mt-2 text-sm text-inverse-muted-foreground">{t('agent.home.hero.tokenShort')}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
