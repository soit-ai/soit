import { del, get, patch, post, type RequestConfigWithToast } from '@/utils/request'

export interface Schedule {
  id: string
  name: string
  description?: string | null
  /** agent or workflow. */
  target_kind: string
  target_id: string
  inputs: Record<string, unknown>
  cron: string
  timezone: string
  enabled: boolean
  /** Whether a missed occurrence runs late rather than being skipped. */
  catch_up: boolean
  /** Null while paused: a paused schedule has no next firing. */
  next_fire_at?: string | null
  last_fired_at?: string | null
  last_run_id?: string | null
  last_status?: string | null
  last_error?: string | null
  created_at: string
  updated_at: string
}

export const listSchedules = (
  params?: { enabled?: boolean; limit?: number; offset?: number },
  config?: RequestConfigWithToast,
): Promise<Schedule[]> => {
  return get<Schedule[]>('/schedules', params, config)
}

export const createSchedule = (
  data: {
    name: string
    target_kind: string
    target_id: string
    cron: string
    timezone?: string
    description?: string
    inputs?: Record<string, unknown>
    enabled?: boolean
    catch_up?: boolean
  },
  config?: RequestConfigWithToast,
): Promise<Schedule> => {
  return post<Schedule>('/schedules', data, config)
}

export const updateSchedule = (
  scheduleId: string,
  data: Partial<{
    name: string
    description: string
    cron: string
    timezone: string
    inputs: Record<string, unknown>
    enabled: boolean
    catch_up: boolean
  }>,
  config?: RequestConfigWithToast,
): Promise<Schedule> => {
  return patch<Schedule>(`/schedules/${scheduleId}`, data, config)
}

export const deleteSchedule = (
  scheduleId: string,
  config?: RequestConfigWithToast,
): Promise<void> => {
  return del<void>(`/schedules/${scheduleId}`, undefined, config)
}

/** Fires now without moving the next occurrence. */
export const runScheduleNow = (
  scheduleId: string,
  config?: RequestConfigWithToast,
): Promise<Schedule> => {
  return post<Schedule>(`/schedules/${scheduleId}/run`, undefined, config)
}

/** Check an expression before saving it. */
export const previewSchedule = (
  data: { cron: string; timezone?: string; count?: number },
  config?: RequestConfigWithToast,
): Promise<{ fires_at: string[] }> => {
  return post<{ fires_at: string[] }>('/schedules/preview', data, config)
}
