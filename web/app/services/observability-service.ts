import { get } from '@/utils/request'

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
}

export interface KnowledgeQualitySummary {
  step_type: string
  event_count: number
}

export interface ApprovalsSummary {
  pending: number
  approved: number
  rejected: number
}

export interface WorkspaceObservabilityDashboard {
  workspace_summary: WorkspaceSummary
  agent_summaries: AgentSummary[]
  model_costs: ModelCostSummary[]
  workflow_bottlenecks: WorkflowBottleneck[]
  tool_health: ToolHealthSummary[]
  knowledge_quality: KnowledgeQualitySummary[]
  approvals_summary: ApprovalsSummary
}

export const getObservabilityDashboard = (): Promise<WorkspaceObservabilityDashboard> => {
  return get<WorkspaceObservabilityDashboard>('/observability/dashboard').then((response) => response.data)
}
