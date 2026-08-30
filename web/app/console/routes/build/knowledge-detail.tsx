import { useEffect, useState } from 'react'

import { useParams } from 'react-router'
import { toast } from 'sonner'

import {
  Backlink,
  ConsoleButton,
  ConsoleModal,
  DataStateNote,
  FilterChip,
  IconReplay,
  IconSearch,
  StatTile,
  StatTileGrid,
  StatusChip,
  TaskProgress,
  WorkbenchPanel,
  useDataStateLabel,
  type ConsoleStatus,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor, compactNumber, latency, percent, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  deleteKnowledgeBase,
  deleteKnowledgeDocument,
  getKnowledgeBase,
  getKnowledgeRetrievalSummary,
  getKnowledgeRunCostSummary,
  listKnowledgeChunks,
  listKnowledgeDocumentVersions,
  listKnowledgeDocuments,
  createKnowledgeIndex,
  deleteKnowledgeIndex,
  listKnowledgeIndexes,
  updateKnowledgeIndex,
  listKnowledgeUsages,
  queryKnowledge,
  rebuildKnowledgeIndex,
  retryKnowledgeDocumentIngest,
  rollbackKnowledgeDocumentVersion,
  updateKnowledgeBase,
  updateKnowledgeChunk,
  uploadKnowledgeDocument,
  type KnowledgeChunk,
  type KnowledgeChunkUpdateRequest,
  type KnowledgeDocument,
  type KnowledgeIndex,
  type KnowledgeQueryResponse,
} from '@/services/knowledge-service'
import { requestErrorMessage } from '@/utils/request'

type KdTab = 'documents' | 'chunks' | 'testing' | 'usages' | 'indexes' | 'analytics' | 'settings'

const DOCS_PAGE_SIZE = 50
const CHUNKS_PAGE_SIZE = 50

/** Knowledge base lifecycle → shared console status vocabulary. */
function baseStatus(status?: string): ConsoleStatus {
  switch (status) {
    case 'active':
      return 'pass'
    case 'draft':
      return 'draft'
    case 'archived':
    case 'disabled':
      return 'disabled'
    case 'failed':
    case 'error':
      return 'failed'
    default:
      return 'info'
  }
}

/** Document / chunk pipeline states → shared console status vocabulary. */
function pipelineStatus(status?: string): ConsoleStatus {
  switch (status) {
    case 'indexed':
    case 'ready':
    case 'active':
      return 'pass'
    case 'failed':
    case 'error':
      return 'failed'
    case 'pending':
    case 'queued':
      return 'queued'
    case 'parsing':
    case 'chunking':
    case 'indexing':
    case 'processing':
    case 'running':
      return 'running'
    case 'disabled':
      return 'disabled'
    default:
      return 'info'
  }
}

function readNumber(source: Record<string, unknown> | undefined, key: string): number | null {
  const value = source?.[key]
  return typeof value === 'number' ? value : null
}

function readString(source: Record<string, unknown> | undefined, key: string): string | null {
  const value = source?.[key]
  return typeof value === 'string' && value.trim() ? value : null
}

function documentLabel(doc: KnowledgeDocument): string {
  return doc.source_uri || doc.title || doc.filename || doc.doc_key
}

/**
 * The threshold box carries the prototype's `score ≥ 0.42` phrasing, so the
 * saved value is the first number in whatever the operator typed; an empty or
 * number-free box clears `retrieval_json.keyword_min_score`.
 */
function parseThreshold(value: string): number | null {
  const match = value.match(/-?\d+(?:\.\d+)?/)
  if (!match) return null
  const parsed = Number(match[0])
  return Number.isFinite(parsed) ? parsed : null
}

const CHUNK_STATUS_OPTIONS: KnowledgeChunkUpdateRequest['index_status'][] = [
  'pending',
  'indexed',
  'failed',
  'disabled',
]

export default function ConsoleKnowledgeDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<KdTab>('documents')
  const [docOffset, setDocOffset] = useState(0)
  const [docFilter, setDocFilter] = useState('')
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [testQuery, setTestQuery] = useState('')
  const [uploadOpen, setUploadOpen] = useState(false)
  const [uploadFiles, setUploadFiles] = useState<File[]>([])
  const [deletingDoc, setDeletingDoc] = useState<KnowledgeDocument | null>(null)
  const [versionsDoc, setVersionsDoc] = useState<KnowledgeDocument | null>(null)
  const [restoring, setRestoring] = useState<KnowledgeDocument | null>(null)
  const [retryDocId, setRetryDocId] = useState<string | null>(null)
  const [editingChunk, setEditingChunk] = useState<KnowledgeChunk | null>(null)
  const [chunkForm, setChunkForm] = useState({ content: '', indexStatus: '' })
  const [settingsForm, setSettingsForm] = useState({ name: '', source: '', threshold: '' })
  const [deleteBaseOpen, setDeleteBaseOpen] = useState(false)
  const [indexForm, setIndexForm] = useState<{
    open: false | 'create' | 'edit'
    id: string
    name: string
    embedding_model_ref: string
    metric_type: string
    is_primary: boolean
  }>({ open: false, id: '', name: '', embedding_model_ref: '', metric_type: 'cosine', is_primary: false })
  const [deletingIndex, setDeletingIndex] = useState<KnowledgeIndex | null>(null)

  const knowledgeId = id || ''
  const enabled = Boolean(knowledgeId)

  const baseQuery = useQuery({
    queryKey: ['console', 'knowledge', 'base', knowledgeId],
    queryFn: () => getKnowledgeBase(knowledgeId),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const documentsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'documents', knowledgeId, docOffset],
    queryFn: () => listKnowledgeDocuments(knowledgeId, { limit: DOCS_PAGE_SIZE, offset: docOffset }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const indexesQuery = useQuery({
    queryKey: ['console', 'knowledge', 'indexes', knowledgeId],
    queryFn: () => listKnowledgeIndexes(knowledgeId),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const usagesQuery = useQuery({
    queryKey: ['console', 'knowledge', 'usages', knowledgeId],
    queryFn: () => listKnowledgeUsages(knowledgeId),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const costQuery = useQuery({
    queryKey: ['console', 'knowledge', 'cost-summary', knowledgeId],
    queryFn: () => getKnowledgeRunCostSummary(knowledgeId),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })

  // Retrieval quality is aggregated from the run ledger, so it covers every
  // query in the window rather than the page of runs shown below.
  const retrievalQuery = useQuery({
    queryKey: ['console', 'knowledge', 'retrieval', knowledgeId],
    queryFn: () =>
      getKnowledgeRetrievalSummary(knowledgeId, {
        since: new Date(Date.now() - 86_400_000).toISOString(),
      }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })

  const base = baseQuery.data
  const documents = documentsQuery.data || []
  const indexes = indexesQuery.data || []
  const usages = usagesQuery.data || []
  const cost = costQuery.data
  const retrievalQuality = retrievalQuery.data

  // Chunks hang off a document, so the first document of the current page is
  // the default selection until a row is picked.
  const activeDocId = selectedDocId || documents[0]?.id || ''
  const chunksQuery = useQuery({
    queryKey: ['console', 'knowledge', 'chunks', knowledgeId, activeDocId],
    queryFn: () => listKnowledgeChunks(knowledgeId, activeDocId, { limit: CHUNKS_PAGE_SIZE }),
    options: {
      enabled: enabled && Boolean(activeDocId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const chunks = chunksQuery.data || []

  const retrieval = base?.retrieval_json
  const topK = readNumber(retrieval, 'top_k') ?? 5
  const useRerank = retrieval?.use_rerank === true

  const queryMutation = useMutation<KnowledgeQueryResponse, unknown, void>({
    mutationKey: ['console', 'knowledge', 'query', knowledgeId],
    mutationFn: () =>
      queryKnowledge(knowledgeId, {
        query: testQuery.trim(),
        top_k: topK,
        use_rerank: useRerank,
      }),
  })
  const results = queryMutation.data?.results || []

  const docsState = useDataStateLabel({
    isPending: documentsQuery.isPending,
    isError: documentsQuery.isError,
  })
  const chunksState = useDataStateLabel({
    isPending: Boolean(activeDocId) && chunksQuery.isPending,
    isError: chunksQuery.isError,
  })
  const indexesState = useDataStateLabel({
    isPending: indexesQuery.isPending,
    isError: indexesQuery.isError,
  })
  const usagesState = useDataStateLabel({
    isPending: usagesQuery.isPending,
    isError: usagesQuery.isError,
  })

  const name = base?.name || knowledgeId
  const primaryIndex = indexes.find((index) => index.is_primary) || indexes[0]
  const chunkSize = readNumber(base?.chunking_json, 'chunk_size')
  const chunkOverlap = readNumber(base?.chunking_json, 'chunk_overlap')
  const sourceUri =
    readString(base?.settings_json, 'source_uri') || readString(base?.settings_json, 'source_kind')
  const embeddingRef = primaryIndex?.embedding_model_ref || base?.default_embedding_model_ref
  const lastSyncAt = primaryIndex?.last_build_at || base?.last_indexed_at || base?.last_ingested_at
  const lastSyncRunId = primaryIndex?.last_run_id
  const agentUsages = usages.filter((usage) => usage.resource_kind === 'agent').length
  const workflowUsages = usages.filter((usage) => usage.resource_kind === 'workflow').length

  const visibleDocuments = documents.filter((doc) => {
    const query = docFilter.trim().toLowerCase()
    if (!query) return true
    return documentLabel(doc).toLowerCase().includes(query)
  })
  const activeDoc = documents.find((doc) => doc.id === activeDocId)

  // Settings mirror the loaded record; a refetch after a save re-seeds them.
  useEffect(() => {
    if (!base) return
    const keywordMin = readNumber(base.retrieval_json, 'keyword_min_score')
    setSettingsForm({
      name: base.name || '',
      // The meta row above falls back to settings_json.source_kind for display;
      // this field binds to source_uri alone so saving can never write the kind
      // into the uri.
      source: readString(base.settings_json, 'source_uri') ?? '',
      threshold: keywordMin != null ? `score ≥ ${keywordMin}` : '',
    })
  }, [base])

  const onWriteError = (fallback: string) => (error: unknown) => {
    setRetryDocId(null)
    toast.error(requestErrorMessage(error, fallback))
  }

  // "Sync now" rebuilds the primary index — the same call the legacy settings
  // page makes; there is no library-level re-sync endpoint.
  const afterIndexWrite = () => {
    setIndexForm((state) => ({ ...state, open: false }))
    setDeletingIndex(null)
    void indexesQuery.refetch()
    void baseQuery.refetch()
  }
  const onIndexError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const createIndexMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'index', 'create', knowledgeId],
    mutationFn: () =>
      createKnowledgeIndex(knowledgeId, {
        name: indexForm.name.trim(),
        embedding_model_ref: indexForm.embedding_model_ref.trim(),
        metric_type: indexForm.metric_type,
        is_primary: indexForm.is_primary,
      }),
    onSuccess: afterIndexWrite,
    onError: onIndexError('Failed to create the index'),
  })

  const updateIndexMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'index', 'update', knowledgeId],
    // The embedding model is only sent when it actually changed: switching it
    // invalidates every vector, so it must not ride along on a rename.
    mutationFn: () => {
      const current = indexes.find((row) => row.id === indexForm.id)
      const nextModel = indexForm.embedding_model_ref.trim()
      return updateKnowledgeIndex(knowledgeId, indexForm.id, {
        name: indexForm.name.trim(),
        is_primary: indexForm.is_primary,
        ...(current && nextModel && nextModel !== current.embedding_model_ref
          ? { embedding_model_ref: nextModel }
          : {}),
      })
    },
    onSuccess: afterIndexWrite,
    onError: onIndexError('Failed to update the index'),
  })

  const deleteIndexMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'index', 'delete', knowledgeId],
    mutationFn: () => deleteKnowledgeIndex(knowledgeId, deletingIndex!.id),
    onSuccess: afterIndexWrite,
    onError: onIndexError('Failed to delete the index'),
  })

  const rebuildMutation = useMutation<unknown, unknown, string | undefined>({
    mutationKey: ['console', 'knowledge', 'rebuild', knowledgeId],
    // The header's Sync rebuilds whichever index serves retrieval; a row's
    // Rebuild has to name its own, or it would silently rebuild a different one.
    mutationFn: (indexId?: string) =>
      rebuildKnowledgeIndex(knowledgeId, indexId || primaryIndex?.id || ''),
    onSuccess: () => {
      toast.success(t('console.knowDetail.syncQueued'))
      void indexesQuery.refetch()
      void baseQuery.refetch()
    },
    onError: onWriteError('Failed to queue the index rebuild'),
  })

  const uploadMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'upload', knowledgeId],
    mutationFn: async () => {
      // One document per file, uploaded in order so a mid-batch failure leaves
      // the earlier documents ingesting rather than rolling everything back.
      for (const file of uploadFiles) {
        await uploadKnowledgeDocument(
          knowledgeId,
          {
            doc_key: `${Date.now()}-${file.name}`,
            source_kind: 'upload',
            title: file.name,
            filename: file.name,
            mime_type: file.type,
            size_bytes: file.size,
          },
          file,
        )
      }
    },
    onSuccess: () => {
      setUploadOpen(false)
      setUploadFiles([])
      void documentsQuery.refetch()
      void baseQuery.refetch()
    },
    onError: onWriteError('Failed to upload the documents'),
  })

  // Re-crawl and "Reprocess with OCR" are the same operation on the API: the
  // document is queued for ingest again. There is no separate crawl endpoint
  // and no OCR switch — the labels are prototype copy.
  const retryDocMutation = useMutation<unknown, unknown, KnowledgeDocument>({
    mutationKey: ['console', 'knowledge', 'retry-ingest', knowledgeId],
    mutationFn: (doc) => retryKnowledgeDocumentIngest(knowledgeId, doc.id),
    onMutate: (doc) => setRetryDocId(doc.id),
    onSuccess: () => {
      setRetryDocId(null)
      void documentsQuery.refetch()
    },
    onError: onWriteError('Failed to reprocess the document'),
  })

  // A document keeps its history under its doc_key, not its row id.
  const versionsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'doc-versions', knowledgeId, versionsDoc?.doc_key],
    queryFn: () => listKnowledgeDocumentVersions(knowledgeId, versionsDoc!.doc_key),
    options: {
      enabled: Boolean(knowledgeId && versionsDoc?.doc_key),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const rollbackMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'doc-rollback', knowledgeId],
    mutationFn: () =>
      rollbackKnowledgeDocumentVersion(knowledgeId, restoring!.doc_key, restoring!.version),
    onSuccess: () => {
      setRestoring(null)
      setVersionsDoc(null)
      void documentsQuery.refetch()
    },
    onError: onWriteError('Failed to restore the version'),
  })

  const versionsState = useDataStateLabel({
    isPending: Boolean(versionsDoc) && versionsQuery.isPending,
    isError: versionsQuery.isError,
  })

  const deleteDocMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'delete-document', knowledgeId],
    mutationFn: () => deleteKnowledgeDocument(knowledgeId, deletingDoc!.id),
    onSuccess: () => {
      setDeletingDoc(null)
      void documentsQuery.refetch()
      void baseQuery.refetch()
    },
    onError: onWriteError('Failed to delete the document'),
  })

  const chunkDirty =
    editingChunk != null &&
    (chunkForm.content !== (editingChunk.text_preview || '') ||
      chunkForm.indexStatus !== editingChunk.index_status)

  const chunkMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'update-chunk', knowledgeId],
    mutationFn: () => {
      const payload: KnowledgeChunkUpdateRequest = {}
      // The list endpoint returns `text_preview`, not the full chunk body, so
      // `content` is only sent when the operator actually rewrote the text —
      // otherwise a save would truncate the chunk to its own preview.
      if (chunkForm.content !== (editingChunk?.text_preview || '')) {
        payload.content = chunkForm.content
      }
      if (chunkForm.indexStatus !== editingChunk?.index_status) {
        payload.index_status = chunkForm.indexStatus as KnowledgeChunkUpdateRequest['index_status']
      }
      return updateKnowledgeChunk(knowledgeId, activeDocId, editingChunk!.id, payload)
    },
    onSuccess: () => {
      setEditingChunk(null)
      void chunksQuery.refetch()
    },
    onError: onWriteError('Failed to save the chunk'),
  })

  const saveSettingsMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'update', knowledgeId],
    mutationFn: () => {
      const settingsJson = { ...(base?.settings_json || {}) }
      const source = settingsForm.source.trim()
      if (source) settingsJson.source_uri = source
      else delete settingsJson.source_uri

      const retrievalJson = { ...(base?.retrieval_json || {}) }
      const threshold = parseThreshold(settingsForm.threshold)
      if (threshold != null) retrievalJson.keyword_min_score = threshold
      else delete retrievalJson.keyword_min_score

      return updateKnowledgeBase(knowledgeId, {
        name: settingsForm.name.trim(),
        settings_json: settingsJson,
        retrieval_json: retrievalJson,
      })
    },
    onSuccess: () => {
      void baseQuery.refetch()
    },
    onError: onWriteError('Failed to save the library settings'),
  })

  const deleteBaseMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'delete', knowledgeId],
    mutationFn: () => deleteKnowledgeBase(knowledgeId),
    onSuccess: () => {
      setDeleteBaseOpen(false)
      navigate('/build/knowledge')
    },
    onError: onWriteError('Failed to delete the library'),
  })

  const tabItems: [KdTab, string, React.ReactNode][] = [
    ['documents', t('console.knowDetail.tabs.documents'), base ? compactNumber(base.doc_count) : null],
    ['chunks', t('console.knowDetail.tabs.chunks'), base ? compactNumber(base.chunk_count) : null],
    ['testing', t('console.knowDetail.tabs.testing'), null],
    ['usages', t('console.knowDetail.tabs.usages'), usages.length ? String(usages.length) : null],
    ['indexes', t('console.knowDetail.indexes.tab'), indexes.length ? String(indexes.length) : null],
    ['analytics', t('console.knowDetail.tabs.analytics'), null],
    ['settings', t('console.knowDetail.tabs.settings'), null],
  ]

  return (
    <>
      <Backlink to="/build/knowledge">{t('console.knowDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <StatusChip
          status={baseStatus(base?.status)}
          label={base ? base.status.toUpperCase() : '—'}
        />
        <span className="chip">
          <i style={{ background: catColor(knowledgeId) }} />
          {base?.knowledge_type || '—'}
        </span>
        <span className="spacer" />
        <ConsoleButton
          disabled={!primaryIndex || rebuildMutation.isPending}
          onClick={() => rebuildMutation.mutate(undefined)}
        >
          <IconReplay />
          {t('console.knowDetail.syncNow')}
        </ConsoleButton>
        <ConsoleButton
          variant="primary"
          disabled={!enabled}
          onClick={() => {
            setUploadFiles([])
            setUploadOpen(true)
          }}
        >
          {t('console.knowDetail.addDocs')}
        </ConsoleButton>
      </div>

      <div className="rd-meta">
        <span>Source<b>{sourceUri || '—'}</b></span>
        <span>Embedding<b>{embeddingRef || '—'}</b></span>
        <span>
          Chunking
          <b>
            {chunkSize != null
              ? `${chunkSize} tok${chunkOverlap != null ? ` / ${chunkOverlap} overlap` : ''}`
              : '—'}
          </b>
        </span>
        {/* No sync-schedule field exists on the knowledge record; ingest is
            triggered per document or per ingest task. */}
        <span>Sync<b>—</b></span>
        <span>
          Last sync
          <b>
            {relativeTime(lastSyncAt)}
            {lastSyncRunId && (
              <>
                {' · '}
                <a
                  className="runid"
                  href={`/observe/runs/${lastSyncRunId}`}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(`/observe/runs/${lastSyncRunId}`)
                  }}
                >
                  {lastSyncRunId}
                </a>
              </>
            )}
          </b>
        </span>
        <span>Bound to<b>{`${agentUsages} agents · ${workflowUsages} workflows`}</b></span>
      </div>

      <div className="tabs">
        {tabItems.map(([value, label, count]) => (
          <button key={value} type="button" className={cn(tab === value && 'on')} onClick={() => setTab(value)}>
            {label}
            {count && <span className="mono">{count}</span>}
          </button>
        ))}
      </div>

      {tab === 'documents' && (
        <WorkbenchPanel
          title={t('console.knowDetail.tabs.documents')}
          hint={t('console.knowDetail.documentsHint')}
          actions={
            <div className="fsearch" style={{ maxWidth: 240, height: 26 }}>
              <IconSearch size={12} style={{ color: 'var(--faint)' }} />
              <input
                placeholder={t('console.knowDetail.filterDocs')}
                value={docFilter}
                onChange={(event) => setDocFilter(event.target.value)}
              />
            </div>
          }
        >
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.document')}</th>
                <th>{t('console.knowDetail.columns.status')}</th>
                <th className="num">{t('console.knowDetail.columns.chunks')}</th>
                <th className="num">{t('console.knowDetail.columns.tokens')}</th>
                <th className="num">{t('console.knowDetail.columns.updated')}</th>
                <th className="num" />
              </tr>
            </thead>
            <tbody>
              {visibleDocuments.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-note">{docsState}</div>
                  </td>
                </tr>
              ) : (
                visibleDocuments.map((doc) => (
                  <tr
                    key={doc.id}
                    className="rowlink"
                    onClick={() => {
                      setSelectedDocId(doc.id)
                      setTab('chunks')
                    }}
                  >
                    <td>
                      <span className="mono">{documentLabel(doc)}</span>
                    </td>
                    <td>
                      <StatusChip status={pipelineStatus(doc.status)} label={doc.status.toUpperCase()} />
                    </td>
                    <td className="num dim">
                      {readNumber(doc.index_meta_json, 'chunk_count') ?? '—'}
                    </td>
                    {/* Documents store no aggregate token count — only chunks
                        carry token_count, and they are not joined here. */}
                    <td className="num dim">—</td>
                    <td className="num dimmer">{relativeTime(doc.updated_at)}</td>
                    <td className="num" onClick={(event) => event.stopPropagation()}>
                      {doc.status !== 'failed' && (
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          disabled={retryDocId === doc.id}
                          onClick={() => retryDocMutation.mutate(doc)}
                        >
                          {t('console.knowDetail.recrawl')}
                        </ConsoleButton>
                      )}
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        onClick={(event) => {
                          event.stopPropagation()
                          setVersionsDoc(doc)
                        }}
                      >
                        {t('console.knowDetail.versions')}
                      </ConsoleButton>
                      {doc.status === 'failed' && (
                        <ConsoleButton
                          size="sm"
                          disabled={retryDocId === doc.id}
                          onClick={() => retryDocMutation.mutate(doc)}
                        >
                          {t('console.knowledge.reprocess')}
                        </ConsoleButton>
                      )}
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        style={{ color: 'var(--danger-foreground)' }}
                        onClick={() => setDeletingDoc(doc)}
                      >
                        {t('console.knowDetail.deleteDoc')}
                      </ConsoleButton>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="pager">
            <span>
              {t('console.knowDetail.docsPager', {
                loaded: documents.length,
                total: base ? compactNumber(base.doc_count) : '—',
              })}
            </span>
            <span className="spacer" />
            <ConsoleButton
              size="sm"
              disabled={docOffset === 0}
              onClick={() => setDocOffset((offset) => Math.max(0, offset - DOCS_PAGE_SIZE))}
            >
              {t('console.runs.prev')}
            </ConsoleButton>
            <ConsoleButton
              size="sm"
              disabled={documents.length < DOCS_PAGE_SIZE}
              onClick={() => setDocOffset((offset) => offset + DOCS_PAGE_SIZE)}
            >
              {t('console.runs.next')}
            </ConsoleButton>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'chunks' && (
        <WorkbenchPanel title={t('console.knowDetail.chunksTitle')} hint={t('console.knowDetail.chunksHint')}>
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.chunk')}</th>
                <th>{t('console.knowDetail.columns.document')}</th>
                <th>{t('console.knowDetail.columns.preview')}</th>
                <th className="num">{t('console.knowDetail.columns.tokens')}</th>
                <th>{t('console.knowDetail.columns.embedding')}</th>
              </tr>
            </thead>
            <tbody>
              {chunks.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <div className="empty-note">{chunksState}</div>
                  </td>
                </tr>
              ) : (
                chunks.map((chunk) => (
                  <tr
                    key={chunk.id}
                    className="rowlink"
                    onClick={() => {
                      setChunkForm({
                        content: chunk.text_preview || '',
                        indexStatus: chunk.index_status,
                      })
                      setEditingChunk(chunk)
                    }}
                  >
                    <td>
                      <span className="mono">{chunk.chunk_key || `${chunk.id}#${chunk.chunk_no}`}</span>
                    </td>
                    <td className="mono dim">{activeDoc ? documentLabel(activeDoc) : '—'}</td>
                    <td className="dim" style={{ maxWidth: 340, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {chunk.text_preview || '—'}
                    </td>
                    <td className="num dim">{chunk.token_count ?? '—'}</td>
                    <td>
                      <StatusChip
                        status={pipelineStatus(chunk.index_status)}
                        label={chunk.index_status.toUpperCase()}
                      />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.chunksNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'testing' && (
        <WorkbenchPanel title={t('console.knowDetail.testingTitle')} hint={t('console.knowDetail.testingHint')}>
          <div style={{ display: 'flex', gap: 8, padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
            <div className="fsearch" style={{ maxWidth: 'none', flex: 1, height: 30 }}>
              <IconSearch size={12} style={{ color: 'var(--faint)' }} />
              <input
                value={testQuery}
                onChange={(event) => setTestQuery(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && testQuery.trim()) queryMutation.mutate()
                }}
              />
            </div>
            <FilterChip>top_k: {topK}</FilterChip>
            <FilterChip>rerank: {useRerank ? 'on' : 'off'}</FilterChip>
            <ConsoleButton
              variant="primary"
              style={{ height: 28 }}
              disabled={!testQuery.trim() || queryMutation.isPending}
              onClick={() => queryMutation.mutate()}
            >
              {t('console.knowDetail.runQuery')}
            </ConsoleButton>
          </div>
          {results.length === 0 ? (
            <DataStateNote isPending={queryMutation.isPending} isError={queryMutation.isError} />
          ) : (
            results.map((result) => {
              const score = result.score <= 1 ? result.score * 100 : result.score
              return (
                <div key={result.chunk_id} className="tres">
                  <div className="tres-h">
                    <TaskProgress
                      pct={Math.max(0, Math.min(100, Math.round(score)))}
                      label={result.score.toFixed(2)}
                    />
                    <span className="mono">{result.chunk_id}</span>
                    <span className="mono">{result.document_id}</span>
                    <span className="spacer" style={{ flex: 1 }} />
                    {/* The query response carries no per-result timing. */}
                  </div>
                  <p>{result.text}</p>
                </div>
              )
            })
          )}
          <div className="pager">
            <span>{t('console.knowDetail.testingNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'usages' && (
        <WorkbenchPanel>
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.consumer')}</th>
                <th>{t('console.knowDetail.columns.kind')}</th>
                <th className="num">{t('console.knowDetail.columns.queries')}</th>
                <th className="num">{t('console.knowDetail.columns.hitRate')}</th>
                <th className="num">{t('console.knowDetail.columns.cited')}</th>
                <th className="num">{t('console.knowDetail.columns.lastQuery')}</th>
              </tr>
            </thead>
            <tbody>
              {usages.length === 0 ? (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-note">{usagesState}</div>
                  </td>
                </tr>
              ) : (
                usages.map((usage) => (
                  <tr key={usage.resource_version_id} className="rowlink">
                    <td>
                      <span
                        className="idm"
                        style={{ '--c': catColor(usage.resource_id) } as React.CSSProperties}
                      >
                        <i />
                        {usage.resource_name}
                      </span>
                    </td>
                    <td className="dim">{usage.resource_kind}</td>
                    <td className="num dim">{compactNumber(usage.run_count)}</td>
                    {/* The usage projection counts runs only — it carries no
                        retrieval hit rate and no citation count. */}
                    <td className="num dim">—</td>
                    <td className="num dim">—</td>
                    <td className="num dimmer">{relativeTime(usage.last_run_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.usagesNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'indexes' && (
        <WorkbenchPanel
          title={t('console.knowDetail.indexes.title')}
          hint={t('console.knowDetail.indexes.hint')}
          actions={
            <ConsoleButton
              variant="primary"
              style={{ height: 24, fontSize: 11 }}
              onClick={() =>
                setIndexForm({
                  open: 'create',
                  id: '',
                  name: '',
                  embedding_model_ref: base?.default_embedding_model_ref || '',
                  metric_type: 'cosine',
                  is_primary: indexes.length === 0,
                })
              }
            >
              {t('console.knowDetail.indexes.newIndex')}
            </ConsoleButton>
          }
        >
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.indexes.columns.index')}</th>
                <th>{t('console.knowDetail.indexes.columns.embedding')}</th>
                <th className="num">{t('console.knowDetail.indexes.columns.dim')}</th>
                <th>{t('console.knowDetail.indexes.columns.metric')}</th>
                <th className="num">{t('console.knowDetail.indexes.columns.vectors')}</th>
                <th>{t('console.knowDetail.indexes.columns.status')}</th>
                <th className="num">{t('console.knowDetail.indexes.columns.lastBuild')}</th>
                <th className="num" />
              </tr>
            </thead>
            <tbody>
              {indexes.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="empty-note">
                      {indexesQuery.isPending || indexesQuery.isError
                        ? indexesState
                        : t('console.knowDetail.indexes.empty')}
                    </div>
                  </td>
                </tr>
              ) : (
                indexes.map((index) => (
                  <tr key={index.id} className="rowlink">
                    <td>
                      <span className="idm" style={{ '--c': catColor(index.id) } as React.CSSProperties}>
                        <i />
                        <span>
                          <b style={{ fontWeight: 600 }}>{index.name}</b>
                          <br />
                          <span className="dimmer" style={{ fontSize: 10.5 }}>
                            {index.is_primary
                              ? t('console.knowDetail.indexes.primary')
                              : t('console.knowDetail.indexes.candidate')}
                          </span>
                        </span>
                      </span>
                    </td>
                    <td className="mono dim">{index.embedding_model_ref}</td>
                    <td className="num dim">{index.dimension || '—'}</td>
                    <td className="dim">{index.metric_type || '—'}</td>
                    <td className="num dim">{compactNumber(index.vector_count)}</td>
                    <td>
                      <StatusChip status={pipelineStatus(index.status)} label={index.status.toUpperCase()} />
                    </td>
                    <td className="num dimmer">{relativeTime(index.last_build_at)}</td>
                    <td className="num">
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          disabled={rebuildMutation.isPending}
                          onClick={() => rebuildMutation.mutate(index.id)}
                        >
                          {t('console.knowDetail.indexes.rebuild')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          onClick={() =>
                            setIndexForm({
                              open: 'edit',
                              id: index.id,
                              name: index.name,
                              embedding_model_ref: index.embedding_model_ref,
                              metric_type: index.metric_type,
                              is_primary: index.is_primary,
                            })
                          }
                        >
                          {t('console.knowDetail.indexes.edit')}
                        </ConsoleButton>
                        {/* The index serving retrieval cannot be removed out from
                            under it; promote another to primary first. */}
                        {!index.is_primary && (
                          <ConsoleButton
                            variant="ghost"
                            size="sm"
                            style={{ color: 'var(--danger-foreground)' }}
                            onClick={() => setDeletingIndex(index)}
                          >
                            {t('console.knowDetail.indexes.del')}
                          </ConsoleButton>
                        )}
                      </span>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.indexes.note')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'analytics' && (
        <>
          <StatTileGrid>
            <StatTile
              label="Queries · 24h"
              value={cost ? compactNumber(cost.request_count) : '—'}
              na={!cost || cost.request_count == null}
              sub="all retrieval runs"
            />
            <StatTile
              label="Hit rate"
              value={retrievalQuality?.hit_rate == null ? '—' : percent(retrievalQuality.hit_rate)}
              na={retrievalQuality?.hit_rate == null}
              sub={
                <span className="mono dimmer">
                  {retrievalQuality ? `score ≥ ${retrievalQuality.score_threshold} threshold` : '—'}
                </span>
              }
            />
            <StatTile
              label="P95 retrieval"
              value={cost && cost.request_count ? latency(cost.ms_total / cost.request_count) : '—'}
              na={!cost || !cost.request_count}
              sub={
                <span className="mono dimmer">
                  {cost ? `embed ${cost.embedding_count} · rerank ${cost.rerank_count}` : '—'}
                </span>
              }
            />
            <StatTile
              label="Zero-hit queries"
              value={retrievalQuality?.zero_hit_rate == null ? '—' : percent(retrievalQuality.zero_hit_rate)}
              na={retrievalQuality?.zero_hit_rate == null}
              sub={
                <span className="mono dimmer">
                  {retrievalQuality
                    ? `${retrievalQuality.zero_hits} of ${retrievalQuality.queries} queries`
                    : '—'}
                </span>
              }
            />
          </StatTileGrid>
          <WorkbenchPanel title={t('console.knowDetail.topQueries')} hint={t('console.knowDetail.topQueriesHint')}>
            <table>
              <thead>
                <tr>
                  <th>{t('console.knowDetail.columns.query')}</th>
                  <th className="num">{t('console.knowDetail.columns.count')}</th>
                  <th className="num">{t('console.knowDetail.columns.avgScore')}</th>
                  <th>{t('console.knowDetail.columns.outcome')}</th>
                </tr>
              </thead>
              <tbody>
                {/* BACKEND-PENDING: query-text analytics are not persisted —
                    there is no top-queries endpoint on knowledge. */}
                <tr>
                  <td colSpan={4}>
                    <div className="empty-note">{t('console.common.empty')}</div>
                  </td>
                </tr>
              </tbody>
            </table>
          </WorkbenchPanel>
        </>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel
          title={t('console.knowDetail.settingsTitle')}
          actions={
            <ConsoleButton
              variant="primary"
              size="sm"
              disabled={!base || !settingsForm.name.trim() || saveSettingsMutation.isPending}
              onClick={() => saveSettingsMutation.mutate(undefined)}
            >
              {t('console.common.save')}
            </ConsoleButton>
          }
        >
          <div className="frow">
            <label>{t('console.knowDetail.fields.name')}</label>
            <input
              className="input"
              value={settingsForm.name}
              onChange={(event) =>
                setSettingsForm((state) => ({ ...state, name: event.target.value }))
              }
            />
          </div>
          <div className="frow">
            <label>
              {t('console.knowDetail.fields.source')}
              <small>{t('console.knowDetail.fields.sourceHint')}</small>
            </label>
            <input
              className="input"
              value={settingsForm.source}
              onChange={(event) =>
                setSettingsForm((state) => ({ ...state, source: event.target.value }))
              }
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            />
          </div>
          {/* BACKEND-PENDING: sync schedule, chunking preset and embedding
              choice are not yet bound — the knowledge record stores free-form
              chunking_json / default_embedding_model_ref rather than the
              preset enums these controls offer. */}
          <div className="frow">
            <label>{t('console.knowDetail.fields.schedule')}</label>
            <select className="input" defaultValue="manual only">
              <option>nightly 02:00Z</option>
              <option>hourly</option>
              <option>manual only</option>
            </select>
          </div>
          <div className="frow">
            <label>
              {t('console.knowDetail.fields.chunking')}
              <small>{t('console.knowDetail.fields.chunkingHint')}</small>
            </label>
            <select className="input" defaultValue="auto · 512 tokens, 64 overlap">
              <option>auto · 512 tokens, 64 overlap</option>
              <option>auto · 1024 tokens</option>
              <option>by heading</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.knowDetail.fields.embedding')}</label>
            <select className="input" defaultValue="bge-m3 · vllm self-hosted">
              <option>bge-m3 · vllm self-hosted</option>
              <option>voyage-3</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.knowDetail.fields.threshold')}</label>
            <input
              className="input"
              value={settingsForm.threshold}
              onChange={(event) =>
                setSettingsForm((state) => ({ ...state, threshold: event.target.value }))
              }
              style={{ maxWidth: 140 }}
            />
          </div>
          <div className="frow">
            <label style={{ color: 'var(--danger-foreground)' }}>
              {t('console.knowDetail.fields.del')}
              <small>{t('console.knowDetail.fields.delHint')}</small>
            </label>
            <div>
              <ConsoleButton
                style={{ color: 'var(--danger-foreground)' }}
                disabled={!base}
                onClick={() => setDeleteBaseOpen(true)}
              >
                {t('console.knowDetail.fields.delBtn')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={uploadOpen}
        onOpenChange={setUploadOpen}
        title={t('console.knowDetail.uploadTitle')}
        note={t('console.knowDetail.uploadNote')}
        confirmLabel={t('console.knowDetail.uploadConfirm')}
        confirmDisabled={uploadFiles.length === 0}
        busy={uploadMutation.isPending}
        onConfirm={() => uploadMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.knowDetail.uploadFields.files')}
            <small>{t('console.knowDetail.uploadFields.filesHint')}</small>
          </label>
          <input
            className="input"
            type="file"
            multiple
            onChange={(event) => setUploadFiles(Array.from(event.target.files || []))}
          />
        </div>
        {uploadFiles.length > 0 && (
          <div className="mrow">
            <label />
            <span className="mono dim">
              {t('console.knowDetail.uploadFields.selected', { count: uploadFiles.length })}
            </span>
          </div>
        )}
      </ConsoleModal>

      <ConsoleModal
        open={deletingDoc != null}
        onOpenChange={(open) => !open && setDeletingDoc(null)}
        title={t('console.knowDetail.deleteDocTitle')}
        confirmLabel={t('console.knowDetail.deleteDoc')}
        destructive
        busy={deleteDocMutation.isPending}
        onConfirm={() => deleteDocMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.knowDetail.deleteDocConfirm', {
            name: deletingDoc ? documentLabel(deletingDoc) : '',
          })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={editingChunk != null}
        onOpenChange={(open) => !open && setEditingChunk(null)}
        title={t('console.knowDetail.chunkEditTitle')}
        note={t('console.knowDetail.chunkEditNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!chunkDirty}
        busy={chunkMutation.isPending}
        onConfirm={() => chunkMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.knowDetail.chunkFields.content')}
            <small>{t('console.knowDetail.chunkFields.contentHint')}</small>
          </label>
          <textarea
            className="input"
            value={chunkForm.content}
            onChange={(event) =>
              setChunkForm((state) => ({ ...state, content: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.knowDetail.chunkFields.status')}</label>
          <select
            className="input"
            value={chunkForm.indexStatus}
            onChange={(event) =>
              setChunkForm((state) => ({ ...state, indexStatus: event.target.value }))
            }
          >
            {/* A chunk can hold a status the update payload does not accept
                (`chunking`, say); keep it selectable so opening the modal never
                silently rewrites it. */}
            {!CHUNK_STATUS_OPTIONS.includes(
              chunkForm.indexStatus as KnowledgeChunkUpdateRequest['index_status'],
            ) && <option value={chunkForm.indexStatus}>{chunkForm.indexStatus}</option>}
            {CHUNK_STATUS_OPTIONS.map((status) => (
              <option key={status} value={status}>
                {status}
              </option>
            ))}
          </select>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deleteBaseOpen}
        onOpenChange={setDeleteBaseOpen}
        title={t('console.knowDetail.deleteTitle')}
        confirmLabel={t('console.knowDetail.fields.delBtn')}
        destructive
        busy={deleteBaseMutation.isPending}
        onConfirm={() => deleteBaseMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.knowDetail.deleteConfirm', { name })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={indexForm.open !== false}
        onOpenChange={(open) => !open && setIndexForm((state) => ({ ...state, open: false }))}
        title={t(
          indexForm.open === 'edit'
            ? 'console.knowDetail.indexes.editTitle'
            : 'console.knowDetail.indexes.createTitle',
        )}
        note={t('console.knowDetail.indexes.createNote')}
        confirmLabel={t(indexForm.open === 'edit' ? 'console.common.save' : 'console.common.create')}
        confirmDisabled={!indexForm.name.trim() || !indexForm.embedding_model_ref.trim()}
        busy={createIndexMutation.isPending || updateIndexMutation.isPending}
        onConfirm={() =>
          indexForm.open === 'edit'
            ? updateIndexMutation.mutate(undefined)
            : createIndexMutation.mutate(undefined)
        }
      >
        <div className="mrow">
          <label>{t('console.knowDetail.indexes.fields.name')}</label>
          <input
            className="input"
            value={indexForm.name}
            onChange={(event) => setIndexForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.knowDetail.indexes.fields.embedding')}
            <small>{t('console.knowDetail.indexes.fields.embeddingHint')}</small>
          </label>
          <input
            className="input"
            value={indexForm.embedding_model_ref}
            onChange={(event) =>
              setIndexForm((state) => ({ ...state, embedding_model_ref: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.knowDetail.indexes.fields.metric')}</label>
          <select
            className="input"
            style={{ maxWidth: 160 }}
            value={indexForm.metric_type}
            onChange={(event) =>
              setIndexForm((state) => ({ ...state, metric_type: event.target.value }))
            }
          >
            <option value="cosine">cosine</option>
            <option value="l2">l2</option>
            <option value="ip">ip</option>
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.knowDetail.indexes.fields.primary')}
            <small>{t('console.knowDetail.indexes.fields.primaryHint')}</small>
          </label>
          <div className="checks">
            <label>
              <input
                type="checkbox"
                checked={indexForm.is_primary}
                onChange={(event) =>
                  setIndexForm((state) => ({ ...state, is_primary: event.target.checked }))
                }
              />
              {t('console.knowDetail.indexes.primary')}
            </label>
          </div>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingIndex != null}
        onOpenChange={(open) => !open && setDeletingIndex(null)}
        title={t('console.knowDetail.indexes.deleteTitle')}
        confirmLabel={t('console.knowDetail.indexes.del')}
        destructive
        busy={deleteIndexMutation.isPending}
        onConfirm={() => deleteIndexMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.knowDetail.indexes.deleteConfirm', { name: deletingIndex?.name ?? '' })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={versionsDoc != null}
        onOpenChange={(open) => !open && setVersionsDoc(null)}
        title={t('console.knowDetail.versionsTitle')}
        note={t('console.knowDetail.versionsHint')}
        confirmLabel={t('console.common.cancel')}
        onConfirm={() => setVersionsDoc(null)}
      >
        <table>
          <thead>
            <tr>
              <th className="num">v</th>
              <th>{t('console.knowDetail.columns.status')}</th>
              <th className="num">{t('console.knowDetail.columns.updated')}</th>
              <th className="num" />
            </tr>
          </thead>
          <tbody>
            {(versionsQuery.data || []).length === 0 ? (
              <tr>
                <td colSpan={4}>
                  <div className="empty-note">
                    {versionsQuery.isPending || versionsQuery.isError
                      ? versionsState
                      : t('console.knowDetail.versionsEmpty')}
                  </div>
                </td>
              </tr>
            ) : (
              (versionsQuery.data || []).map((version) => (
                <tr key={`${version.doc_key}:${version.version}`}>
                  <td className="num mono">{version.version}</td>
                  <td>
                    <StatusChip
                      status={pipelineStatus(version.status)}
                      label={version.status.toUpperCase()}
                    />
                  </td>
                  <td className="num dimmer">{relativeTime(version.updated_at)}</td>
                  <td className="num">
                    {version.is_latest ? (
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {t('console.knowDetail.currentVersion')}
                      </span>
                    ) : (
                      <ConsoleButton size="sm" onClick={() => setRestoring(version)}>
                        {t('console.knowDetail.restore')}
                      </ConsoleButton>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </ConsoleModal>

      <ConsoleModal
        open={restoring != null}
        onOpenChange={(open) => !open && setRestoring(null)}
        title={t('console.knowDetail.restoreTitle')}
        confirmLabel={t('console.knowDetail.restore')}
        busy={rollbackMutation.isPending}
        onConfirm={() => rollbackMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.knowDetail.restoreConfirm', {
            version: restoring?.version ?? '',
            name: restoring ? documentLabel(restoring) : '',
          })}
        </div>
      </ConsoleModal>
    </>
  )
}
