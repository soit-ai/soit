import { useMemo } from 'react'

import { useQuery } from '@/hooks/use-query'
import { listAgentBindings, listAgents } from '@/services/agent-service'
import { listRuns, type RunResponse } from '@/services/run-service'

type BoundAgent = {
  agentId: string
  agentName: string
  capabilityRefs: string[]
}

type CapabilityGovernanceUsage = {
  boundAgents: BoundAgent[]
  recentRuns: RunResponse[]
  isLoading: boolean
}

export function useCapabilityGovernanceUsage(capabilityRefs: string[]): CapabilityGovernanceUsage {
  const sortedRefs = useMemo(
    () => capabilityRefs.filter(Boolean).sort(),
    [capabilityRefs]
  )
  const capabilityRefSet = useMemo(() => new Set(sortedRefs), [sortedRefs])

  const { data: agentPage, isLoading: agentsLoading } = useQuery({
    queryKey: ['capability-governance', 'agents'],
    queryFn: () => listAgents({ page_size: 100 }),
    options: {
      enabled: sortedRefs.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const agents = agentPage?.items || []

  const { data: boundAgents = [], isLoading: bindingsLoading } = useQuery<BoundAgent[]>({
    queryKey: ['capability-governance', 'bindings', sortedRefs.join('|'), agents.map((agent) => agent.id).join('|')],
    queryFn: async () => {
      const agentBindings = await Promise.all(
        agents.map(async (agent) => ({
          agent,
          bindings: await listAgentBindings(agent.id),
        }))
      )

      return agentBindings
        .map(({ agent, bindings }) => {
          const matches = bindings
            .map((binding) => binding.target_key)
            .filter((targetKey): targetKey is string => Boolean(targetKey) && capabilityRefSet.has(targetKey))

          if (!matches.length) {
            return null
          }

          return {
            agentId: agent.id,
            agentName: agent.name,
            capabilityRefs: Array.from(new Set(matches)),
          }
        })
        .filter((item): item is BoundAgent => item !== null)
    },
    options: {
      enabled: sortedRefs.length > 0 && agents.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const runAgentIds = useMemo(
    () => boundAgents.slice(0, 5).map((agent) => agent.agentId),
    [boundAgents]
  )

  const { data: recentRuns = [], isLoading: runsLoading } = useQuery<RunResponse[]>({
    queryKey: ['capability-governance', 'runs', runAgentIds.join('|')],
    queryFn: async () => {
      const runPages = await Promise.all(
        runAgentIds.map((agentId) =>
          listRuns({
            subject_id: agentId,
            page_size: 3,
          })
        )
      )

      return runPages
        .flatMap((page) => page.items || [])
        .sort((left, right) => {
          const leftTime = left.started_at ? new Date(left.started_at).getTime() : 0
          const rightTime = right.started_at ? new Date(right.started_at).getTime() : 0
          return rightTime - leftTime
        })
        .slice(0, 5)
    },
    options: {
      enabled: runAgentIds.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  return {
    boundAgents,
    recentRuns,
    isLoading: agentsLoading || bindingsLoading || runsLoading,
  }
}
