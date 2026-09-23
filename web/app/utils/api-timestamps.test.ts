import { describe, expect, it } from 'vitest'

import { markApiTimestampsUtc } from './api-timestamps'

describe('markApiTimestampsUtc', () => {
  it('marks naive timestamps under timestamp keys as UTC, at any depth', () => {
    const payload = {
      items: [
        {
          started_at: '2026-09-23T17:00:00.123456',
          nested: { created_at: '2026-09-23T17:00:00' },
          timestamp: '2026-09-23T17:00:00',
        },
      ],
      since: '2026-09-22T17:00:00',
    }

    markApiTimestampsUtc(payload)

    expect(payload.items[0].started_at).toBe('2026-09-23T17:00:00.123456Z')
    expect(payload.items[0].nested.created_at).toBe('2026-09-23T17:00:00Z')
    expect(payload.items[0].timestamp).toBe('2026-09-23T17:00:00Z')
    expect(payload.since).toBe('2026-09-22T17:00:00Z')
    expect(new Date(payload.items[0].nested.created_at).toISOString()).toBe(
      '2026-09-23T17:00:00.000Z',
    )
  })

  it('leaves offset-bearing values, other keys and non-timestamps alone', () => {
    const payload = {
      ended_at: '2026-09-23T17:00:00+08:00',
      updated_at: '2026-09-23T17:00:00Z',
      note: '2026-09-23T17:00:00',
      expires_at: null,
      deleted_at: 'never',
    }

    markApiTimestampsUtc(payload)

    expect(payload).toEqual({
      ended_at: '2026-09-23T17:00:00+08:00',
      updated_at: '2026-09-23T17:00:00Z',
      note: '2026-09-23T17:00:00',
      expires_at: null,
      deleted_at: 'never',
    })
  })
})
