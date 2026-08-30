import { del, get, post, patch, type RequestConfigWithToast } from '@/utils/request'

export interface CurrentUser {
  id: string
  email: string
  name?: string | null
  is_active: boolean
  created_at: string
  tenant_id?: string | null
  workspace_id?: string | null
  tenant_role?: string | null
  workspace_role?: string | null
  profile?: Record<string, any> | null
}

export interface ResourceGrant {
  id: string
  tenant_id: string
  workspace_id: string
  resource_type: string
  resource_id: string
  user_id: string
  actions: string[]
  created_by?: string | null
  created_at: string
  updated_at: string
}

export const getCurrentUser = (config?: RequestConfigWithToast): Promise<CurrentUser> => {
  return get<CurrentUser>('/me', undefined, config)
}

export const updateCurrentUser = (data: {
  email?: string
  name?: string
  profile?: Record<string, any>
}): Promise<CurrentUser> => {
  return patch<CurrentUser>('/me', data)
}

export const changePassword = (
  data: {
    current_password: string
    new_password: string
  },
  config?: RequestConfigWithToast,
): Promise<void> => {
  return post('/me/password', data, config)
}

export interface WorkspaceInfo {
  id: string
  tenant_id: string
  name: string
  description?: string | null
  metadata?: Record<string, any> | null
  /** Members without a confirmed second factor cannot reach this workspace. */
  require_mfa?: boolean
  created_at: string
}

export interface WorkspaceMember {
  user_id: string
  email: string
  name?: string | null
  role: string
  status: string
  created_at: string
  /** Most recent activity across their sessions; null if never seen. */
  last_active_at?: string | null
  /** Whether this member has confirmed a second factor. */
  mfa_enabled?: boolean
}

export interface SavedView {
  id: string
  /** Which screen the view belongs to, e.g. "runs". */
  surface: string
  name: string
  /** The screen's own query string, without a leading question mark. */
  query: string
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface PinnedObject {
  id: string
  object_type: string
  object_id: string
  /** Captured when pinning; the live object is the authority on its name. */
  label?: string | null
  created_at: string
}

export const listSavedViews = (
  params?: { surface?: string },
  config?: RequestConfigWithToast,
): Promise<SavedView[]> => {
  return get<SavedView[]>('/me/views', params, config)
}

/** Saving over a name replaces that view rather than failing. */
export const createSavedView = (
  data: { surface: string; name: string; query: string; is_default?: boolean },
  config?: RequestConfigWithToast,
): Promise<SavedView> => {
  return post<SavedView>('/me/views', data, config)
}

export const updateSavedView = (
  viewId: string,
  data: { name?: string; query?: string; is_default?: boolean },
  config?: RequestConfigWithToast,
): Promise<SavedView> => {
  return patch<SavedView>(`/me/views/${viewId}`, data, config)
}

export const deleteSavedView = (
  viewId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del<void>(`/me/views/${viewId}`, undefined, config)
}

export const listPins = (config?: RequestConfigWithToast): Promise<PinnedObject[]> => {
  return get<PinnedObject[]>('/me/pins', undefined, config)
}

export const createPin = (
  data: { object_type: string; object_id: string; label?: string },
  config?: RequestConfigWithToast,
): Promise<PinnedObject> => {
  return post<PinnedObject>('/me/pins', data, config)
}

export const deletePin = (pinId: string, config?: RequestConfigWithToast): Promise<void> => {
  return del<void>(`/me/pins/${pinId}`, undefined, config)
}

export interface WorkspaceInvitation {
  id: string
  workspace_id: string
  email: string
  role: string
  status: string
  invited_by?: string | null
  expires_at: string
  accepted_at?: string | null
  created_at: string
}

export const listInvitations = (
  workspaceId: string,
  config?: RequestConfigWithToast,
): Promise<WorkspaceInvitation[]> => {
  return get<WorkspaceInvitation[]>(`/workspaces/${workspaceId}/invitations`, undefined, config)
}

/** Re-inviting the same address resends rather than stacking a second offer. */
export const createInvitation = (
  workspaceId: string,
  data: { email: string; role: string },
  config?: RequestConfigWithToast,
): Promise<WorkspaceInvitation> => {
  return post<WorkspaceInvitation>(`/workspaces/${workspaceId}/invitations`, data, config)
}

export const revokeInvitation = (
  invitationId: string,
  config?: RequestConfigWithToast,
): Promise<WorkspaceInvitation> => {
  return del<WorkspaceInvitation>(`/invitations/${invitationId}`, undefined, config)
}

export const acceptInvitation = (
  token: string,
  config?: RequestConfigWithToast,
): Promise<WorkspaceInvitation> => {
  return post<WorkspaceInvitation>(`/invitations/accept`, { token }, config)
}

export interface MyWorkspace {
  id: string
  name: string
  description?: string | null
  /** The caller's role in that workspace. */
  role: string
  created_at: string
}

/**
 * The workspaces the caller belongs to. Distinct from listing every workspace
 * in the tenant, which is an administrative question needing admin rights.
 */
export const listMyWorkspaces = (
  config?: RequestConfigWithToast,
): Promise<MyWorkspace[]> => {
  return get<MyWorkspace[]>('/me/workspaces', undefined, config)
}

export const getWorkspace = (workspaceId: string): Promise<WorkspaceInfo> => {
  return get<WorkspaceInfo>(`/workspaces/${workspaceId}`)
}

export const updateWorkspace = (
  workspaceId: string,
  data: {
    name?: string
    description?: string | null
    metadata?: Record<string, any>
    /** Members without a confirmed second factor cannot reach this workspace. */
    require_mfa?: boolean
  },
  config?: RequestConfigWithToast,
): Promise<WorkspaceInfo> => {
  return patch<WorkspaceInfo>(`/workspaces/${workspaceId}`, data, config)
}

export const listWorkspaceMembers = (workspaceId: string): Promise<WorkspaceMember[]> => {
  return get<WorkspaceMember[]>(`/workspaces/${workspaceId}/members`)
}

export const updateWorkspaceMemberRole = (
  workspaceId: string,
  userId: string,
  role: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return patch(`/workspaces/${workspaceId}/members/${userId}`, { role }, config)
}

export const removeWorkspaceMember = (
  workspaceId: string,
  userId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/workspaces/${workspaceId}/members/${userId}`, undefined, config)
}

export const addWorkspaceMember = (
  workspaceId: string,
  data: { user_id: string; role: string },
  config?: RequestConfigWithToast,
): Promise<void> => {
  return post(`/workspaces/${workspaceId}/members`, data, config)
}

export const listResourceGrants = (
  resourceType: string,
  resourceId: string,
  config?: RequestConfigWithToast,
): Promise<ResourceGrant[]> => {
  return get<ResourceGrant[]>(
    '/resource-grants',
    { resource_type: resourceType, resource_id: resourceId },
    config,
  )
}

/**
 * Every grant in the workspace, newest first, optionally narrowed to one
 * resource type. Answers the access surface in one call instead of a request
 * per object; `limit` caps what the server will return.
 */
export const listWorkspaceResourceGrants = (
  params?: { resource_type?: string; limit?: number },
  config?: RequestConfigWithToast,
): Promise<ResourceGrant[]> => {
  return get<ResourceGrant[]>('/resource-grants', params, config)
}

export const createResourceGrant = (data: {
  resource_type: string
  resource_id: string
  user_id: string
  actions: string[]
}, config?: RequestConfigWithToast): Promise<ResourceGrant> => {
  return post<ResourceGrant>('/resource-grants', data, config)
}

export const revokeResourceGrant = (
  resourceType: string,
  resourceId: string,
  userId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/resource-grants/${resourceType}/${resourceId}/${userId}`, undefined, config)
}
