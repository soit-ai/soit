import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  FilterChip,
  FilterSearch,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  TaskProgress,
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
import { useTranslation } from '@/i18n'

type KnTab = 'libraries' | 'ingest' | 'exceptions' | 'recycle'
type KindFilter = 'all' | 'web crawl' | 'upload' | 'git sync'

interface MockLibrary {
  id: string
  color: string
  kind: Exclude<KindFilter, 'all'>
  status: ConsoleStatus
  status_label: string
  documents: string
  chunks: string
  queries: string
  hit_rate: string
  last_sync: string
}

// BACKEND-PENDING: knowledge-service list replaces the fixtures.
const MOCK_LIBRARIES: MockLibrary[] = [
  { id: 'product-docs', color: 'var(--cat-blue)', kind: 'web crawl', status: 'pass', status_label: 'SYNCED', documents: '1,204', chunks: '18,392', queries: '2,381', hit_rate: '91%', last_sync: '8h ago' },
  { id: 'support-macros', color: 'var(--cat-indigo)', kind: 'upload', status: 'pass', status_label: 'SYNCED', documents: '86', chunks: '1,022', queries: '944', hit_rate: '88%', last_sync: '3d ago' },
  { id: 'runbooks', color: 'var(--cat-teal)', kind: 'git sync', status: 'running', status_label: 'INGESTING', documents: '312', chunks: '4,410', queries: '512', hit_rate: '83%', last_sync: 'now' },
  { id: 'billing-policies', color: 'var(--cat-pink)', kind: 'upload', status: 'warn', status_label: 'DEGRADED', documents: '24', chunks: '388', queries: '207', hit_rate: '61%', last_sync: '14d ago' },
]

export default function ConsoleKnowledge() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<KnTab>('libraries')
  const [filter, setFilter] = useState<KindFilter>('all')
  const [search, setSearch] = useState('')

  const rows = MOCK_LIBRARIES.filter((row) => {
    if (filter !== 'all' && row.kind !== filter) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return row.id.toLowerCase().includes(query)
  })

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
          <StatTile label={t('console.knowledge.tiles.libraries')} value="4" sub={<span className="mono dimmer">3 synced · 1 degraded</span>} />
          <StatTile label={t('console.knowledge.tiles.documents')} value="1,626" sub={<span className="mono dimmer">24,212 chunks</span>} />
          <StatTile label={t('console.knowledge.tiles.queries')} value="4,044" delta={{ direction: 'up', label: '+9.2%' }} sub="hit rate 87%" />
          <StatTile label={t('console.knowledge.tiles.p95')} value="240ms" sub={<span className="mono dimmer">bge-m3 · self-hosted</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'libraries', label: t('console.knowledge.tabs.libraries'), count: 4 },
            { id: 'ingest', label: t('console.knowledge.tabs.ingest'), count: 2 },
            { id: 'exceptions', label: t('console.knowledge.tabs.exceptions'), count: 1 },
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
                ['all', t('console.knowledge.filters.all'), 4],
                ['web crawl', t('console.knowledge.filters.webCrawl'), 1],
                ['upload', t('console.knowledge.filters.upload'), 2],
                ['git sync', t('console.knowledge.filters.gitSync'), 1],
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
              {rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="rowlink cursor-pointer"
                  onClick={() => navigate(`/v2/build/knowledge/${row.id}`)}
                >
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      {row.id}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{row.kind}</TableCell>
                  <TableCell>
                    <StatusChip status={row.status} label={row.status_label} />
                  </TableCell>
                  <TableCell className="num dim">{row.documents}</TableCell>
                  <TableCell className="num dim">{row.chunks}</TableCell>
                  <TableCell className="num dim">{row.queries}</TableCell>
                  <TableCell className="num dim">{row.hit_rate}</TableCell>
                  <TableCell className="num dimmer">{row.last_sync}</TableCell>
                </TableRow>
              ))}
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
              <TableRow>
                <TableCell className="mono">ingest_7c21</TableCell>
                <TableCell>
                  <span className="idm" style={{ '--c': 'var(--cat-teal)' } as React.CSSProperties}>
                    <i />
                    runbooks
                  </span>
                </TableCell>
                <TableCell>
                  <span className="kind" style={{ '--c': 'var(--cat-cyan)' } as React.CSSProperties}>
                    <i />
                    embed
                  </span>
                </TableCell>
                <TableCell>
                  <TaskProgress pct={64} label="198/312" />
                </TableCell>
                <TableCell className="num dim">312</TableCell>
                <TableCell>
                  <a
                    className="runid"
                    href="/v2/observe/runs/run_01J9KD8XM4"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/observe/runs/run_01J9KD8XM4')
                    }}
                  >
                    run_01J9KD8XM4
                  </a>
                </TableCell>
                <TableCell className="num dimmer">2m ago</TableCell>
              </TableRow>
              <TableRow>
                <TableCell className="mono">ingest_7b9e</TableCell>
                <TableCell>
                  <span className="idm" style={{ '--c': 'var(--cat-blue)' } as React.CSSProperties}>
                    <i />
                    product-docs
                  </span>
                </TableCell>
                <TableCell>
                  <span className="kind" style={{ '--c': 'var(--cat-blue)' } as React.CSSProperties}>
                    <i />
                    crawl
                  </span>
                </TableCell>
                <TableCell>
                  <TaskProgress pct={12} label="142/1,204" />
                </TableCell>
                <TableCell className="num dim">1,204</TableCell>
                <TableCell>
                  <span className="dimmer">queued</span>
                </TableCell>
                <TableCell className="num dimmer">just now</TableCell>
              </TableRow>
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
              <TableRow>
                <TableCell>
                  <span className="idm" style={{ '--c': 'var(--cat-pink)' } as React.CSSProperties}>
                    <i />
                    billing-policies
                  </span>
                </TableCell>
                <TableCell>
                  <StatusChip status="warn" label="DEGRADED" />{' '}
                  <span className="dim">3 scanned PDFs failed to parse · hit rate dropped to 61%</span>
                </TableCell>
                <TableCell className="num dim">3</TableCell>
                <TableCell>
                  <a
                    className="runid"
                    href="/v2/observe/runs/run_01J9KCXK3B"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/observe/runs/run_01J9KCXK3B')
                    }}
                  >
                    run_01J9KCXK3B
                  </a>
                </TableCell>
                <TableCell className="num">
                  <ConsoleButton size="sm">{t('console.knowledge.reprocess')}</ConsoleButton>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

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
