import type { RunCostEntryResponse } from '@/services/run-service'

/**
 * The run's priced cost, one total per currency. Amounts in different
 * currencies are never added together, and an unpriced entry (no amount)
 * adds nothing rather than counting as zero.
 */
export function formatCostTotal(costs: Pick<RunCostEntryResponse, 'amount' | 'currency'>[]): string {
  const totals = new Map<string, number>()
  for (const entry of costs) {
    if (entry.amount == null || !entry.currency) continue
    const amount = Number(entry.amount)
    if (!Number.isFinite(amount)) continue
    totals.set(entry.currency, (totals.get(entry.currency) ?? 0) + amount)
  }
  if (totals.size === 0) return '—'
  return [...totals.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([currency, total]) => (currency === 'USD' ? `$${total.toFixed(3)}` : `${total.toFixed(3)} ${currency}`))
    .join(' · ')
}
