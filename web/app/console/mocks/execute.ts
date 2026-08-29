/**
 * Mock data for the Execute pillar (tasks, schedules, inbound events),
 * mirroring the v13 prototype samples.
 * // BACKEND-PENDING: tasks wire to task-service; schedules and inbound
 * // events are new objects (mock-first per the rebuild plan).
 */
import type { ConsoleStatus } from '../components'

export interface MockTaskRow {
  id: string
  name: string
  note: string
  type: string
  status: ConsoleStatus
  status_label: string
  pct: number
  progress_label: string
  attempt: string
  run_id?: string
  updated: string
}

export const mockTaskTiles = {
  queued: { value: '3', sub: 'oldest 4m in queue' },
  processing: { value: '2', sub: '2 workers busy · 6 idle' },
  awaiting: { value: '2', sub: 'oldest waiting 1h 12m' },
  failed: { value: '1', sub: 'after 3 attempts · retry available' },
}

export const mockTaskCounts = { all: 14, queued: 3, processing: 2, awaiting: 2, done: 6, failed: 1 }

export const mockTasks: MockTaskRow[] = [
  { id: 'task_invoice', name: 'invoice-reconcile · monthly close', note: 'workflow · triggered by schedule', type: 'wf.batch', status: 'warn', status_label: 'AWAITING APPROVAL', pct: 72, progress_label: '6/7 steps', attempt: '1', run_id: 'run_01J9KCYW7N', updated: '12:38Z' },
  { id: 'task_churn', name: 'churn-signal-scan · Q3 backfill', note: 'agent batch · 4,812 accounts', type: 'agent.batch', status: 'running', status_label: 'PROCESSING', pct: 41, progress_label: '41%', attempt: '1', run_id: 'run_01J9KD9TB2', updated: 'just now' },
  { id: 'task_docs', name: 'docs-nightly-sync · full re-embed', note: 'workflow · manual trigger', type: 'wf.batch', status: 'running', status_label: 'PROCESSING', pct: 88, progress_label: '88%', attempt: '2', run_id: 'run_01J9KD8XM4', updated: '2m ago' },
  { id: 'task_evidence', name: 'evidence-export · 2026-07 bundle', note: 'compliance export · requested by audit', type: 'evidence.export', status: 'queued', status_label: 'QUEUED', pct: 0, progress_label: '—', attempt: '—', updated: '13:41Z' },
  { id: 'task_quota', name: 'quota-report · weekly finance', note: 'agent · schedule', type: 'agent.run', status: 'queued', status_label: 'QUEUED', pct: 0, progress_label: '—', attempt: '—', updated: '13:30Z' },
  { id: 'task_release', name: 'release-digest · week 35', note: 'workflow · schedule', type: 'wf.run', status: 'pass', status_label: 'DONE', pct: 100, progress_label: '5/5 steps', attempt: '1', run_id: 'run_01J9KD2M9C', updated: '13:04Z' },
  { id: 'task_billing', name: 'billing-audit · hourly reconcile', note: 'agent · schedule · egress blocked at step 2', type: 'agent.run', status: 'failed', status_label: 'FAILED', pct: 28, progress_label: '2/8 steps', attempt: '3/3', run_id: 'run_01J9KD6H0T', updated: '13:38Z' },
]

export const mockTaskPagerNote = 'workers 2/8 busy · throughput 41/h · P95 wait 3m 40s · retry 3× backoff'

export interface MockTaskEvent {
  tone: 'plain' | 'brand' | 'ok' | 'warn' | 'live'
  text: string
  mono?: string[]
  run_id?: string
  at: string
}

export const mockTaskDetail = {
  id: 'task_invoice',
  name: 'invoice-reconcile · monthly close',
  status: 'warn' as ConsoleStatus,
  status_label: 'AWAITING APPROVAL',
  pct: 72,
  progress_label: '6/7 steps',
  meta: [
    { key: 'Type', value: 'wf.batch' },
    { key: 'Workflow', value: 'invoice-reconcile · v8', link: true, to: '/v2/build/workflows/invoice-reconcile' },
    { key: 'Schedule', value: '0 2 1 * * · monthly' },
    { key: 'Owner', value: 'Wei' },
    { key: 'Attempt', value: '1 of 3' },
    { key: 'Started', value: '2026-08-28 12:02:11Z' },
    { key: 'Elapsed', value: '36m 12s' },
  ],
  events: [
    { tone: 'plain', text: 'Queued by schedule', mono: ['0 2 1 * *'], at: '12:02:11.004Z' },
    { tone: 'brand', text: 'Started on worker w-3 · policy bundle v2026.08.27-2', at: '12:02:14.180Z' },
    { tone: 'brand', text: 'Run started —', run_id: 'run_01J9KCYW7N', at: '12:02:20.412Z' },
    { tone: 'ok', text: 'Steps 1–4 completed · fetched 1,204 usage rows, diffed against 3 invoices', at: '12:19:44.902Z' },
    { tone: 'plain', text: 'Checkpoint ckpt_04 written after step 4 · 1.8 MB', at: '12:24:03.771Z' },
    { tone: 'warn', text: 'Step 5 retried — transient ERP timeout · attempt 2 succeeded in 4.1s', at: '12:31:47.230Z' },
    { tone: 'warn', text: 'Approval requested — gate human-approval · finance.journal.post · step 6 held', at: '12:38:02.518Z' },
    { tone: 'live', text: 'Waiting for approval · escalates to #finance-ops after 2h', at: 'now' },
  ] satisfies MockTaskEvent[],
  checkpoints: [
    { id: 'ckpt_04', after: '4 · diff complete', size: '1.8 MB', created: '12:24:03Z' },
    { id: 'ckpt_02', after: '2 · fetch complete', size: '1.1 MB', created: '12:08:19Z' },
  ],
  approval: {
    text: 'Post 14 journal entries to the ERP for the monthly close.',
    detail: 'gate human-approval · finance.journal.post · waiting 1h 12m',
  },
  configuration: [
    { key: 'Retry policy', value: '3× · backoff 2ⁿ min' },
    { key: 'Timeout', value: '2h hard' },
    { key: 'Priority', value: 'normal' },
    { key: 'On failure', value: 'notify #finance-ops' },
    { key: 'Checkpointing', value: 'after each step' },
  ],
  linked_runs: [
    { key: 'Attempt 1', value: 'run_01J9KCYW7N' },
    { key: 'Previous month', value: 'run_01J8VMK2P0' },
  ],
}

export interface MockScheduleRow {
  id: string
  name: string
  note: string
  cron: string
  target: string
  target_color: string
  next_fire: string
  outcome_run?: string
  outcome_note?: string
  outcome_status: ConsoleStatus
  outcome_label: string
  enabled: boolean
}

export const mockSchedules: MockScheduleRow[] = [
  { id: 'sch_billing', name: 'hourly-billing-audit', note: 'usage reconciliation', cron: '0 * * * *', target: 'billing-audit', target_color: 'var(--cat-indigo)', next_fire: 'in 22m', outcome_run: 'run_01J9KD6H0T', outcome_status: 'blocked', outcome_label: 'BLOCKED', enabled: true },
  { id: 'sch_docs', name: 'nightly-docs-sync', note: 'crawl → chunk → embed → verify', cron: '0 2 * * *', target: 'docs-nightly-sync', target_color: 'var(--cat-teal)', next_fire: 'in 3h 12m', outcome_run: 'run_01J9KCXK3B', outcome_status: 'pass', outcome_label: 'PASS', enabled: true },
  { id: 'sch_close', name: 'monthly-close', note: 'journal reconcile + approval gate', cron: '0 2 1 * *', target: 'invoice-reconcile', target_color: 'var(--cat-indigo)', next_fire: 'Sep 1 · 02:00Z', outcome_run: 'run_01J9KCYW7N', outcome_status: 'warn', outcome_label: 'AWAITING APPROVAL', enabled: true },
  { id: 'sch_quota', name: 'weekly-quota-report', note: 'usage by team → finance', cron: '0 9 * * 1', target: 'quota-sentinel', target_color: 'var(--cat-amber)', next_fire: 'paused', outcome_run: 'run_01J9KD0S8V', outcome_status: 'pass', outcome_label: 'PASS', enabled: false },
  { id: 'sch_retention', name: 'evidence-retention-sweep', note: 'expire artifacts past policy window', cron: '0 4 * * 0', target: 'system', target_color: 'var(--cat-slate)', next_fire: 'Sun 04:00Z', outcome_note: 'swept 1,204 artifacts', outcome_status: 'info', outcome_label: 'APPLIED', enabled: true },
]

export interface MockEventRow {
  id: string
  source: 'webhook' | 'schedule' | 'api' | 'chat'
  source_color: string
  type: string
  target?: string
  target_color?: string
  decision_status: ConsoleStatus
  decision_label: string
  decision_note?: string
  run_id?: string
  received: string
}

export const mockEventTiles = {
  total: { value: '892', sub: 'webhook 611 · schedule 214 · api 44 · chat 23' },
  accepted: { value: '861', sub: '96.5%' },
  deduped: { value: '18 / 9', sub: 'idempotency window 10m' },
  rejected: { value: '4', sub: 'signature or auth failure' },
}

export const mockEventCounts = { all: 892, webhook: 611, schedule: 214, api: 44, chat: 23 }

export const mockEvents: MockEventRow[] = [
  { id: 'evt_a91f04', source: 'webhook', source_color: 'var(--cat-amber)', type: 'ticket.created', target: 'support-triage', target_color: 'var(--cat-cyan)', decision_status: 'pass', decision_label: 'ACCEPTED', run_id: 'run_01J9KD84QF', received: '13:47:09Z' },
  { id: 'evt_a91ede', source: 'chat', source_color: 'var(--cat-purple)', type: 'thread.message', target: 'ops-copilot', target_color: 'var(--cat-purple)', decision_status: 'pass', decision_label: 'ACCEPTED', run_id: 'run_01J9KD7Z2M', received: '13:45:31Z' },
  { id: 'evt_a91e2b', source: 'webhook', source_color: 'var(--cat-amber)', type: 'ticket.created', target: 'support-triage', target_color: 'var(--cat-cyan)', decision_status: 'info', decision_label: 'DEDUPED', decision_note: 'same delivery id · 44s apart', received: '13:44:02Z' },
  { id: 'evt_a91d90', source: 'schedule', source_color: 'var(--cat-slate)', type: 'cron.fire · 0 * * * *', target: 'billing-audit', target_color: 'var(--cat-indigo)', decision_status: 'pass', decision_label: 'ACCEPTED', run_id: 'run_01J9KD6H0T', received: '13:38:00Z' },
  { id: 'evt_a91cd4', source: 'api', source_color: 'var(--cat-blue)', type: 'agent.invoke', target: 'release-notes', target_color: 'var(--cat-pink)', decision_status: 'pass', decision_label: 'ACCEPTED', run_id: 'run_01J9KD2M9C', received: '13:04:11Z' },
  { id: 'evt_a91c02', source: 'webhook', source_color: 'var(--cat-amber)', type: 'ticket.created', target: 'support-triage', target_color: 'var(--cat-cyan)', decision_status: 'warn', decision_label: 'RATE-LIMITED', decision_note: 'burst > 60/min · retried +30s', run_id: 'run_01J9KD1T4H', received: '12:57:33Z' },
  { id: 'evt_a91b77', source: 'webhook', source_color: 'var(--cat-amber)', type: 'ticket.created', decision_status: 'failed', decision_label: 'REJECTED', decision_note: 'signature verification failed', received: '12:41:18Z' },
  { id: 'evt_a91a40', source: 'api', source_color: 'var(--cat-blue)', type: 'agent.invoke', target: 'quota-sentinel', target_color: 'var(--cat-amber)', decision_status: 'failed', decision_label: 'REJECTED', decision_note: 'agent paused', received: '12:12:50Z' },
]
