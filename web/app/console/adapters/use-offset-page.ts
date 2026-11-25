import { useCallback, useState } from 'react'

/**
 * Offset paging for list endpoints that take `limit` and `offset` and return a
 * bare array. Each page asks for one row more than it shows: that extra row is
 * how the page knows another one follows, since these endpoints report no
 * total.
 */
export function useOffsetPage(pageSize: number) {
  const [offset, setOffset] = useState(0)

  const take = useCallback(
    <T,>(items: T[] | undefined) => {
      const all = items || []
      return { rows: all.slice(0, pageSize), hasMore: all.length > pageSize }
    },
    [pageSize],
  )

  return {
    offset,
    limit: pageSize + 1,
    hasPrevious: offset > 0,
    take,
    next: () => setOffset((current) => current + pageSize),
    prev: () => setOffset((current) => Math.max(0, current - pageSize)),
    reset: () => setOffset(0),
  }
}
