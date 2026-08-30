/**
 * Side-panel fixture for the one thing the prototype shows that no service can
 * answer yet.
 *
 * // BACKEND-PENDING: the review queue for drafts, which carry no review state
 * // server-side. It is kept here rather than inline so a grep for `mocks/`
 * // still finds every invented figure in the shell, and so deleting this file
 * // is all it takes to retire it.
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
