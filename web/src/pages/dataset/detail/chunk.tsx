import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Badge } from '@/components/ui/badge'
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Textarea } from '@/components/ui/textarea'
import { toast } from 'sonner'
import { Download, Pencil, RefreshCw } from 'lucide-react'
import { getDocument, listChunks, updateChunk, type Chunk, type Document as ApiDocument } from '@/services/dataset-service'
import { useTranslation } from '@/i18n'

const PAGE_SIZE = 50

function Page() {
  const { t } = useTranslation()
  const { datasetId, documentId } = useParams<{ datasetId: string; documentId: string }>()
  const [documentInfo, setDocumentInfo] = useState<ApiDocument | null>(null)
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [loading, setLoading] = useState(false)
  const [loadingMore, setLoadingMore] = useState(false)
  const [nextOffset, setNextOffset] = useState<number | null>(0)
  const [searchQuery, setSearchQuery] = useState('')
  const [editingChunk, setEditingChunk] = useState<Chunk | null>(null)
  const [editContent, setEditContent] = useState('')
  const [saving, setSaving] = useState(false)

  const formatDate = (value?: string | null) => {
    if (!value) return '-'
    const date = new Date(value)
    if (Number.isNaN(date.getTime())) return value
    return date.toLocaleString()
  }

  const fetchDocument = async () => {
    if (!datasetId || !documentId) return
    try {
      const doc = await getDocument(datasetId, documentId)
      setDocumentInfo(doc)
    } catch (error) {
      toast.error(t('dataset.chunk.toast.fetchDocumentError'))
      console.error('Failed to fetch document info:', error)
    }
  }

  const fetchChunks = async ({ append = false }: { append?: boolean } = {}) => {
    if (!datasetId || !documentId) return
    if (append && nextOffset === null) return
    try {
      if (append) {
        setLoadingMore(true)
      } else {
        setLoading(true)
      }
      const offset = append ? nextOffset || 0 : 0
      const data = await listChunks(datasetId, documentId, { limit: PAGE_SIZE, offset })
      setChunks((prev) => (append ? [...prev, ...data] : data))
      const hasNext = data.length === PAGE_SIZE
      setNextOffset(hasNext ? offset + data.length : null)
    } catch (error) {
      toast.error(t('dataset.chunk.toast.fetchError'))
      console.error('Failed to fetch chunks:', error)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }

  useEffect(() => {
    fetchDocument()
    fetchChunks({ append: false })
  }, [datasetId, documentId])

  const filteredChunks = useMemo(() => {
    if (!searchQuery) return chunks
    const keyword = searchQuery.toLowerCase()
    return chunks.filter((chunk) => {
      return (
        chunk.text_preview?.toLowerCase().includes(keyword) ||
        String(chunk.chunk_no).includes(keyword)
      )
    })
  }, [chunks, searchQuery])

  const openEdit = (chunk: Chunk) => {
    setEditingChunk(chunk)
    setEditContent(chunk.text_preview || '')
  }

  const handleSave = async () => {
    if (!datasetId || !documentId || !editingChunk) return
    try {
      setSaving(true)
      await updateChunk(datasetId, documentId, editingChunk.id, { content: editContent })
      toast.success(t('dataset.chunk.toast.updateSuccess'))
      setEditingChunk(null)
      fetchChunks({ append: false })
    } catch (error) {
      toast.error(t('dataset.chunk.toast.updateError'))
      console.error('Failed to update chunk:', error)
    } finally {
      setSaving(false)
    }
  }

  const toggleChunkStatus = async (chunk: Chunk) => {
    if (!datasetId || !documentId) return
    const nextStatus = chunk.index_status === 'disabled' ? 'indexed' : 'disabled'
    try {
      await updateChunk(datasetId, documentId, chunk.id, { index_status: nextStatus })
      toast.success(nextStatus === 'disabled' ? t('dataset.chunk.toast.disabled') : t('dataset.chunk.toast.enabled'))
      fetchChunks({ append: false })
    } catch (error) {
      toast.error(t('dataset.chunk.toast.statusError'))
      console.error('Failed to update chunk status:', error)
    }
  }

  const exportChunks = () => {
    const payload = filteredChunks.map((chunk) => ({
      id: chunk.id,
      chunk_no: chunk.chunk_no,
      text_preview: chunk.text_preview,
      start_offset: chunk.start_offset,
      end_offset: chunk.end_offset,
      token_count: chunk.token_count,
      index_status: chunk.index_status,
    }))
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = window.document.createElement('a')
    link.href = url
    link.download = `chunks-${documentId}.json`
    window.document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  const totalChunks =
    typeof documentInfo?.index_meta_json?.chunk_count === 'number'
      ? documentInfo?.index_meta_json?.chunk_count
      : typeof documentInfo?.parse_meta_json?.chunk_count === 'number'
        ? documentInfo?.parse_meta_json?.chunk_count
        : null

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.chunk.info.title')}</CardTitle>
          <CardDescription>{t('dataset.chunk.info.description')}</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          <div>
            <div className="text-xs text-muted-foreground">{t('dataset.chunk.info.name')}</div>
            <div className="text-sm font-medium">
              {documentInfo?.title || documentInfo?.filename || documentInfo?.doc_key || '-'}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t('dataset.chunk.info.status')}</div>
            <div className="text-sm font-medium">{documentInfo?.status || '-'}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t('dataset.chunk.info.updatedAt')}</div>
            <div className="text-sm font-medium">{formatDate(documentInfo?.updated_at)}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t('dataset.chunk.info.chunkCount')}</div>
            <div className="text-sm font-medium">{totalChunks ?? '-'}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">{t('dataset.chunk.info.loadedCount')}</div>
            <div className="text-sm font-medium">{chunks.length}</div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{t('dataset.chunk.title')}</CardTitle>
            <CardDescription>{t('dataset.chunk.description')}</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => fetchChunks({ append: false })} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            </Button>
            <Button variant="outline" onClick={exportChunks} disabled={filteredChunks.length === 0}>
              <Download className="mr-2 h-4 w-4" />
              {t('dataset.chunk.actions.export')}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Input
            placeholder={t('dataset.chunk.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          {loading && <div className="text-sm text-muted-foreground">{t('dataset.chunk.loading')}</div>}
          {!loading && filteredChunks.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.chunk.empty')}</div>
          )}
          {filteredChunks.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[80px]">{t('dataset.chunk.table.index')}</TableHead>
                  <TableHead>{t('dataset.chunk.table.preview')}</TableHead>
                  <TableHead className="w-[120px]">{t('dataset.chunk.table.tokens')}</TableHead>
                  <TableHead className="w-[120px]">{t('dataset.chunk.table.status')}</TableHead>
                  <TableHead className="w-[160px]">{t('dataset.chunk.table.actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredChunks.map((chunk) => (
                  <TableRow key={chunk.id}>
                    <TableCell>#{chunk.chunk_no}</TableCell>
                    <TableCell>
                      <div className="line-clamp-2 text-sm text-muted-foreground">
                        {chunk.text_preview || '-'}
                      </div>
                    </TableCell>
                    <TableCell>{chunk.token_count ?? '-'}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{chunk.index_status}</Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={() => openEdit(chunk)}>
                          <Pencil className="mr-2 h-4 w-4" />
                          {t('dataset.chunk.actions.edit')}
                        </Button>
                        <Button
                          variant={chunk.index_status === 'disabled' ? 'default' : 'secondary'}
                          size="sm"
                          onClick={() => toggleChunkStatus(chunk)}
                        >
                          {chunk.index_status === 'disabled'
                            ? t('dataset.chunk.actions.enable')
                            : t('dataset.chunk.actions.disable')}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {nextOffset !== null && (
        <div className="flex justify-center">
          <Button variant="outline" onClick={() => fetchChunks({ append: true })} disabled={loadingMore}>
            {loadingMore ? t('dataset.chunk.loading') : t('dataset.chunk.actions.loadMore')}
          </Button>
        </div>
      )}

      <Dialog open={!!editingChunk} onOpenChange={(open) => !open && setEditingChunk(null)}>
        <DialogContent className="max-w-2xl">
          <DialogHeader>
            <DialogTitle>{t('dataset.chunk.dialog.title')}</DialogTitle>
            <DialogDescription>{t('dataset.chunk.dialog.description')}</DialogDescription>
          </DialogHeader>
          <Textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="min-h-[200px]"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingChunk(null)}>
              {t('dataset.chunk.actions.cancel')}
            </Button>
            <Button onClick={handleSave} disabled={saving}>
              {saving ? t('dataset.chunk.actions.saving') : t('dataset.chunk.actions.save')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default Page
