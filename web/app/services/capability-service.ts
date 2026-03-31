import { get } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface CapabilityRegistryItem {
  ref: string
  kind: string
  name: string
  source_kind: string
  source_id?: string | null
  source_version?: string | null
  metadata_json?: Record<string, unknown> | null
}

export interface CapabilityRegistryListParams {
  kind?: string
  source_kind?: string
  page_token?: string
  page_size?: number
}

export const listCapabilityRegistry = (
  params?: CapabilityRegistryListParams
): Promise<PaginatedResponse<CapabilityRegistryItem>> => {
  return get<PaginatedResponse<CapabilityRegistryItem>>('/capabilities', params).then((response) => response.data)
}

export const listCapabilitiesByKind = (
  kind: string,
  params?: Omit<CapabilityRegistryListParams, 'kind'>
): Promise<PaginatedResponse<CapabilityRegistryItem>> => {
  return listCapabilityRegistry({
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

export const getCapabilityMetadataEntries = (
  item: CapabilityRegistryItem,
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
