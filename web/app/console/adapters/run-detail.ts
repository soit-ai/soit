/**
 * Maps the run-service detail payload onto the prototype's run-detail view
 * model. The page renders the same shape whether it came from fixtures or the
 * API, so the layout stays 1:1 with the v13 prototype and only the source
 * changes. Server-computed governance evidence (the 13 checks) passes through
 * verbatim — the console never recomputes a verdict.
 */
import type {
  RunArtifactResponse,
  RunCostEntryResponse,
  RunDetailResponse,
  RunGovernanceEvidence,
  RunResponseEvent,
  RunStepResponse,
} from '@/services/run-service'

import { runStatusToConsole, type ConsoleStatus } from '../components/status-chip'
import type { ConsoleKind } from '../components/kind-chip'
import { CONSOLE_KIND_COLOR } from '../components/kind-chip'

export interface RunDetailView {
  id: string
  verdict: ConsoleStatus
  subject_kind: ConsoleKind
  subject_id: string
  meta: Array<{ key: string; value: string }>
  tabs: { ledger: number; gates: number; checks: number; events: number; artifacts: number }
  ledger: Array<{
    ix: string
    kind: string
    kind_color: string
    name: string
    detail: string
    left: number
    width: number
    duration: string
    status: ConsoleStatus
  }>
  ledger_code: { command: string; output: string }
  gates: Array<{ name: string; rule: string; status: ConsoleStatus }>
  evidence_summary: { pass: number; warn: number; na: number }
  evidence: Array<{
    name: string
    description: string
    refs?: string
    refs_missing?: string
    status: ConsoleStatus
  }>
  policy_code: string
  events: Array<{ ix: string; type: string; payload: string; at: string }>
  events_code: { command: string; output: string }
  artifacts: Array<{ name: string; type: string; digest: string; size: string }>
  raw: string
  verdict_note: string
  chain: Array<{ title: string; detail: string }>
  cost_breakdown: Array<{ key: string; value: string }>
  context: Array<{ key: string; value: string; link?: boolean; to?: string }>
}

const STEP_KIND_COLOR: Record<string, string> = {
  policy: 'var(--cat-pink)',
  gate: 'var(--cat-pink)',
  model: 'var(--cat-blue)',
  llm: 'var(--cat-blue)',
  tool: 'var(--cat-cyan)',
  artifact: 'var(--cat-teal)',
  knowledge: 'var(--cat-indigo)',
  workflow: 'var(--cat-purple)',
}

/** Prototype kind chips read "policy·gate", "model·call", "tool·call". */
function stepKindLabel(stepType: string): string {
  return stepType.replace(/[_.]/g, '·')
}

function stepKindColor(stepType: string): string {
  const head = stepType.split(/[_.·]/)[0]?.toLowerCase() || ''
  return STEP_KIND_COLOR[head] || 'var(--cat-slate)'
}

function ms(from?: string | null, to?: string | null): number | null {
  if (!from || !to) return null
  const start = new Date(from).getTime()
  const end = new Date(to).getTime()
  if (Number.isNaN(start) || Number.isNaN(end)) return null
  return end - start
}

export function formatDurationMs(value?: number | null): string {
  if (value == null) return '—'
  if (value >= 60_000) return `${(value / 60_000).toFixed(1)}m`
  if (value >= 1000) return `${(value / 1000).toFixed(2)}s`
  return `${value}ms`
}

function formatBytes(value?: number | null): string {
  if (value == null) return '—'
  if (value >= 1_048_576) return `${(value / 1_048_576).toFixed(1)} MB`
  if (value >= 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${value} B`
}

function shortDigest(sha?: string | null): string {
  if (!sha) return '—'
  const bare = sha.replace(/^sha256:/, '')
  if (bare.length <= 12) return `sha256:${bare}`
  return `sha256:${bare.slice(0, 4)}…${bare.slice(-4)}`
}

function clockTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

/** The prototype's semantic timeline stamps mm:ss.mmm within the run. */
function eventStamp(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return date.toISOString().slice(14, 23)
}

function sumAmount(costs: RunCostEntryResponse[]): string {
  const total = costs.reduce((acc, entry) => acc + Number(entry.amount || 0), 0)
  if (!Number.isFinite(total) || total === 0) return '—'
  return `$${total.toFixed(3)}`
}

function evidenceStatus(status: RunGovernanceEvidence['status']): ConsoleStatus {
  if (status === 'pass') return 'pass'
  if (status === 'warning') return 'warn'
  if (status === 'fail') return 'failed'
  return 'na'
}

function artifactName(artifact: RunArtifactResponse): string {
  const meta = artifact.meta_json as { name?: string; filename?: string } | null | undefined
  return meta?.name || meta?.filename || artifact.storage_key.split('/').pop() || artifact.id
}

/** Waterfall geometry: each step's offset and width as a % of the run window. */
function ledgerRows(run: RunDetailResponse): RunDetailView['ledger'] {
  const steps = run.steps
  if (steps.length === 0) return []
  const windowStart = new Date(run.run.started_at).getTime()
  const windowEnd = run.run.ended_at
    ? new Date(run.run.ended_at).getTime()
    : Math.max(
        ...steps.map((step) =>
          new Date(step.ended_at || step.started_at).getTime(),
        ),
      )
  const span = Math.max(1, windowEnd - windowStart)

  return steps.map((step: RunStepResponse, index) => {
    const startedAt = new Date(step.started_at).getTime()
    const duration = ms(step.started_at, step.ended_at)
    const left = Number.isNaN(startedAt) ? 0 : ((startedAt - windowStart) / span) * 100
    const width = duration == null ? 1 : (duration / span) * 100
    return {
      ix: String(index + 1).padStart(2, '0'),
      kind: stepKindLabel(step.step_type),
      kind_color: stepKindColor(step.step_type),
      name: step.node_id || step.step_id || step.step_type,
      detail: step.output_summary || step.input_summary || step.error_message || '',
      left: Math.max(0, Math.min(100, left)),
      width: Math.max(1, Math.min(100 - Math.max(0, left), width)),
      duration: formatDurationMs(duration),
      status: runStatusToConsole(step.status),
    }
  })
}

function gateRows(run: RunDetailResponse): RunDetailView['gates'] {
  return run.audits.map((audit) => ({
    name: audit.gateway_type || audit.step_type,
    rule: audit.preview || `step ${audit.step_id}`,
    status: runStatusToConsole(audit.outcome || 'unknown'),
  }))
}

function eventRows(events: RunResponseEvent[]): RunDetailView['events'] {
  return events.map((event) => ({
    ix: `#${event.sequence}`,
    type: event.type,
    payload: JSON.stringify(event.payload_json ?? {}),
    at: eventStamp(event.created_at),
  }))
}

export function toRunDetailView(detail: RunDetailResponse): RunDetailView {
  const { run } = detail
  const evidence = detail.governance_evidence || []
  const passCount = evidence.filter((row) => row.status === 'pass').length
  const warnCount = evidence.filter((row) => row.status === 'warning' || row.status === 'fail').length
  const naCount = evidence.filter((row) => row.status === 'not_applicable').length
  const totalCost = sumAmount(detail.costs || [])
  const modelRef = detail.costs?.find((entry) => entry.model_ref)?.model_ref || '—'
  const subjectKind = (run.subject_kind && run.subject_kind in CONSOLE_KIND_COLOR
    ? run.subject_kind
    : 'agent') as ConsoleKind

  return {
    id: run.id,
    verdict: runStatusToConsole(run.status),
    subject_kind: subjectKind,
    subject_id: run.subject_id || '—',
    meta: [
      { key: 'Trigger', value: run.mode },
      { key: 'Model', value: modelRef },
      { key: 'Started', value: run.started_at.replace('T', ' ').slice(0, 19) + 'Z' },
      { key: 'Duration', value: formatDurationMs(run.duration_ms) },
      { key: 'Cost', value: totalCost },
      { key: 'Attempt', value: `#${run.attempt_no}` },
    ],
    tabs: {
      ledger: detail.steps.length,
      gates: detail.audits.length,
      checks: evidence.length,
      events: detail.response_events.length,
      artifacts: detail.artifacts.length,
    },
    ledger: ledgerRows(detail),
    ledger_code: {
      command: `soit runs replay ${run.id} --dry-run`,
      output: `replaying ${detail.steps.length} steps · verdict on record: ${run.status}`,
    },
    gates: gateRows(detail),
    evidence_summary: { pass: passCount, warn: warnCount, na: naCount },
    evidence: evidence.map((row) => ({
      name: row.key,
      description: row.summary || row.label,
      refs: row.evidence_refs?.length ? row.evidence_refs.join(' · ') : undefined,
      refs_missing: row.missing?.length ? `missing: ${row.missing.join(', ')}` : undefined,
      status: evidenceStatus(row.status),
    })),
    policy_code: JSON.stringify({
      verdict: run.status,
      gates: detail.audits.length,
      evidence: { pass: passCount, warn: warnCount, na: naCount },
      replayable: detail.steps.length > 0,
    }),
    events: eventRows(detail.response_events || []),
    events_code: {
      command: `soit runs events ${run.id} --follow`,
      output: `${detail.response_events.length} events · same stream the Chat surface renders from`,
    },
    artifacts: (detail.artifacts || []).map((artifact) => ({
      name: artifactName(artifact),
      type: artifact.type || artifact.mime || '—',
      digest: shortDigest(artifact.sha256),
      size: formatBytes(artifact.size_bytes),
    })),
    raw: JSON.stringify(
      {
        run_id: run.id,
        subject: run.subject_id,
        mode: run.mode,
        status: run.status,
        steps: detail.steps.length,
        duration_ms: run.duration_ms,
        trace_id: run.trace_id,
      },
      null,
      2,
    ),
    verdict_note:
      run.error_message ||
      `${detail.audits.length} gateway audits recorded. Verdict reproducible via replay.`,
    chain: [
      { title: 'Intent captured', detail: `${clockTime(run.started_at)} · ${run.mode}` },
      { title: 'Policy evaluated', detail: `${detail.audits.length} gateway audits` },
      {
        title: 'Execution observed',
        detail: `${detail.steps.length} steps · ${detail.tool_calls.length} tool calls`,
      },
      { title: 'Evidence retained', detail: `${detail.artifacts.length} artifacts` },
    ],
    cost_breakdown: [
      {
        key: 'Prompt tokens',
        value: String(detail.usage_summary?.tokens_prompt ?? 0),
      },
      {
        key: 'Completion tokens',
        value: String(detail.usage_summary?.tokens_completion ?? 0),
      },
      { key: 'Cost entries', value: String(detail.costs?.length ?? 0) },
      { key: 'Total', value: totalCost },
    ],
    context: [
      { key: 'Workspace', value: run.subject_version_id || '—' },
      { key: 'Mode', value: run.mode },
      ...(run.trace_id
        ? [
            {
              key: 'Trace',
              value: run.trace_id,
              link: true,
              to: `/observe/traces/${run.trace_id}`,
            },
          ]
        : []),
      { key: 'Requested by', value: run.user_id || '—' },
    ],
  }
}
