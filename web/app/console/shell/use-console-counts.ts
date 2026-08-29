import { useQuery } from '@/hooks/use-query'
import { getAgentWorkbench } from '@/services/agent-service'
import { getKnowledgeWorkbench } from '@/services/knowledge-service'
import { listApprovals, listDeadLetters } from '@/services/observe-service'
import { listPlugins } from '@/services/plugin-service'
import { getModelWorkbenchOverview } from '@/services/provider-service'
import { listSecrets } from '@/services/secrets-service'
import { getTaskWorkbench } from '@/services/task-service'
import { listThreads } from '@/services/thread-service'
import { getWorkflowWorkbench } from '@/services/workflow-service'

import { mockSchedules } from '../mocks/execute'
import type { ConsoleCountKey, ConsolePillar } from './panel-config'

/**
 * The prototype's side panel is not just links: each carries a live figure, and
 * some pillars add a "recently edited" or attention list underneath. Fetching
 * all of that on every render would be a dozen requests per navigation, so each
 * pillar asks only for its own, cached long enough that moving between screens
 * inside a pillar does not refetch.
 *
 * Anything that fails to load is simply absent — a side-panel figure is never
 * worth an error state, and a zero would read as a real measurement.
 */
const STALE_MS = 60_000

const SHARED = { retry: false, refetchOnWindowFocus: false, staleTime: STALE_MS } as const

/** A "recently edited" row: what it is, when it moved, where it lives. */
export interface PanelRecent {
  id: string
  label: string
  kind: string
  note: string
  to: string
  at?: string | null
}

/** An attention row: a dot-toned figure worth acting on. */
export interface PanelAttention {
  id: string
  label: string
  tone: 'primary' | 'warn' | 'bad'
  count: number
  to: string
}

export interface ConsolePanelData {
  counts: Partial<Record<ConsoleCountKey, number>>
  recents: PanelRecent[]
  attention: PanelAttention[]
}

function newestFirst<T extends { at?: string | null }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => String(b.at || '').localeCompare(String(a.at || '')))
}

export function useConsolePanelData(pillar: ConsolePillar): ConsolePanelData {
  const isBuild = pillar === 'build'
  const isExecute = pillar === 'execute'
  const isGovern = pillar === 'govern'
  const isChat = pillar === 'chat'

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

  const threads = useQuery({
    queryKey: ['console', 'counts', 'threads'],
    queryFn: () => listThreads({ page_size: 100 }),
    options: { ...SHARED, enabled: isChat },
  })

  const counts: Partial<Record<ConsoleCountKey, number>> = {
    agents: agents.data?.summary.total_agents,
    workflows: workflows.data?.summary.total_workflows,
    knowledge: knowledge.data?.summary.total_knowledge_bases,
    plugins: plugins.data?.items.filter((row) => row.installed).length,
    models: models.data?.summary.total_models,
    tasks: tasks.data?.summary.total_tasks,
    // No schedule service exists; the figure matches the fixtures that page shows.
    schedules: isExecute ? mockSchedules.length : undefined,
    events: deadLetters.data?.length,
    approvals: isGovern ? approvals.data?.items.length : undefined,
    secrets: secrets.data?.length,
    threads: threads.data?.items.length,
  }

  const recents: PanelRecent[] = isBuild
    ? newestFirst([
        ...(agents.data?.items || []).map((row) => ({
          id: `agent:${row.id}`,
          label: row.name,
          kind: 'agent',
          note: row.description || row.status,
          to: `/v2/build/agents/${row.id}`,
          at: row.updated_at,
        })),
        ...(workflows.data?.items || []).map((row) => ({
          id: `workflow:${row.id}`,
          label: row.name,
          kind: 'wf',
          note: row.summary || row.description || row.status,
          to: `/v2/build/workflows/${row.id}`,
          at: row.updated_at,
        })),
        ...(knowledge.data?.items || []).map((row) => ({
          id: `knowledge:${row.id}`,
          label: row.name,
          kind: 'kb',
          note: row.description || `${row.document_count} documents`,
          to: `/v2/build/knowledge/${row.id}`,
          at: row.updated_at,
        })),
      ]).slice(0, 3)
    : []

  const taskSummary = tasks.data?.summary
  const attention: PanelAttention[] = isExecute
    ? [
        taskSummary?.running != null && {
          id: 'running',
          label: 'Processing',
          tone: 'primary' as const,
          count: taskSummary.running,
          to: '/v2/execute/tasks',
        },
        taskSummary?.waiting_approval != null && {
          id: 'awaiting',
          label: 'Awaiting approval',
          tone: 'warn' as const,
          count: taskSummary.waiting_approval,
          to: '/v2/govern/approvals',
        },
        taskSummary?.failed != null && {
          id: 'failed',
          label: 'Failed',
          tone: 'bad' as const,
          count: taskSummary.failed,
          to: '/v2/execute/tasks',
        },
      ].filter(Boolean as unknown as (value: unknown) => value is PanelAttention)
    : []

  return { counts, recents, attention }
}
