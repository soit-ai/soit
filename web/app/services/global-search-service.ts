import { get } from '@/utils/request'

export type SearchKind = 'agent' | 'workflow' | 'knowledge' | 'plugin' | 'model' | 'thread' | 'run'

export interface GlobalSearchResult {
  kind: SearchKind
  id: string
  title: string
  subtitle?: string | null
  status?: string | null
  url: string
  updated_at?: string | null
}

export interface GlobalSearchResponse {
  query: string
  items: GlobalSearchResult[]
  counts: Partial<Record<SearchKind, number>>
}

export const searchWorkspace = (
  query: string,
  options: { types?: SearchKind[]; limit?: number } = {},
): Promise<GlobalSearchResponse> => {
  const params = new URLSearchParams({
    q: query,
    limit: String(options.limit ?? 5),
  })
  for (const type of options.types || []) {
    params.append('types', type)
  }
  return get<GlobalSearchResponse>(`/search?${params.toString()}`)
}
