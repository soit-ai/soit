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
 * The prototype's side panel puts a live figure beside each link. Fetching all
 * of them on every render would be a dozen requests per navigation, so each
 * pillar only asks for its own, and the results are cached long enough that
 * moving between screens inside a pillar does not refetch.
 *
 * Failures resolve to `undefined`, which renders no badge — a side-panel count
 * is never worth an error state.
 */
const STALE_MS = 60_000

const SHARED = { retry: false, refetchOnWindowFocus: false, staleTime: STALE_MS } as const

export function useConsoleCounts(
  pillar: ConsolePillar,
): Partial<Record<ConsoleCountKey, number>> {
  const isBuild = pillar === 'build'
  const isExecute = pillar === 'execute'
  const isGovern = pillar === 'govern'
  const isChat = pillar === 'chat'

  const agents = useQuery({
    queryKey: ['console', 'counts', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: 1 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const workflows = useQuery({
    queryKey: ['console', 'counts', 'workflows'],
    queryFn: () => getWorkflowWorkbench({ page_size: 1 }),
    options: { ...SHARED, enabled: isBuild },
  })
  const knowledge = useQuery({
    queryKey: ['console', 'counts', 'knowledge'],
    queryFn: () => getKnowledgeWorkbench({ page_size: 1 }),
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
    options: { ...SHARED, enabled: isGovern },
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

  return {
    agents: agents.data?.summary.total_agents,
    workflows: workflows.data?.summary.total_workflows,
    knowledge: knowledge.data?.summary.total_knowledge_bases,
    plugins: plugins.data?.items.filter((row) => row.installed).length,
    models: models.data?.summary.total_models,
    tasks: tasks.data?.summary.total_tasks,
    // No schedule service exists; the count reflects the fixtures the page shows.
    schedules: isExecute ? mockSchedules.length : undefined,
    events: deadLetters.data?.length,
    approvals: approvals.data?.items.length,
    secrets: secrets.data?.length,
    threads: threads.data?.items.length,
  }
}
