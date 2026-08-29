/**
 * Mock data for the Govern pillar, mirroring the v13 prototype samples.
 * // BACKEND-PENDING: approvals wire to the existing observe approvals API;
 * // egress/usage rules and secrets have real endpoints; policy bundles and
 * // staged diffs stay mock-first (backend keeps only policy_ref today).
 */
import type { ConsoleStatus } from '../components'

export const mockApprovalTiles = {
  pending: { value: '2', sub: 'oldest waiting 1h 12m' },
  decided: { value: '41', sub: '37 approved · 4 rejected' },
  median: { value: '18m', sub: 'p95 1h 50m' },
  escalations: { value: '1', sub: '→ #finance-ops after 2h' },
}

export interface MockApprovalPending {
  id: string
  request: string
  note: string
  gate: string
  requested_by: string
  waiting: string
  waiting_warn?: boolean
  context: { label: string; to: string }[]
}

export const mockApprovalsPending: MockApprovalPending[] = [
  {
    id: 'apr_journal',
    request: 'Post 14 journal entries to the ERP',
    note: 'invoice-reconcile · monthly close · step 6/7 held',
    gate: 'finance.journal.post',
    requested_by: 'workflow · schedule',
    waiting: '1h 12m',
    waiting_warn: true,
    context: [
      { label: 'task', to: '/v2/execute/tasks/task_invoice' },
      { label: 'run', to: '/v2/observe/runs/run_01J9KCYW7N' },
    ],
  },
  {
    id: 'apr_scale',
    request: 'Scale checkout-api to 16 replicas in production',
    note: 'ops-copilot · requested in chat by Wei',
    gate: 'infra.scale.prod',
    requested_by: 'chat · Wei',
    waiting: '18m',
    context: [
      { label: 'thread', to: '/v2/chat' },
      { label: 'run', to: '/v2/observe/runs/run_01J9KD7Z2M' },
    ],
  },
]

export interface MockApprovalDecided {
  time: string
  request: string
  gate: string
  decided_by: string
  took: string
  status: ConsoleStatus
  status_label: string
  note?: string
}

export const mockApprovalsDecided: MockApprovalDecided[] = [
  { time: '08-27 15:22Z', request: 'post 12 journal entries · July close', gate: 'finance.journal.post', decided_by: 'Wei', took: '22m', status: 'pass', status_label: 'APPROVED' },
  { time: '08-26 10:04Z', request: 'scale checkout-api 12 → 8 replicas', gate: 'infra.scale.prod', decided_by: 'Jude', took: '6m', status: 'pass', status_label: 'APPROVED' },
  { time: '08-25 16:40Z', request: 'raise ops-copilot budget to $40/day', gate: 'budget.change', decided_by: 'Jude', took: '1h 04m', status: 'blocked', status_label: 'REJECTED', note: '"wait for Q3 review"' },
]

export const mockPolicyTiles = {
  active: { value: 'v2026.08.27-2', sub: 'production since 09:15Z' },
  rules: { value: '7', sub: '3 grants · intents · egress · budget · approval' },
  evaluations: { value: '4,959', sub: '15 blocked · 0 overrides' },
  attention: { value: '2', sub: '1 staged rollout · 12 egress blocks' },
}

export interface MockPolicyRule {
  id: string
  kind: string
  kind_color: string
  scope: string
  evaluations: string
  blocked: string
}

export const mockPolicyRules: MockPolicyRule[] = [
  { id: 'intent-screen', kind: 'intents', kind_color: 'var(--cat-pink)', scope: '12 allowed intents on ops.* · default deny', evaluations: '1,271', blocked: '3' },
  { id: 'g_44', kind: 'tool·grant', kind_color: 'var(--cat-cyan)', scope: 'k8s.* on ns/staging · expires 2026-09-30', evaluations: '502', blocked: '0' },
  { id: 'g_45', kind: 'tool·grant', kind_color: 'var(--cat-cyan)', scope: 'tickets.read / tickets.write · support-triage', evaluations: '866', blocked: '0' },
  { id: 'g_51', kind: 'tool·grant', kind_color: 'var(--cat-cyan)', scope: 'finance.journal.post · requires human approval', evaluations: '14', blocked: '0' },
  { id: 'egress-allowlist', kind: 'egress', kind_color: 'var(--cat-indigo)', scope: '8 domains · default deny', evaluations: '1,022', blocked: '12' },
  { id: 'cost-guard', kind: 'budget', kind_color: 'var(--cat-amber)', scope: 'ops-copilot $25/day · workspace $120/day', evaluations: '1,284', blocked: '0' },
  { id: 'approval-prod', kind: 'approval', kind_color: 'var(--cat-purple)', scope: 'infra.*.prod → owner sign-off', evaluations: '6', blocked: '—' },
]

export const mockPolicyRuleCounts = { all: 7, grants: 3, intents: 1, egress: 1, budget: 1, approval: 1 }

export interface MockBundle {
  id: string
  status: ConsoleStatus
  status_label: string
  note: string
  active?: boolean
}

export const mockBundles: MockBundle[] = [
  { id: 'v2026.08.28-1', status: 'running', status_label: 'STAGED 10%', note: 'draft by Jude · rolling out to 10% of runs · 0 blocked-regressions' },
  { id: 'v2026.08.27-2', status: 'pass', status_label: 'ACTIVE', note: 'production since 09:15Z · 1,284 runs evaluated · 24h', active: true },
  { id: 'v2026.08.27-1', status: 'info', status_label: 'ARCHIVED', note: 'superseded same day · rollback target' },
  { id: 'v2026.08.20-3', status: 'info', status_label: 'ARCHIVED', note: 'active 7 days · 8,912 runs evaluated' },
]

export const mockStagedDiff = [
  { kind: 'hd', text: 'rule egress-allowlist' },
  { kind: 'add', text: '+ allow api.statuspage.io', comment: '# incident status updates' },
  { kind: 'del', text: '− allow legacy.internal.acme.io', comment: '# decommissioned 2026-08-25' },
  { kind: 'hd', text: 'rule g_44 (tool grant)' },
  { kind: 'add', text: '+ scope k8s.scale max_replicas=16', comment: '# was 12 · requested by ops' },
  { kind: 'hd', text: 'bundle metadata' },
  { kind: 'add', text: '+ rollout: staged 10% → 50% after 24h clean' },
] as const

export const mockAuditTiles = {
  entries: { value: '47', sub: '9 human · 38 system' },
  blocks: { value: '15', sub: '12 egress · 3 intent' },
  changes: { value: '6', sub: 'bundle · secret · agent channel' },
  review: { value: '3', sub: 'unacknowledged blocks' },
}

export interface MockAuditEntry {
  time: string
  actor: string
  action: string
  object: string
  status: ConsoleStatus
  status_label: string
}

export const mockAuditAll: MockAuditEntry[] = [
  { time: '13:42:07Z', actor: 'policy · egress-allowlist', action: 'tool call blocked', object: 'fetch_url → api.unknown.io', status: 'blocked', status_label: 'BLOCKED' },
  { time: '12:41:18Z', actor: 'gateway', action: 'event rejected', object: 'evt_a91b77 · bad signature', status: 'blocked', status_label: 'REJECTED' },
  { time: '09:15:02Z', actor: 'Jude', action: 'policy bundle activated', object: 'v2026.08.27-2', status: 'info', status_label: 'APPLIED' },
  { time: '08:03:19Z', actor: 'secrets', action: 'secret rotated', object: 'SLACK_BOT_TOKEN', status: 'info', status_label: 'APPLIED' },
  { time: '07:40:56Z', actor: 'Wei', action: 'agent promoted', object: 'release-notes → production', status: 'info', status_label: 'APPLIED' },
  { time: '06:12:33Z', actor: 'cost-guard', action: 'budget threshold notice', object: 'ops-copilot · 80%', status: 'warn', status_label: 'NOTICE' },
]

export const mockAuditBlocks = [
  { time: '13:42:07Z', rule: 'egress-allowlist', blocked: 'fetch_url → api.unknown.io', run_id: 'run_01J9KD6H0T' },
  { time: '13:46:18Z', rule: 'tool-permission', blocked: 'cdn.purge · no grant', run_id: 'run_01J9KD8B4X' },
  { time: '11:02:44Z', rule: 'intent-screen', blocked: 'intent "delete workspace data" denied', run_id: 'run_01J9KCT1Q8' },
]

export const mockAuditChanges = [
  { time: '09:15:02Z', actor: 'Jude', change: 'bundle v2026.08.27-2 activated', diff: 'view diff', diff_to: '/v2/govern/policies' },
  { time: '08:03:19Z', actor: 'secrets', change: 'SLACK_BOT_TOKEN rotated · 3 agents re-bound', diff: 'value write-only' },
  { time: '07:40:56Z', actor: 'Wei', change: 'release-notes channel → production', diff: 'v5 → v6', diff_to: '/v2/build/agents/release-notes' },
]

export const mockSecretTiles = {
  secrets: { value: '4', sub: 'values write-only · refs everywhere' },
  resolutions: { value: '3,214', sub: 'at call time · never logged' },
  rotation: { value: '9d', sub: 'vault:helpdesk-api · 90d policy' },
  attention: { value: '1', sub: 'k8s-staging unrotated 30d' },
}

export interface MockSecretRow {
  ref: string
  kind: string
  bound: string
  rotated: string
  due: string
  due_warn?: boolean
  last_used: string
}

export const mockSecrets: MockSecretRow[] = [
  { ref: 'vault:anthropic-prod', kind: 'API key', bound: '5', rotated: '14d ago', due: '76d', last_used: 'just now' },
  { ref: 'vault:k8s-staging', kind: 'kubeconfig', bound: '1', rotated: '30d ago', due: 'overdue soon', due_warn: true, last_used: '2m ago' },
  { ref: 'vault:SLACK_BOT_TOKEN', kind: 'token', bound: '3', rotated: '6h ago', due: '89d', last_used: '31m ago' },
  { ref: 'vault:helpdesk-api', kind: 'token', bound: '1', rotated: '81d ago', due: '9d', due_warn: true, last_used: 'just now' },
]

export const mockSecretRotations = [
  { time: '08:03:19Z', secret: 'vault:SLACK_BOT_TOKEN', by: 'secrets · scheduled', rebound: '3 agents', audit: 'aud_8811' },
  { time: '08-14', secret: 'vault:anthropic-prod', by: 'Jude', rebound: '5 agents', audit: 'aud_7ac2' },
  { time: '08-09', secret: 'vault:helpdesk-api', by: 'Wei', rebound: '1 agent', audit: 'aud_76f0' },
]

export const mockSecretUsage = [
  { secret: 'vault:anthropic-prod', consumers: ['5 agents', 'model gateway'], resolutions: '1,942', denied: '—' },
  { secret: 'vault:k8s-staging', consumers: ['ops-copilot'], resolutions: '502', denied: '—' },
  { secret: 'vault:SLACK_BOT_TOKEN', consumers: ['3 agents'], resolutions: '214', denied: '—' },
  { secret: 'vault:helpdesk-api', consumers: ['support-triage'], resolutions: '556', denied: '1 · no grant', denied_bad: true },
]
