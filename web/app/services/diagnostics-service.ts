import { get } from '@/utils/request'

export type DiagnosticStatus = 'healthy' | 'unavailable'

export interface DependencyDiagnostic {
  name: 'database' | 'object_storage'
  status: DiagnosticStatus
  latency_ms: number
  message?: string | null
}

export interface DiagnosticsSnapshot {
  generated_at: string
  version: string
  environment: string
  overall_status: 'healthy' | 'degraded'
  dependencies: DependencyDiagnostic[]
  process: {
    uptime_seconds: number
    rss_bytes: number
    thread_count: number
  }
  workspace: {
    agents: number | null
    workflows: number | null
    knowledge_bases: number | null
    plugins: number | null
    models: number | null
    threads: number | null
    active_runs: number | null
    failed_runs_24h: number | null
    open_feedback: number | null
  }
}

export const getDiagnosticsSnapshot = (): Promise<DiagnosticsSnapshot> => {
  return get<DiagnosticsSnapshot>('/diagnostics')
}
