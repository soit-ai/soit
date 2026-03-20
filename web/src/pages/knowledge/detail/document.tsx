import { useTranslation } from '@/i18n'
import { useState, useEffect, useMemo } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { toast } from 'sonner'
import {
  cancelKnowledgeIngestTask,
  deleteKnowledgeDocument,
  downloadKnowledgeDocument,
  listKnowledgeDocuments,
  listKnowledgeDocumentVersions,
  listKnowledgeIngestTasks,
  retryKnowledgeDocumentIngest,
  retryKnowledgeIngestTask,
  rollbackKnowledgeDocumentVersion,
  type KnowledgeDocument as ApiDocument,
  type KnowledgeIngestTask as IngestTask,
} from '@/services/knowledge-service'
import {
  DocumentHeader,
  DocumentFilterBar,
  DocumentTable,
  DocumentPreviewDialog,
  UploadDocumentDialog,
} from './ui/document'
import { IngestTasksDialog } from './ui/document/ingest-tasks-dialog'
import { VersionHistoryDialog, type DocumentVersion } from './ui/document/version-history-dialog'
import { useNavLayout } from '@/components/layout/nav-layout'
import { PageHeader } from './ui/document/page-header'

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

const detectType = (doc: ApiDocument) => {
  if (doc.mime_type?.startsWith('image/')) return 'image'
  if (doc.mime_type?.startsWith('video/')) return 'video'
  if (doc.source_type === 'crawler' || doc.source_uri) return 'website'
  return 'document'
}

const mapStatus = (status: string): DocumentStatus => {
  if (['failed', 'deleted', 'canceled'].includes(status)) return 'failed'
  if (['queued'].includes(status)) return 'pending'
  if (['running', 'parsing', 'chunking', 'indexing'].includes(status)) return 'processing'
  if (['uploaded', 'parsed', 'chunked', 'indexed'].includes(status)) return 'completed'
  return 'pending'
}

const formatBytes = (bytes?: number | null) => {
  if (!bytes || bytes <= 0) return '-'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let size = bytes
  let unitIndex = 0
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex += 1
  }
  return `${size.toFixed(size < 10 && unitIndex > 0 ? 1 : 0)} ${units[unitIndex]}`
}

const toUiDocument = (doc: ApiDocument): Document => {
  const name = doc.title || doc.filename || doc.doc_key
  return {
    id: doc.id,
    doc_key: doc.doc_key,
    version: doc.version,
    name,
    type: detectType(doc),
    size: formatBytes(doc.size_bytes || undefined),
    status: mapStatus(doc.status),
    updated_at: doc.updated_at ? new Date(doc.updated_at).toLocaleString() : '',
    content: doc.source_uri || '',
    mime_type: doc.mime_type,
    error_code: doc.error_code,
    error_message: doc.error_message,
  }
}

function Page() {
  const { t } = useTranslation()
  const { knowledgeId } = useParams<{ knowledgeId: string }>()

  const [documents, setDocuments] = useState<Document[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedType, setSelectedType] = useState<string>('all')
  const [sortField, setSortField] = useState<string>('updated_at')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [selectedDocs, setSelectedDocs] = useState<string[]>([])
  const [previewDoc, setPreviewDoc] = useState<Document | null>(null)
  const [showUploadDialog, setShowUploadDialog] = useState(false)
  const [activeTab, setActiveTab] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [totalCount, setTotalCount] = useState(0)
  const [versionDoc, setVersionDoc] = useState<Document | null>(null)
  const [versions, setVersions] = useState<DocumentVersion[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [showTasksDialog, setShowTasksDialog] = useState(false)
  const [tasks, setTasks] = useState<IngestTask[]>([])
  const [tasksLoading, setTasksLoading] = useState(false)

  const { setHeaderContent } = useNavLayout()

  useEffect(() => {
    setHeaderContent(
      <PageHeader
        documentCount={totalCount}
        selectedDocs={selectedDocs}
        onShowUploadDialog={() => setShowUploadDialog(true)}
        onShowTasksDialog={() => setShowTasksDialog(true)}
        onBatchDelete={handleBatchDelete}
        onRefresh={() => {
          fetchDocuments()
        }}
      />
    )
    return () => setHeaderContent(null)
  }, [setHeaderContent, totalCount, selectedDocs])

  const fetchDocuments = async () => {
    if (!knowledgeId) return
    try {
      setLoading(true)
      const offset = (currentPage - 1) * pageSize
      const response = await listKnowledgeDocuments(knowledgeId, {
        limit: pageSize,
        offset,
      })
      const mapped = response.map(toUiDocument)
      const filtered = mapped.filter((doc) => {
        if (activeTab !== 'all' && doc.type !== activeTab) return false
        if (selectedType !== 'all' && doc.type !== selectedType) return false
        if (searchQuery && !doc.name.toLowerCase().includes(searchQuery.toLowerCase())) return false
        return true
      })
      const sorted = filtered.sort((a, b) => {
        const direction = sortOrder === 'asc' ? 1 : -1
        if (sortField === 'name') {
          return a.name.localeCompare(b.name) * direction
        }
        return a.updated_at.localeCompare(b.updated_at) * direction
      })
      setDocuments(sorted)
      const hasNext = response.length === pageSize
      setTotalCount(hasNext ? offset + response.length + pageSize : offset + response.length)
    } catch (error) {
      console.error('Failed to fetch documents:', error)
      toast.error(t('knowledge.document.list.fetch_error'))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchDocuments()
  }, [knowledgeId, searchQuery, selectedType, currentPage, pageSize, sortField, sortOrder, activeTab])

  const handleDeleteDoc = async (docId: string) => {
    if (!knowledgeId) return
    try {
      await deleteKnowledgeDocument(knowledgeId, docId)
      toast.success(t('knowledge.document.delete.success'))
      fetchDocuments()
    } catch (error) {
      toast.error(t('knowledge.document.delete.error'))
      console.error('Delete error:', error)
    }
  }

  const handleViewVersions = async (doc: Document) => {
    if (!knowledgeId) return
    try {
      setVersionsLoading(true)
      setVersionDoc(doc)
      const versionList = await listKnowledgeDocumentVersions(knowledgeId, doc.doc_key)
      const mapped = versionList.map((item) => ({
        version: item.version,
        created_at: item.created_at ? new Date(item.created_at).toLocaleString() : '',
      }))
      setVersions(mapped)
    } catch (error) {
      toast.error(t('knowledge.document.version.history.fetch_error'))
      console.error('Failed to load versions:', error)
    } finally {
      setVersionsLoading(false)
    }
  }

  const handleRollbackVersion = async (version: number) => {
    if (!knowledgeId || !versionDoc) return
    try {
      await rollbackKnowledgeDocumentVersion(knowledgeId, versionDoc.doc_key, version)
      toast.success(t('knowledge.document.version.rollback.success'))
      setVersionDoc(null)
      fetchDocuments()
    } catch (error) {
      toast.error(t('knowledge.document.version.rollback.error'))
      console.error('Failed to rollback version:', error)
    }
  }

  const extractFilename = (contentDisposition?: string) => {
    if (!contentDisposition) return null
    const match = /filename\*?=(?:UTF-8'')?\"?([^\";]+)\"?/i.exec(contentDisposition)
    if (!match) return null
    return decodeURIComponent(match[1])
  }

  const handleDownloadDoc = async (doc: Document) => {
    if (!knowledgeId) return
    try {
      const response = await downloadKnowledgeDocument(knowledgeId, doc.id)
      const blob = response.data as Blob
      const headerName = response.headers?.['content-disposition'] || response.headers?.['Content-Disposition']
      const filename = extractFilename(headerName) || doc.name || 'document'
      const url = URL.createObjectURL(blob)
      const link = window.document.createElement('a')
      link.href = url
      link.download = filename
      window.document.body.appendChild(link)
      link.click()
      link.remove()
      URL.revokeObjectURL(url)
    } catch (error) {
      toast.error(t('knowledge.document.download.error'))
      console.error('Failed to download document:', error)
    }
  }

  const handleBatchDelete = async () => {
    if (!knowledgeId || selectedDocs.length === 0) return
    try {
      await Promise.all(selectedDocs.map((docId) => deleteKnowledgeDocument(knowledgeId, docId)))
      toast.success(t('knowledge.document.batch_delete.success'))
      setSelectedDocs([])
      fetchDocuments()
    } catch (error) {
      toast.error(t('knowledge.document.batch_delete.error'))
      console.error('Batch delete error:', error)
    }
  }

  const handleRetryDoc = async (doc: Document) => {
    if (!knowledgeId) return
    try {
      await retryKnowledgeDocumentIngest(knowledgeId, doc.id)
      toast.success(t('knowledge.document.retry.success'))
      fetchDocuments()
    } catch (error) {
      toast.error(t('knowledge.document.retry.error'))
      console.error('Retry error:', error)
    }
  }

  const fetchTasks = async () => {
    if (!knowledgeId) return
    try {
      setTasksLoading(true)
      const response = await listKnowledgeIngestTasks(knowledgeId, { limit: 50, offset: 0 })
      setTasks(response)
    } catch (error) {
      console.error('Failed to fetch ingest tasks:', error)
      toast.error(t('knowledge.document.tasks.fetch_error'))
    } finally {
      setTasksLoading(false)
    }
  }

  const handleRetryTask = async (task: IngestTask) => {
    if (!knowledgeId) return
    try {
      await retryKnowledgeIngestTask(knowledgeId, task.id)
      toast.success(t('knowledge.document.tasks.retry_success'))
      fetchTasks()
      fetchDocuments()
    } catch (error) {
      console.error('Failed to retry task:', error)
      toast.error(t('knowledge.document.tasks.retry_error'))
    }
  }

  const handleCancelTask = async (task: IngestTask) => {
    if (!knowledgeId) return
    try {
      await cancelKnowledgeIngestTask(knowledgeId, task.id)
      toast.success(t('knowledge.document.tasks.cancel_success'))
      fetchTasks()
      fetchDocuments()
    } catch (error) {
      console.error('Failed to cancel task:', error)
      toast.error(t('knowledge.document.tasks.cancel_error'))
    }
  }

  useEffect(() => {
    if (!showTasksDialog) return
    fetchTasks()
  }, [showTasksDialog])

  const handlePageChange = (page: number) => {
    setCurrentPage(page)
    setSelectedDocs([])
  }

  const handlePageSizeChange = (size: number) => {
    setPageSize(size)
    setCurrentPage(1)
    setSelectedDocs([])
  }

  const handleSort = (field: string) => {
    if (field === sortField) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc')
    } else {
      setSortField(field)
      setSortOrder('desc')
    }
  }

  const handleDocSelect = (docId: string) => {
    setSelectedDocs((prev) => (prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]))
  }

  const handleSelectAll = () => {
    setSelectedDocs((prev) => (prev.length === documents.length ? [] : documents.map((doc) => doc.id)))
  }

  const documentTypeCounts = useMemo(() => {
    const counts = {
      all: documents.length,
      document: 0,
      image: 0,
      video: 0,
      website: 0,
      knowledge: 0,
    }
    documents.forEach((doc) => {
      if (doc.type in counts) {
        counts[doc.type as keyof typeof counts] += 1
      }
    })
    return counts
  }, [documents])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <DocumentHeader activeTab={activeTab} onTabChange={setActiveTab} documentTypeCounts={documentTypeCounts} />

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle>{t('knowledge.document.list.title')}</CardTitle>
            <DocumentFilterBar searchQuery={searchQuery} selectedType={selectedType} onSearchChange={setSearchQuery} onTypeChange={setSelectedType} />
          </div>
        </CardHeader>
        <CardContent>
          <DocumentTable
            documents={documents}
            knowledgeId={knowledgeId || ''}
            selectedDocs={selectedDocs}
            sortField={sortField}
            sortOrder={sortOrder}
            onSort={handleSort}
            onDocSelect={handleDocSelect}
            onSelectAll={handleSelectAll}
            onDeleteDoc={handleDeleteDoc}
            onPreviewDoc={setPreviewDoc}
            onViewVersions={handleViewVersions}
            onDownloadDoc={handleDownloadDoc}
            onRetryDoc={handleRetryDoc}
            currentPage={currentPage}
            pageSize={pageSize}
            totalCount={totalCount}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
          />
        </CardContent>
      </Card>

      <DocumentPreviewDialog
        open={!!previewDoc}
        onOpenChange={() => setPreviewDoc(null)}
        knowledgeId={knowledgeId || ''}
        document={previewDoc}
      />

      <VersionHistoryDialog
        open={!!versionDoc}
        onOpenChange={(open) => !open && setVersionDoc(null)}
        versions={versions}
        loading={versionsLoading}
        onRollback={handleRollbackVersion}
      />

      {knowledgeId && (
        <UploadDocumentDialog
          knowledgeId={knowledgeId}
          open={showUploadDialog}
          onOpenChange={setShowUploadDialog}
          onUploadSuccess={() => {
            fetchDocuments()
          }}
        />
      )}

      <IngestTasksDialog
        open={showTasksDialog}
        onOpenChange={setShowTasksDialog}
        tasks={tasks}
        loading={tasksLoading}
        onRefresh={fetchTasks}
        onRetry={handleRetryTask}
        onCancel={handleCancelTask}
      />

      {loading && (
        <div className="fixed inset-0 bg-background/80 backdrop-blur-sm flex items-center justify-center">
          <div className="flex flex-col items-center gap-2">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary"></div>
            <div className="text-sm">{t('knowledge.document.common.loading')}</div>
          </div>
        </div>
      )}
    </div>
  )
}

export default Page
