import { useCallback } from 'react'

import { useQueryClient } from '@tanstack/react-query'

/**
 * Refetches everything the Evaluations pages hold. A change to one dataset
 * moves its revision, its case count, its versions and the list the page
 * before it shows, so each write refreshes the lot instead of naming which.
 */
export function useRefreshEvaluations() {
  const queryClient = useQueryClient()
  return useCallback(
    () => queryClient.invalidateQueries({ queryKey: ['console', 'evaluations'] }),
    [queryClient],
  )
}
