import { useTranslation } from '@/i18n'
import { useQuery } from '@/hooks/use-query'
import { getAgentWorkbench } from '@/services/agent-service'
import { getKnowledgeWorkbench } from '@/services/knowledge-service'
import { listApiKeys } from '@/services/api-key-service'
import { listWorkspaceMembers } from '@/services/identity-service'
import { listApprovals, listDeadLetters } from '@/services/observe-service'
import { listPlugins } from '@/services/plugin-service'
import { getModelWorkbenchOverview } from '@/services/provider-service'
import { listRunAudits, listRuns } from '@/services/run-service'
import { listSecrets } from '@/services/secrets-service'
import { getTaskWorkbench } from '@/services/task-service'
import { listThreads } from '@/services/thread-service'
import { getWorkflowWorkbench } from '@/services/workflow-service'

import { catColor, relativeTime } from '../adapters/palette'
import { useSubjectNames } from '../adapters/subject-names'
import { mockSchedules } from '../mocks/execute'
import {
  mockDraftReviews,
  mockGovernAttention,
  mockPanelCounts,
  mockPinned,
  mockSavedViews,
  mockTodayStats,
} from '../mocks/panel'
import type { ConsoleCountKey, ConsolePillar, PanelSlot } from './panel-config'

/**
 * The prototype's side panel is not just links: each carries a live figure, and
 * every pillar adds two or three grouped lists underneath. Fetching all of that
 * on every render would be a dozen requests per navigation, so each pillar asks
 * only for its own, cached long enough that moving between screens inside a
 * pillar does not refetch.
 *
 * Anything that fails to load is simply absent — a side-panel figure is never
 * worth an error state, and a zero would read as a real measurement.
 */
const STALE_MS = 60_000

const SHARED = { retry: false, refetchOnWindowFocus: false, staleTime: STALE_MS } as const

/** A `.sl` row whose `.ct` holds a formatted figure rather than a bare count. */
export interface PanelStatRow {
  kind: 'stat'
  id: string
  label: string
  value: string
  to: string
}

/** A `.sub-mini` row: what it is, when it moved, one line of context. */
export interface PanelMiniRow {
  kind: 'mini'
  id: string
  label: string
  /** The right-aligned mono fragment inside the row's bold line. */
  meta: string
  note: string
  to: string
  at?: string | null
}

/** A `.sub-note` row: a toned dot, a sentence, an optional figure. */
export interface PanelNoteRow {
  kind: 'note'
  id: string
  label: string
  tone: 'primary' | 'warn' | 'bad'
  value?: string
  to: string
  /** Replaces the trailing figure with the prototype's pulsing `.livedot`. */
  live?: boolean
}

/** An `.idm` row: an identity dot in the category ramp, then a count. */
export interface PanelIdentityRow {
  kind: 'idm'
  id: string
  label: string
  color: string
  value?: string
  to: string
}

export type PanelRow = PanelStatRow | PanelMiniRow | PanelNoteRow | PanelIdentityRow

export interface ConsolePanelData {
  /** A figure is a plain count or a formatted fragment ("41k spans", "v08.27-2"). */
  counts: Partial<Record<ConsoleCountKey, number | string>>
  groups: Partial<Record<PanelSlot, PanelRow[]>>
}

/** Drops the rows a missing figure switched off, keeping the union intact. */
function compact(rows: Array<PanelRow | false | undefined>): PanelRow[] {
  return rows.filter((row): row is PanelRow => !!row)
}

function newestFirst<T extends { at?: string | null }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => String(b.at || '').localeCompare(String(a.at || '')))
}

export function useConsolePanelData(
  pillar: ConsolePillar,
  workspaceId = '',
): ConsolePanelData {
  const { t } = useTranslation()
  const subjectName = useSubjectNames()
  const isOverview = pillar === 'overview'
  const isBuild = pillar === 'build'
  const isExecute = pillar === 'execute'
  const isGovern = pillar === 'govern'
  const isChat = pillar === 'chat'
  const isObserve = pillar === 'observe'
  const isSettings = pillar === 'settings'

  const agents = useQuery({
    queryKey: ['console', 'counts', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: 20 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const workflows = useQuery({
    queryKey: ['console', 'counts', 'workflows'],
    queryFn: () => getWorkflowWorkbench({ page_size: 20 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const knowledge = useQuery({
    queryKey: ['console', 'counts', 'knowledge'],
    queryFn: () => getKnowledgeWorkbench({ page_size: 20 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const plugins = useQuery({
    queryKey: ['console', 'counts', 'plugins'],
    queryFn: () => listPlugins({ page_size: 100 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const models = useQuery({
    queryKey: ['console', 'counts', 'models'],
    queryFn: () => getModelWorkbenchOverview(),
    options: { ...SHARED, enabled: isBuild },
  })

  const tasks = useQuery({
    queryKey: ['console', 'counts', 'tasks'],
    queryFn: () => getTaskWorkbench({ page_size: 1 }),
    options: { ...SHARED, enabled: isExecute },
  })
  const deadLetters = useQuery({
    queryKey: ['console', 'counts', 'dead-letters'],
    queryFn: () => listDeadLetters({ limit: 100 }),
    options: { ...SHARED, enabled: isExecute },
  })

  const approvals = useQuery({
    queryKey: ['console', 'counts', 'approvals'],
    queryFn: () => listApprovals({ status: 'pending', page_size: 100 }),
    options: { ...SHARED, enabled: isGovern || isExecute },
  })
  const secrets = useQuery({
    queryKey: ['console', 'counts', 'secrets'],
    queryFn: () => listSecrets({ limit: 200 }),
    options: { ...SHARED, enabled: isGovern },
  })
  const audits = useQuery({
    queryKey: ['console', 'panel', 'audits'],
    queryFn: () => listRunAudits({ page_size: 2 }),
    options: { ...SHARED, enabled: isGovern },
  })

  // Team and API keys have real services, so they are read rather than faked.
  const members = useQuery({
    queryKey: ['console', 'counts', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: { ...SHARED, enabled: isSettings && !!workspaceId },
  })
  const apiKeys = useQuery({
    queryKey: ['console', 'counts', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: { ...SHARED, enabled: isSettings },
  })

  const threads = useQuery({
    queryKey: ['console', 'counts', 'threads'],
    queryFn: () => listThreads({ page_size: 100 }),
    options: { ...SHARED, enabled: isChat },
  })

  // The panel's "Live" group is a running-runs list, so it must not be served
  // from the minute-long cache the rest of the panel uses.
  const liveRuns = useQuery({
    queryKey: ['console', 'panel', 'live-runs'],
    queryFn: () => listRuns({ status: 'running', page_size: 3 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
      staleTime: 10_000,
      enabled: isObserve,
    },
  })

  // Every read below is optional the whole way down. The response types promise
  // a `summary` and an `items`, but a real deployment can answer with a partial
  // body, and the side panel wraps every screen — a missing field here would
  // take the entire console down rather than drop one badge.
  const counts: Partial<Record<ConsoleCountKey, number | string>> = {
    agents: agents.data?.summary?.total_agents,
    workflows: workflows.data?.summary?.total_workflows,
    knowledge: knowledge.data?.summary?.total_knowledge_bases,
    plugins: plugins.data?.items?.filter((row) => row.installed).length,
    models: models.data?.summary?.total_models,
    tasks: tasks.data?.summary?.total_tasks,
    // No schedule service exists; the figure matches the fixtures that page shows.
    schedules: isExecute ? mockSchedules.length : undefined,
    events: deadLetters.data?.length,
    approvals: isGovern ? approvals.data?.items?.length : undefined,
    secrets: secrets.data?.length,
    threads: threads.data?.items?.length,
    team: members.data?.length,
    apiKeys: apiKeys.data?.items?.length,
    // Fixtures, not measurements: these five have no endpoint that can answer
    // them. Each is a fallback, so shipping the API retires it on its own.
    runs: isObserve ? mockPanelCounts.runs : undefined,
    traces: isObserve ? mockPanelCounts.traces : undefined,
    policies: isGovern ? mockPanelCounts.policies : undefined,
    audit: isGovern ? mockPanelCounts.audit : undefined,
    access: isGovern ? mockPanelCounts.access : undefined,
  }

  const groups: Partial<Record<PanelSlot, PanelRow[]>> = {}

  if (isOverview) {
    groups.today = mockTodayStats.map((row) => ({ kind: 'stat' as const, ...row }))
    groups.pinned = mockPinned.map((row) => ({ kind: 'mini' as const, ...row }))
  }

  if (isChat) {
    const items = threads.data?.items || []
    groups.chatActive = items.slice(0, 3).map((row) => ({
      kind: 'mini',
      id: row.id,
      label: row.title || t('console.shell.untitledThread'),
      meta: relativeTime(row.updated_at || row.created_at),
      note: row.summary || row.status,
      // A thread is addressed by agent and id; one without an agent can only
      // be reached through the list.
      to: row.agent_id ? `/chat/${row.agent_id}/${row.id}` : '/chat',
    }))

    // One row per agent that owns a thread, ordered by how many it holds.
    const byAgent = new Map<string, number>()
    for (const row of items) {
      if (row.agent_id) byAgent.set(row.agent_id, (byAgent.get(row.agent_id) || 0) + 1)
    }
    groups.chatByAgent = [...byAgent.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, 4)
      .map(([agentId, total]) => ({
        kind: 'idm',
        id: agentId,
        label: agentId,
        color: catColor(agentId),
        value: String(total),
        to: `/chat/${agentId}`,
      }))

    groups.guarantee = [
      {
        kind: 'note',
        id: 'governed',
        label: t('console.shell.guaranteeNote'),
        tone: 'primary',
        to: '/observe/runs',
      },
    ]
  }

  if (isBuild) {
    groups.recents = newestFirst([
      ...(agents.data?.items || []).map((row) => ({
        id: `agent:${row.id}`,
        label: row.name,
        meta: 'agent',
        note: row.description || row.status,
        to: `/build/agents/${row.id}`,
        at: row.updated_at,
      })),
      ...(workflows.data?.items || []).map((row) => ({
        id: `workflow:${row.id}`,
        label: row.name,
        meta: 'wf',
        note: row.summary || row.description || row.status,
        to: `/build/workflows/${row.id}`,
        at: row.updated_at,
      })),
      ...(knowledge.data?.items || []).map((row) => ({
        id: `knowledge:${row.id}`,
        label: row.name,
        meta: 'kb',
        note: row.description || `${row.document_count} documents`,
        to: `/build/knowledge/${row.id}`,
        at: row.updated_at,
      })),
    ])
      .slice(0, 3)
      .map((row) => ({ kind: 'mini' as const, ...row }))

    groups.draftReviews = mockDraftReviews.map((row) => ({ kind: 'note' as const, ...row }))
  }

  if (isExecute) {
    const summary = tasks.data?.summary
    groups.queue = compact([
      summary?.running != null && {
        kind: 'note' as const,
        id: 'running',
        label: t('console.shell.processing'),
        tone: 'primary' as const,
        value: String(summary.running),
        to: '/execute/tasks',
      },
      summary?.waiting_approval != null && {
        kind: 'note' as const,
        id: 'awaiting',
        label: t('console.shell.awaitingApproval'),
        tone: 'warn' as const,
        value: String(summary.waiting_approval),
        to: '/govern/approvals',
      },
      summary?.failed != null && {
        kind: 'note' as const,
        id: 'failed',
        label: t('console.shell.failed'),
        tone: 'bad' as const,
        value: String(summary.failed),
        to: '/execute/tasks',
      },
    ])

    // The schedules page runs on the same fixtures; the panel must agree with it.
    groups.nextUp = mockSchedules
      .filter((row) => row.enabled)
      .slice(0, 2)
      .map((row) => ({
        kind: 'mini',
        id: row.id,
        label: row.name,
        meta: row.next_fire,
        note: `${row.target} · ${row.cron}`,
        to: '/execute/schedules',
      }))
  }

  if (isObserve) {
    groups.savedViews = mockSavedViews.map((row) => ({ kind: 'stat' as const, ...row }))

    const running = liveRuns.data?.items || []
    groups.live = compact([
      ...running.slice(0, 1).map((row) => ({
        kind: 'mini' as const,
        id: row.id,
        label: row.id,
        meta: relativeTime(row.started_at),
        note: [subjectName(row.subject_id), row.mode].filter(Boolean).join(' · ') || row.status,
        to: `/observe/runs/${row.id}`,
      })),
      running.length > 0 && {
        kind: 'note' as const,
        id: 'in-flight',
        label: t('console.shell.runsInFlight', { count: running.length }),
        tone: 'primary' as const,
        to: '/observe/runs?status=running',
        live: true,
      },
    ])
  }

  if (isGovern) {
    // The prototype puts the number in the sentence and the age of the oldest
    // request in the figure — that pairing is what makes the row actionable.
    const pendingRows = approvals.data?.items || []
    const oldest = pendingRows
      .map((row) => row.created_at)
      .filter(Boolean)
      .sort()[0]
    groups.governAttention = compact([
      pendingRows.length > 0 && {
        kind: 'note' as const,
        id: 'approvals',
        label: t('console.shell.approvalsPending', { count: pendingRows.length }),
        tone: 'warn' as const,
        value: oldest ? relativeTime(oldest) : undefined,
        to: '/govern/approvals',
      },
      ...mockGovernAttention.map((row) => ({ kind: 'note' as const, ...row })),
    ])

    groups.governRecent = (audits.data?.items || []).slice(0, 2).map((row) => ({
      kind: 'mini',
      id: row.audit_id || `${row.run_id}:${row.step_id}`,
      label: row.gateway_type || row.step_type,
      meta: relativeTime(row.timestamp),
      note: row.preview || row.outcome || row.step_type,
      to: `/observe/runs/${row.run_id}`,
    }))
  }

  return { counts, groups }
}
