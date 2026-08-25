import { Bot, Database, ShieldAlert } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import type { Agent } from '@/services/agent-service'
import type { KnowledgeBase } from '@/services/knowledge-service'
import type { Task } from '@/services/task-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

import { useHomeFormatters } from '../hooks/use-home-formatters'
import type { DashboardSummary } from '../hooks/use-home-dashboard'
import { FocusDecisionLane } from './focus-decision-lane'

type FocusPanelProps = {
  summary: DashboardSummary
  agents: Agent[]
  tasks: Task[]
  knowledgeBases: KnowledgeBase[]
  isLoading: boolean
}

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

export function FocusPanel({ summary, agents, tasks, knowledgeBases, isLoading }: FocusPanelProps) {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { formatNumber } = useHomeFormatters()

  const publishRate = summary.agentCount > 0 ? Math.round((summary.publishedAgents / summary.agentCount) * 100) : 0
  const docsPerKnowledge = summary.knowledgeCount > 0 ? Math.round(summary.totalDocuments / summary.knowledgeCount) : 0

  const statusKey =
    summary.failedRunCount > 0 || summary.attentionTaskCount > 2
      ? 'critical'
      : summary.activeTaskCount > 0 || summary.draftAgents > 0
        ? 'watch'
        : 'stable'

  const statusClassName =
    statusKey === 'critical'
      ? 'border-danger/20 bg-danger/12 text-danger-foreground'
      : statusKey === 'watch'
        ? 'border-warning/20 bg-warning/12 text-warning-foreground'
        : 'border-success/20 bg-success/12 text-success-foreground'

  const taskItems = isLoading
    ? [
        {
          primary: t('agent.home.focus.tasksLoading'),
          secondary: '...',
        },
      ]
    : tasks.length > 0
      ? tasks.slice(0, 2).map((task) => ({
          primary: task.task_type,
          secondary: t('agent.home.focus.updatedAt', { timestamp: formatTimestamp(task.updated_at) }),
          badge: task.status,
          badgeClassName:
            task.status === 'failed'
              ? 'border-danger/20 bg-danger/12 text-danger-foreground'
              : task.status === 'waiting_input' || task.status === 'waiting_approval'
                ? 'border-primary/20 bg-primary/12 text-primary'
                : 'border-border bg-muted text-muted-foreground dark:bg-panel dark:text-foreground',
        }))
      : [
          {
            primary: t('agent.home.focus.tasksEmpty'),
            secondary: t('agent.home.focus.laneTaskHint'),
          },
        ]

  const agentItems =
    agents.length > 0
      ? agents.slice(0, 2).map((agent) => ({
          primary: agent.name,
          secondary: agent.description || t('agent.home.focus.noDescription'),
          badge: agent.published_version_id ? t('agent.home.focus.publishedShort') : t('agent.home.focus.draftShort'),
          badgeClassName: agent.published_version_id
            ? 'border-success/20 bg-success/12 text-success-foreground'
            : 'border-border bg-muted text-muted-foreground dark:bg-panel dark:text-foreground',
        }))
      : [
          {
            primary: t('agent.home.focus.noAgents'),
            secondary: t('agent.home.focus.laneAgentHint'),
          },
        ]

  const knowledgeItems =
    knowledgeBases.length > 0
      ? knowledgeBases.slice(0, 2).map((base) => ({
          primary: base.name,
          secondary: `${t('agent.home.focus.docs', { count: formatNumber(base.doc_count) })} · ${t('agent.home.focus.chunks', { count: formatNumber(base.chunk_count) })} · ${formatTimestamp(base.last_ingested_at)}`,
          badge: base.status,
          badgeClassName: 'border-warning/20 bg-warning/12 text-warning-foreground',
        }))
      : [
          {
            primary: t('agent.home.focus.noKnowledge'),
            secondary: t('agent.home.focus.laneKnowledgeHint'),
          },
        ]

  return (
    <Card className="overflow-hidden">
      <CardHeader className="space-y-3 border-b border-border/70">
        <div className="text-[11px] font-medium uppercase tracking-[0.28em] text-muted-foreground">
          {t('agent.home.focus.eyebrow')}
        </div>
        <CardTitle>{t('agent.home.focus.title')}</CardTitle>
        <CardDescription>{t('agent.home.focus.description')}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <section className="rounded-[var(--radius-xl)] border border-inverse-border bg-[linear-gradient(135deg,rgba(16,24,38,0.96)_0%,rgba(15,44,68,0.92)_100%)] p-4 text-white">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-[11px] font-medium uppercase tracking-[0.24em] text-inverse-muted-foreground">
                {t('agent.home.focus.postureEyebrow')}
              </div>
              <div className="mt-2 text-lg font-semibold">{t('agent.home.focus.postureTitle')}</div>
              <div className="mt-1 text-sm text-inverse-muted-foreground">{t('agent.home.focus.postureDescription')}</div>
            </div>
            <Badge className={statusClassName}>{t(`agent.home.focus.status.${statusKey}` as const)}</Badge>
          </div>

          <div className="mt-4 grid gap-px overflow-hidden rounded-[24px] border border-white/10 bg-white/10 sm:grid-cols-3">
            <div className="bg-inverse/18 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-inverse-muted-foreground">
                {t('agent.home.focus.summaryAttention')}
              </div>
              <div className="mt-2 text-2xl font-semibold">{formatNumber(summary.attentionTaskCount)}</div>
            </div>
            <div className="bg-inverse/18 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-inverse-muted-foreground">
                {t('agent.home.focus.posturePublish')}
              </div>
              <div className="mt-2 text-2xl font-semibold">{formatNumber(publishRate)}%</div>
            </div>
            <div className="bg-inverse/18 px-4 py-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-inverse-muted-foreground">
                {t('agent.home.focus.postureKnowledge')}
              </div>
              <div className="mt-2 text-2xl font-semibold">{formatNumber(docsPerKnowledge)}</div>
            </div>
          </div>
        </section>

        <div className="grid gap-4">
          <FocusDecisionLane
            title={t('agent.home.focus.tasksTitle')}
            metric={formatNumber(summary.attentionTaskCount)}
            actionLabel={t('agent.home.focus.openTasks')}
            icon={ShieldAlert}
            iconClassName="text-danger-foreground"
            items={taskItems}
            onAction={() => navigate('/tasks')}
          />

          <FocusDecisionLane
            title={t('agent.home.focus.releaseTitle')}
            metric={`${formatNumber(summary.draftAgents)} / ${formatNumber(summary.agentCount)}`}
            actionLabel={t('agent.home.focus.openAgents')}
            icon={Bot}
            iconClassName="text-primary"
            items={agentItems}
            onAction={() => navigate('/agents')}
          />

          <FocusDecisionLane
            title={t('agent.home.focus.knowledgeTitle')}
            metric={formatNumber(summary.knowledgeCount)}
            actionLabel={t('agent.home.focus.openKnowledge')}
            icon={Database}
            iconClassName="text-warning-foreground"
            items={knowledgeItems}
            onAction={() => navigate('/knowledge')}
          />
        </div>
      </CardContent>
    </Card>
  )
}

