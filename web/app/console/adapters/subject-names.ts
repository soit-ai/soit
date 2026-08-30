import { useCallback, useMemo } from 'react'

import { useQuery } from '@/hooks/use-query'
import { getAgentWorkbench } from '@/services/agent-service'
import { getWorkflowWorkbench } from '@/services/workflow-service'

/**
 * Resolves a run's `subject_id` to the name of the agent or workflow it ran.
 *
 * A run record carries only the subject's id, so every Observe surface was
 * rendering an opaque `agt_...` where the prototype names the agent. The
 * workbench lists are already the console's source for those names, so the join
 * happens here once rather than in each screen.
 *
 * An id that resolves to nothing is returned unchanged: an unknown subject is
 * still worth identifying, and hiding it behind a dash would lose the only
 * handle an operator has on it.
 */
const SHARED = { retry: false, refetchOnWindowFocus: false, staleTime: 60_000 } as const

export function useSubjectNames() {
  const agents = useQuery({
    queryKey: ['console', 'subject-names', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: 100 }),
    options: SHARED,
  })
  const workflows = useQuery({
    queryKey: ['console', 'subject-names', 'workflows'],
    queryFn: () => getWorkflowWorkbench({ page_size: 100 }),
    options: SHARED,
  })

  const names = useMemo(() => {
    const map = new Map<string, string>()
    for (const row of agents.data?.items || []) {
      if (row.id && row.name) map.set(row.id, row.name)
    }
    for (const row of workflows.data?.items || []) {
      if (row.id && row.name) map.set(row.id, row.name)
    }
    return map
  }, [agents.data, workflows.data])

  return useCallback(
    (subjectId?: string | null) => (subjectId ? names.get(subjectId) || subjectId : '—'),
    [names]
  )
}
