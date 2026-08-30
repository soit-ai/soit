/**
 * Marketplace fixture for the Agents workbench.
 *
 * // BACKEND-PENDING: there is no agent marketplace. No catalogue, template
 * // registry or install endpoint exists server-side. The cards below hold the
 * // design of that idea and nothing else on the screen depends on them, so
 * // deleting this file is all it takes to drop the tab.
 *
 * Publish review used to live here too. Drafts now carry a review state, so
 * that tab reads `GET /agents/drafts/awaiting-review`.
 */
export const mockAgentMarket = [
  { name: 'Incident Scribe', color: 'var(--cat-blue)', origin: 'template · soit-labs', description: 'Turns pages and alerts into structured incident timelines with evidence links.', needs: 'needs: chat-ops scopes' },
  { name: 'SRE Toolkit Agent', color: 'var(--cat-cyan)', origin: 'template · soit-labs', description: 'Restart, scale and log-pull playbooks pre-wired to k8s-toolkit grants.', needs: 'needs: k8s.* grant' },
  { name: 'Finance Reconciler', color: 'var(--cat-indigo)', origin: 'template · community', description: 'Ledger diff and journal drafting with a mandatory human-approval gate.', needs: 'needs: approval gate' },
]
