import { toast } from 'sonner'

import { useQuery } from '@/hooks/use-query'
import { getDiagnosticsSnapshot } from '@/services/diagnostics-service'
import { getCurrentUser, getWorkspace, listWorkspaceMembers } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

/** A failed write reports the server's reason, or the fallback when it gave none. */
export const onWriteError = (fallback: string) => (error: unknown) => {
  toast.error(requestErrorMessage(error, fallback))
}

/**
 * The signed-in identity and the workspace the settings act on.
 *
 * Account, Team and Billing fetch `/me`; the other panes only read it from the
 * cache. The workspace id for the member list comes from the signed-in
 * identity rather than a URL param.
 */
export function useSettingsIdentity(fetchUser: boolean) {
  const userQuery = useQuery({
    queryKey: ['console', 'settings', 'me'],
    queryFn: () => getCurrentUser(),
    options: {
      enabled: fetchUser,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  // The persisted user store is the app's own accessor for the active
  // workspace; localStorage is the same value request.ts sends as
  // X-Workspace-Id and only backs the store up on a cold load.
  const storedWorkspaceId = useUserStore((state) => state.currentUser?.workspace_id)
  const workspaceId =
    userQuery.data?.workspace_id ||
    storedWorkspaceId ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')
  return { userQuery, workspaceId }
}

/** The workspace's members: the Team list, the Billing seat count and the API pane's principal owners. */
export function useMembersQuery(workspaceId: string) {
  return useQuery({
    queryKey: ['console', 'settings', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: {
      enabled: Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
}

/** Account renames the workspace; Security sets its policies. */
export function useWorkspaceQuery(workspaceId: string) {
  return useQuery({
    queryKey: ['console', 'settings', 'workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId),
    options: {
      enabled: Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
}

/** The runtime's diagnostics snapshot, fetched by About and read from the cache elsewhere. */
export function useDiagnosticsQuery(fetch: boolean) {
  return useQuery({
    queryKey: ['console', 'settings', 'diagnostics'],
    queryFn: () => getDiagnosticsSnapshot(),
    options: { enabled: fetch, retry: false, refetchOnWindowFocus: false },
  })
}
