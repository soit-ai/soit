/**
 * Side-panel fixtures for the groups the prototype shows but no service can
 * answer yet.
 *
 * // BACKEND-PENDING: four of the panel's groups have no endpoint behind them —
 * // workspace day-figures (`Today`), user-pinned objects (`Pinned`), saved run
 * // filters (`Saved views`) and the review queue for drafts. They are kept here
 * // rather than inline so a grep for `mocks/` still finds every invented figure
 * // in the shell, and so deleting this file is all it takes to retire them.
 *
 * Everything else in the panel — counts, recents, the execute queue, live runs,
 * chat threads — reads its real service and is absent when that service fails.
 */

/** A `.sl` row whose `.ct` is a formatted figure rather than a bare count. */
export interface MockPanelStat {
  id: string
  label: string
  value: string
  to: string
}

/** A `.sub-mini` row: object, when it moved, one line of context. */
export interface MockPanelMini {
  id: string
  label: string
  /** The mono fragment on the row's bold line (object kind, or a time). */
  meta: string
  note: string
  to: string
}

/** A `.sub-note` row: a toned dot, a sentence, an optional figure. */
export interface MockPanelNote {
  id: string
  label: string
  tone: 'primary' | 'warn' | 'bad'
  value?: string
  to: string
}

/** Overview › Today — a workspace day-summary endpoint does not exist. */
export const mockTodayStats: MockPanelStat[] = [
  { id: 'runs', label: 'Runs · 24h', value: '1,284', to: '/observe/runs' },
  { id: 'pass', label: 'Policy pass rate', value: '96.4%', to: '/observe/runs' },
  { id: 'spend', label: 'Spend', value: '$41.32', to: '/observe/runs' },
]

/** Overview › Pinned — nothing in the API models a per-user pin. */
export const mockPinned: MockPanelMini[] = [
  { id: 'pin-task', label: 'invoice-reconcile', meta: 'task', note: 'awaiting approval · 1h 12m', to: '/execute/tasks' },
  { id: 'pin-bundle', label: 'v2026.08.28-1', meta: 'bundle', note: 'staged rollout · 10% of runs', to: '/govern/policies' },
  { id: 'pin-kb', label: 'product-docs', meta: 'kb', note: 'synced 8h ago · 91% hit rate', to: '/build/knowledge' },
]

/** Observe › Saved views — run filters are not persisted server-side. */
export const mockSavedViews: MockPanelStat[] = [
  { id: 'failed', label: 'Failed only', value: '15', to: '/observe/runs?status=failed' },
  { id: 'audited', label: 'Has audit', value: '156', to: '/observe/runs?audited=true' },
  { id: 'degraded', label: 'Degraded · 24h', value: '31', to: '/observe/runs?status=degraded' },
  { id: 'slow', label: 'Slow traces > 5s', value: '42', to: '/observe/traces?min_duration=5000' },
]

/** Build › Drafts awaiting review — drafts carry no review state yet. */
export const mockDraftReviews: MockPanelNote[] = [
  { id: 'release-notes', label: 'release-notes v6 · scope change', tone: 'warn', value: '3h', to: '/build/agents' },
]

/* ---------------------------------------------------------------------------
 * Figures the prototype shows that no endpoint can answer yet.
 *
 * // BACKEND-PENDING: each entry below names an API that has to exist before it
 * // can go live. They are fallbacks, never overrides — `use-console-counts`
 * // prefers a real figure wherever a service answers, so shipping the endpoint
 * // is enough to retire the fixture without touching the panel.
 * ------------------------------------------------------------------------- */

/**
 * The one side-panel link figure with no service behind it: policy bundles are
 * not versioned server-side, so there is no active-bundle identifier to read.
 *
 * Runs, traces, audit and access used to sit here too. They now read counted
 * endpoints, so their figures are measurements.
 */
export const mockPanelCounts = {
  policies: 'v08.27-2',
} as const

/**
 * Govern › Needs attention — the row below the live approvals row.
 *
 * // BACKEND-PENDING: staged rollout needs policy-bundle versioning with a
 * // rollout percentage and a regression count.
 *
 * Egress blocks used to sit here. They are now counted from the audit ledger,
 * which records every refused outbound request.
 */
export const mockGovernAttention: MockPanelNote[] = [
  { id: 'rollout', label: 'Staged rollout at 10%', tone: 'primary', value: '0 regressions', to: '/govern/policies' },
]
