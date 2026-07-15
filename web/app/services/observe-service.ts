import { get } from '@/utils/request'
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

export interface WorkspaceSummary {
  run_count: number
  failed_run_count: number
  active_run_count: number
  pending_approvals: number
  feedback_count: number
  total_cost_usd: number
}

export interface AgentSummary {
  agent_id: string
  run_count: number
  failed_run_count: number
  last_run_at?: string | null
}

export interface ModelCostSummary {
  model_ref: string
  total_cost_usd: number
  total_tokens: number
}

export interface WorkflowBottleneck {
  node_id: string
  step_count: number
  failed_step_count: number
}

export interface ToolHealthSummary {
  tool_ref: string
  call_count: number
  failed_call_count: number
  failure_rate: number
  health_status: HealthStatus
}

export interface KnowledgeQualitySummary {
  knowledge_id: string
  query_count: number
  failed_query_count: number
  result_count: number
  citation_count: number
  avg_score?: number | null
  failure_rate: number
  avg_results_per_query: number
  citation_rate: number
  quality_status: HealthStatus
}

export interface ApprovalsSummary {
  pending: number
  approved: number
  rejected: number
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
  run_count?: number
  failed_run_count?: number
  success_rate?: number
  tool_count?: number
  tool_failed_count?: number
  retrieval_count?: number
  retrieval_failed_count?: number
}

export interface DashboardSection {
  id: ObserveTabId
  summary_cards: MetricCard[]
  charts: Record<string, unknown>
  rows: Array<Record<string, unknown> & { id: string; name?: string; status?: HealthStatus | string }>
  page: DashboardPage
  empty_state: EmptyState
}

export interface WorkspaceObserveDashboard {
  overview: DashboardOverview
  metric_cards: MetricCard[]
  priority_alert?: PriorityAlert | null
  tabs: DashboardTab[]
  section: DashboardSection

  workspace_summary: WorkspaceSummary
  agent_summaries: AgentSummary[]
  model_costs: ModelCostSummary[]
  workflow_bottlenecks: WorkflowBottleneck[]
  tool_health: ToolHealthSummary[]
  knowledge_quality: KnowledgeQualitySummary[]
  approvals_summary: ApprovalsSummary
  recent_runs: RecentRun[]
}

const defaultWorkspaceSummary: WorkspaceSummary = {
  run_count: 0,
  failed_run_count: 0,
  active_run_count: 0,
  pending_approvals: 0,
  feedback_count: 0,
  total_cost_usd: 0,
}

const defaultApprovalsSummary: ApprovalsSummary = {
  pending: 0,
  approved: 0,
  rejected: 0,
}

const tabLabels: Record<ObserveTabId, string> = {
  agent_health: 'Agent 健康',
  workflow_bottlenecks: '工作流瓶颈',
  tool_reliability: '工具可靠性',
  knowledge_quality: '知识质量',
}

const emptyState: EmptyState = {
  title: '暂无数据',
  description: '当前时间范围内没有对应应用观测数据。',
}

const knownTabs = Object.keys(tabLabels) as ObserveTabId[]

const toNumber = (value: unknown, fallback = 0) => (typeof value === 'number' && Number.isFinite(value) ? value : fallback)
const ratio = (part: number, total: number) => (total > 0 ? part / total : 0)
const roundOne = (value: number) => Math.round(value * 10) / 10
const percentText = (value: number) => `${value >= 0 ? '+' : ''}${roundOne(value * 100)}%`

const healthStatusForFailureRate = (failureRate: number): HealthStatus => {
  if (failureRate >= 0.5) return 'critical'
  if (failureRate > 0) return 'warning'
  return 'healthy'
}

const matchesQuery = (row: Record<string, unknown>, q?: string) => {
  const query = q?.trim().toLowerCase()
  if (!query) return true
  return Object.values(row).some((value) => String(value ?? '').toLowerCase().includes(query))
}

const buildOverview = (summary: WorkspaceSummary): DashboardOverview => {
  const failureRate = ratio(summary.failed_run_count, summary.run_count)
  return {
    workspace_health_score: summary.run_count > 0 ? roundOne((1 - failureRate) * 100) : 100,
    workspace_health_status: healthStatusForFailureRate(failureRate),
    active_alert_count: summary.failed_run_count,
    sampling_rate: 0,
    sampling_status: summary.run_count > 0 ? 'legacy' : 'no_data',
    refreshed_at: new Date().toISOString(),
  }
}

const buildMetricCards = (summary: WorkspaceSummary): MetricCard[] => [
  { id: 'run_count', label: '运行次数', value: String(summary.run_count), delta: null, trend: [], tone: 'blue' },
  { id: 'failed_run_count', label: '失败运行', value: String(summary.failed_run_count), delta: null, trend: [], tone: 'red' },
  { id: 'active_run_count', label: '活跃运行', value: String(summary.active_run_count), delta: null, trend: [], tone: 'cyan' },
  { id: 'pending_approvals', label: '待审批', value: String(summary.pending_approvals), delta: null, trend: [], tone: 'amber' },
  { id: 'total_cost_usd', label: '成本 (USD)', value: summary.total_cost_usd.toFixed(2), delta: null, trend: [], tone: 'green' },
]

const buildPriorityAlert = (summary: WorkspaceSummary): PriorityAlert | null => {
  if (!summary.failed_run_count) return null
  return {
    priority: 'P1',
    title: '运行失败率上升',
    started_at: null,
    scope: '当前工作区',
    affected_agents: summary.failed_run_count,
    duration_label: '当前窗口',
    detail_url: '/observe/runs',
  }
}

const legacyRows = (
  tab: ObserveTabId,
  dashboard: Partial<WorkspaceObserveDashboard>,
  q?: string,
): Array<Record<string, unknown> & { id: string; name?: string; status?: HealthStatus | string }> => {
  if (tab === 'agent_health') {
    return (dashboard.agent_summaries || [])
      .map((item) => {
        const failureRate = ratio(toNumber(item.failed_run_count), toNumber(item.run_count))
        const successRate = 1 - failureRate
        return {
          id: item.agent_id,
          name: item.agent_id,
          status: healthStatusForFailureRate(failureRate),
          run_count: item.run_count,
          failed_run_count: item.failed_run_count,
          avg_latency_ms: 0,
          success_rate: successRate,
          last_error: item.failed_run_count > 0 ? 'failure' : '-',
          owner: '-',
          last_run_at: item.last_run_at || '-',
        }
      })
      .filter((row) => matchesQuery(row, q))
  }

  if (tab === 'workflow_bottlenecks') {
    return (dashboard.workflow_bottlenecks || [])
      .map((item) => {
        const failureRate = ratio(toNumber(item.failed_step_count), toNumber(item.step_count))
        return {
          id: item.node_id,
          name: item.node_id,
          stage: item.node_id,
          current_queue: item.step_count,
          avg_wait_ms: 0,
          failure_rate: failureRate,
          affected_agents: [],
          owner: '-',
          status: healthStatusForFailureRate(failureRate),
        }
      })
      .filter((row) => matchesQuery(row, q))
  }

  if (tab === 'tool_reliability') {
    return (dashboard.tool_health || [])
      .map((item) => ({
        id: item.tool_ref,
        name: item.tool_ref,
        type: '工具',
        call_count: item.call_count,
        success_rate: 1 - toNumber(item.failure_rate),
        avg_latency_ms: 0,
        failure_reason: item.failed_call_count > 0 ? { failed: item.failed_call_count } : {},
        related_agents: [],
        owner: '-',
        status: item.health_status,
      }))
      .filter((row) => matchesQuery(row, q))
  }

  return (dashboard.knowledge_quality || [])
    .map((item) => {
      const source = item as KnowledgeQualitySummary & Record<string, unknown>
      const id = String(source.knowledge_id || source.step_type || source.id || 'unknown')
      return {
        id,
        name: id,
        related_agents: [],
        hit_rate: 1 - toNumber(source.failure_rate),
        missing_answer_rate: toNumber(source.failure_rate),
        expired_chunks: 0,
        last_updated: '-',
        status: source.quality_status || healthStatusForFailureRate(toNumber(source.failure_rate)),
        owner: '-',
      }
    })
    .filter((row) => matchesQuery(row, q))
}

const buildCharts = (
  tab: ObserveTabId,
  rows: Array<Record<string, unknown> & { id: string; name?: string; status?: HealthStatus | string }>,
) => {
  if (tab === 'agent_health') {
    const statusCounts = rows.reduce<Record<string, number>>((acc, row) => {
      const status = String(row.status || 'unknown')
      acc[status] = (acc[status] || 0) + 1
      return acc
    }, {})
    return {
      trend: [],
      health_distribution: Object.entries(statusCounts).map(([status, count]) => ({ status, count })),
      alert_compression: {
        raw_alerts: rows.filter((row) => row.status !== 'healthy').length,
        compressed_alerts: rows.filter((row) => row.status !== 'healthy').length,
      },
    }
  }

  if (tab === 'workflow_bottlenecks') {
    return {
      trend: [],
      queue_distribution: rows,
      latency_percentiles: { p50_ms: 0, p95_ms: 0, p99_ms: 0 },
    }
  }

  if (tab === 'tool_reliability') {
    const failedCount = rows.reduce((total, row) => total + Object.values((row.failure_reason || {}) as Record<string, number>).reduce((sum, value) => sum + toNumber(value), 0), 0)
    return {
      trend: [],
      error_distribution: failedCount > 0 ? [{ type: 'failed', count: failedCount }] : [],
    }
  }

  return {
    trend: [],
    quality_score: rows.length ? roundOne(rows.reduce((sum, row) => sum + toNumber(row.hit_rate), 0) * 100 / rows.length) : 100,
    low_quality_sources: rows,
  }
}

const buildSummaryCards = (
  tab: ObserveTabId,
  rows: Array<Record<string, unknown> & { id: string; name?: string; status?: HealthStatus | string }>,
): MetricCard[] => {
  if (tab === 'agent_health') {
    const healthyCount = rows.filter((row) => row.status === 'healthy').length
    return [
      { id: 'agent_count', label: 'Agent 数', value: String(rows.length), delta: null, trend: [], tone: 'blue' },
      { id: 'healthy_agent_count', label: '健康 Agent', value: String(healthyCount), delta: null, trend: [], tone: 'green' },
    ]
  }

  if (tab === 'workflow_bottlenecks') {
    return [
      { id: 'bottleneck_count', label: '瓶颈数', value: String(rows.length), delta: null, trend: [], tone: 'amber' },
    ]
  }

  if (tab === 'tool_reliability') {
    const totalCalls = rows.reduce((sum, row) => sum + toNumber(row.call_count), 0)
    return [
      { id: 'tool_count', label: '工具数', value: String(rows.length), delta: null, trend: [], tone: 'blue' },
      { id: 'tool_call_count', label: '调用次数', value: String(totalCalls), delta: null, trend: [], tone: 'green' },
    ]
  }

  const averageHitRate = rows.length ? rows.reduce((sum, row) => sum + toNumber(row.hit_rate), 0) / rows.length : 0
  return [
    { id: 'knowledge_count', label: '知识库数', value: String(rows.length), delta: null, trend: [], tone: 'blue' },
    { id: 'hit_rate', label: '平均命中率', value: percentText(averageHitRate).replace('+', ''), delta: null, trend: [], tone: 'green' },
  ]
}

const buildSection = (
  tab: ObserveTabId,
  dashboard: Partial<WorkspaceObserveDashboard>,
  params: ObserveDashboardParams,
): DashboardSection => {
  const rows = legacyRows(tab, dashboard, params.q)
  return {
    id: tab,
    summary_cards: buildSummaryCards(tab, rows),
    charts: buildCharts(tab, rows),
    rows,
    page: {
      page_size: params.page_size || rows.length || 10,
      next_page_token: null,
      total_count: rows.length,
    },
    empty_state: emptyState,
  }
}

const buildTabs = (dashboard: Partial<WorkspaceObserveDashboard>): DashboardTab[] => [
  { id: 'agent_health', label: tabLabels.agent_health, count: dashboard.agent_summaries?.length || 0 },
  { id: 'workflow_bottlenecks', label: tabLabels.workflow_bottlenecks, count: dashboard.workflow_bottlenecks?.length || 0 },
  { id: 'tool_reliability', label: tabLabels.tool_reliability, count: dashboard.tool_health?.length || 0 },
  { id: 'knowledge_quality', label: tabLabels.knowledge_quality, count: dashboard.knowledge_quality?.length || 0 },
]

const normalizeObserveDashboard = (
  dashboard: Partial<WorkspaceObserveDashboard> | null | undefined,
  params: ObserveDashboardParams,
): WorkspaceObserveDashboard => {
  const source = dashboard || {}
  const tab = knownTabs.includes(params.tab as ObserveTabId) ? params.tab as ObserveTabId : 'agent_health'
  const workspaceSummary = { ...defaultWorkspaceSummary, ...(source.workspace_summary || {}) }
  const agentSummaries = source.agent_summaries || []
  const modelCosts = source.model_costs || []
  const workflowBottlenecks = source.workflow_bottlenecks || []
  const toolHealth = source.tool_health || []
  const knowledgeQuality = source.knowledge_quality || []
  const approvalsSummary = { ...defaultApprovalsSummary, ...(source.approvals_summary || {}) }
  const recentRuns = source.recent_runs || []

  return {
    overview: source.overview || buildOverview(workspaceSummary),
    metric_cards: source.metric_cards || buildMetricCards(workspaceSummary),
    priority_alert: source.priority_alert === undefined ? buildPriorityAlert(workspaceSummary) : source.priority_alert,
    tabs: source.tabs || buildTabs({ ...source, agent_summaries: agentSummaries, workflow_bottlenecks: workflowBottlenecks, tool_health: toolHealth, knowledge_quality: knowledgeQuality }),
    section: source.section || buildSection(tab, {
      ...source,
      agent_summaries: agentSummaries,
      workflow_bottlenecks: workflowBottlenecks,
      tool_health: toolHealth,
      knowledge_quality: knowledgeQuality,
    }, params),
    workspace_summary: workspaceSummary,
    agent_summaries: agentSummaries,
    model_costs: modelCosts,
    workflow_bottlenecks: workflowBottlenecks,
    tool_health: toolHealth,
    knowledge_quality: knowledgeQuality,
    approvals_summary: approvalsSummary,
    recent_runs: recentRuns,
  }
}

export const getObserveDashboard = (
  params: ObserveDashboardParams = {},
): Promise<WorkspaceObserveDashboard> => {
  return get<Partial<WorkspaceObserveDashboard>>('/observe/dashboard', params)
    .then((response) => normalizeObserveDashboard(response, params))
}
