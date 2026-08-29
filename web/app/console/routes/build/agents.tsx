import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  ConsoleToggle,
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
import {
  mockAgentCards,
  mockAgentExceptions,
  mockAgentLibrary,
  mockAgentMarket,
  mockAgentRecycle,
  mockAgentReview,
  mockAgentTiles,
} from '../../mocks/build-agents'
import { useTranslation } from '@/i18n'

type AgentsTab = 'workbench' | 'library' | 'market' | 'review' | 'exceptions' | 'recycle'
type CardFilter = 'all' | 'enabled' | 'paused'

// BACKEND-PENDING: library/exceptions/recycle wire to agent-service;
// marketplace and publish review are mock-first objects.
export default function ConsoleAgents() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AgentsTab>('workbench')
  const [filter, setFilter] = useState<CardFilter>('all')
  const [search, setSearch] = useState('')
  const [enabled, setEnabled] = useState<Record<string, boolean>>(
    Object.fromEntries(mockAgentCards.map((card) => [card.id, card.enabled])),
  )

  const cards = mockAgentCards.filter((card) => {
    if (filter === 'enabled' && !enabled[card.id]) return false
    if (filter === 'paused' && enabled[card.id]) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [card.name, card.model_trigger, card.description].some((value) =>
      value.toLowerCase().includes(query),
    )
  })

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
          <StatTile label={t('console.agents.tiles.agents')} value={mockAgentTiles.agents.value} sub={<span className="mono dimmer">{mockAgentTiles.agents.sub}</span>} />
          <StatTile label={t('console.agents.tiles.runs')} value={mockAgentTiles.runs.value} delta={{ direction: 'up', label: mockAgentTiles.runs.delta }} sub={mockAgentTiles.runs.sub} />
          <StatTile label={t('console.agents.tiles.pass')} value={mockAgentTiles.pass.value} sub={<span className="mono dimmer">{mockAgentTiles.pass.sub}</span>} />
          <StatTile label={t('console.agents.tiles.attention')} value={mockAgentTiles.attention.value} sub={<span className="mono dimmer">{mockAgentTiles.attention.sub}</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'workbench', label: t('console.agents.tabs.workbench') },
            { id: 'library', label: t('console.agents.tabs.library'), count: 9 },
            { id: 'market', label: t('console.agents.tabs.market') },
            { id: 'review', label: t('console.agents.tabs.review'), count: 1 },
            { id: 'exceptions', label: t('console.agents.tabs.exceptions'), count: 2 },
            { id: 'recycle', label: t('console.agents.tabs.recycle'), count: 1 },
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
                ['all', t('console.agents.filters.all'), 6],
                ['enabled', t('console.agents.filters.enabled'), 5],
                ['paused', t('console.agents.filters.paused'), 1],
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
      {tab === 'workbench' && (
        <div className="cards">
          {cards.map((card) => (
            <div key={card.id} className="acard">
              <div className="acard-top">
                <span className="aavatar" style={{ '--c': card.color } as React.CSSProperties} />
                <span>
                  <b
                    className="cursor-pointer"
                    onClick={() => navigate(`/v2/build/agents/${card.id}`)}
                  >
                    {card.name}
                  </b>
                  <span className="mono">{card.model_trigger}</span>
                </span>
              </div>
              <p>{card.description}</p>
              <div className="acard-stats">
                <span>
                  <b>{card.stats.runs}</b>
                  {t('console.agents.card.runs')}
                </span>
                <span>
                  <b>{card.stats.pass}</b>
                  {t('console.agents.card.pass')}
                </span>
                <span>
                  <b>{card.stats.spend}</b>
                  {t('console.agents.card.spend')}
                </span>
              </div>
              <div className="acard-foot">
                <ConsoleToggle
                  on={enabled[card.id]}
                  label={card.name}
                  onChange={(next) => setEnabled((state) => ({ ...state, [card.id]: next }))}
                />
                <span className="dim" style={{ fontSize: 11.5 }}>
                  {enabled[card.id] ? t('console.status.enabled') : t('console.status.paused')}
                </span>
                <span className="spacer" />
                <span className="mono dimmer" style={{ fontSize: 10.5 }}>
                  {t('console.agents.card.lastRun')} {card.last_run}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

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
              {mockAgentLibrary.map((row) => (
                <TableRow
                  key={row.id}
                  className="rowlink cursor-pointer"
                  onClick={() => navigate(`/v2/build/agents/${row.id}`)}
                >
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      {row.id}
                    </span>
                  </TableCell>
                  <TableCell className="mono dim">{row.version}</TableCell>
                  <TableCell>
                    <span className="scopes">
                      {row.capabilities.map((capability) => (
                        <span key={capability} className="chip">
                          {capability}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{row.owner}</TableCell>
                  <TableCell className="num dim">{row.runs}</TableCell>
                  <TableCell className="num dimmer">{row.updated}</TableCell>
                </TableRow>
              ))}
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
              {mockAgentExceptions.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      {row.id}
                    </span>
                  </TableCell>
                  <TableCell>
                    <StatusChip status={row.status} label={row.status_label} />{' '}
                    <span className="dim">{row.detail}</span>
                  </TableCell>
                  <TableCell className="num dim">{row.failed}</TableCell>
                  <TableCell>
                    <a
                      className="runid"
                      href={`/v2/observe/runs/${row.run_id}`}
                      onClick={(event) => {
                        event.preventDefault()
                        navigate(`/v2/observe/runs/${row.run_id}`)
                      }}
                    >
                      {row.run_id}
                    </a>
                  </TableCell>
                  <TableCell className="num">
                    <ConsoleButton size="sm">{t('console.audit.acknowledge')}</ConsoleButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'recycle' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.agents.columns.agent')}</TableHead>
                <TableHead>{t('console.agents.columns.deletedBy')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.deleted')}</TableHead>
                <TableHead className="num">{t('console.agents.columns.purgedIn')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockAgentRecycle.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      {row.id}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{row.deleted_by}</TableCell>
                  <TableCell className="num dim">{row.deleted}</TableCell>
                  <TableCell className="num dim">{row.purged_in}</TableCell>
                  <TableCell className="num">
                    <ConsoleButton size="sm">{t('console.agents.restore')}</ConsoleButton>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.agents.recycleNote')} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
