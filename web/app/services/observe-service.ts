import { get, post } from '@/utils/request'
import type { RunObserveSummary } from '@/services/run-service'

export type ObserveTabId =
  | 'agent_health'
  | 'workflow_bottlenecks'
  | 'tool_reliability'
  | 'knowledge_quality'

export type ObserveRange = '1h' | '6h' | '24h' | '7d'
export type ObserveBucket = '5m' | '10m' | '30m' | '1h' | '1d'
export type HealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown'

export interface ObserveDashboardParams {
  tab?: ObserveTabId
  range?: ObserveRange
  bucket?: ObserveBucket
  q?: string
  workspace_scope?: string
  page_token?: string
  page_size?: number
}

export interface RunFeedbackCreate {
  run_id?: string | null
  task_id?: string | null
  thread_id?: string | null
  agent_id?: string | null
  rating: number
  category: string
  comment?: string | null
  metadata_json?: Record<string, unknown>
}

export interface DashboardOverview {
  workspace_health_score: number
  workspace_health_status: HealthStatus
  active_alert_count: number
  sampling_rate: number
  sampling_status: string
  refreshed_at: string
}

export interface MetricCard {
  id: string
  label: string
  value: string
  delta?: string | null
  trend: number[]
  tone: 'blue' | 'green' | 'amber' | 'red' | 'cyan' | string
  run_id?: string | null
  detail_url?: string | null
  status?: HealthStatus | string | null
  cost_usd?: number | null
  failure_reason?: string | null
}

export interface PriorityAlert {
  priority: string
  title: string
  started_at?: string | null
  scope: string
  affected_agents: number
  duration_label: string
  detail_url: string
}

export interface RecentRun {
  run_id: string
  mode?: string | null
  kind?: string | null
  subject_kind?: string | null
  subject_id?: string | null
  status: string
  cost_usd: number
  failure_reason?: string | null
  started_at?: string | null
  duration_ms?: number | null
  observe_summary?: RunObserveSummary | null
  detail_url: string
}

export interface DashboardTab {
  id: ObserveTabId
  label: string
  count: number
}

export interface DashboardPage {
  page_size: number
  next_page_token?: string | null
  total_count: number
}

export interface EmptyState {
  title: string
  description: string
}

export interface TrendPoint {
  bucket: string
  run_count: number
  failed_run_count: number
  success_rate: number
  tool_count: number
  tool_failed_count: number
  retrieval_count: number
  retrieval_failed_count: number
}

export interface HealthDistributionDatum {
  status: HealthStatus
  count: number
}

export interface ErrorDistributionDatum {
  type: string
  count: number
}

export interface AlertCompression {
  raw_alerts: number
  compressed_alerts: number
}

export interface DashboardChartRunFields {
  latest_run_id: string | null
  latest_run_status: string | null
  latest_run_cost_usd: number
  latest_failure_reason: string | null
  detail_url: string | null
}

export interface WorkflowQueueDatum extends DashboardChartRunFields {
  id: string
  name: string
  description: string
  stage: string
  current_queue: number
  avg_wait_ms: number
  failure_rate: number
  affected_agents: string[]
  owner: string
}

export interface KnowledgeSourceDatum extends DashboardChartRunFields {
  id: string
  name: string
  description: string
  related_agents: string[]
  hit_rate: number
  missing_answer_rate: number
  expired_chunks: number
  last_updated: string | null
  status: HealthStatus | string
  owner: string
}

export interface DashboardChartsByTab {
  agent_health: {
    trend: TrendPoint[]
    health_distribution: HealthDistributionDatum[]
    alert_compression: AlertCompression
  }
  workflow_bottlenecks: {
    bottleneck_flow: WorkflowQueueDatum[]
    queue_distribution: WorkflowQueueDatum[]
    latency_percentiles: {
      p50: number
      p95: number
      p99: number
    }
  }
  tool_reliability: {
    trend: TrendPoint[]
    error_distribution: ErrorDistributionDatum[]
  }
  knowledge_quality: {
    trend: TrendPoint[]
    quality_score: number
    low_quality_sources: KnowledgeSourceDatum[]
  }
}

interface DashboardSectionBase {
  summary_cards: MetricCard[]
  rows: Array<Record<string, unknown> & {
    id: string
    name?: string
    status?: HealthStatus | string
  }>
  page: DashboardPage
  empty_state: EmptyState
}

export type DashboardSection = {
  [TTab in ObserveTabId]: DashboardSectionBase & {
    id: TTab
    charts: DashboardChartsByTab[TTab]
  }
}[ObserveTabId]

export interface WorkspaceObserveDashboard {
  overview: DashboardOverview
  metric_cards: MetricCard[]
  priority_alert?: PriorityAlert | null
  tabs: DashboardTab[]
  section: DashboardSection
  recent_runs: RecentRun[]
}

export const getObserveDashboard = (
  params: ObserveDashboardParams = {},
): Promise<WorkspaceObserveDashboard> => {
  return get<WorkspaceObserveDashboard>('/observe/dashboard', params)
}

export const createRunFeedback = (data: RunFeedbackCreate) => {
  return post('/observe/feedback', data)
}
