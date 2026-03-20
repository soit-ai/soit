import { get, post, del } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface Plugin {
  id: string
  name: string
  version: string
  description?: string | null
  spec_json: Record<string, any>
  manifest_json?: Record<string, any> | null
  metadata_json?: Record<string, any> | null
  published: boolean
  installed_count: number
  installed?: boolean
  enabled?: boolean | null
  installation_id?: string | null
  installed_at?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface PluginInstallResponse {
  id: string
  plugin_id: string
  installed_at?: string | null
}

export interface PluginInstallationResponse {
  id: string
  plugin_id: string
  tenant_id: string
  workspace_id: string
  config_json?: Record<string, any> | null
  created_at: string
}

export const listPlugins = (params?: {
  published_only?: boolean
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Plugin>> => {
  return get<PaginatedResponse<Plugin>>('/plugins', params) as unknown as Promise<PaginatedResponse<Plugin>>
}

export const getPlugin = (pluginId: string): Promise<Plugin> => {
  return get<Plugin>(`/plugins/${pluginId}`) as unknown as Promise<Plugin>
}

export const installPlugin = (
  pluginId: string,
  config_json?: Record<string, any>
): Promise<PluginInstallResponse> => {
  return post<PluginInstallResponse>(`/plugins/${pluginId}/install`, { config_json }) as unknown as Promise<PluginInstallResponse>
}

export const uninstallPlugin = (pluginId: string): Promise<void> => {
  return del(`/plugins/${pluginId}/install`).then(() => undefined)
}

export const setPluginEnabled = (
  pluginId: string,
  enabled: boolean
): Promise<PluginInstallationResponse> => {
  return post<PluginInstallationResponse>(`/plugins/${pluginId}/enabled`, { enabled }) as unknown as Promise<PluginInstallationResponse>
}

export interface PluginRuntimeReloadResponse {
  loaded_count: number
}

export const reloadPluginRuntime = (): Promise<PluginRuntimeReloadResponse> => {
  return post<PluginRuntimeReloadResponse>('/plugins/runtime/reload', {}) as unknown as Promise<PluginRuntimeReloadResponse>
}
