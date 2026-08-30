import { useMemo, useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  DataStateRow,
  FilterSearch,
  IconExport,
  Pager,
  Seg,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
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
import { relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listApprovals } from '@/services/observe-service'
import { listRunAudits, type RunAuditLogResponse } from '@/services/run-service'
import { listEgressPolicyAudits } from '@/services/security-service'

const RANGES = ['1h', '24h', '7d', '30d'] as const
type AuditTab = 'all' | 'blocks' | 'changes' | 'decisions'

const PAGE_SIZE = 50

/** The window each range names, in milliseconds. */
const RANGE_MS: Record<(typeof RANGES)[number], number> = {
  '1h': 3_600_000,
  '24h': 86_400_000,
  '7d': 7 * 86_400_000,
  '30d': 30 * 86_400_000,
}

function clockTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

/** A gateway audit is a block when its recorded outcome is not a success. */
function isBlock(entry: RunAuditLogResponse): boolean {
  const outcome = (entry.outcome || '').toLowerCase()
  return outcome !== '' && outcome !== 'succeeded' && outcome !== 'ok' && outcome !== 'pass'
}

function outcomeChip(entry: RunAuditLogResponse) {
  if (isBlock(entry)) return { status: 'blocked' as const, label: (entry.outcome || 'BLOCKED').toUpperCase() }
  return { status: 'pass' as const, label: 'PASS' }
}

export default function ConsoleAudit() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AuditTab>('all')
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [search, setSearch] = useState('')
  const [actor, setActor] = useState('')
  const [object, setObject] = useState('')

  // The window is a filter on the query, not a label on the page. Every panel
  // below answers for the same window, so the tiles and the rows agree.
  const since = useMemo(
    () => new Date(Date.now() - RANGE_MS[range]).toISOString(),
    [range],
  )
  const filters = useMemo(
    () => ({
      since,
      ...(actor.trim() ? { actor_user_id: actor.trim() } : {}),
      ...(object.trim() ? { resource_id: object.trim() } : {}),
    }),
    [since, actor, object],
  )

  // Gateway audits derived from run steps — the platform's append-only record
  // of every governed call.
  const auditsQuery = useQuery({
    queryKey: ['console', 'audit', 'runs', filters],
    queryFn: () => listRunAudits({ ...filters, page_size: PAGE_SIZE, with_total: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // Policy configuration changes.
  const changesQuery = useQuery({
    queryKey: ['console', 'audit', 'changes'],
    queryFn: () => listEgressPolicyAudits({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // Human decisions on approval gates.
  const decisionsQuery = useQuery({
    queryKey: ['console', 'audit', 'decisions'],
    queryFn: async () => {
      const [approved, rejected] = await Promise.all([
        listApprovals({ status: 'approved', page_size: PAGE_SIZE }),
        listApprovals({ status: 'rejected', page_size: PAGE_SIZE }),
      ])
      return [...approved.items, ...rejected.items].sort((a, b) =>
        String(b.resolved_at || b.created_at).localeCompare(String(a.resolved_at || a.created_at)),
      )
    },
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const audits = useMemo(() => auditsQuery.data?.items || [], [auditsQuery.data])
  // The total counts what matched the filters, not what fits on this page.
  const matched = auditsQuery.data?.total ?? null
  const changes = changesQuery.data?.items || []
  const decisions = decisionsQuery.data || []
  const blocks = useMemo(() => audits.filter(isBlock), [audits])

  const allRows = audits.filter((row) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [
      row.gateway_type,
      row.step_type,
      row.run_id,
      row.preview,
      row.actor_user_id,
      row.resource_id,
      row.operation,
    ]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  })

  const runLink = (runId?: string | null) =>
    runId ? (
      <a
        className="runid"
        href={`/observe/runs/${runId}`}
        onClick={(event) => {
          event.preventDefault()
          navigate(`/observe/runs/${runId}`)
        }}
      >
        {runId}
      </a>
    ) : (
      <span className="dimmer">—</span>
    )

  return (
    <Workbench
      title={t('console.audit.title')}
      description={t('console.audit.description')}
      actions={
        <ConsoleButton>
          <IconExport />
          {t('console.audit.export')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.audit.tiles.entries')}
            value={matched == null ? '—' : String(matched)}
            na={matched == null}
            sub={<span className="mono dimmer">in the last {range}</span>}
          />
          <StatTile
            label={t('console.audit.tiles.blocks')}
            value={auditsQuery.data ? String(blocks.length) : '—'}
            na={!auditsQuery.data}
            sub={<span className="mono dimmer">non-success outcomes</span>}
          />
          <StatTile
            label={t('console.audit.tiles.changes')}
            value={changesQuery.data ? String(changes.length) : '—'}
            na={!changesQuery.data}
            sub={<span className="mono dimmer">policy edits</span>}
          />
          <StatTile
            label={t('console.audit.tiles.review')}
            value={decisionsQuery.data ? String(decisions.length) : '—'}
            na={!decisionsQuery.data}
            sub={<span className="mono dimmer">human decisions</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'all', label: t('console.audit.tabs.all'), count: audits.length },
            { id: 'blocks', label: t('console.audit.tabs.blocks'), count: blocks.length },
            { id: 'changes', label: t('console.audit.tabs.changes'), count: changes.length },
            { id: 'decisions', label: t('console.audit.tabs.decisions'), count: decisions.length },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'all' ? (
          <>
            <FilterSearch
              value={actor}
              onChange={(event) => setActor(event.target.value)}
              placeholder={t('console.audit.filters.actorPlaceholder')}
            />
            <FilterSearch
              value={object}
              onChange={(event) => setObject(event.target.value)}
              placeholder={t('console.audit.filters.objectPlaceholder')}
            />
            <Seg options={RANGES} value={range} onChange={setRange} />
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.audit.filters.searchPlaceholder')}
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
                <TableHead>{t('console.audit.columns.time')}</TableHead>
                <TableHead>{t('console.audit.columns.actor')}</TableHead>
                <TableHead>{t('console.audit.columns.action')}</TableHead>
                <TableHead>{t('console.audit.columns.object')}</TableHead>
                <TableHead>{t('console.audit.columns.result')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {allRows.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={auditsQuery.isPending}
                  isError={auditsQuery.isError}
                />
              ) : (
                allRows.map((row, index) => {
                  const chip = outcomeChip(row)
                  return (
                    <TableRow key={row.audit_id || `${row.run_id}:${row.step_id}:${index}`}>
                      <TableCell className="num dimmer">
                        {clockTime(row.timestamp || row.created_at)}
                      </TableCell>
                      {/* A call made by the runtime itself has no user behind
                          it, and saying "system" is truer than a blank. */}
                      <TableCell className="dim">{row.actor_user_id || 'system'}</TableCell>
                      <TableCell>{row.operation || row.step_type}</TableCell>
                      <TableCell className="mono dim">
                        {row.resource_id || row.run_id}
                      </TableCell>
                      <TableCell>
                        <StatusChip status={chip.status} label={chip.label} />
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.audit.allNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'blocks' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.audit.columns.time')}</TableHead>
                <TableHead>{t('console.audit.columns.rule')}</TableHead>
                <TableHead>{t('console.audit.columns.blocked')}</TableHead>
                <TableHead>{t('console.audit.columns.run')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {blocks.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={auditsQuery.isPending}
                  isError={auditsQuery.isError}
                />
              ) : (
                blocks.map((row, index) => (
                  <TableRow key={row.audit_id || `${row.run_id}:${index}`}>
                    <TableCell className="num dimmer">{clockTime(row.timestamp)}</TableCell>
                    <TableCell className="mono dim">{row.gateway_type || row.step_type}</TableCell>
                    <TableCell className="dim">{row.preview || row.step_type}</TableCell>
                    <TableCell>{runLink(row.run_id)}</TableCell>
                    <TableCell className="num">
                      <ConsoleButton
                        size="sm"
                        onClick={() => row.run_id && navigate(`/observe/runs/${row.run_id}`)}
                      >
                        {t('console.audit.acknowledge')}
                      </ConsoleButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.audit.blocksNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'changes' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.audit.columns.time')}</TableHead>
                <TableHead>{t('console.audit.columns.actor')}</TableHead>
                <TableHead>{t('console.audit.columns.change')}</TableHead>
                <TableHead>{t('console.audit.columns.diff')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {changes.length === 0 ? (
                <DataStateRow
                  colSpan={4}
                  isPending={changesQuery.isPending}
                  isError={changesQuery.isError}
                />
              ) : (
                changes.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="num dimmer">{relativeTime(row.created_at)}</TableCell>
                    <TableCell className="dim">{row.created_by || 'system'}</TableCell>
                    <TableCell className="dim">egress policy · {row.scope}</TableCell>
                    <TableCell>
                      <span className="dimmer">
                        {row.allowlist.length} allowed · {row.blocklist.length} blocked
                      </span>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'decisions' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.audit.columns.time')}</TableHead>
                <TableHead>{t('console.audit.columns.decidedBy')}</TableHead>
                <TableHead>{t('console.audit.columns.request')}</TableHead>
                <TableHead>{t('console.audit.columns.gate')}</TableHead>
                <TableHead>{t('console.audit.columns.decision')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {decisions.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={decisionsQuery.isPending}
                  isError={decisionsQuery.isError}
                />
              ) : (
                decisions.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell className="num dimmer">
                      {relativeTime(row.resolved_at || row.created_at)}
                    </TableCell>
                    <TableCell className="dim">{row.resolved_by || '—'}</TableCell>
                    <TableCell className="dim">{row.title || row.id}</TableCell>
                    <TableCell className="mono dim">{row.policy_ref || '—'}</TableCell>
                    <TableCell>
                      <StatusChip
                        status={row.status === 'approved' ? 'pass' : 'blocked'}
                        label={row.status.toUpperCase()}
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
