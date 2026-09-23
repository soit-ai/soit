/**
 * The API stores timestamps as naive UTC and serialises most of them without
 * an offset ("2026-09-23T17:00:00.123456"). `new Date()` reads an offset-less
 * ISO string as *local* time, so every consumer would shift it by the
 * browser's UTC offset. Marking those values as UTC once, where the envelope
 * is unwrapped, keeps every screen from having to remember.
 *
 * Only keys that name a timestamp are touched, so free-form content that
 * happens to look like a date is left alone.
 */

const NAIVE_ISO = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?$/

const TIMESTAMP_KEYS = new Set(['timestamp', 'since', 'until'])

function isTimestampKey(key: string): boolean {
  return key.endsWith('_at') || TIMESTAMP_KEYS.has(key)
}

/** Append `Z` to offset-less timestamps under timestamp keys, in place. */
export function markApiTimestampsUtc<T>(value: T): T {
  if (Array.isArray(value)) {
    for (const item of value) markApiTimestampsUtc(item)
    return value
  }
  if (value && typeof value === 'object') {
    const record = value as Record<string, unknown>
    for (const key of Object.keys(record)) {
      const field = record[key]
      if (typeof field === 'string') {
        if (isTimestampKey(key) && NAIVE_ISO.test(field)) record[key] = `${field}Z`
      } else if (field && typeof field === 'object') {
        markApiTimestampsUtc(field)
      }
    }
  }
  return value
}
