import { useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { ArrowLeft, FileText, Search } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { getKnowledgeBase, listKnowledgeDocuments } from '@/services/knowledge-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function KnowledgeDocumentsPage() {
  const { knowledgeId = '' } = useParams()
  const navigate = useNavigate()
  const [search, setSearch] = useState('')

  const { data: knowledge } = useQuery({
    queryKey: ['knowledge', knowledgeId],
    queryFn: () => getKnowledgeBase(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: documents = [], isLoading } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'documents'],
    queryFn: () => listKnowledgeDocuments(knowledgeId, { limit: 200 }),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const filtered = useMemo(() => {
    if (!search.trim()) {
      return documents
    }
    const keyword = search.trim().toLowerCase()
    return documents.filter((item) =>
      [item.title || '', item.filename || '', item.doc_key, item.source_uri || ''].join(' ').toLowerCase().includes(keyword)
    )
  }, [documents, search])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={() => navigate(`/knowledge/${knowledgeId}`)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Knowledge
        </Button>
        {knowledge && <Badge variant="outline">{knowledge.status}</Badge>}
      </div>

      <Card className="border-none bg-gradient-to-br from-stone-950 via-stone-900 to-stone-800 text-white shadow-xl">
        <CardHeader>
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            Documents
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">{knowledge?.name || 'Knowledge documents'}</CardTitle>
          <CardDescription className="text-stone-300">
            Review the current ingestion ledger for this knowledge base.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Document Inventory</CardTitle>
            <CardDescription>Latest document versions attached to this knowledge base.</CardDescription>
          </div>
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search documents"
              className="w-[280px] pl-9"
            />
          </div>
        </CardHeader>
        <CardContent>
          {isLoading && <div className="text-sm text-muted-foreground">Loading documents...</div>}
          {!isLoading && filtered.length === 0 && (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No documents found.
            </div>
          )}
          {!isLoading && filtered.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Document</TableHead>
                  <TableHead>Source</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Updated</TableHead>
                  <TableHead className="text-right">Version</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((document) => (
                  <TableRow key={document.id}>
                    <TableCell>
                      <div className="flex items-center gap-2 font-medium">
                        <FileText className="h-4 w-4 text-muted-foreground" />
                        {document.title || document.filename || document.doc_key}
                      </div>
                      <div className="text-xs text-muted-foreground">{document.doc_key}</div>
                    </TableCell>
                    <TableCell>{document.source_kind}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{document.status}</Badge>
                    </TableCell>
                    <TableCell>{formatTimestamp(document.updated_at)}</TableCell>
                    <TableCell className="text-right">v{document.version}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default KnowledgeDocumentsPage
