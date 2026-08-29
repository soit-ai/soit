import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  ConsoleToggle,
  DataStateNote,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconExport,
  IconPlus,
  Pager,
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
import { catColor, compactNumber, latency, percent, relativeTime } from '../../adapters/palette'
import { mockAgentMarket, mockAgentReview } from '../../mocks/build-agents'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAgentWorkbench, type AgentWorkbenchRow } from '@/services/agent-service'

type AgentsTab = 'workbench' | 'library' | 'market' | 'review' | 'exceptions' | 'recycle'
type CardFilter = 'all' | 'enabled' | 'paused'

const PAGE_SIZE = 50

// BACKEND-PENDING: marketplace and publish review have no server-side object
// yet; every other tab reads agent-service.
export default function ConsoleAgents() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AgentsTab>('workbench')
  const [filter, setFilter] = useState<CardFilter>('all')
  const [search, setSearch] = useState('')
  const [pausedOverride, setPausedOverride] = useState<Record<string, boolean>>({})

  const workbenchQuery = useQuery({
    queryKey: ['console', 'agents', 'workbench'],
    queryFn: () => getAgentWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const summary = workbenchQuery.data?.summary
  const rows = workbenchQuery.data?.items || []
  const isEnabled = (row: AgentWorkbenchRow) =>
    pausedOverride[row.id] ?? row.action_enabled

  const matchesSearch = (row: AgentWorkbenchRow) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.name, row.description, row.owner]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  }

  const cards = rows.filter((row) => {
    if (filter === 'enabled' && !isEnabled(row)) return false
    if (filter === 'paused' && isEnabled(row)) return false
    return matchesSearch(row)
  })

  const exceptions = rows.filter((row) => row.recent_exception_count > 0)

  return (
    <Workbench
      title={t('console.agents.title')}
      description={t('console.agents.description')}
      actions={
        <>
          <ConsoleButton>
            <IconExport />
            {t('console.agents.import')}
          </ConsoleButton>
          <ConsoleButton variant="primary" onClick={() => navigate('/v2/build/agents/new')}>
            <IconPlus />
            {t('console.agents.newAgent')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.agents.tiles.agents')}
            value={summary ? compactNumber(summary.total_agents) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {summary
                  ? `${summary.running_agents} running · ${summary.configured_agents} configured`
                  : t('console.common.loading')}
              </span>
            }
          />
          <StatTile
            label={t('console.agents.tiles.runs')}
            value={summary ? compactNumber(summary.today_calls) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">today</span>}
          />
          <StatTile
            label={t('console.agents.tiles.pass')}
            value={summary ? percent(summary.success_rate) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">p50 {latency(summary?.avg_latency_ms)}</span>}
          />
          <StatTile
            label={t('console.agents.tiles.attention')}
            value={summary ? String(summary.pending_exceptions) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">pending exceptions</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'workbench', label: t('console.agents.tabs.workbench') },
            { id: 'library', label: t('console.agents.tabs.library'), count: rows.length },
            { id: 'market', label: t('console.agents.tabs.market') },
            { id: 'review', label: t('console.agents.tabs.review'), count: mockAgentReview.length },
            {
              id: 'exceptions',
              label: t('console.agents.tabs.exceptions'),
              count: exceptions.length,
            },
            { id: 'recycle', label: t('console.agents.tabs.recycle') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'workbench' ? (
          <>
            {(
              [
                ['all', t('console.agents.filters.all'), rows.length],
                ['enabled', t('console.agents.filters.enabled'), rows.filter(isEnabled).length],
                [
                  'paused',
                  t('console.agents.filters.paused'),
                  rows.filter((row) => !isEnabled(row)).length,
                ],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterChip>{t('console.agents.filters.triggerAny')}</FilterChip>
            <FilterChip>{t('console.agents.filters.modelAny')}</FilterChip>
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.agents.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'workbench' &&
        (cards.length === 0 ? (
          <WorkbenchPanel>
            <DataStateNote
              isPending={workbenchQuery.isPending}
              isError={workbenchQuery.isError}
              emptyLabel={t('console.agents.empty')}
            />
          </WorkbenchPanel>
        ) : (
          <div className="cards">
            {cards.map((card) => (
              <div key={card.id} className="acard">
                <div className="acard-top">
                  <span
                    className="aavatar"
                    style={{ '--c': catColor(card.id) } as React.CSSProperties}
                  />
                  <span>
                    <b
                      className="cursor-pointer"
                      onClick={() => navigate(`/v2/build/agents/${card.id}`)}
                    >
                      {card.name}
                    </b>
                    <span className="mono">
                      {card.capabilities.map((capability) => capability.label).join(' · ') ||
                        card.status}
                    </span>
                  </span>
                </div>
                <p>{card.description || '—'}</p>
                <div className="acard-stats">
                  <span>
                    <b>{compactNumber(card.today_calls)}</b>
                    {t('console.agents.card.runs')}
                  </span>
                  <span>
                    <b>{percent(card.success_rate)}</b>
                    {t('console.agents.card.pass')}
                  </span>
                  <span>
                    <b>{latency(card.avg_latency_ms)}</b>
                    {t('console.agents.card.latency')}
                  </span>
                </div>
                <div className="acard-foot">
                  <ConsoleToggle
                    on={isEnabled(card)}
                    label={card.name}
                    onChange={(next) =>
                      setPausedOverride((state) => ({ ...state, [card.id]: next }))
                    }
                  />
                  <span className="dim" style={{ fontSize: 11.5 }}>
                    {isEnabled(card) ? t('console.status.enabled') : t('console.status.paused')}
                  </span>
                  <span className="spacer" />
                  <span className="mono dimmer" style={{ fontSize: 10.5 }}>
                    {t('console.agents.card.lastRun')} {relativeTime(card.last_run_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        ))}

      {tab === 'library' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.agents.columns.agent')}</TableHead>
                <TableHead>{t('console.agents.columns.version')}</TableHead>
                <TableHead>{t('console.agents.columns.capabilities')}</TableHead>
                <TableHead>{t('console.agents.columns.owner')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.runs')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.updated')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.filter(matchesSearch).length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                  emptyLabel={t('console.agents.empty')}
                />
              ) : (
                rows.filter(matchesSearch).map((row) => (
                  <TableRow
                    key={row.id}
                    className="rowlink cursor-pointer"
                    onClick={() => navigate(`/v2/build/agents/${row.id}`)}
                  >
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(row.id) } as React.CSSProperties}>
                        <i />
                        {row.name}
                      </span>
                    </TableCell>
                    <TableCell className="mono dim">{row.status}</TableCell>
                    <TableCell>
                      <span className="scopes">
                        {row.capabilities.map((capability) => (
                          <span key={`${capability.type}:${capability.label}`} className="chip">
                            {capability.label}
                          </span>
                        ))}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{row.owner || '—'}</TableCell>
                    <TableCell className="num dim">{compactNumber(row.today_calls)}</TableCell>
                    <TableCell className="num dimmer">{relativeTime(row.updated_at)}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'market' && (
        <div className="mt-3.5">
          <div className="cards">
            {mockAgentMarket.map((card) => (
              <div key={card.name} className="acard">
                <div className="acard-top">
                  <span className="aavatar" style={{ '--c': card.color } as React.CSSProperties} />
                  <span>
                    <b>{card.name}</b>
                    <span className="mono">{card.origin}</span>
                  </span>
                </div>
                <p>{card.description}</p>
                <div className="acard-foot">
                  <span className="chip">{card.needs}</span>
                  <span className="spacer" />
                  <ConsoleButton>{t('console.agents.install')}</ConsoleButton>
                </div>
              </div>
            ))}
          </div>
          <p className="dim" style={{ marginTop: 10, fontSize: 11.5 }}>
            {t('console.agents.marketNote')}
          </p>
        </div>
      )}

      {tab === 'review' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.agents.columns.agent')}</TableHead>
                <TableHead>{t('console.agents.columns.change')}</TableHead>
                <TableHead>{t('console.agents.columns.requestedBy')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.waiting')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockAgentReview.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      {row.id}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{row.change}</TableCell>
                  <TableCell className="dim">{row.requested_by}</TableCell>
                  <TableCell className="num dim">{row.waiting}</TableCell>
                  <TableCell className="num">
                    <span style={{ display: 'inline-flex', gap: 6 }}>
                      <ConsoleButton variant="primary" size="sm">
                        {t('console.approvals.approve')}
                      </ConsoleButton>
                      <ConsoleButton size="sm">{t('console.approvals.reject')}</ConsoleButton>
                      <ConsoleButton variant="ghost" size="sm">
                        {t('console.agents.diff')}
                      </ConsoleButton>
                    </span>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.agents.reviewNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'exceptions' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.agents.columns.agent')}</TableHead>
                <TableHead>{t('console.agents.columns.exception')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.failed')}</TableHead>
                <TableHead>{t('console.agents.columns.lastFailure')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {exceptions.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={workbenchQuery.isPending}
                  isError={workbenchQuery.isError}
                  emptyLabel={t('console.agents.exceptionsEmpty')}
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
                      <StatusChip
                        status={row.status === 'abnormal' ? 'failed' : 'warn'}
                        label={row.status.toUpperCase()}
                      />{' '}
                      <span className="dim">{row.description || '—'}</span>
                    </TableCell>
                    <TableCell className="num dim">{row.recent_exception_count}</TableCell>
                    <TableCell className="dimmer">{relativeTime(row.last_run_at)}</TableCell>
                    <TableCell className="num">
                      <ConsoleButton
                        size="sm"
                        onClick={() => navigate(`/v2/build/agents/${row.id}`)}
                      >
                        {t('console.agents.openAgent')}
                      </ConsoleButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {/* Soft-deleted agents have no list endpoint; DELETE /agents/{id} only
          flips deleted_at. Show the retention promise rather than fixtures. */}
      {tab === 'recycle' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.agents.recycleEmpty')}
            <span className="mono">{t('console.agents.recycleNote')}</span>
          </div>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
