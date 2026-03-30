import { get } from '@/utils/request'

export interface PaginatedResponse<T> {
  items: T[]
  next_page_token?: string | null
  page_size: number
}

export interface SkillRelease {
  id: string
  skill_id: string
  version_id: string
  action: string
  scope: string
  status: string
  from_version_id?: string | null
  to_version_id: string
  notes?: string | null
  rollback_of_publish_id?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export const listSkillReleases = (
  skillId: string,
  params?: {
    page_token?: string
    page_size?: number
  }
): Promise<PaginatedResponse<SkillRelease>> => {
  return get<PaginatedResponse<SkillRelease>>(`/skills/${skillId}/releases`, params).then((response) => response.data)
}
