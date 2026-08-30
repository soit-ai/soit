import { useTranslation } from '@/i18n'
import { useQuery } from '@/hooks/use-query'
import { getAgentWorkbench, listDraftsAwaitingReview } from '@/services/agent-service'
import { getKnowledgeWorkbench } from '@/services/knowledge-service'
import { listApiKeys } from '@/services/api-key-service'
import {
  listPins,
  listSavedViews,
  listWorkspaceMembers,
  listWorkspaceResourceGrants,
} from '@/services/identity-service'
import { listApprovals, listDeadLetters } from '@/services/observe-service'
import { listPlugins } from '@/services/plugin-service'
import { getModelWorkbenchOverview } from '@/services/provider-service'
import { getRunWindowSummary, listRunAudits, listRunSteps, listRuns } from '@/services/run-service'
import { getEgressBlockSummary, getPolicyBundle } from '@/services/security-service'
import { listSchedules } from '@/services/schedule-service'
import { listSecrets } from '@/services/secrets-service'
import { getTaskWorkbench } from '@/services/task-service'
import { listThreads } from '@/services/thread-service'
import { getWorkflowWorkbench } from '@/services/workflow-service'

import { catColor, compactNumber, money, percent, relativeTime } from '../adapters/palette'
import { useSubjectNames } from '../adapters/subject-names'
import type { ConsoleCountKey, ConsolePillar, PanelSlot } from './panel-config'

/**
 * The side panel's policy figure.
 *
 * A revision number is what an operator recognises, so it wins when the live
 * policy matches a recorded one. When it does not -- a fresh install, or a
 * policy changed outside the API -- the content identifier is shown instead,
 * because that is the identifier refusals are recorded against and it can
 * still be looked up.
 */
function policyLabel(bundle?: { revision: number; bundle_id: string }): string | undefined {
  if (!bundle) return undefined
  return bundle.revision > 0 ? `r${bundle.revision}` : bundle.bundle_id.slice(3, 11)
}

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

const DAY_MS = 24 * 60 * 60 * 1000

/**
 * A total is optional the whole way down: absent means the count was not
 * answered, and the row then shows no figure at all. Rendering a zero would
 * claim a measurement the server never made.
 */
function countLabel(total?: number | null): string | undefined {
  return total == null ? undefined : compactNumber(total)
}

function spanLabel(total?: number | null): string | undefined {
  return total == null ? undefined : `${compactNumber(total)} spans`
}

/** Where a pinned object opens. Unknown kinds fall back to their pillar list. */
function pinRoute(objectType: string, objectId: string): string {
  switch (objectType) {
    case 'agent':
      return `/build/agents/${objectId}`
    case 'workflow':
      return `/build/workflows/${objectId}`
    case 'knowledge':
      return `/build/knowledge/${objectId}`
    case 'run':
      return `/observe/runs/${objectId}`
    case 'task':
      return `/execute/tasks/${objectId}`
    default:
      return '/'
  }
}

/** A saved view is its screen plus the query it kept. */
function savedViewRoute(view: { surface: string; query: string }): string {
  const base = view.surface === 'traces' ? '/observe/traces' : `/observe/${view.surface}`
  return view.query ? `${base}?${view.query}` : base
}

function windowLabel(total?: number | null): string | undefined {
  return total == null ? undefined : `${compactNumber(total)} · 24h`
}

/**
 * The largest charged currency in a window. Workspaces normally price in one
 * currency; when more than one is present the panel shows the biggest rather
 * than adding amounts that cannot be added.
 */
function primaryAmount(
  charges?: { entry_count: number; amounts: Record<string, string> },
): { amount: number; currency: string } | null {
  if (!charges?.entry_count) return null
  const rows = Object.entries(charges.amounts || {})
    .map(([currency, value]) => ({ currency, amount: Number(value) }))
    .filter((row) => Number.isFinite(row.amount))
    .sort((a, b) => b.amount - a.amount)
  return rows[0] || null
}

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

  // One call answers the whole Today group: run volume, pass rate and spend
  // over the same window, counted server-side rather than sampled.
  const today = useQuery({
    queryKey: ['console', 'panel', 'today'],
    queryFn: () =>
      getRunWindowSummary({ since: new Date(Date.now() - DAY_MS).toISOString() }),
    options: { ...SHARED, enabled: isOverview },
  })

  // Three counted reads. Each asks for one row and the total, so the figure
  // costs a count query rather than a page of rows nobody renders.
  const runCount = useQuery({
    queryKey: ['console', 'panel', 'run-count'],
    queryFn: () => listRuns({ page_size: 1, with_total: true }),
    options: { ...SHARED, enabled: isObserve },
  })
  const spanCount = useQuery({
    queryKey: ['console', 'panel', 'span-count'],
    queryFn: () => listRunSteps({ page_size: 1, with_total: true }),
    options: { ...SHARED, enabled: isObserve },
  })
  const egressBlocks = useQuery({
    queryKey: ['console', 'counts', 'egress-blocks'],
    queryFn: () =>
      getEgressBlockSummary({ since: new Date(Date.now() - DAY_MS).toISOString() }),
    options: { ...SHARED, enabled: isGovern },
  })
  // The identifier of the policy in force. Derived from the policy content,
  // so it is the same identifier recorded on every request the policy refuses.
  const policyBundle = useQuery({
    queryKey: ['console', 'counts', 'policy-bundle'],
    queryFn: () => getPolicyBundle(),
    options: { ...SHARED, enabled: isGovern },
  })
  const draftReviews = useQuery({
    queryKey: ['console', 'panel', 'draft-reviews'],
    queryFn: () => listDraftsAwaitingReview({ limit: 5 }, { suppressErrorToast: true }),
    options: { ...SHARED, enabled: isBuild },
  })
  // Personal shortcuts. Both are per-user and per-workspace, so they follow
  // the same cache rules as the rest of the panel.
  const savedViews = useQuery({
    queryKey: ['console', 'panel', 'saved-views'],
    queryFn: () => listSavedViews(undefined, { suppressErrorToast: true }),
    options: { ...SHARED, enabled: isObserve },
  })
  const pins = useQuery({
    queryKey: ['console', 'panel', 'pins'],
    queryFn: () => listPins({ suppressErrorToast: true }),
    options: { ...SHARED, enabled: isOverview },
  })

  const schedules = useQuery({
    queryKey: ['console', 'counts', 'schedules'],
    queryFn: () => listSchedules({ limit: 100 }, { suppressErrorToast: true }),
    options: { ...SHARED, enabled: isExecute },
  })
  const grants = useQuery({
    queryKey: ['console', 'counts', 'grants'],
    queryFn: () => listWorkspaceResourceGrants({ limit: 500 }),
    options: { ...SHARED, enabled: isGovern },
  })
  const auditCount = useQuery({
    queryKey: ['console', 'panel', 'audit-count'],
    queryFn: () =>
      listRunAudits({
        since: new Date(Date.now() - DAY_MS).toISOString(),
        page_size: 1,
        with_total: true,
      }),
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
    schedules: schedules.data?.length,
    events: deadLetters.data?.length,
    approvals: isGovern ? approvals.data?.items?.length : undefined,
    secrets: secrets.data?.length,
    threads: threads.data?.items?.length,
    team: members.data?.length,
    apiKeys: apiKeys.data?.items?.length,
    runs: countLabel(runCount.data?.total),
    traces: spanLabel(spanCount.data?.total),
    audit: windowLabel(auditCount.data?.total),
    access: grants.data?.length,
    policies: policyLabel(policyBundle.data),
  }

  const groups: Partial<Record<PanelSlot, PanelRow[]>> = {}

  if (isOverview) {
    // Every row drops out when its figure is missing rather than showing a
    // zero, so an unreachable summary leaves the group empty instead of
    // reporting a quiet day.
    const summary = today.data
    const spend = primaryAmount(summary?.charges)
    groups.today = compact([
      summary != null && {
        kind: 'stat',
        id: 'runs',
        label: t('console.shell.todayStats.runs'),
        value: compactNumber(summary.total),
        to: '/observe/runs',
      },
      summary?.pass_rate != null && {
        kind: 'stat',
        id: 'pass',
        label: t('console.shell.todayStats.passRate'),
        value: percent(summary.pass_rate),
        to: '/observe/runs',
      },
      spend != null && {
        kind: 'stat',
        id: 'spend',
        label: t('console.shell.todayStats.spend'),
        value: money(spend.amount, spend.currency),
        to: '/observe/runs',
      },
    ])
    groups.pinned = (pins.data || []).slice(0, 5).map((row) => ({
      kind: 'mini' as const,
      id: row.id,
      label: row.label || row.object_id,
      meta: row.object_type,
      note: relativeTime(row.created_at),
      to: pinRoute(row.object_type, row.object_id),
      at: row.created_at,
    }))
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

    // Only drafts somebody was actually asked to look at. A draft nobody
    // requested review on is work in progress, not a queue entry.
    // Defensive: the panel wraps every screen, so a service answering with a
    // shape this does not expect must leave a group empty, never take the
    // console down.
    groups.draftReviews = (Array.isArray(draftReviews.data) ? draftReviews.data : []).map((row) => ({
      kind: 'note' as const,
      id: row.version_id,
      label: `${row.agent_name || row.agent_id} v${row.version}${
        row.review_note ? ` · ${row.review_note}` : ''
      }`,
      tone: row.review_status === 'changes_requested' ? ('bad' as const) : ('warn' as const),
      value: row.review_requested_at ? relativeTime(row.review_requested_at) : undefined,
      to: `/build/agents/${row.agent_id}`,
    }))
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

    // Soonest first, and only what is actually going to fire: a paused
    // schedule has no next occurrence to be next up for.
    groups.nextUp = (schedules.data || [])
      .filter((row) => row.enabled && row.next_fire_at)
      .sort((a, b) => String(a.next_fire_at).localeCompare(String(b.next_fire_at)))
      .slice(0, 2)
      .map((row) => ({
        kind: 'mini',
        id: row.id,
        label: row.name,
        meta: relativeTime(row.next_fire_at),
        note: `${row.target_id} · ${row.cron}`,
        to: '/execute/schedules',
      }))
  }

  if (isObserve) {
    // A saved view carries no count: its query belongs to the screen, and
    // asking the server to count each one would be a request per row for a
    // figure the prototype only ever used as decoration.
    groups.savedViews = (savedViews.data || []).slice(0, 6).map((row) => ({
      kind: 'stat' as const,
      id: row.id,
      label: row.name,
      value: row.is_default ? t('console.shell.defaultView') : '',
      to: savedViewRoute(row),
    }))

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
      // Only shown once something was actually refused: a "0 blocks" row would
      // take a slot to say nothing happened.
      !!egressBlocks.data?.total && {
        kind: 'note' as const,
        id: 'egress',
        label: t('console.shell.egressBlocks', { count: egressBlocks.data.total }),
        tone: 'bad' as const,
        value: t('console.shell.egressSubjects', {
          count: egressBlocks.data.subjects,
        }),
        to: '/govern/policies',
      },
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
