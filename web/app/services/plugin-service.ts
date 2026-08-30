import { get, post, del, uploadFile, type RequestConfigWithToast } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

type ApiEnvelope<T> = {
  success?: boolean
  data: T
}

function unwrapApiData<T>(response: T | ApiEnvelope<T>): T {
  if (
    response &&
    typeof response === 'object' &&
    'data' in response &&
    (
      'success' in response ||
      !('items' in response)
    )
  ) {
    return (response as ApiEnvelope<T>).data
  }
  return response as T
}

export interface Plugin {
  id: string
  name: string
  version: string
  publisher: string
  plugin_type: 'skill' | 'mcp' | 'tool' | 'workflow_node' | 'mixed'
  status: string
  description?: string | null
  spec_json: Record<string, any>
  manifest_json?: Record<string, any> | null
  metadata_json?: Record<string, any> | null
  publish_status: string
  installed_count: number
  current_version_id?: string | null
  published_version_id?: string | null
  installed?: boolean
  enabled?: boolean | null
  installation_id?: string | null
  installed_at?: string | null
  /** Derived from the permissions the plugin declares, never stored. */
  risk_level?: 'low' | 'medium' | 'high'
  /** The declared scopes that produced the level. */
  risk_reasons?: string[]
  /** True when this installation is pinned behind the published version. */
  update_available?: boolean
  installed_version_id?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export interface PluginInstallResponse {
  id: string
  plugin_id: string
  installed_at?: string | null
}

export interface PluginPackageInstallResponse {
  install_dir: string
  package_path: string
  manifest_path: string
  spec_path: string
}

export interface PluginPackageUploadResponse {
  action: 'created' | 'upgraded' | 'reinstalled'
  plugin: Plugin
  install: PluginPackageInstallResponse
}

export interface PluginUpgradeResponse {
  plugin: Plugin
  install: PluginPackageInstallResponse
}

export interface PluginInstallationResponse {
  id: string
  plugin_id: string
  plugin_version_id?: string | null
  tenant_id: string
  workspace_id: string
  enabled: boolean
  state: string
  config_json?: Record<string, any> | null
  created_at: string
  updated_at?: string | null
}

export interface PluginArtifact {
  id: string
  plugin_id: string
  plugin_version_id?: string | null
  installation_id?: string | null
  artifact_kind: 'skill' | 'mcp_server' | 'tool' | 'workflow_node'
  artifact_ref: string
  artifact_id?: string | null
  artifact_version_id?: string | null
  state: string
  enabled: boolean
  metadata_json: Record<string, any>
  created_at: string
  updated_at: string
}

export interface PluginCapability {
  ref: string
  kind: string
  name: string
  source_kind: 'plugin'
  source_id?: string | null
  source_version?: string | null
  artifact_kind?: string | null
  plugin_id?: string | null
  plugin_version_id?: string | null
  installation_id?: string | null
  metadata_json: Record<string, any>
}

export const listPlugins = (params?: {
  published_only?: boolean
  plugin_type?: Plugin['plugin_type']
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<Plugin>> => {
  return get<PaginatedResponse<Plugin>>('/plugins', params).then(unwrapApiData)
}

export const getPlugin = (pluginId: string): Promise<Plugin> => {
  return get<Plugin>(`/plugins/${pluginId}`).then(unwrapApiData)
}

export const installPlugin = (
  pluginId: string,
  config_json?: Record<string, any>,
  config?: RequestConfigWithToast,
): Promise<PluginInstallResponse> => {
  return post<PluginInstallResponse>(`/plugins/${pluginId}/install`, { config_json }, config).then(
    unwrapApiData,
  )
}

export const uninstallPlugin = (
  pluginId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del(`/plugins/${pluginId}/install`, undefined, config).then(() => undefined)
}

export const uploadPluginPackage = (
  file: File,
  mode: 'auto' | 'reinstall' = 'auto'
): Promise<PluginPackageUploadResponse> => {
  const formData = new FormData()
  formData.append('package', file)
  return uploadFile<PluginPackageUploadResponse>('/plugins/package', formData, {
    params: { mode },
    suppressErrorToast: true,
  }).then(unwrapApiData)
}

export const upgradePluginPackage = (
  pluginId: string,
  file: File
): Promise<PluginUpgradeResponse> => {
  const formData = new FormData()
  formData.append('package', file)
  return uploadFile<PluginUpgradeResponse>(`/plugins/${pluginId}/upgrade-package`, formData, {
    suppressErrorToast: true,
  }).then(unwrapApiData)
}

export const setPluginEnabled = (
  pluginId: string,
  enabled: boolean
): Promise<PluginInstallationResponse> => {
  return post<PluginInstallationResponse>(`/plugins/${pluginId}/enabled`, { enabled }).then(unwrapApiData)
}

export interface PluginRuntimeReloadResponse {
  loaded_count: number
}

export interface RuntimeToolItem {
  tool_ref: string
  version: string
  plugin?: {
    name: string
    version: string
  } | null
  tool_spec?: {
    name?: string
    description?: string | null
    input_schema?: Record<string, unknown> | null
  } | null
}

export const listRuntimeTools = (): Promise<{ tools: RuntimeToolItem[] }> =>
  get<{ tools: RuntimeToolItem[] }>('/plugins/runtime/tools')

export const reloadPluginRuntime = (): Promise<PluginRuntimeReloadResponse> => {
  return post<PluginRuntimeReloadResponse>('/plugins/runtime/reload', {}).then(unwrapApiData)
}

export const listPluginArtifacts = (params?: {
  plugin_id?: string
  artifact_kind?: PluginArtifact['artifact_kind']
  enabled?: boolean
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<PluginArtifact>> => {
  const { plugin_id, ...query } = params || {}
  const path = plugin_id ? `/plugins/${plugin_id}/artifacts` : '/plugins/artifacts'
  return get<PaginatedResponse<PluginArtifact>>(path, query).then(unwrapApiData)
}

export const listPluginCapabilities = (params?: {
  kind?: string
  page_token?: string
  page_size?: number
}): Promise<PaginatedResponse<PluginCapability>> => {
  return get<PaginatedResponse<PluginCapability>>('/plugins/capabilities', params).then(unwrapApiData)
}
