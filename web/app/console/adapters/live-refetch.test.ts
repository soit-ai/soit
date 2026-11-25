import { describe, expect, it } from 'vitest'

import { liveRefetchInterval } from './live-refetch'

const interval = liveRefetchInterval((data: { status?: string }) => data.status)
const at = (status: string | undefined, dataUpdateCount = 1) =>
  interval({ state: { data: { status }, dataUpdateCount } })

describe('liveRefetchInterval', () => {
  it('polls while running and backs off to fifteen seconds', () => {
    expect(at('running', 1)).toBe(2_000)
    expect(at('running', 2)).toBe(3_000)
    expect(at('waiting_approval', 4)).toBe(6_750)
    expect(at('queued', 20)).toBe(15_000)
  })

  it('stops once the status is terminal or unknown', () => {
    for (const status of ['succeeded', 'failed', 'canceled', 'expired', undefined]) {
      expect(at(status)).toBe(false)
    }
    expect(interval({ state: { data: undefined, dataUpdateCount: 0 } })).toBe(false)
  })
})
