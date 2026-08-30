/**
 * Side-panel fixtures for the two things the prototype shows that no service
 * can answer yet.
 *
 * // BACKEND-PENDING: the review queue for drafts (drafts carry no review
 * // state) and the policy bundle version with its staged rollout (policy is
 * // not versioned server-side). They are kept here rather than inline so a
 * // grep for `mocks/` still finds every invented figure in the shell, and so
 * // deleting this file is all it takes to retire them.
 *
 * Everything else in the panel — counts, today's figures, pins, saved views,
 * recents, the execute queue, live runs, chat threads — reads its real service
 * and is absent when that service fails.
 */

/** A `.sub-note` row: a toned dot, a sentence, an optional figure. */
export interface MockPanelNote {
  id: string
  label: string
  tone: 'primary' | 'warn' | 'bad'
  value?: string
  to: string
}

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
