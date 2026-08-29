/**
 * Schedule fixtures for the Execute pillar.
 *
 * // BACKEND-PENDING: schedules are the only console object with no server side
 * // at all — no model, no service, no route. Every other Execute screen reads
 * // its real service, so these rows exist purely to hold the design of an
 * // unbuilt feature and must never be mistaken for live state.
 */
import type { ConsoleStatus } from '../components'

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
