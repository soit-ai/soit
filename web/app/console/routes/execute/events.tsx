import { useState } from 'react'

import {
  FilterChip,
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
import { mockEventCounts, mockEventTiles, mockEvents } from '../../mocks/execute'
import { useTranslation } from '@/i18n'

const RANGES = ['1h', '24h', '7d'] as const
type SourceFilter = 'all' | 'webhook' | 'schedule' | 'api' | 'chat'

// BACKEND-PENDING: inbound events are mock-first; dead-letters + redrive
// have real endpoints and join in the service wiring pass.
export default function ConsoleEvents() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [source, setSource] = useState<SourceFilter>('all')
  const [rejectedOnly, setRejectedOnly] = useState(false)

  const rows = mockEvents.filter((row) => {
    if (source !== 'all' && row.source !== source) return false
    if (rejectedOnly && row.decision_label !== 'REJECTED') return false
    return true
  })

  return (
    <Workbench
      title={t('console.events.title')}
      description={t('console.events.description')}
      actions={<Seg options={RANGES} value={range} onChange={setRange} />}
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.events.tiles.total')} value={mockEventTiles.total.value} sub={<span className="mono dimmer">{mockEventTiles.total.sub}</span>} />
          <StatTile label={t('console.events.tiles.accepted')} value={mockEventTiles.accepted.value} sub={<span className="mono dimmer">{mockEventTiles.accepted.sub}</span>} />
          <StatTile label={t('console.events.tiles.deduped')} value={mockEventTiles.deduped.value} sub={<span className="mono dimmer">{mockEventTiles.deduped.sub}</span>} />
          <StatTile label={t('console.events.tiles.rejected')} value={mockEventTiles.rejected.value} sub={<span className="mono dimmer">{mockEventTiles.rejected.sub}</span>} />
        </StatTileGrid>
      }
      filters={
        <>
          {(
            [
              ['all', t('console.events.filters.all'), mockEventCounts.all],
              ['webhook', t('console.events.filters.webhook'), mockEventCounts.webhook],
              ['schedule', t('console.events.filters.schedule'), mockEventCounts.schedule],
              ['api', t('console.events.filters.api'), mockEventCounts.api],
              ['chat', t('console.events.filters.chat'), mockEventCounts.chat],
            ] as const
          ).map(([value, label, count]) => (
            <FilterChip key={value} active={source === value} count={count} onClick={() => setSource(value)}>
              {label}
            </FilterChip>
          ))}
          <FilterChip active={rejectedOnly} onClick={() => setRejectedOnly((value) => !value)}>
            {t('console.events.filters.rejectedOnly')}
          </FilterChip>
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.events.columns.event')}</TableHead>
              <TableHead>{t('console.events.columns.source')}</TableHead>
              <TableHead>{t('console.events.columns.type')}</TableHead>
              <TableHead>{t('console.events.columns.target')}</TableHead>
              <TableHead>{t('console.events.columns.decision')}</TableHead>
              <TableHead>{t('console.events.columns.run')}</TableHead>
              <TableHead className="num">{t('console.events.columns.received')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow key={row.id} className="rowlink">
                <TableCell>
                  <span className="mono">{row.id}</span>
                </TableCell>
                <TableCell>
                  <span className="kind" style={{ '--c': row.source_color } as React.CSSProperties}>
                    <i />
                    {row.source}
                  </span>
                </TableCell>
                <TableCell className="mono dim">{row.type}</TableCell>
                <TableCell>
                  {row.target ? (
                    <span className="idm" style={{ '--c': row.target_color } as React.CSSProperties}>
                      <i />
                      {row.target}
                    </span>
                  ) : (
                    <span className="dimmer">{t('console.events.unresolved')}</span>
                  )}
                </TableCell>
                <TableCell>
                  <StatusChip status={row.decision_status} label={row.decision_label} />
                  {row.decision_note && (
                    <>
                      {' '}
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {row.decision_note}
                      </span>
                    </>
                  )}
                </TableCell>
                <TableCell>
                  {row.run_id ? (
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
                  ) : (
                    <span className="dimmer">—</span>
                  )}
                </TableCell>
                <TableCell className="num dimmer">{row.received}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pager
          summary={t('console.events.pageSummary', { count: rows.length })}
          onPrev={() => {}}
          onNext={() => {}}
          prevDisabled
          nextDisabled
          prevLabel={t('console.runs.prev')}
          nextLabel={t('console.runs.next')}
        />
      </WorkbenchPanel>
    </Workbench>
  )
}
