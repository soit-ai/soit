import { useCallback, useState } from 'react'

/**
 * Cursor paging for list endpoints that answer with `next_page_token`.
 *
 * The API pages forward only, so going back replays the tokens that led to
 * the current page. Call `reset` whenever a filter changes: a token belongs to
 * the query that produced it.
 */
export function usePageCursor() {
  const [pageToken, setPageToken] = useState<string | undefined>(undefined)
  const [previous, setPrevious] = useState<string[]>([])

  const next = useCallback(
    (token: string | null | undefined) => {
      if (!token) return
      setPrevious((stack) => [...stack, pageToken ?? ''])
      setPageToken(token)
    },
    [pageToken],
  )

  const prev = useCallback(() => {
    if (previous.length === 0) return
    const stack = previous.slice(0, -1)
    const last = previous[previous.length - 1]
    setPrevious(stack)
    setPageToken(last || undefined)
  }, [previous])

  const reset = useCallback(() => {
    setPageToken(undefined)
    setPrevious([])
  }, [])

  return { pageToken, hasPrevious: previous.length > 0, next, prev, reset }
}
