import { Navigate, useLocation, useParams } from 'react-router'

/**
 * Path map for the switch-over, when the console takes the application root and
 * the pre-rebuild URLs stop resolving. Bookmarks and links in older runs,
 * notifications and audit entries must keep working, so every renamed path gets
 * a permanent redirect rather than a 404.
 *
 * Paths absent from this map are unchanged by the rebuild (`/observe/runs`,
 * `/chat`, `/settings/*`, `/notifications`) and need no entry.
 */
export const LEGACY_PATH_MAP: Array<{ from: string; to: (params: Record<string, string | undefined>) => string }> = [
  { from: '/agents', to: () => '/build/agents' },
  { from: '/agents/:agentId', to: (p) => `/build/agents/${p.agentId ?? ''}` },
  { from: '/knowledge', to: () => '/build/knowledge' },
  { from: '/knowledge/:knowledgeId', to: (p) => `/build/knowledge/${p.knowledgeId ?? ''}` },
  { from: '/workflow', to: () => '/build/workflows' },
  { from: '/workflow/:id/build', to: (p) => `/build/workflows/${p.id ?? ''}` },
  { from: '/workflow/:id/monitor', to: (p) => `/build/workflows/${p.id ?? ''}` },
  { from: '/workflow/:id/publish', to: (p) => `/build/workflows/${p.id ?? ''}` },
  { from: '/workflow/:id/setting', to: (p) => `/build/workflows/${p.id ?? ''}` },
  { from: '/workflow/:id/log', to: (p) => `/build/workflows/${p.id ?? ''}` },
  { from: '/plugins', to: () => '/build/plugins' },
  { from: '/models', to: () => '/build/models' },
  { from: '/tasks', to: () => '/execute/tasks' },
  { from: '/tasks/:taskId', to: (p) => `/execute/tasks/${p.taskId ?? ''}` },
  { from: '/observe/audits', to: () => '/govern/audit' },
]

/**
 * Renders the redirect for one mapped legacy path. Query and hash are carried
 * over so deep links keep their filters.
 */
export function LegacyRedirect({
  to,
}: {
  to: (params: Record<string, string | undefined>) => string
}) {
  const params = useParams()
  const location = useLocation()
  return <Navigate to={`${to(params)}${location.search}${location.hash}`} replace />
}
