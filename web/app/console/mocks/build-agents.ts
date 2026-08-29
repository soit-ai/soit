/**
 * Marketplace and publish-review fixtures for the Agents workbench.
 *
 * // BACKEND-PENDING: neither object exists server-side. There is no agent
 * // marketplace or catalogue endpoint, and no publish-review queue — publishing
 * // is a direct POST /agents/{id}/publish with no gate in front of it. Every
 * // other tab on that screen reads agent-service; these two hold the design of
 * // features that have not been built.
 */
export const mockAgentMarket = [
  { name: 'Incident Scribe', color: 'var(--cat-blue)', origin: 'template · soit-labs', description: 'Turns pages and alerts into structured incident timelines with evidence links.', needs: 'needs: chat-ops scopes' },
  { name: 'SRE Toolkit Agent', color: 'var(--cat-cyan)', origin: 'template · soit-labs', description: 'Restart, scale and log-pull playbooks pre-wired to k8s-toolkit grants.', needs: 'needs: k8s.* grant' },
  { name: 'Finance Reconciler', color: 'var(--cat-indigo)', origin: 'template · community', description: 'Ledger diff and journal drafting with a mandatory human-approval gate.', needs: 'needs: approval gate' },
]

export const mockAgentReview = [
  { id: 'release-notes', color: 'var(--cat-pink)', change: 'v5 → v6 · prompt rewrite + adds web-fetch scope', requested_by: 'Wei', waiting: '3h' },
]
