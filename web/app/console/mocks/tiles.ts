/**
 * Page-level tile fixtures, carrying the v13 prototype's own figures.
 *
 * // BACKEND-PENDING: every entry names the endpoint that has to exist before
 * // it can go live. Until then these tiles show the prototype's numbers rather
 * // than an em dash, so the console reads as designed; each `reason` is the
 * // work item that retires its fixture.
 *
 * Nothing here overrides a real measurement — these fill tiles that had no
 * service to read from at all. Grep `mocks/` to find every invented figure.
 */

export interface MockTile {
  value: string
  sub: string
  /** The API that has to ship before this tile can read a real figure. */
  reason: string
}

export const mockTiles = {
  pluginUpdates: {
    value: '1',
    sub: 'k8s-toolkit 1.4.2 → 1.5.0',
    reason: 'no version-check / available-upgrade endpoint',
  },
  pluginHighRisk: {
    value: '1',
    sub: 'finance.journal.post · approval-gated',
    reason: 'the plugin record carries no risk classification',
  },
  knowledgeHitRate: {
    value: '91%',
    sub: 'score ≥ 0.6 threshold',
    reason: 'no retrieval-quality aggregation endpoint',
  },
  knowledgeZeroHit: {
    value: '7.1%',
    sub: '169 queries · gap candidates',
    reason: 'query-text analytics are not persisted',
  },
  /** Seats keeps the live member count as its numerator; only the licensed
   *  cap and the renewal date below are invented. */
  settingsSeats: {
    value: '25',
    sub: 'renewal 2027-03-01',
    reason: 'no licence record: seat cap, edition and renewal have no server object',
  },
} satisfies Record<string, MockTile>
