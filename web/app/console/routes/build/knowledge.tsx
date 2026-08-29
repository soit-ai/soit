import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
  type ConsoleStatus,
} from '../../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor, compactNumber, latency, percent, relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  getKnowledgeWorkbench,
  listKnowledgeIngestTasks,
  type KnowledgeIngestTask,
  type KnowledgeWorkbenchRow,
} from '@/services/knowledge-service'

type KnTab = 'libraries' | 'ingest' | 'exceptions' | 'recycle'
type KindFilter = 'all' | 'web crawl' | 'upload' | 'git sync'

const PAGE_SIZE = 50

/** Workbench row states map onto the shared console status vocabulary. */
const ROW_STATUS: Record<KnowledgeWorkbenchRow['status'], ConsoleStatus> = {
  ready: 'pass',
  indexing: 'running',
  error: 'failed',
  unconfigured: 'warn',
}

interface IngestEntry {
  task: KnowledgeIngestTask
  library: KnowledgeWorkbenchRow
}

export default function ConsoleKnowledge() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<KnTab>('libraries')
  const [filter, setFilter] = useState<KindFilter>('all')
  const [search, setSearch] = useState('')

  const workbenchQuery = useQuery({
    queryKey: ['console', 'knowledge', 'workbench'],
    queryFn: () => getKnowledgeWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const summary = workbenchQuery.data?.summary
  const libraries = workbenchQuery.data?.items || []

  // Ingest tasks are only exposed per knowledge base
  // (GET /knowledge/{id}/ingest-tasks); there is no workspace-wide queue
  // endpoint yet, so the console fans out across the loaded libraries.
  const libraryIds = libraries.map((row) => row.id)
  const ingestQuery = useQuery<IngestEntry[]>({
    queryKey: ['console', 'knowledge', 'ingest-tasks', libraryIds],
    queryFn: async () => {
      const perLibrary = await Promise.all(
        libraries.map((library) =>
          listKnowledgeIngestTasks(library.id, { limit: 20 })
            .then((tasks) => tasks.map((task) => ({ task, library })))
            .catch(() => [] as IngestEntry[]),
        ),
      )
      return perLibrary
        .flat()
        .sort(
          (a, b) =>
            new Date(b.task.created_at).getTime() - new Date(a.task.created_at).getTime(),
        )
    },
    options: {
      enabled: libraryIds.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const ingestTasks = ingestQuery.data || []
  const ingestPending =
    workbenchQuery.isPending || (libraryIds.length > 0 && ingestQuery.isPending)

  const matchesKind = (row: KnowledgeWorkbenchRow, kind: Exclude<KindFilter, 'all'>) =>
    (row.content_source || '').toLowerCase().includes(kind)

  const matchesSearch = (row: KnowledgeWorkbenchRow) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.name, row.description, row.content_source, row.owner]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  }

  const rows = libraries.filter((row) => {
    if (filter !== 'all' && !matchesKind(row, filter)) return false
    return matchesSearch(row)
  })

  const exceptions = libraries.filter((row) => row.recent_exception_count > 0)

  return (
    <Workbench
      title={t('console.knowledge.title')}
      description={t('console.knowledge.description')}
      actions={
        <ConsoleButton variant="primary" onClick={() => navigate('/v2/build/knowledge/new')}>
          <IconPlus />
          {t('console.knowledge.newKb')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.knowledge.tiles.libraries')}
            value={summary ? compactNumber(summary.total_knowledge_bases) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {summary
                  ? `${summary.ready_knowledge_bases} ready · ${summary.recent_exceptions} exceptions`
                  : t('console.common.loading')}
              </span>
            }
          />
          <StatTile
            label={t('console.knowledge.tiles.documents')}
            value={summary ? compactNumber(summary.total_documents) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {summary ? `${compactNumber(summary.total_chunks)} chunks` : '—'}
              </span>
            }
          />
          <StatTile
            label={t('console.knowledge.tiles.queries')}
            value={summary ? compactNumber(summary.today_calls) : '—'}
            na={!summary}
            sub={summary ? `hit rate ${percent(summary.hit_rate)}` : '—'}
          />
          {/* The workbench summary reports mean retrieval latency; there is no
              percentile aggregation endpoint, so no p95 figure is available. */}
          <StatTile
            label={t('console.knowledge.tiles.p95')}
            value={summary ? latency(summary.avg_latency_ms) : '—'}
            na={!summary || summary.avg_latency_ms == null}
            sub={<span className="mono dimmer">avg · all retrieval runs</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            {
              id: 'libraries',
              label: t('console.knowledge.tabs.libraries'),
              count: libraries.length,
            },
            { id: 'ingest', label: t('console.knowledge.tabs.ingest'), count: ingestTasks.length },
            {
              id: 'exceptions',
              label: t('console.knowledge.tabs.exceptions'),
              count: exceptions.length,
            },
            { id: 'recycle', label: t('console.knowledge.tabs.recycle') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'libraries' ? (
          <>
            {(
              [
                ['all', t('console.knowledge.filters.all'), libraries.length],
                [
                  'web crawl',
                  t('console.knowledge.filters.webCrawl'),
                  libraries.filter((row) => matchesKind(row, 'web crawl')).length,
                ],
                [
                  'upload',
                  t('console.knowledge.filters.upload'),
                  libraries.filter((row) => matchesKind(row, 'upload')).length,
                ],
                [
                  'git sync',
                  t('console.knowledge.filters.gitSync'),
                  libraries.filter((row) => matchesKind(row, 'git sync')).length,
                ],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.knowledge.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'libraries' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.knowledge.columns.name')}</TableHead>
                <TableHead>{t('console.knowledge.columns.kind')}</TableHead>
                <TableHead>{t('console.knowledge.columns.status')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.documents')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.chunks')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.queries')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.hitRate')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.lastSync')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={8}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                />
              ) : (
                rows.map((row) => (
                  <TableRow
                    key={row.id}
                    className="rowlink cursor-pointer"
                    onClick={() => navigate(`/v2/build/knowledge/${row.id}`)}
                  >
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(row.id) } as React.CSSProperties}>
                        <i />
                        {row.name}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{row.content_source || '—'}</TableCell>
                    <TableCell>
                      <StatusChip status={ROW_STATUS[row.status]} label={row.status.toUpperCase()} />
                    </TableCell>
                    <TableCell className="num dim">{compactNumber(row.document_count)}</TableCell>
                    <TableCell className="num dim">{compactNumber(row.chunk_count)}</TableCell>
                    <TableCell className="num dim">{compactNumber(row.today_calls)}</TableCell>
                    <TableCell className="num dim">{percent(row.hit_rate)}</TableCell>
                    <TableCell className="num dimmer">{relativeTime(row.last_sync_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'ingest' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.knowledge.columns.job')}</TableHead>
                <TableHead>{t('console.knowledge.columns.library')}</TableHead>
                <TableHead>{t('console.knowledge.columns.stage')}</TableHead>
                <TableHead>{t('console.knowledge.columns.progress')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.docs')}</TableHead>
                <TableHead>{t('console.knowledge.columns.run')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.started')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {ingestTasks.length === 0 ? (
                <DataStateRow colSpan={7} isPending={ingestPending} isError={ingestQuery.isError} />
              ) : (
                ingestTasks.map(({ task, library }) => (
                  <TableRow key={task.id}>
                    <TableCell className="mono">{task.id}</TableCell>
                    <TableCell>
                      <span
                        className="idm"
                        style={{ '--c': catColor(library.id) } as React.CSSProperties}
                      >
                        <i />
                        {library.name}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className="kind"
                        style={{ '--c': catColor(task.status) } as React.CSSProperties}
                      >
                        <i />
                        {task.status}
                      </span>
                    </TableCell>
                    {/* Ingest tasks carry retry counters but no processed/total
                        counters, so there is no percentage to plot. */}
                    <TableCell className="dimmer">—</TableCell>
                    <TableCell className="num dim">{task.document_id ? 1 : '—'}</TableCell>
                    <TableCell>
                      {task.run_id ? (
                        <a
                          className="runid"
                          href={`/v2/observe/runs/${task.run_id}`}
                          onClick={(event) => {
                            event.preventDefault()
                            navigate(`/v2/observe/runs/${task.run_id}`)
                          }}
                        >
                          {task.run_id}
                        </a>
                      ) : (
                        <span className="dimmer">—</span>
                      )}
                    </TableCell>
                    <TableCell className="num dimmer">
                      {relativeTime(task.started_at || task.created_at)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.knowledge.ingestNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'exceptions' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.knowledge.columns.library')}</TableHead>
                <TableHead>{t('console.knowledge.columns.exception')}</TableHead>
                <TableHead className="num">{t('console.knowledge.columns.affected')}</TableHead>
                <TableHead>{t('console.knowledge.columns.lastFailure')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {exceptions.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                />
              ) : (
                exceptions.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(row.id) } as React.CSSProperties}>
                        <i />
                        {row.name}
                      </span>
                    </TableCell>
                    <TableCell>
                      <StatusChip status={ROW_STATUS[row.status]} label={row.status.toUpperCase()} />{' '}
                      <span className="dim">{row.description || '—'}</span>
                    </TableCell>
                    <TableCell className="num dim">{row.recent_exception_count}</TableCell>
                    {/* The workbench row aggregates failing runs but does not
                        return the failing run id, so this is the last sync
                        stamp rather than a link into the run ledger. */}
                    <TableCell className="dimmer">{relativeTime(row.last_sync_at)}</TableCell>
                    <TableCell className="num">
                      <ConsoleButton size="sm">{t('console.knowledge.reprocess')}</ConsoleButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {/* Soft-deleted knowledge bases have no list endpoint; DELETE
          /knowledge/{id} only flips deleted_at. Show the retention promise
          rather than fixtures. */}
      {tab === 'recycle' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.knowledge.recycleEmpty')}
            <span className="mono">{t('console.knowledge.recycleNote')}</span>
          </div>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
