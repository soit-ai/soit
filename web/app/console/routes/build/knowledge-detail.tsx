import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  ConsoleButton,
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
import { catColor, compactNumber, latency, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  getKnowledgeBase,
  getKnowledgeRunCostSummary,
  listKnowledgeChunks,
  listKnowledgeDocuments,
  listKnowledgeIndexes,
  listKnowledgeUsages,
  queryKnowledge,
  type KnowledgeDocument,
  type KnowledgeQueryResponse,
} from '@/services/knowledge-service'

type KdTab = 'documents' | 'chunks' | 'testing' | 'usages' | 'analytics' | 'settings'

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

export default function ConsoleKnowledgeDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<KdTab>('documents')
  const [docOffset, setDocOffset] = useState(0)
  const [docFilter, setDocFilter] = useState('')
  const [selectedDocId, setSelectedDocId] = useState<string | null>(null)
  const [testQuery, setTestQuery] = useState('')

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

  const base = baseQuery.data
  const documents = documentsQuery.data || []
  const indexes = indexesQuery.data || []
  const usages = usagesQuery.data || []
  const cost = costQuery.data

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

  const tabItems: [KdTab, string, React.ReactNode][] = [
    ['documents', t('console.knowDetail.tabs.documents'), base ? compactNumber(base.doc_count) : null],
    ['chunks', t('console.knowDetail.tabs.chunks'), base ? compactNumber(base.chunk_count) : null],
    ['testing', t('console.knowDetail.tabs.testing'), null],
    ['usages', t('console.knowDetail.tabs.usages'), usages.length ? String(usages.length) : null],
    ['analytics', t('console.knowDetail.tabs.analytics'), null],
    ['settings', t('console.knowDetail.tabs.settings'), null],
  ]

  return (
    <>
      <Backlink to="/v2/build/knowledge">{t('console.knowDetail.back')}</Backlink>

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
        <ConsoleButton>
          <IconReplay />
          {t('console.knowDetail.syncNow')}
        </ConsoleButton>
        <ConsoleButton variant="primary">{t('console.knowDetail.addDocs')}</ConsoleButton>
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
                  href={`/v2/observe/runs/${lastSyncRunId}`}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(`/v2/observe/runs/${lastSyncRunId}`)
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
                    <td className="num">
                      {doc.status !== 'failed' && (
                        <ConsoleButton variant="ghost" size="sm">
                          {t('console.knowDetail.recrawl')}
                        </ConsoleButton>
                      )}
                      {doc.status === 'failed' && (
                        <ConsoleButton size="sm">{t('console.knowledge.reprocess')}</ConsoleButton>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="pager">
            <span className="mono">
              {`${documents.length} / ${base ? compactNumber(base.doc_count) : '—'}`}
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
                  <tr key={chunk.id} className="rowlink">
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

      {tab === 'analytics' && (
        <>
          <StatTileGrid>
            <StatTile
              label="Queries · 24h"
              value={cost ? compactNumber(cost.request_count) : '—'}
              na={!cost || cost.request_count == null}
              sub="all retrieval runs"
            />
            {/* Retrieval hit rate and zero-hit share have no aggregation
                endpoint; the run cost summary only reports volume and spend. */}
            <StatTile label="Hit rate" value="—" na sub={<span className="mono dimmer">no aggregation endpoint</span>} />
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
              value="—"
              na
              sub={<span className="mono dimmer">no aggregation endpoint</span>}
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
        <WorkbenchPanel title={t('console.knowDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.knowDetail.fields.name')}</label>
            <input key={`name-${base?.id ?? 'pending'}`} className="input" defaultValue={base?.name ?? ''} />
          </div>
          <div className="frow">
            <label>
              {t('console.knowDetail.fields.source')}
              <small>{t('console.knowDetail.fields.sourceHint')}</small>
            </label>
            <input
              key={`source-${base?.id ?? 'pending'}`}
              className="input"
              defaultValue={sourceUri ?? ''}
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
              key={`threshold-${base?.id ?? 'pending'}`}
              className="input"
              defaultValue={
                readNumber(retrieval, 'keyword_min_score') != null
                  ? `score ≥ ${readNumber(retrieval, 'keyword_min_score')}`
                  : ''
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
              <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                {t('console.knowDetail.fields.delBtn')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}
    </>
  )
}
