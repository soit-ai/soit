/**
 * Mock data for Build · Agents, mirroring the v13 prototype samples.
 * // BACKEND-PENDING: library/exceptions/recycle wire to agent-service;
 * // marketplace and publish review stay mock-first.
 */
import type { ConsoleStatus } from '../components'

export const mockAgentTiles = {
  agents: { value: '6', sub: '5 enabled · 1 paused' },
  runs: { value: '973', delta: '+9.1%', sub: 'vs prev 24h' },
  pass: { value: '97.6%', sub: '952 pass · 14 degraded · 7 blocked' },
  attention: { value: '3', sub: '1 publish review · 2 exceptions' },
}

export interface MockAgentCard {
  id: string
  name: string
  color: string
  model_trigger: string
  description: string
  stats: { runs: string; pass: string; spend: string }
  enabled: boolean
  last_run: string
}

export const mockAgentCards: MockAgentCard[] = [
  { id: 'support-triage', name: 'support-triage', color: 'var(--cat-cyan)', model_trigger: 'claude-sonnet-5 · webhook', description: 'Classifies inbound tickets, drafts replies, escalates on low confidence. Egress limited to helpdesk API.', stats: { runs: '412', pass: '98.3%', spend: '$11.20' }, enabled: true, last_run: '13:47Z' },
  { id: 'ops-copilot', name: 'ops-copilot', color: 'var(--cat-purple)', model_trigger: 'claude-sonnet-5 · chat', description: 'Chat-driven infra operations with per-tool grants: restarts, scaling, log pulls. Everything gated and replayable.', stats: { runs: '287', pass: '97.9%', spend: '$16.44' }, enabled: true, last_run: '13:45Z' },
  { id: 'kb-refresher', name: 'kb-refresher', color: 'var(--cat-teal)', model_trigger: 'qwen3-235b · schedule', description: 'Nightly sync of product docs into knowledge bases; re-chunks, re-embeds and reports drift.', stats: { runs: '96', pass: '93.7%', spend: '$8.02' }, enabled: true, last_run: '13:25Z' },
  { id: 'billing-audit', name: 'billing-audit', color: 'var(--cat-indigo)', model_trigger: 'claude-haiku-4.5 · schedule', description: 'Hourly reconciliation of usage metering against invoices. Strict egress allowlist; blocked calls surface here.', stats: { runs: '64', pass: '90.6%', spend: '$2.87' }, enabled: true, last_run: '13:38Z' },
  { id: 'release-notes', name: 'release-notes', color: 'var(--cat-pink)', model_trigger: 'claude-sonnet-5 · api', description: 'Turns merged PRs into customer-facing release notes; drafts stay internal until human publish.', stats: { runs: '18', pass: '100%', spend: '$1.94' }, enabled: true, last_run: '13:04Z' },
  { id: 'quota-sentinel', name: 'quota-sentinel', color: 'var(--cat-amber)', model_trigger: 'claude-haiku-4.5 · schedule', description: 'Watches per-team model quotas and files notifications before limits bite. Read-only toolset.', stats: { runs: '96', pass: '100%', spend: '$0.85' }, enabled: false, last_run: '12:45Z' },
]

export interface MockAgentLibraryRow {
  id: string
  color: string
  version: string
  capabilities: string[]
  owner: string
  runs: string
  updated: string
}

export const mockAgentLibrary: MockAgentLibraryRow[] = [
  { id: 'support-triage', color: 'var(--cat-cyan)', version: 'v12 · published', capabilities: ['helpdesk-api', 'web-fetch', 'skill · incident-writeup'], owner: 'Wei', runs: '412', updated: '2d ago' },
  { id: 'ops-copilot', color: 'var(--cat-purple)', version: 'v9 · published', capabilities: ['k8s-toolkit', 'vault-secrets'], owner: 'Jude', runs: '287', updated: '5d ago' },
  { id: 'kb-refresher', color: 'var(--cat-teal)', version: 'v22 · published', capabilities: ['web-fetch'], owner: 'Jude', runs: '96', updated: '8h ago' },
  { id: 'billing-audit', color: 'var(--cat-indigo)', version: 'v6 · published', capabilities: ['erp-connector'], owner: 'Wei', runs: '64', updated: '14d ago' },
  { id: 'release-notes', color: 'var(--cat-pink)', version: 'v5 · published · v6 in review', capabilities: ['web-fetch'], owner: 'Wei', runs: '18', updated: '1d ago' },
  { id: 'quota-sentinel', color: 'var(--cat-amber)', version: 'v3 · paused', capabilities: ['read-only'], owner: 'Jude', runs: '96', updated: '21d ago' },
]

export const mockAgentMarket = [
  { name: 'Incident Scribe', color: 'var(--cat-blue)', origin: 'template · soit-labs', description: 'Turns pages and alerts into structured incident timelines with evidence links.', needs: 'needs: chat-ops scopes' },
  { name: 'SRE Toolkit Agent', color: 'var(--cat-cyan)', origin: 'template · soit-labs', description: 'Restart, scale and log-pull playbooks pre-wired to k8s-toolkit grants.', needs: 'needs: k8s.* grant' },
  { name: 'Finance Reconciler', color: 'var(--cat-indigo)', origin: 'template · community', description: 'Ledger diff and journal drafting with a mandatory human-approval gate.', needs: 'needs: approval gate' },
]

export const mockAgentReview = [
  { id: 'release-notes', color: 'var(--cat-pink)', change: 'v5 → v6 · prompt rewrite + adds web-fetch scope', requested_by: 'Wei', waiting: '3h' },
]

export interface MockAgentException {
  id: string
  color: string
  status: ConsoleStatus
  status_label: string
  detail: string
  failed: string
  run_id: string
}

export const mockAgentExceptions: MockAgentException[] = [
  { id: 'billing-audit', color: 'var(--cat-indigo)', status: 'blocked', status_label: 'BLOCKED', detail: 'egress destination not in allowlist', failed: '3', run_id: 'run_01J9KD6H0T' },
  { id: 'kb-refresher', color: 'var(--cat-teal)', status: 'warn', status_label: 'DEGRADED', detail: 'embedding endpoint timeout · retried', failed: '2', run_id: 'run_01J9KD4XN2' },
]

export const mockAgentRecycle = [
  { id: 'demo-onboarding', color: 'var(--cat-slate)', deleted_by: 'Jude', deleted: '2026-08-20', purged_in: '22d' },
]
