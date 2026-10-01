import type { CostGroupBy, CostReconciliationGroup } from '@/services/run-service'

export type CostRange = '24h' | '7d' | '30d' | 'month'

const RANGE_MS: Record<Exclude<CostRange, 'month'>, number> = {
  '24h': 24 * 3_600_000,
  '7d': 7 * 24 * 3_600_000,
  '30d': 30 * 24 * 3_600_000,
}

/** Start of the window, as an ISO timestamp; `month` starts at 00:00 UTC on the 1st. */
export function windowStart(range: CostRange, now: Date): string {
  if (range === 'month') {
    return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1)).toISOString()
  }
  return new Date(now.getTime() - RANGE_MS[range]).toISOString()
}

/**
 * One figure per currency, never added across currencies: `12.30 USD · 5.00 CNY`.
 * A dash when nothing was priced.
 */
export function formatCurrencyAmounts(amounts: Record<string, string>, digits = 2): string {
  const entries = Object.entries(amounts)
    .map(([currency, value]) => [currency, Number(value)] as const)
    .filter(([, value]) => Number.isFinite(value))
    .sort(([a], [b]) => a.localeCompare(b))
  if (entries.length === 0) return '—'
  return entries.map(([currency, value]) => `${value.toFixed(digits)} ${currency}`).join(' · ')
}

/** The amount column of a group row: unpriced rows have no amount. */
export function groupAmount(group: CostReconciliationGroup): string {
  if (group.amount == null || !group.currency) return '—'
  const value = Number(group.amount)
  return Number.isFinite(value) ? `${value.toFixed(4)} ${group.currency}` : '—'
}

function csvCell(value: string | number | null): string {
  if (value == null) return ''
  const text = String(value)
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text
}

/**
 * The grouped rows as CSV, for setting beside a provider's bill in a
 * spreadsheet. Amounts stay as the ledger's decimal strings; unpriced rows
 * have an empty currency and amount rather than a zero.
 */
export function groupsToCsv(groups: CostReconciliationGroup[], groupBy: CostGroupBy): string {
  const header = [groupBy, 'currency', 'entries', 'amount', 'estimated_entries', 'unpriced_entries', 'total_tokens']
  const lines = groups.map((group) =>
    [
      group.key,
      group.currency,
      group.entry_count,
      group.amount,
      group.estimated_count,
      group.unpriced_count,
      group.total_tokens,
    ]
      .map(csvCell)
      .join(','),
  )
  return [header.join(','), ...lines].join('\n') + '\n'
}
