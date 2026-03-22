import { Database, FileText, RefreshCw, Search } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { listKnowledgeBases, type KnowledgeBase } from '@/services/knowledge-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function KnowledgePage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const {
    data: knowledgePage,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['knowledge', 'list'],
    queryFn: () => listKnowledgeBases({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const knowledgeItems = useMemo(() => {
    const items = knowledgePage?.items || []
    if (!search.trim()) {
      return items
    }
    const keyword = search.trim().toLowerCase()
    return items.filter((knowledge: KnowledgeBase) => {
      const haystack = [knowledge.name, knowledge.description || '', ...(knowledge.tags || [])]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
  }, [knowledgePage?.items, search])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-stone-950 via-stone-900 to-stone-800 text-white shadow-xl">
        <CardHeader>
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            Knowledge
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">Knowledge is the retrieval layer for agents.</CardTitle>
          <CardDescription className="max-w-2xl text-stone-300">
            Curate source collections, keep document ingestion healthy, and connect knowledge bases back into agent and
            workflow execution.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Knowledge Bases</CardTitle>
            <CardDescription>Knowledge bases provide retrieval context, documents, and runtime analytics for agents.</CardDescription>
          </div>
          <div className="flex gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search knowledge"
                className="w-[260px] pl-9"
              />
            </div>
            <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <div className="text-sm text-muted-foreground">Loading knowledge bases...</div>}
          {!isLoading && knowledgeItems.length === 0 && (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No knowledge bases found.
            </div>
          )}
          {!isLoading && knowledgeItems.length > 0 && (
            <div className="grid gap-4 xl:grid-cols-2">
              {knowledgeItems.map((knowledge: KnowledgeBase) => (
                <Card key={knowledge.id} className="transition-colors hover:border-primary/40">
                  <CardHeader className="gap-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <CardTitle className="flex items-center gap-2 text-xl">
                          <Database className="h-5 w-5" />
                          {knowledge.name}
                        </CardTitle>
                        <CardDescription>{knowledge.description || 'No description yet.'}</CardDescription>
                      </div>
                      <Badge variant="outline">{knowledge.status}</Badge>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="secondary">{knowledge.doc_count} docs</Badge>
                      <Badge variant="secondary">{knowledge.chunk_count} chunks</Badge>
                      <Badge variant="outline">{knowledge.visibility}</Badge>
                      {(knowledge.tags || []).map((tag) => (
                        <Badge key={tag} variant="outline">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                      <div>Last ingested: {formatTimestamp(knowledge.last_ingested_at)}</div>
                      <div>Last indexed: {formatTimestamp(knowledge.last_indexed_at)}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => navigate(`/knowledge/${knowledge.id}`)}>
                        <Database className="mr-2 h-4 w-4" />
                        Overview
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/knowledge/${knowledge.id}/document`)}>
                        <FileText className="mr-2 h-4 w-4" />
                        Manage Documents
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/knowledge/${knowledge.id}/analytics`)}>
                        Analytics
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default KnowledgePage
