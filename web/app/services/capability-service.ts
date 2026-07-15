import { get } from '@/utils/request'
import type { PaginatedResponse } from '@/types/api'

export type { PaginatedResponse } from '@/types/api'

export interface AgentCapabilityItem {
  ref: string
  kind: string
  name: string
  source_kind: string
  source_id?: string | null
  source_version?: string | null
  metadata_json?: Record<string, unknown> | null
}

export interface AgentCapabilityListParams {
  kind?: string
  source_kind?: string
  page_token?: string
  page_size?: number
}

const sourceLabelMap: Record<string, string> = {
  builtin: 'Builtin',
  native: 'Native',
  mcp: 'MCP',
  plugin: 'Plugin',
}

const asRecord = (value: unknown): Record<string, unknown> | null => {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

export const listAgentCapabilities = (
  params?: AgentCapabilityListParams
): Promise<PaginatedResponse<AgentCapabilityItem>> => {
  return get<PaginatedResponse<AgentCapabilityItem>>('/agents/capabilities', params)
}

export const listCapabilitiesByKind = (
  kind: string,
  params?: Omit<AgentCapabilityListParams, 'kind'>
): Promise<PaginatedResponse<AgentCapabilityItem>> => {
  return listAgentCapabilities({
    ...params,
    kind,
  })
}

export const formatCapabilityMetadataValue = (value: unknown): string => {
  if (value === null || value === undefined || value === '') {
    return '-'
  }
  if (Array.isArray(value)) {
    return value.map((entry) => formatCapabilityMetadataValue(entry)).join(', ')
  }
  if (typeof value === 'object') {
    try {
      return JSON.stringify(value)
    } catch {
      return '[object]'
    }
  }
  return String(value)
}

export const getCapabilitySourceLabel = (item: AgentCapabilityItem): string => {
  return sourceLabelMap[item.source_kind?.toLowerCase()] || item.source_kind || 'Native'
}

export const getCapabilityPluginSourceLabel = (item: AgentCapabilityItem): string | null => {
  const metadata = item.metadata_json || {}
  const plugin = asRecord(metadata.plugin)
  const pluginName = typeof plugin?.name === 'string' ? plugin.name : item.source_kind === 'plugin' ? item.source_id : null
  const pluginVersion = typeof plugin?.version === 'string' ? plugin.version : item.source_kind === 'plugin' ? item.source_version : null

  if (pluginName && pluginVersion) {
    return `${pluginName}@${pluginVersion}`
  }
  return pluginName || null
}

export const getCapabilityMetadataEntries = (
  item: AgentCapabilityItem,
  limit = 4
): Array<{ key: string; value: string }> => {
  const metadata = item.metadata_json || {}
  return Object.entries(metadata)
    .slice(0, limit)
    .map(([key, value]) => ({
      key,
      value: formatCapabilityMetadataValue(value),
    }))
}
