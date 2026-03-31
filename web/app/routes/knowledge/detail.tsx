import { useMemo } from 'react'
import { ArrowLeft, Activity, BarChart3, Clock3, Database, FileText, Link2 } from 'lucide-react'
import { useParams } from 'react-router'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { getKnowledgeBase, listKnowledgeRuns, listKnowledgeUsages } from '@/services/knowledge-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function KnowledgeDetailPage() {
  const { knowledgeId = '' } = useParams()
  const navigate = useNavigate()

  const { data: knowledge, isLoading } = useQuery({
    queryKey: ['knowledge', knowledgeId],
    queryFn: () => getKnowledgeBase(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: usages = [] } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'usages'],
    queryFn: () => listKnowledgeUsages(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: runPage } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'runs'],
    queryFn: () => listKnowledgeRuns(knowledgeId, { page_size: 5 }),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const recentUsages = useMemo(() => usages.slice(0, 4), [usages])
  const recentRuns = useMemo(() => (runPage?.items || []).slice(0, 5), [runPage?.items])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={() => navigate('/knowledge')}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Knowledge
        </Button>
        {knowledge && <Badge variant="outline">{knowledge.status}</Badge>}
      </div>

      <Card className="border-none bg-gradient-to-br from-amber-100 via-orange-50 to-white shadow-sm">
        <CardHeader>
          <Badge variant="secondary" className="w-fit">
            Knowledge Base
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">
            {knowledge?.name || (isLoading ? 'Loading knowledge base...' : 'Knowledge base not found')}
          </CardTitle>
          <CardDescription className="max-w-2xl text-muted-foreground">
            {knowledge?.description || 'Inspect retrieval defaults, document inventory, and runtime behavior for this knowledge base.'}
          </CardDescription>
          {knowledge && (
            <div className="flex flex-wrap gap-2 pt-1">
              <Badge variant="secondary">{knowledge.knowledge_type}</Badge>
              <Badge variant="outline">{knowledge.visibility}</Badge>
              <Badge variant="outline">{knowledge.status}</Badge>
            </div>
          )}
        </CardHeader>
      </Card>

      {knowledge && (
        <>
          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Database className="h-4 w-4" />
                  Inventory
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div>Documents: {knowledge.doc_count}</div>
                <div>Chunks: {knowledge.chunk_count}</div>
                <div>Visibility: {knowledge.visibility}</div>
                <div>Knowledge type: {knowledge.knowledge_type}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Pipeline Health</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div>Last ingested: {formatTimestamp(knowledge.last_ingested_at)}</div>
                <div>Last indexed: {formatTimestamp(knowledge.last_indexed_at)}</div>
                <div>Created: {formatTimestamp(knowledge.created_at)}</div>
                <div>Updated: {formatTimestamp(knowledge.updated_at)}</div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Runtime Defaults</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                <div>Embedding: {knowledge.default_embedding_model_ref || '-'}</div>
                <div>Reranker: {knowledge.default_reranker_ref || '-'}</div>
                <div>Index: {knowledge.default_index_id || '-'}</div>
                <div>Tags: {(knowledge.tags || []).join(', ') || '-'}</div>
              </CardContent>
            </Card>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Link2 className="h-4 w-4" />
                  Bound By Agents
                </CardTitle>
                <CardDescription>Agents and workflows currently referencing this knowledge base.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {recentUsages.length === 0 && <div className="text-sm text-muted-foreground">No usages linked yet.</div>}
                {recentUsages.map((usage) => (
                  <div key={usage.resource_version_id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 font-medium">
                          <Link2 className="h-4 w-4 text-muted-foreground" />
                          {usage.resource_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {usage.resource_kind} · v{usage.resource_version}
                        </div>
                      </div>
                      <Badge variant="outline">{usage.resource_status}</Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Version status: {usage.resource_version_status} · Last run: {formatTimestamp(usage.last_run_at)} · Run count:{' '}
                      {usage.run_count}
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Clock3 className="h-4 w-4" />
                  Recent Runtime Usage
                </CardTitle>
                <CardDescription>Recent runs associated with this knowledge base.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                {recentRuns.length === 0 && <div className="text-sm text-muted-foreground">No runs recorded yet.</div>}
                {recentRuns.map((run) => (
                  <div key={run.id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 font-medium">
                          <Activity className="h-4 w-4 text-muted-foreground" />
                          {run.mode}
                        </div>
                        <div className="text-xs text-muted-foreground">{run.id}</div>
                      </div>
                      <Badge variant="outline">{run.status}</Badge>
                    </div>
                    <div className="mt-2 flex items-center justify-between gap-3 text-xs text-muted-foreground">
                      <span>Started: {formatTimestamp(run.started_at)}</span>
                      <span>Ended: {formatTimestamp(run.ended_at)}</span>
                    </div>
                    <div className="mt-3 flex justify-end">
                      <Button variant="ghost" size="sm" onClick={() => navigate(`/observability/runs/${run.id}`)}>
                        Open Run
                        <BarChart3 className="ml-2 h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Operations</CardTitle>
              <CardDescription>Open document inventory and runtime analytics directly from the knowledge surface.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              <Button onClick={() => navigate(`/knowledge/${knowledge.id}/document`)}>
                <FileText className="mr-2 h-4 w-4" />
                Manage Documents
              </Button>
              <Button variant="outline" onClick={() => navigate(`/knowledge/${knowledge.id}/analytics`)}>
                <BarChart3 className="mr-2 h-4 w-4" />
                Analytics
              </Button>
              <Button variant="outline" onClick={() => navigate(`/knowledge/${knowledge.id}/setting`)}>
                <Database className="mr-2 h-4 w-4" />
                Settings
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}

export default KnowledgeDetailPage
