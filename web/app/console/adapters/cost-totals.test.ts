import { describe, expect, it } from 'vitest'

import type { RunCostEntryResponse } from '@/services/run-service'

import { formatCostTotal } from './cost-totals'

function entry(amount: string | null, currency: string | null): RunCostEntryResponse {
  return { amount, currency } as RunCostEntryResponse
}

describe('formatCostTotal', () => {
  it('totals one currency', () => {
    expect(formatCostTotal([entry('0.1', 'USD'), entry('0.025', 'USD')])).toBe('$0.125')
  })

  it('keeps currencies apart instead of adding them', () => {
    expect(formatCostTotal([entry('1', 'USD'), entry('2.5', 'CNY'), entry('0.5', 'USD')])).toBe(
      '2.500 CNY · $1.500',
    )
  })

  it('skips unpriced entries and shows a dash when nothing is priced', () => {
    expect(formatCostTotal([entry(null, null)])).toBe('—')
    expect(formatCostTotal([entry(null, null), entry('0.2', 'EUR')])).toBe('0.200 EUR')
  })

  it('shows an explicitly free run as zero rather than a dash', () => {
    expect(formatCostTotal([entry('0', 'USD')])).toBe('$0.000')
  })
})
