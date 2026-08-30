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
  pluginInvocations: {
    value: '8,430',
    sub: 'tool calls + skill uses',
    reason: 'no per-plugin invocation counters are exposed',
  },
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
  traceErrorSpans: {
    value: '0.6%',
    sub: '241 of 41,208 spans',
    reason: 'no span-level error aggregation endpoint',
  },
  secretResolutions: {
    value: '3,214',
    sub: 'at call time · never logged',
    reason: 'secret resolutions are not counted server-side',
  },
  policyEvaluations: {
    value: '4,959',
    sub: '15 blocked · 0 overrides',
    reason: 'policy evaluations are not counted server-side',
  },
  taskQueued: {
    value: '3',
    sub: 'oldest 4m in queue',
    reason: 'the task summary reports no queue depth or queue age',
  },
  agentSpend: {
    value: '$11.20',
    sub: 'cap $12.00/day · 93%',
    reason: 'no per-agent cost rollup (/runs/costs/* aggregates only)',
  },
  /** Seats keeps the live member count as its numerator; only the licensed
   *  cap and the renewal date below are invented. */
  settingsSeats: {
    value: '25',
    sub: 'renewal 2027-03-01',
    reason: 'no licence record: seat cap, edition and renewal have no server object',
  },
} satisfies Record<string, MockTile>
