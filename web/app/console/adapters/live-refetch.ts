/**
 * Polling for pages that show something still running.
 *
 * A run or task page that never refetches keeps the snapshot it opened with,
 * so a run that finished a second later still reads "running". These pages
 * poll while the status is not terminal, starting at two seconds and backing
 * off to fifteen so a long wait does not hammer the API, and stop once it is.
 * React Query already pauses the interval while the tab is hidden.
 */

/** The backend's terminal run and task statuses (runtime/status.py). */
const TERMINAL_STATUSES = new Set(['succeeded', 'failed', 'canceled', 'expired'])

const FIRST_POLL_MS = 2_000
const MAX_POLL_MS = 15_000

interface PolledQuery<T> {
  state: { data: T | undefined; dataUpdateCount: number }
}

export function liveRefetchInterval<T>(statusOf: (data: T) => string | null | undefined) {
  return (query: PolledQuery<T>): number | false => {
    const data = query.state.data
    if (data === undefined) return false
    const status = statusOf(data)
    if (!status || TERMINAL_STATUSES.has(status)) return false
    const step = Math.max(0, query.state.dataUpdateCount - 1)
    return Math.min(MAX_POLL_MS, Math.round(FIRST_POLL_MS * 1.5 ** step))
  }
}
