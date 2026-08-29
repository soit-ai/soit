import { useState } from 'react'

import { NavLink } from 'react-router'

import {
  ConsoleButton,
  ConsoleTabs,
  FilterChip,
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
import {
  mockAuditAll,
  mockAuditBlocks,
  mockAuditChanges,
  mockAuditTiles,
  mockApprovalsDecided,
} from '../../mocks/govern'
import { useTranslation } from '@/i18n'

const RANGES = ['1h', '24h', '7d', '30d'] as const
type AuditTab = 'all' | 'blocks' | 'changes' | 'decisions'

// BACKEND-PENDING: security-service audit endpoints replace the fixtures.
export default function ConsoleAudit() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AuditTab>('all')
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [search, setSearch] = useState('')

  const allRows = mockAuditAll.filter((row) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.actor, row.action, row.object].some((value) => value.toLowerCase().includes(query))
  })

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
          <StatTile label={t('console.audit.tiles.entries')} value={mockAuditTiles.entries.value} sub={<span className="mono dimmer">{mockAuditTiles.entries.sub}</span>} />
          <StatTile label={t('console.audit.tiles.blocks')} value={mockAuditTiles.blocks.value} sub={<span className="mono dimmer">{mockAuditTiles.blocks.sub}</span>} />
          <StatTile label={t('console.audit.tiles.changes')} value={mockAuditTiles.changes.value} sub={<span className="mono dimmer">{mockAuditTiles.changes.sub}</span>} />
          <StatTile label={t('console.audit.tiles.review')} value={mockAuditTiles.review.value} sub={<span className="mono dimmer">{mockAuditTiles.review.sub}</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'all', label: t('console.audit.tabs.all'), count: 47 },
            { id: 'blocks', label: t('console.audit.tabs.blocks'), count: 15 },
            { id: 'changes', label: t('console.audit.tabs.changes'), count: 6 },
            { id: 'decisions', label: t('console.audit.tabs.decisions'), count: 3 },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'all' ? (
          <>
            <FilterChip>{t('console.audit.filters.actor')}</FilterChip>
            <FilterChip>{t('console.audit.filters.object')}</FilterChip>
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
              {allRows.map((row, index) => (
                <TableRow key={index}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="dim">{row.actor}</TableCell>
                  <TableCell>{row.action}</TableCell>
                  <TableCell className="mono dim">{row.object}</TableCell>
                  <TableCell>
                    <StatusChip status={row.status} label={row.status_label} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.audit.allNote')} onNext={() => {}} nextLabel={t('console.audit.older')} />
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
              {mockAuditBlocks.map((row) => (
                <TableRow key={row.time}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="mono dim">{row.rule}</TableCell>
                  <TableCell className="dim">{row.blocked}</TableCell>
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
              {mockAuditChanges.map((row) => (
                <TableRow key={row.time}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="dim">{row.actor}</TableCell>
                  <TableCell className="dim">{row.change}</TableCell>
                  <TableCell>
                    {row.diff_to ? (
                      <a
                        className="runid"
                        href={row.diff_to}
                        onClick={(event) => {
                          event.preventDefault()
                          navigate(row.diff_to as string)
                        }}
                      >
                        {row.diff}
                      </a>
                    ) : (
                      <span className="dimmer">{row.diff}</span>
                    )}
                  </TableCell>
                </TableRow>
              ))}
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
              {mockApprovalsDecided.map((row) => (
                <TableRow key={row.time}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="dim">{row.decided_by}</TableCell>
                  <TableCell className="dim">{row.request}</TableCell>
                  <TableCell className="mono dim">{row.gate}</TableCell>
                  <TableCell>
                    <StatusChip status={row.status} label={row.status_label} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager
            summary={
              <>
                {t('console.audit.decisionsNote')}{' '}
                <NavLink className="more" to="/v2/govern/approvals">
                  {t('console.audit.approvalsLink')}
                </NavLink>
              </>
            }
          />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
