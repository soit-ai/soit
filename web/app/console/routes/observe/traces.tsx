import { useState } from 'react'

import {
  FilterChip,
  FilterSearch,
  Pager,
  Seg,
  StatTile,
  StatTileGrid,
  TBar,
  TBarLegend,
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
import { mockTraces, mockTraceTiles } from '../../mocks/observe'
import { useTranslation } from '@/i18n'

const RANGES = ['1h', '24h', '7d', '30d'] as const

// BACKEND-PENDING: observe-service trace search replaces the fixtures.
export default function ConsoleTraces() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [slowOnly, setSlowOnly] = useState(false)
  const [search, setSearch] = useState('')

  const rows = mockTraces.filter((row) => {
    if (slowOnly && parseFloat(row.duration) <= 5) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.trace_id, row.root_op, row.run_id, row.subject_id].some((value) =>
      value.toLowerCase().includes(query),
    )
  })

  return (
    <Workbench
      title={t('console.traces.title')}
      description={t('console.traces.description')}
      actions={<Seg options={RANGES} value={range} onChange={setRange} />}
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.traces.tiles.spans', { range })}
            value={mockTraceTiles.spans_indexed}
            sub={<span className="mono dimmer">{mockTraceTiles.spans_sub}</span>}
          />
          <StatTile
            label={t('console.traces.tiles.p95')}
            value={mockTraceTiles.p95}
            sub={<span className="mono dimmer">{mockTraceTiles.p95_sub}</span>}
          />
          <StatTile
            label={t('console.traces.tiles.slowest')}
            value={<span style={{ fontSize: 15 }}>{mockTraceTiles.slowest_op}</span>}
            sub={<span className="mono dimmer">{mockTraceTiles.slowest_sub}</span>}
          />
          <StatTile
            label={t('console.traces.tiles.errors')}
            value={mockTraceTiles.error_rate}
            sub={<span className="mono dimmer">{mockTraceTiles.error_sub}</span>}
          />
        </StatTileGrid>
      }
      filters={
        <>
          <FilterChip>{t('console.traces.filters.kindAny')}</FilterChip>
          <FilterChip>{t('console.traces.filters.agentAll')}</FilterChip>
          <FilterChip active={slowOnly} onClick={() => setSlowOnly((value) => !value)}>
            {t('console.traces.filters.slow')}
          </FilterChip>
          <FilterSearch
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder={t('console.traces.filters.searchPlaceholder')}
            className="max-w-[340px]"
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.traces.columns.trace')}</TableHead>
              <TableHead>{t('console.traces.columns.rootOp')}</TableHead>
              <TableHead>{t('console.traces.columns.run')}</TableHead>
              <TableHead>{t('console.traces.columns.agent')}</TableHead>
              <TableHead className="num">{t('console.traces.columns.spans')}</TableHead>
              <TableHead>{t('console.traces.columns.breakdown')}</TableHead>
              <TableHead className="num">{t('console.traces.columns.duration')}</TableHead>
              <TableHead className="num">{t('console.traces.columns.started')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row) => (
              <TableRow
                key={row.trace_id}
                className="rowlink cursor-pointer"
                onClick={() => navigate(`/v2/observe/traces/${row.trace_id}`)}
              >
                <TableCell>
                  <span className="runid">{row.trace_id}</span>
                </TableCell>
                <TableCell className="mono dim">{row.root_op}</TableCell>
                <TableCell>
                  <span className="runid">{row.run_id}</span>
                </TableCell>
                <TableCell>
                  <span className="idm" style={{ '--c': row.subject_color } as React.CSSProperties}>
                    <i />
                    {row.subject_id}
                  </span>
                </TableCell>
                <TableCell className="num dim">{row.span_count}</TableCell>
                <TableCell>
                  <TBar slices={row.breakdown} />
                </TableCell>
                <TableCell className="num dim">{row.duration}</TableCell>
                <TableCell className="num dimmer">{row.started}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pager
          summary={
            <>
              {t('console.traces.pageSummary', { count: rows.length })}
              <TBarLegend slices={['policy', 'model', 'tool', 'artifact']} />
            </>
          }
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
