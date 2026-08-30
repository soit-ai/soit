/**
 * The prototype assigns every entity a categorical accent from the `--cat-*`
 * ramp. Fixtures hard-coded one per row; live data carries no colour, so we
 * derive a stable one from the identifier — the same entity keeps the same
 * accent across pages and reloads, which is what makes the colour readable as
 * identity rather than decoration.
 */
const CAT_COLORS = [
  'var(--cat-blue)',
  'var(--cat-cyan)',
  'var(--cat-teal)',
  'var(--cat-indigo)',
  'var(--cat-purple)',
  'var(--cat-pink)',
  'var(--cat-amber)',
  'var(--cat-slate)',
] as const

export function catColor(seed: string | null | undefined): string {
  if (!seed) return 'var(--cat-slate)'
  let hash = 0
  for (let index = 0; index < seed.length; index += 1) {
    hash = (hash * 31 + seed.charCodeAt(index)) | 0
  }
  return CAT_COLORS[Math.abs(hash) % CAT_COLORS.length]
}

/** "8h ago" / "3d ago" — the prototype's relative stamp for list columns. */
export function relativeTime(iso?: string | null): string {
  if (!iso) return '—'
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return iso
  const delta = Date.now() - then
  if (delta < 0) return 'just now'
  const minutes = Math.floor(delta / 60_000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toISOString().slice(0, 10)
}

/** Compact counts for stat tiles: 1,284 · 12.4k · 5.1M. */
export function compactNumber(value?: number | null): string {
  if (value == null) return '—'
  if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
  if (Math.abs(value) >= 10_000) return `${(value / 1000).toFixed(1)}k`
  return value.toLocaleString('en-US')
}

/** Currency for tiles and tables: $12.40 for USD, "12.40 EUR" otherwise. */
export function money(amount?: number | null, currency?: string | null): string {
  if (amount == null) return '—'
  const value = amount.toFixed(2)
  if (!currency) return value
  return currency.toUpperCase() === 'USD' ? `$${value}` : `${value} ${currency}`
}

export function percent(value?: number | null, digits = 1): string {
  if (value == null) return '—'
  // Backends report success rates either as 0–1 ratios or 0–100 percentages.
  const scaled = value <= 1 ? value * 100 : value
  return `${scaled.toFixed(digits)}%`
}

export function latency(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${Math.round(ms)}ms`
}
