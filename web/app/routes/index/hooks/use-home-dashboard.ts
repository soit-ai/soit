import { useMemo } from 'react'

import { useQuery } from '@/hooks/use-query'
import { listAgents, type Agent } from '@/services/agent-service'
import { listKnowledgeBases, type KnowledgeBase } from '@/services/knowledge-service'
import { getRunCostSummary, listRuns } from '@/services/run-service'
import { listTasks, type Task } from '@/services/task-service'
import { listWorkflows } from '@/services/workflow-service'

export type DashboardSummary = {
  agentCount: number
  publishedAgents: number
  draftAgents: number
  knowledgeCount: number
  totalDocuments: number
  totalChunks: number
  workflowCount: number
  versionedWorkflows: number
  activeTaskCount: number
  attentionTaskCount: number
  runCount: number
  failedRunCount: number
  promptTokens: number
  completionTokens: number
  runtimeMs: number
}

const activeTaskStatuses = new Set(['queued', 'preparing', 'running', 'waiting_input', 'waiting_approval'])
const attentionTaskStatuses = new Set(['failed', 'waiting_input', 'waiting_approval', 'paused'])

const taskPriority: Record<string, number> = {
  failed: 0,
  waiting_approval: 1,
  waiting_input: 2,
  paused: 3,
  running: 4,
  preparing: 5,
  queued: 6,
}

const byNewest = <T extends { updated_at?: string; created_at: string }>(items: T[]) =>
  [...items].sort((left, right) => {
    const leftValue = left.updated_at || left.created_at
    const rightValue = right.updated_at || right.created_at
    return new Date(rightValue).getTime() - new Date(leftValue).getTime()
  })

export function useHomeDashboard() {
  const agentsQuery = useQuery({
    queryKey: ['home', 'agents'],
    queryFn: () => listAgents({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const knowledgeQuery = useQuery({
    queryKey: ['home', 'knowledge'],
    queryFn: () => listKnowledgeBases({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const workflowsQuery = useQuery({
    queryKey: ['home', 'workflows'],
    queryFn: () => listWorkflows({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const tasksQuery = useQuery({
    queryKey: ['home', 'tasks'],
    queryFn: () => listTasks({ page_size: 30 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const runsQuery = useQuery({
    queryKey: ['home', 'runs'],
    queryFn: () => listRuns({ page_size: 10 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const costsQuery = useQuery({
    queryKey: ['home', 'costs'],
    queryFn: () => getRunCostSummary(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const agents = agentsQuery.data?.items || []
  const knowledgeBases = knowledgeQuery.data?.items || []
  const workflows = workflowsQuery.data?.items || []
  const tasks = tasksQuery.data?.items || []
  const runs = runsQuery.data?.items || []

  const summary = useMemo<DashboardSummary>(() => {
    const publishedAgents = agents.filter((agent) => Boolean(agent.published_version_id)).length
    const draftAgents = Math.max(agents.length - publishedAgents, 0)
    const totalDocuments = knowledgeBases.reduce((sum, item) => sum + (item.doc_count || 0), 0)
    const totalChunks = knowledgeBases.reduce((sum, item) => sum + (item.chunk_count || 0), 0)
    const versionedWorkflows = workflows.filter((workflow) => Boolean(workflow.current_version_id)).length
    const activeTaskCount = tasks.filter((task) => activeTaskStatuses.has(task.status)).length
    const attentionTaskCount = tasks.filter((task) => attentionTaskStatuses.has(task.status)).length
    const failedRunCount = runs.filter((run) => run.status === 'failed').length

    return {
      agentCount: agents.length,
      publishedAgents,
      draftAgents,
      knowledgeCount: knowledgeBases.length,
      totalDocuments,
      totalChunks,
      workflowCount: workflows.length,
      versionedWorkflows,
      activeTaskCount,
      attentionTaskCount,
      runCount: runs.length,
      failedRunCount,
      promptTokens: costsQuery.data?.tokens_prompt ?? 0,
      completionTokens: costsQuery.data?.tokens_completion ?? 0,
      runtimeMs: costsQuery.data?.ms_total ?? 0,
    }
  }, [agents, knowledgeBases, workflows, tasks, runs, costsQuery.data])

  const newestAgents = useMemo<Agent[]>(() => byNewest(agents).slice(0, 4), [agents])

  const recentKnowledge = useMemo<KnowledgeBase[]>(
    () =>
      [...knowledgeBases]
        .sort((left, right) => {
          const leftValue = left.last_ingested_at || left.updated_at
          const rightValue = right.last_ingested_at || right.updated_at
          return new Date(rightValue).getTime() - new Date(leftValue).getTime()
        })
        .slice(0, 3),
    [knowledgeBases]
  )

  const attentionTasks = useMemo<Task[]>(
    () =>
      [...tasks]
        .sort((left, right) => {
          const priorityDelta = (taskPriority[left.status] ?? 99) - (taskPriority[right.status] ?? 99)
          if (priorityDelta !== 0) {
            return priorityDelta
          }
          return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
        })
        .filter((task) => attentionTaskStatuses.has(task.status) || activeTaskStatuses.has(task.status))
        .slice(0, 5),
    [tasks]
  )

  const isInitialLoading =
    (agentsQuery.isLoading && !agents.length) ||
    (knowledgeQuery.isLoading && !knowledgeBases.length) ||
    (workflowsQuery.isLoading && !workflows.length)

  const isRefreshing =
    agentsQuery.isFetching ||
    knowledgeQuery.isFetching ||
    workflowsQuery.isFetching ||
    tasksQuery.isFetching ||
    runsQuery.isFetching ||
    costsQuery.isFetching

  const partialFailure = Boolean(
    agentsQuery.error ||
      knowledgeQuery.error ||
      workflowsQuery.error ||
      tasksQuery.error ||
      runsQuery.error ||
      costsQuery.error
  )

  // A total failure with nothing loaded: the zero counts are misleading (they look
  // like an empty workspace), so surface a clear error rather than empty-looking data.
  const hasAnyData = Boolean(
    agents.length || knowledgeBases.length || workflows.length || tasks.length || runs.length
  )
  const isInitialError = partialFailure && !hasAnyData && !isInitialLoading

  const refetchAll = () => {
    void agentsQuery.refetch()
    void knowledgeQuery.refetch()
    void workflowsQuery.refetch()
    void tasksQuery.refetch()
    void runsQuery.refetch()
    void costsQuery.refetch()
  }

  return {
    agents,
    knowledgeBases,
    workflows,
    tasks,
    runs,
    summary,
    newestAgents,
    recentKnowledge,
    attentionTasks,
    isInitialLoading,
    isRefreshing,
    partialFailure,
    isInitialError,
    refetchAll,
  }
}
