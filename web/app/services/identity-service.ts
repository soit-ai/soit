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
  created_at: string
}

export interface WorkspaceMember {
  user_id: string
  email: string
  name?: string | null
  role: string
  status: string
  created_at: string
}

export const getWorkspace = (workspaceId: string): Promise<WorkspaceInfo> => {
  return get<WorkspaceInfo>(`/workspaces/${workspaceId}`)
}

export const updateWorkspace = (
  workspaceId: string,
  data: { name?: string; description?: string | null; metadata?: Record<string, any> }
): Promise<WorkspaceInfo> => {
  return patch<WorkspaceInfo>(`/workspaces/${workspaceId}`, data)
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
