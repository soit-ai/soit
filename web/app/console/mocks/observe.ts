/**
 * Mock data for the Observe detail screens, mirroring the v13 prototype
 * sample content. Field names follow backend conventions (snake_case, *_id)
 * so swapping in the real services later is a shape-preserving change.
 * // BACKEND-PENDING: rundetail/tracedetail read from run-service and
 * // observe-service once P2 wiring replaces these fixtures.
 */
import type { ConsoleKind, ConsoleStatus } from '../components'

export interface MockLedgerStep {
  ix: string
  kind: string
  kind_color: string
  name: string
  detail: string
  left: number
  width: number
  duration: string
  status: ConsoleStatus
}

export interface MockGate {
  name: string
  rule: string
  status: ConsoleStatus
}

export interface MockEvidenceRow {
  name: string
  description: string
  refs?: string
  refs_missing?: string
  status: ConsoleStatus
}

export interface MockSemEvent {
  ix: string
  type: string
  payload: string
  at: string
}

export const mockRunDetail = {
  id: 'run_01J9KD7Z2M',
  verdict: 'pass' as ConsoleStatus,
  subject_kind: 'agent' as ConsoleKind,
  subject_id: 'ops-copilot',
  meta: [
    { key: 'Trigger', value: 'chat · thread_8f2c' },
    { key: 'Model', value: 'claude-sonnet-5' },
    { key: 'Started', value: '2026-08-28 13:45:31Z' },
    { key: 'Duration', value: '8.9s' },
    { key: 'Cost', value: '$0.038' },
    { key: 'Policy bundle', value: 'v2026.08.27-2' },
  ],
  tabs: { ledger: 7, gates: 2, checks: 13, events: 9, artifacts: 1 },
  ledger: [
    { ix: '01', kind: 'policy·gate', kind_color: 'var(--cat-pink)', name: 'intent-screen', detail: 'classified intent "restart staging pod" → allowed with constraints', left: 0, width: 2.5, duration: '0.21s', status: 'pass' },
    { ix: '02', kind: 'model·call', kind_color: 'var(--cat-blue)', name: 'plan', detail: 'claude-sonnet-5 · 1,842 in / 312 out tok · plan with 2 tool steps', left: 2.5, width: 21, duration: '1.87s', status: 'pass' },
    { ix: '03', kind: 'policy·gate', kind_color: 'var(--cat-pink)', name: 'tool-permission', detail: 'k8s.rollout_restart on ns/staging · scope matched grant g_44', left: 23.5, width: 1.5, duration: '0.13s', status: 'pass' },
    { ix: '04', kind: 'tool·call', kind_color: 'var(--cat-cyan)', name: 'k8s.rollout_restart', detail: 'deployment/checkout-api · ns/staging · secret ref vault:k8s-staging', left: 25, width: 38, duration: '3.38s', status: 'pass' },
    { ix: '05', kind: 'tool·call', kind_color: 'var(--cat-cyan)', name: 'k8s.rollout_status', detail: 'watch until ready · 12 replicas available', left: 63, width: 22, duration: '1.96s', status: 'pass' },
    { ix: '06', kind: 'model·call', kind_color: 'var(--cat-blue)', name: 'summarize', detail: 'claude-sonnet-5 · 640 in / 188 out tok · user-facing summary', left: 85, width: 11, duration: '0.98s', status: 'pass' },
    { ix: '07', kind: 'artifact', kind_color: 'var(--cat-teal)', name: 'run-report.md', detail: 'evidence bundle written · sha256:9f31…c2ae · retained 90d', left: 96, width: 4, duration: '0.37s', status: 'pass' },
  ] satisfies MockLedgerStep[],
  ledger_code: {
    command: 'soit runs replay run_01J9KD7Z2M --dry-run',
    output: 'replaying 7 steps against policy bundle v2026.08.27-2 … verdict unchanged: PASS',
  },
  gates: [
    { name: 'intent-screen', rule: 'rule: ops.intents.allowed · matched "infra.restart.staging"', status: 'pass' },
    { name: 'tool-permission', rule: 'rule: grants.g_44 · k8s.* on ns/staging · expires 2026-09-30', status: 'pass' },
  ] satisfies MockGate[],
  evidence_summary: { pass: 10, warn: 1, na: 2 },
  evidence: [
    { name: 'actor-scope', description: 'Run is tied to tenant, workspace, user and run identifiers.', refs: 'ws_acme-robotics · u_wei · run_01J9KD7Z2M', status: 'pass' },
    { name: 'subject-version', description: 'Run is tied to a versioned subject.', refs: 'agent · ops-copilot · agtv_0142', status: 'pass' },
    { name: 'capability-binding', description: 'Tool capabilities bound at plugin version level.', refs: 'k8s-toolkit v1.4.2 · pinned', status: 'pass' },
    { name: 'permission-scope', description: 'Explicit permission decision recorded per tool call.', refs: 'grant g_44 · 2 decisions', status: 'pass' },
    { name: 'secret-boundary', description: 'Secrets resolved by reference at call time, values never logged.', refs: 'vault:k8s-staging', status: 'pass' },
    { name: 'egress-policy', description: 'This run has no external egress surface.', status: 'na' },
    { name: 'audit-record', description: 'Gateway audit written for every governed tool call.', refs: '2 records · aud_77b2, aud_77b9', status: 'pass' },
    { name: 'cost-attribution', description: 'Cost entries attached per step.', refs: '4 entries · $0.038 total', status: 'pass' },
    { name: 'trace-timeline', description: 'Steps and spans correlated end to end.', refs: '7 steps · 31 spans · trace_4d19a2', status: 'pass' },
    { name: 'tool-call', description: 'Tool calls recorded with I/O digests.', refs: '2 calls · sha256 digests attached', status: 'pass' },
    { name: 'knowledge-citation', description: 'No knowledge citations attached although the runbooks KB is bound.', refs_missing: 'missing: citations', status: 'warn' },
    { name: 'child-workflow', description: 'No child workflow runs were triggered.', status: 'na' },
    { name: 'replay-ready', description: 'Inputs, policy bundle and step I/O retained for deterministic replay.', refs: 'sha256:2b77…91d0 · 90d retention', status: 'pass' },
  ] satisfies MockEvidenceRow[],
  policy_code: '{ "verdict": "pass", "gates": 2, "evidence": { "pass": 10, "warn": 1, "na": 2 }, "bundle": "v2026.08.27-2", "replayable": true }',
  events: [
    { ix: '#1', type: 'RUN_STARTED', payload: '{"threadId":"thread_8f2c","runId":"run_01J9KD7Z2M"}', at: '45:31.204' },
    { ix: '#2', type: 'CUSTOM · soit.resources', payload: '{"schemaVersion":1,"executionRunId":"run_01J9KD7Z2M","policyBundle":"v2026.08.27-2"}', at: '45:31.290' },
    { ix: '#3', type: 'ACTIVITY_SNAPSHOT', payload: '{"activityType":"soit.agent.plan","status":"running","iteration":1}', at: '45:31.420' },
    { ix: '#4', type: 'TOOL_CALL_START', payload: '{"tool":"k8s.rollout_restart","grant":"g_44","secretRef":"vault:k8s-staging"}', at: '45:33.510' },
    { ix: '#5', type: 'TOOL_CALL_END', payload: '{"tool":"k8s.rollout_restart","status":"ok","durationMs":3380}', at: '45:36.890' },
    { ix: '#6', type: 'TOOL_CALL_START', payload: '{"tool":"k8s.rollout_status"}', at: '45:36.930' },
    { ix: '#7', type: 'TOOL_CALL_END', payload: '{"tool":"k8s.rollout_status","status":"ok","durationMs":1960}', at: '45:38.910' },
    { ix: '#8', type: 'TEXT_MESSAGE_CONTENT', payload: '{"messageId":"msg_a06b","delta":"Restarted deployment/checkout-api in ns/staging…"}', at: '45:39.880' },
    { ix: '#9', type: 'RUN_FINISHED', payload: '{"verdict":"pass","costUsd":0.038,"durationMs":8900}', at: '45:40.104' },
  ] satisfies MockSemEvent[],
  events_code: {
    command: 'soit runs events run_01J9KD7Z2M --follow',
    output: '9 events · same stream the Chat surface renders from',
  },
  artifacts: [
    { name: 'run-report.md', type: 'markdown', digest: 'sha256:9f31…c2ae', size: '4.2 KB' },
  ],
  raw: `{
  "run_id": "run_01J9KD7Z2M",
  "agent": "ops-copilot",
  "trigger": { "type": "chat", "thread": "thread_8f2c" },
  "policy_bundle": "v2026.08.27-2",
  "verdict": "pass",
  "steps": 7,
  "cost_usd": 0.038,
  "duration_ms": 8900,
  "evidence_digest": "sha256:2b77…91d0"
}`,
  verdict_note: '2 gates evaluated pre-execution. No overrides. Verdict reproducible via replay.',
  chain: [
    { title: 'Intent captured', detail: '13:45:31.204Z · chat message' },
    { title: 'Policy evaluated', detail: '2 gates · bundle v2026.08.27-2' },
    { title: 'Execution observed', detail: '7 steps · full trace + I/O digests' },
    { title: 'Evidence retained', detail: 'sha256:2b77…91d0 · 90d retention' },
  ],
  cost_breakdown: [
    { key: 'Model tokens', value: '$0.031' },
    { key: 'Tool compute', value: '$0.006' },
    { key: 'Storage', value: '$0.001' },
    { key: 'Total', value: '$0.038' },
  ],
  context: [
    { key: 'Workspace', value: 'acme-robotics' },
    { key: 'Environment', value: 'production' },
    { key: 'Thread', value: 'thread_8f2c', link: true },
    { key: 'Trace', value: 'trace_4d19a2', link: true, to: '/v2/observe/traces/trace_4d19a2' },
    { key: 'Requested by', value: 'wei@acme.io' },
  ],
}

export interface MockBreakdownSlice {
  kind: 'policy' | 'model' | 'tool' | 'artifact'
  pct: number
}

export const BREAKDOWN_COLOR: Record<MockBreakdownSlice['kind'], string> = {
  policy: 'var(--cat-pink)',
  model: 'var(--cat-blue)',
  tool: 'var(--cat-cyan)',
  artifact: 'var(--cat-teal)',
}

export interface MockTraceRow {
  trace_id: string
  root_op: string
  run_id: string
  subject_kind: ConsoleKind
  subject_id: string
  subject_color: string
  span_count: number
  breakdown: MockBreakdownSlice[]
  duration: string
  started: string
}

export const mockTraceTiles = {
  spans_indexed: '41,208',
  spans_sub: 'across 1,284 runs',
  p95: '9.6s',
  p95_sub: 'p50 3.1s · p99 24.8s',
  slowest_op: 'k8s.rollout_status',
  slowest_sub: 'p95 4.1s · tool·call',
  error_rate: '0.6%',
  error_sub: '241 of 41,208 spans',
}

export const mockTraces: MockTraceRow[] = [
  { trace_id: 'trace_4d19a2', root_op: 'agent.run / ops-copilot', run_id: 'run_01J9KD7Z2M', subject_kind: 'workflow', subject_id: 'ops-copilot', subject_color: 'var(--cat-purple)', span_count: 31, breakdown: [{ kind: 'policy', pct: 4 }, { kind: 'model', pct: 32 }, { kind: 'tool', pct: 60 }, { kind: 'artifact', pct: 4 }], duration: '8.9s', started: '13:45:31Z' },
  { trace_id: 'trace_9c02f7', root_op: 'wf.run / docs-nightly-sync', run_id: 'run_01J9KD4XN2', subject_kind: 'knowledge', subject_id: 'kb-refresher', subject_color: 'var(--cat-teal)', span_count: 88, breakdown: [{ kind: 'policy', pct: 2 }, { kind: 'model', pct: 18 }, { kind: 'tool', pct: 71 }, { kind: 'artifact', pct: 9 }], duration: '21.7s', started: '13:25:19Z' },
  { trace_id: 'trace_71b8ce', root_op: 'agent.run / ops-copilot', run_id: 'run_01J9KCZQ1D', subject_kind: 'workflow', subject_id: 'ops-copilot', subject_color: 'var(--cat-purple)', span_count: 46, breakdown: [{ kind: 'policy', pct: 3 }, { kind: 'model', pct: 41 }, { kind: 'tool', pct: 52 }, { kind: 'artifact', pct: 4 }], duration: '14.2s', started: '12:31:48Z' },
  { trace_id: 'trace_e344d1', root_op: 'agent.run / billing-audit', run_id: 'run_01J9KCYW7N', subject_kind: 'tool', subject_id: 'billing-audit', subject_color: 'var(--cat-indigo)', span_count: 27, breakdown: [{ kind: 'policy', pct: 5 }, { kind: 'model', pct: 24 }, { kind: 'tool', pct: 63 }, { kind: 'artifact', pct: 8 }], duration: '7.7s', started: '12:08:02Z' },
  { trace_id: 'trace_ab55e0', root_op: 'wf.run / ticket-escalation', run_id: 'run_01J9KD1T4H', subject_kind: 'plugin', subject_id: 'support-triage', subject_color: 'var(--cat-cyan)', span_count: 22, breakdown: [{ kind: 'policy', pct: 6 }, { kind: 'model', pct: 47 }, { kind: 'tool', pct: 42 }, { kind: 'artifact', pct: 5 }], duration: '3.8s', started: '12:58:03Z' },
  { trace_id: 'trace_50c9b4', root_op: 'wf.run / invoice-reconcile', run_id: 'run_01J9KD6H0T', subject_kind: 'tool', subject_id: 'billing-audit', subject_color: 'var(--cat-indigo)', span_count: 9, breakdown: [{ kind: 'policy', pct: 21 }, { kind: 'model', pct: 68 }, { kind: 'tool', pct: 11 }], duration: '1.2s', started: '13:38:02Z' },
]

export interface MockSpan {
  id: string
  name: string
  bold?: boolean
  child?: boolean
  expandable?: boolean
  kind: string
  color: string
  left: number
  width: number
  duration: string
  /** Right-rail detail when this span is selected. */
  detail?: {
    span: { key: string; value: string; ok?: boolean }[]
    attributes: { key: string; value: string }[]
    events: { key: string; value: string }[]
  }
}

export const mockTraceDetail = {
  id: 'trace_4d19a2',
  status: 'pass' as ConsoleStatus,
  status_label: 'OK',
  subject_id: 'ops-copilot',
  subject_color: 'var(--cat-purple)',
  run_id: 'run_01J9KD7Z2M',
  meta: [
    { key: 'Root operation', value: 'agent.run / ops-copilot' },
    { key: 'Run', value: 'run_01J9KD7Z2M', link: true, to: '/v2/observe/runs/run_01J9KD7Z2M' },
    { key: 'Spans', value: '31 · 15 shown' },
    { key: 'Duration', value: '8.9s' },
    { key: 'Started', value: '2026-08-28 13:45:31.204Z' },
    { key: 'Evidence digest', value: 'sha256:2b77…91d0' },
  ],
  ticks: ['0s', '2.2s', '4.4s', '6.7s', '8.9s'],
  breakdown: [
    { kind: 'policy', pct: 4 },
    { kind: 'model', pct: 32 },
    { kind: 'tool', pct: 60 },
    { kind: 'artifact', pct: 4 },
  ] satisfies MockBreakdownSlice[],
  breakdown_rows: [
    { key: 'tool', value: '5.34s · 60%' },
    { key: 'model', value: '2.85s · 32%' },
    { key: 'policy', value: '0.34s · 4%' },
    { key: 'artifact', value: '0.37s · 4%' },
  ],
  code: {
    command: 'soit traces get trace_4d19a2 --format otlp-json > trace.json',
    output: '31 spans · evidence digest matches run_01J9KD7Z2M ✓',
  },
  spans: [
    { id: 'span_root', name: 'agent.run', bold: true, expandable: true, kind: 'root', color: 'var(--cat-slate)', left: 0, width: 100, duration: '8.90s' },
    { id: 'span_gate1', name: 'policy.gate intent-screen', expandable: true, kind: 'policy', color: 'var(--cat-pink)', left: 0, width: 2.4, duration: '0.21s' },
    { id: 'span_eval', name: 'policy.eval · 4 rules', child: true, kind: 'policy', color: 'var(--cat-pink)', left: 0.4, width: 1.8, duration: '0.16s' },
    { id: 'span_plan', name: 'model.call plan', expandable: true, kind: 'model', color: 'var(--cat-blue)', left: 2.4, width: 21, duration: '1.87s' },
    { id: 'span_req', name: 'model.request · claude-sonnet-5 · 1,842 in / 312 out', child: true, kind: 'model', color: 'var(--cat-blue)', left: 3, width: 19.6, duration: '1.74s' },
    { id: 'span_gate2', name: 'policy.gate tool-permission', kind: 'policy', color: 'var(--cat-pink)', left: 23.5, width: 1.5, duration: '0.13s' },
    {
      id: 'span_9f21c0', name: 'tool.call k8s.rollout_restart', bold: true, expandable: true, kind: 'tool', color: 'var(--cat-cyan)', left: 25, width: 38, duration: '3.38s',
      detail: {
        span: [
          { key: 'Span id', value: 'span_9f21c0' },
          { key: 'Parent', value: 'agent.run' },
          { key: 'Kind', value: 'tool·call' },
          { key: 'Service', value: 'k8s-toolkit v1.4.2' },
          { key: 'Started', value: '+2.21s' },
          { key: 'Duration', value: '3.38s' },
          { key: 'Status', value: 'OK', ok: true },
        ],
        attributes: [
          { key: 'k8s.namespace', value: 'staging' },
          { key: 'k8s.deployment', value: 'checkout-api' },
          { key: 'secret.ref', value: 'vault:k8s-staging' },
          { key: 'grant', value: 'g_44' },
          { key: 'retry.count', value: '0' },
        ],
        events: [
          { key: '+2.79s', value: 'patch accepted' },
          { key: '+5.52s', value: '12 replicas ready' },
        ],
      },
    },
    { id: 'span_secret', name: 'secret.resolve · vault:k8s-staging', child: true, kind: 'secret', color: 'var(--cat-slate)', left: 25.2, width: 1.2, duration: '0.11s' },
    { id: 'span_patch', name: 'k8s.api · patch deployment/checkout-api', child: true, kind: 'tool', color: 'var(--cat-cyan)', left: 26.8, width: 6.5, duration: '0.58s' },
    { id: 'span_watch', name: 'k8s.api · watch rollout until ready', child: true, kind: 'tool', color: 'var(--cat-cyan)', left: 33.6, width: 29, duration: '2.58s' },
    { id: 'span_status', name: 'tool.call k8s.rollout_status', expandable: true, kind: 'tool', color: 'var(--cat-cyan)', left: 63, width: 22, duration: '1.96s' },
    { id: 'span_get', name: 'k8s.api · get status · 3 calls', child: true, kind: 'tool', color: 'var(--cat-cyan)', left: 63.5, width: 21, duration: '1.87s' },
    { id: 'span_sum', name: 'model.call summarize', expandable: true, kind: 'model', color: 'var(--cat-blue)', left: 85, width: 11, duration: '0.98s' },
    { id: 'span_art', name: 'artifact.write run-report.md', expandable: true, kind: 'artifact', color: 'var(--cat-teal)', left: 96, width: 4, duration: '0.37s' },
    { id: 'span_store', name: 'store.put · evidence bundle · sha256', child: true, kind: 'artifact', color: 'var(--cat-teal)', left: 96.6, width: 3.2, duration: '0.29s' },
  ] satisfies MockSpan[],
  default_selected: 'span_9f21c0',
}
