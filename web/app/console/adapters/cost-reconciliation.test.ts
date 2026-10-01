import { describe, expect, it } from 'vitest'

import type { CostReconciliationGroup } from '@/services/run-service'

import { formatCurrencyAmounts, groupAmount, groupsToCsv, windowStart } from './cost-reconciliation'

function group(overrides: Partial<CostReconciliationGroup>): CostReconciliationGroup {
  return {
    key: 'model:openai:gpt-5.1',
    currency: 'USD',
    entry_count: 2,
    amount: '0.500000',
    estimated_count: 0,
    unpriced_count: 0,
    total_tokens: 20,
    ...overrides,
  }
}

describe('windowStart', () => {
  const now = new Date('2026-10-15T08:30:00Z')

  it('counts back from now for the rolling ranges', () => {
    expect(windowStart('24h', now)).toBe('2026-10-14T08:30:00.000Z')
    expect(windowStart('7d', now)).toBe('2026-10-08T08:30:00.000Z')
  })

  it('starts the month at midnight UTC on the first', () => {
    expect(windowStart('month', now)).toBe('2026-10-01T00:00:00.000Z')
  })
})

describe('formatCurrencyAmounts', () => {
  it('keeps one figure per currency, sorted', () => {
    expect(formatCurrencyAmounts({ USD: '12.3', CNY: '5' })).toBe('5.00 CNY · 12.30 USD')
  })

  it('shows a dash when nothing was priced', () => {
    expect(formatCurrencyAmounts({})).toBe('—')
  })
})

describe('groupAmount', () => {
  it('names the currency of a priced row', () => {
    expect(groupAmount(group({}))).toBe('0.5000 USD')
  })

  it('shows a dash for the row of unpriced entries, not a zero', () => {
    expect(groupAmount(group({ currency: null, amount: null, unpriced_count: 2 }))).toBe('—')
  })
})

describe('groupsToCsv', () => {
  it('writes a header and leaves unpriced amounts empty', () => {
    const csv = groupsToCsv(
      [group({}), group({ key: null, currency: null, amount: null, unpriced_count: 1, entry_count: 1 })],
      'model',
    )
    expect(csv).toBe(
      'model,currency,entries,amount,estimated_entries,unpriced_entries,total_tokens\n' +
        'model:openai:gpt-5.1,USD,2,0.500000,0,0,20\n' +
        ',,1,,0,1,20\n',
    )
  })

  it('quotes cells that hold a comma or a quote', () => {
    const csv = groupsToCsv([group({ key: 'tool:a,"b"' })], 'tool')
    expect(csv.split('\n')[1].startsWith('"tool:a,""b"""')).toBe(true)
  })
})
