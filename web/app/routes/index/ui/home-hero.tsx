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
  onRefresh: () => void
}

export function HomeHero({ summary, isRefreshing, partialFailure, onRefresh }: HomeHeroProps) {
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
    },
    {
      label: t('agent.home.hero.signalKnowledge'),
      value: formatCompact(summary.totalDocuments),
      meta: `${formatCompact(summary.totalChunks)} ${t('agent.home.hero.chunksUnit')}`,
      icon: Database,
    },
    {
      label: t('agent.home.hero.signalRuntime'),
      value: formatNumber(summary.activeTaskCount),
      meta: `${formatNumber(summary.failedRunCount)} ${t('agent.home.hero.failedRuns')}`,
      icon: Waypoints,
    },
    {
      label: t('agent.home.hero.totalTokens'),
      value: formatCompact(totalTokens),
      meta: t('agent.home.hero.runtimeMs', { count: formatCompact(summary.runtimeMs) }),
      icon: Activity,
    },
  ]

  return (
    <section className="animate-in fade-in slide-in-from-top-2 duration-500">
      <div className="relative overflow-hidden rounded-[38px] border border-slate-200/70 bg-[linear-gradient(135deg,rgba(8,15,30,0.99)_0%,rgba(13,46,73,0.96)_42%,rgba(20,92,128,0.9)_100%)] p-5 text-white md:p-6 xl:p-7">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_16%_18%,rgba(56,189,248,0.24),transparent_30%),radial-gradient(circle_at_82%_12%,rgba(251,191,36,0.14),transparent_20%),linear-gradient(rgba(255,255,255,0.045)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.045)_1px,transparent_1px)] [background-size:auto,auto,28px_28px,28px_28px]" />

        <div className="relative grid gap-3 border-b border-white/10 pb-4 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
          <div className="flex flex-wrap items-center gap-3">
            <Badge className="border-white/10 bg-white/10 text-white hover:bg-white/10">
              {t('agent.home.hero.badge')}
            </Badge>
            <Badge className="border-white/10 bg-cyan-400/15 text-cyan-100 hover:bg-cyan-400/15">
              {t('agent.home.hero.mode')}
            </Badge>
            <span className="text-[11px] uppercase tracking-[0.24em] text-cyan-100/70">
              {t('agent.home.hero.commandRail')}
            </span>
            {partialFailure && (
              <Badge className="border-amber-300/20 bg-amber-300/15 text-amber-100 hover:bg-amber-300/15">
                <AlertTriangle className="mr-1 h-3.5 w-3.5" />
                {t('agent.home.hero.partialFailure')}
              </Badge>
            )}
          </div>

          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            {railMetrics.map((metric) => (
              <div
                key={metric.label}
                className="rounded-2xl border border-white/10 bg-white/[0.06] px-3 py-2.5"
              >
                <div className="text-[10px] uppercase tracking-[0.18em] text-slate-300">{metric.label}</div>
                <div className="mt-1 text-base font-semibold">{metric.value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mt-5 grid gap-5 xl:grid-cols-[minmax(0,1.16fr)_390px] xl:items-stretch">
          <div className="rounded-[30px] border border-white/10 bg-white/[0.05] p-5">
            <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-start">
              <div className="space-y-4">
                <div className="max-w-3xl space-y-3">
                  <h1 className="max-w-4xl text-3xl font-semibold tracking-tight text-white md:text-5xl">
                    {t('agent.home.hero.title')}
                  </h1>
                  <p className="max-w-2xl text-sm leading-7 text-slate-200/92 md:text-[15px]">
                    {t('agent.home.hero.description')}
                  </p>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button
                    className="bg-white text-slate-950 hover:bg-slate-100"
                    onClick={() => navigate('/agents')}
                  >
                    <Bot className="mr-2 h-4 w-4" />
                    {t('agent.home.hero.ctaAgents')}
                  </Button>
                  <Button
                    variant="secondary"
                    className="border-white/10 bg-white/10 text-white hover:bg-white/[0.16]"
                    onClick={() => navigate('/workflow')}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {t('agent.home.hero.ctaWorkflow')}
                  </Button>
                  <Button
                    variant="ghost"
                    className="border border-white/10 text-white hover:bg-white/10"
                    onClick={() => navigate('/observability/runs')}
                  >
                    {t('agent.home.hero.ctaRuns')}
                    <ArrowRight className="ml-2 h-4 w-4" />
                  </Button>
                </div>
              </div>

              <div className="grid gap-2.5 text-xs text-slate-300 sm:grid-cols-3 lg:grid-cols-1">
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-2">
                  {t('agent.home.hero.runtimeMs', { count: formatCompact(summary.runtimeMs) })}
                </span>
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-2">
                  {t('agent.home.hero.attentionTasks', { count: formatNumber(summary.attentionTaskCount) })}
                </span>
                <span className="rounded-full border border-white/10 bg-white/10 px-3 py-2">
                  {t('agent.home.hero.promptTokens', {
                    prompt: formatCompact(summary.promptTokens),
                    completion: formatCompact(summary.completionTokens),
                  })}
                </span>
              </div>
            </div>

            <div className="mt-5">
              <div className="mb-3 text-[11px] uppercase tracking-[0.24em] text-slate-300">
                {t('agent.home.hero.signalStrip')}
              </div>
              <div className="grid gap-px overflow-hidden rounded-[26px] border border-white/10 bg-white/10 sm:grid-cols-2 lg:grid-cols-4">
                {signalPanels.map((panel) => {
                  const Icon = panel.icon

                  return (
                    <div key={panel.label} className="bg-slate-950/18 px-4 py-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="text-[10px] uppercase tracking-[0.2em] text-slate-300">
                            {panel.label}
                          </div>
                          <div className="mt-2 text-2xl font-semibold text-white">{panel.value}</div>
                        </div>
                        <div className="rounded-2xl border border-white/10 bg-white/8 p-2.5">
                          <Icon className="h-4 w-4 text-cyan-100" />
                        </div>
                      </div>
                      <div className="mt-3 text-sm text-slate-300">{panel.meta}</div>
                    </div>
                  )
                })}
              </div>
            </div>
          </div>

          <div className="rounded-[30px] border border-white/10 bg-slate-950/22 p-5">
            <div className="mb-4 flex items-center justify-between">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-cyan-100/70">
                  {t('agent.home.hero.controlDeck')}
                </div>
                <div className="mt-1 text-lg font-medium">{t('agent.home.hero.controlDeckTitle')}</div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="text-white hover:bg-white/10"
                disabled={isRefreshing}
                onClick={onRefresh}
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              </Button>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="rounded-2xl border border-white/10 bg-white/[0.08] p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-300">{t('agent.home.hero.publishing')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.publishedAgents)}</div>
                  </div>
                  <Bot className="h-5 w-5 text-cyan-200" />
                </div>
                <div className="mt-2 text-sm text-slate-300">{t('agent.home.hero.publishingShort')}</div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.08] p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-300">{t('agent.home.hero.retrieval')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.knowledgeCount)}</div>
                  </div>
                  <Database className="h-5 w-5 text-amber-200" />
                </div>
                <div className="mt-2 text-sm text-slate-300">{t('agent.home.hero.retrievalShort')}</div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.08] p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-300">{t('agent.home.hero.execution')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.runCount)}</div>
                  </div>
                  <Waypoints className="h-5 w-5 text-emerald-200" />
                </div>
                <div className="mt-2 text-sm text-slate-300">{t('agent.home.hero.executionShort')}</div>
              </div>

              <div className="rounded-2xl border border-white/10 bg-white/[0.08] p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs uppercase tracking-[0.2em] text-slate-300">{t('agent.home.hero.totalTokens')}</div>
                    <div className="mt-2 text-2xl font-semibold">{formatCompact(totalTokens)}</div>
                  </div>
                  <Activity className="h-5 w-5 text-cyan-200" />
                </div>
                <div className="mt-2 text-sm text-slate-300">{t('agent.home.hero.tokenShort')}</div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

