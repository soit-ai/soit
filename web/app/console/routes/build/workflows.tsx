import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  FilterChip,
  FilterSearch,
  Hist,
  IconExport,
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
import { useTranslation } from '@/i18n'

type WfTab = 'all' | 'publish' | 'archived'
type WfFilter = 'all' | 'published' | 'draft'

interface MockWorkflowRow {
  id: string
  name: string
  note: string
  version: string
  draft?: boolean
  nodes: string
  last_status: ConsoleStatus
  last_label: string
  hist: string
  success: string
  updated: string
}

// BACKEND-PENDING: workflow-service list replaces the fixtures.
const MOCK_WORKFLOWS: MockWorkflowRow[] = [
  { id: 'ticket-escalation', name: 'ticket-escalation', note: 'triage → enrich → route → notify', version: 'v14 · published', nodes: '9', last_status: 'pass', last_label: 'PASS', hist: 'ppppppppdppppppppppppfpppppp', success: '99.2%', updated: '2d ago' },
  { id: 'invoice-reconcile', name: 'invoice-reconcile', note: 'fetch → diff → post journal → report', version: 'v8 · published', nodes: '7', last_status: 'blocked', last_label: 'BLOCKED', hist: 'ppppfppppppppfppppppdpppppfp', success: '96.1%', updated: '5d ago' },
  { id: 'docs-nightly-sync', name: 'docs-nightly-sync', note: 'crawl → chunk → embed → verify', version: 'v22 · published', nodes: '12', last_status: 'warn', last_label: 'DEGRADED', hist: 'ppdppppdppppppppdppppppdpppp', success: '97.4%', updated: '8h ago' },
  { id: 'release-digest', name: 'release-digest', note: 'collect PRs → summarize → review gate', version: 'v5 · published', nodes: '5', last_status: 'pass', last_label: 'PASS', hist: 'pppppppppppppppppppppppppppp', success: '100%', updated: '12d ago' },
  { id: 'churn-signal-scan', name: 'churn-signal-scan', note: 'query → score → draft outreach', version: 'v2 · draft', draft: true, nodes: '6', last_status: 'info', last_label: 'NEVER RUN', hist: 'eeeeeeeeeeeeeeeeeeeeeeeeeeee', success: '—', updated: '1h ago' },
]

export default function ConsoleWorkflows() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<WfTab>('all')
  const [filter, setFilter] = useState<WfFilter>('all')
  const [search, setSearch] = useState('')

  const rows = MOCK_WORKFLOWS.filter((row) => {
    if (filter === 'published' && row.draft) return false
    if (filter === 'draft' && !row.draft) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.name, row.note].some((value) => value.toLowerCase().includes(query))
  })

  return (
    <Workbench
      title={t('console.workflows.title')}
      description={t('console.workflows.description')}
      actions={
        <>
          <ConsoleButton>
            <IconExport />
            {t('console.workflows.import')}
          </ConsoleButton>
          <ConsoleButton variant="primary" onClick={() => navigate('/v2/build/workflows/new')}>
            <IconPlus />
            {t('console.workflows.newWorkflow')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.workflows.tiles.workflows')} value="5" sub={<span className="mono dimmer">4 published · 1 draft</span>} />
          <StatTile label={t('console.workflows.tiles.runs')} value="2,148" delta={{ direction: 'up', label: '+4.7%' }} sub="vs prev 7d" />
          <StatTile label={t('console.workflows.tiles.success')} value="98.4%" sub={<span className="mono dimmer">2,114 pass · 26 degraded · 8 failed</span>} />
          <StatTile label={t('console.workflows.tiles.attention')} value="2" sub={<span className="mono dimmer">1 publish pending · 1 legacy node</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'all', label: t('console.workflows.tabs.all'), count: 5 },
            { id: 'publish', label: t('console.workflows.tabs.publish'), count: 1 },
            { id: 'archived', label: t('console.workflows.tabs.archived') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'all' ? (
          <>
            {(
              [
                ['all', t('console.workflows.filters.all'), 5],
                ['published', t('console.workflows.filters.published'), 4],
                ['draft', t('console.workflows.filters.draft'), 1],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterChip>{t('console.workflows.filters.triggerAny')}</FilterChip>
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.workflows.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'all' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.workflows.columns.workflow')}</TableHead>
                <TableHead>{t('console.workflows.columns.version')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.nodes')}</TableHead>
                <TableHead>{t('console.workflows.columns.lastRun')}</TableHead>
                <TableHead>{t('console.workflows.columns.outcomes')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.success')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.updated')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow
                  key={row.id}
                  className="rowlink cursor-pointer"
                  onClick={() => navigate(`/v2/build/workflows/${row.id}`)}
                >
                  <TableCell>
                    <b style={{ fontWeight: 600 }}>{row.name}</b>
                    <br />
                    <span className="dimmer" style={{ fontSize: 11 }}>
                      {row.note}
                    </span>
                  </TableCell>
                  <TableCell className="mono dim">{row.version}</TableCell>
                  <TableCell className="num dim">{row.nodes}</TableCell>
                  <TableCell>
                    <StatusChip status={row.last_status} label={row.last_label} />
                  </TableCell>
                  <TableCell>
                    <Hist pattern={row.hist} label="last 28 run outcomes" />
                  </TableCell>
                  <TableCell className="num dim">{row.success}</TableCell>
                  <TableCell className="num dimmer">{row.updated}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'publish' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.workflows.publishTitle')}
          hint={t('console.workflows.publishHint')}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.workflows.columns.workflow')}</TableHead>
                <TableHead>{t('console.workflows.columns.version')}</TableHead>
                <TableHead>{t('console.workflows.columns.gate')}</TableHead>
                <TableHead>{t('console.workflows.columns.requestedBy')}</TableHead>
                <TableHead className="num">{t('console.workflows.columns.waiting')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>
                  <b style={{ fontWeight: 600 }}>ticket-escalation</b>
                </TableCell>
                <TableCell className="mono dim">v15 · draft</TableCell>
                <TableCell>
                  <StatusChip status="warn" label="BLOCKED BY LEGACY NODE" />{' '}
                  <span className="dimmer" style={{ fontSize: 10.5 }}>
                    set_var_1 must migrate first
                  </span>
                </TableCell>
                <TableCell className="dim">Jude</TableCell>
                <TableCell className="num dim">2h</TableCell>
                <TableCell className="num">
                  <span style={{ display: 'inline-flex', gap: 6 }}>
                    <ConsoleButton size="sm" onClick={() => navigate('/v2/build/workflows/ticket-escalation')}>
                      {t('console.workflows.openBuilder')}
                    </ConsoleButton>
                    <ConsoleButton variant="ghost" size="sm">
                      {t('console.workflows.diffVs')}
                    </ConsoleButton>
                  </span>
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <Pager summary={t('console.workflows.publishNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'archived' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.workflows.archivedEmpty')}
            <span className="mono">{t('console.workflows.archivedRestore')}</span>
          </div>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
