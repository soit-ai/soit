import { Navigate, useLocation, useParams, type Location } from 'react-router'

/**
 * Renders a permanent redirect for one path the rebuild renamed. Query and hash
 * carry through so deep links keep their filters, and the resolver gets the
 * location as well as the params because the `/v2/*` family rewrites a prefix
 * rather than reading a segment.
 *
 * Paths the rebuild did not rename (`/observe/runs`, `/chat`, `/settings/*`,
 * `/notifications`) need no entry — they resolve directly.
 */
export function LegacyRedirect({
  to,
}: {
  to: (params: Record<string, string | undefined>, location: Location) => string
}) {
  const params = useParams()
  const location = useLocation()
  const target = to(params, location)
  return <Navigate to={`${target}${location.search}${location.hash}`} replace />
}
