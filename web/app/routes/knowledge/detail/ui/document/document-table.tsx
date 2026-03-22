import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Checkbox } from '@/components/ui/checkbox'
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu'
import { Link } from '@/components/ui/link'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { ArrowUpDown, Eye, FileText, Globe, Image, Link as LucideLink, MoreHorizontal, Trash2, Video, History, Download, RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'

const DocumentType = {
  document: 'document',
  image: 'image',
  video: 'video',
  link: 'link',
  website: 'website',
  knowledge: 'knowledge',
} as const

const DocumentTypeIcon = {
  [DocumentType.document]: FileText,
  [DocumentType.image]: Image,
  [DocumentType.video]: Video,
  [DocumentType.link]: LucideLink,
  [DocumentType.website]: Globe,
  [DocumentType.knowledge]: FileText,
}

type DocumentStatus = 'pending' | 'processing' | 'completed' | 'failed'

interface Document {
  id: string
  doc_key: string
  version: number
  name: string
  type: string
  size: string
  status: DocumentStatus
  updated_at: string
  content?: string
  mime_type?: string | null
  error_code?: string | null
  error_message?: string | null
}

interface DocumentTableProps {
  documents: Document[]
  knowledgeId: string
  selectedDocs: string[]
  sortField: string
  sortOrder: 'asc' | 'desc'
  onSort: (field: string) => void
  onDocSelect: (docId: string) => void
  onSelectAll: () => void
  onDeleteDoc: (docId: string) => void
  onPreviewDoc: (doc: Document) => void
  onViewVersions: (doc: Document) => void
  onDownloadDoc: (doc: Document) => void
  onRetryDoc?: (doc: Document) => void
  currentPage?: number
  pageSize?: number
  totalCount?: number
  onPageChange?: (page: number) => void
  onPageSizeChange?: (size: number) => void
}

export function DocumentTable({
  documents = [],
  knowledgeId,
  selectedDocs,
  sortField,
  sortOrder,
  onSort,
  onDocSelect,
  onSelectAll,
  onDeleteDoc,
  onPreviewDoc,
  onViewVersions,
  onDownloadDoc,
  onRetryDoc,
  currentPage = 1,
  pageSize = 10,
  totalCount,
  onPageChange,
  onPageSizeChange,
}: DocumentTableProps) {
  const { t } = useTranslation()

  const getDocumentTypeLabel = (type: string) => {
    const typeMap: Record<string, string> = {
      [DocumentType.document]: t('knowledge.document.types.document'),
      [DocumentType.image]: t('knowledge.document.types.image'),
      [DocumentType.video]: t('knowledge.document.types.video'),
      [DocumentType.link]: t('knowledge.document.types.link'),
      [DocumentType.website]: t('knowledge.document.types.website'),
      [DocumentType.knowledge]: t('knowledge.document.types.knowledge'),
    }
    return typeMap[type] || type
  }

  const statusMap: Record<DocumentStatus, { label: string; variant: 'default' | 'secondary' | 'destructive' | 'outline' }> = {
    pending: { label: t('knowledge.document.status.pending'), variant: 'outline' },
    processing: { label: t('knowledge.document.status.processing'), variant: 'secondary' },
    completed: { label: t('knowledge.document.status.completed'), variant: 'default' },
    failed: { label: t('knowledge.document.status.failed'), variant: 'destructive' },
  }

  const total = totalCount || documents.length
  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="flex flex-col gap-4">
      <div className="text-sm text-muted-foreground">
        {t('knowledge.document.table.summary', { count: documents.length })}
      </div>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-[50px]">
              <Checkbox
                checked={selectedDocs.length === documents.length && documents.length > 0}
                onCheckedChange={onSelectAll}
              />
            </TableHead>
            <TableHead className="w-[300px]">
              <div className="flex items-center gap-2">
                {t('knowledge.document.table.name')}
                <Button variant="ghost" size="sm" onClick={() => onSort('name')}>
                  <ArrowUpDown className="h-4 w-4" />
                </Button>
              </div>
            </TableHead>
            <TableHead>{t('knowledge.document.table.type')}</TableHead>
            <TableHead>{t('knowledge.document.table.size')}</TableHead>
            <TableHead>{t('knowledge.document.table.status')}</TableHead>
            <TableHead>
              <div className="flex items-center gap-2">
                {t('knowledge.document.table.updatedAt')}
                <Button variant="ghost" size="sm" onClick={() => onSort('updated_at')}>
                  <ArrowUpDown className="h-4 w-4" />
                </Button>
              </div>
            </TableHead>
            <TableHead className="w-[100px]">{t('knowledge.document.table.actions')}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {documents.map((doc) => {
            const Icon = DocumentTypeIcon[doc.type as keyof typeof DocumentType] || FileText
            return (
              <TableRow key={doc.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedDocs.includes(doc.id)}
                    onCheckedChange={() => onDocSelect(doc.id)}
                  />
                </TableCell>
                <TableCell className="font-medium">
                  <div className="flex items-center gap-2">
                    <Icon className="h-4 w-4 text-muted-foreground" />
                    <Link
                      to={`/knowledge/${knowledgeId}/document/${doc.id}/chunk`}
                      className="text-primary font-semibold hover:underline cursor-pointer"
                    >
                      {doc.name}
                    </Link>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant="outline">
                    {getDocumentTypeLabel(doc.type)}
                  </Badge>
                </TableCell>
                <TableCell>{doc.size}</TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <Badge variant={statusMap[doc.status]?.variant || 'outline'}>
                      {statusMap[doc.status]?.label || t('knowledge.document.status.unknown')}
                    </Badge>
                    {doc.status === 'failed' && doc.error_message ? (
                      <span className="text-xs text-muted-foreground line-clamp-2">
                        {doc.error_message}
                      </span>
                    ) : null}
                  </div>
                </TableCell>
                <TableCell>{doc.updated_at}</TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="sm">
                        <MoreHorizontal className="h-4 w-4" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem onClick={() => onPreviewDoc(doc)}>
                        <Eye className="mr-2 h-4 w-4" />
                        {t('knowledge.document.actions.preview')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onViewVersions(doc)}>
                        <History className="mr-2 h-4 w-4" />
                        {t('knowledge.document.actions.versionHistory')}
                      </DropdownMenuItem>
                      <DropdownMenuItem onClick={() => onDownloadDoc(doc)}>
                        <Download className="mr-2 h-4 w-4" />
                        {t('knowledge.document.actions.download')}
                      </DropdownMenuItem>
                      {doc.status === 'failed' && onRetryDoc ? (
                        <DropdownMenuItem onClick={() => onRetryDoc(doc)}>
                          <RefreshCw className="mr-2 h-4 w-4" />
                          {t('knowledge.document.actions.retry')}
                        </DropdownMenuItem>
                      ) : null}
                      <DropdownMenuSeparator />
                      <DropdownMenuItem
                        className="text-destructive"
                        onClick={() => onDeleteDoc(doc.id)}
                      >
                        <Trash2 className="mr-2 h-4 w-4" />
                        {t('knowledge.document.actions.delete')}
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            )
          })}
        </TableBody>
      </Table>

      {documents.length > 0 && (
        <div className="flex items-center justify-between mt-4 text-sm">
          <div className="text-muted-foreground">
            {t('knowledge.document.table.pagination.summary', {
              start: (currentPage - 1) * pageSize + 1,
              end: Math.min(currentPage * pageSize, total),
              total,
            })}
          </div>
          <div className="flex items-center gap-2">
            <Select value={pageSize.toString()} onValueChange={(value) => onPageSizeChange ? onPageSizeChange(Number(value)) : undefined}>
              <SelectTrigger className="h-8 w-[70px]">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="10">{t('knowledge.document.table.pagination.pageSize', { size: 10 })}</SelectItem>
                <SelectItem value="20">{t('knowledge.document.table.pagination.pageSize', { size: 20 })}</SelectItem>
                <SelectItem value="50">{t('knowledge.document.table.pagination.pageSize', { size: 50 })}</SelectItem>
              </SelectContent>
            </Select>

            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={currentPage === 1}
                onClick={() => onPageChange ? onPageChange(1) : undefined}
              >
                <span className="sr-only">{t('knowledge.document.table.pagination.first')}</span>
                <span>«</span>
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={currentPage === 1}
                onClick={() => onPageChange ? onPageChange(currentPage - 1) : undefined}
              >
                <span className="sr-only">{t('knowledge.document.table.pagination.previous')}</span>
                <span>‹</span>
              </Button>

              {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                let pageNum = currentPage - 2 + i
                if (currentPage < 3) {
                  pageNum = i + 1
                } else if (currentPage > totalPages - 2) {
                  pageNum = totalPages - 4 + i
                }
                if (pageNum > 0 && pageNum <= totalPages) {
                  return (
                    <Button
                      key={pageNum}
                      variant={currentPage === pageNum ? 'default' : 'outline'}
                      size="icon"
                      className="h-8 w-8"
                      onClick={() => onPageChange ? onPageChange(pageNum) : undefined}
                    >
                      {pageNum}
                    </Button>
                  )
                }
                return null
              })}

              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={currentPage === totalPages}
                onClick={() => onPageChange ? onPageChange(currentPage + 1) : undefined}
              >
                <span className="sr-only">{t('knowledge.document.table.pagination.next')}</span>
                <span>›</span>
              </Button>
              <Button
                variant="outline"
                size="icon"
                className="h-8 w-8"
                disabled={currentPage === totalPages}
                onClick={() => onPageChange ? onPageChange(totalPages) : undefined}
              >
                <span className="sr-only">{t('knowledge.document.table.pagination.last')}</span>
                <span>»</span>
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
