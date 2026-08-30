import { useMemo, useState } from 'react'

import {
  DataStateRow,
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
  type BreakdownSlice,
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
import { catColor } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { mockTiles } from '../../mocks/tiles'
import { useSubjectNames } from '../../adapters/subject-names'
import { useTranslation } from '@/i18n'
import { listRunSteps, listRuns, type RunStepResponse } from '@/services/run-service'

const RANGES = ['1h', '24h', '7d', '30d'] as const

const RANGE_MS: Record<(typeof RANGES)[number], number> = {
  '1h': 3_600_000,
  '24h': 86_400_000,
  '7d': 7 * 86_400_000,
  '30d': 30 * 86_400_000,
}

const PAGE_SIZE = 20
const STEP_SAMPLE = 400

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`
  return `${(ms / 1000).toFixed(1)}s`
}

function clockTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

/** Step types collapse into the four lanes the prototype's bar renders. */
function stepLane(stepType: string): BreakdownSlice['kind'] {
  const head = stepType.split(/[_.·]/)[0]?.toLowerCase() || ''
  if (head === 'policy' || head === 'gate') return 'policy'
  if (head === 'tool') return 'tool'
  if (head === 'artifact') return 'artifact'
  return 'model'
}

function breakdownFor(steps: RunStepResponse[]): BreakdownSlice[] {
  if (steps.length === 0) return []
  const totals = new Map<BreakdownSlice['kind'], number>()
  steps.forEach((step) => {
    const lane = stepLane(step.step_type)
    const duration =
      step.ended_at && step.started_at
        ? Math.max(0, new Date(step.ended_at).getTime() - new Date(step.started_at).getTime())
        : 0
    totals.set(lane, (totals.get(lane) || 0) + Math.max(duration, 1))
  })
  const sum = [...totals.values()].reduce((a, b) => a + b, 0) || 1
  return [...totals.entries()].map(([kind, value]) => ({
    kind,
    pct: (value / sum) * 100,
  }))
}

/**
 * The platform has no standalone trace or span resource — a trace is the set of
 * runs sharing a trace_id, and run steps are its spans. This screen composes
 * both rather than reading a fictional /traces endpoint.
 */
export default function ConsoleTraces() {
  const subjectName = useSubjectNames()
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<(typeof RANGES)[number]>('24h')
  const [slowOnly, setSlowOnly] = useState(false)
  const [search, setSearch] = useState('')

  const startedAfter = useMemo(
    () => new Date(Date.now() - RANGE_MS[range]).toISOString(),
    [range],
  )

  const runsQuery = useQuery({
    queryKey: ['console', 'traces', 'runs', startedAfter],
    queryFn: () =>
      listRuns({
        started_after: startedAfter,
        include_observe_summary: true,
        page_size: PAGE_SIZE,
      }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // One sampled page of steps, grouped client-side, keeps the lane breakdown
  // real without firing a request per row.
  const stepsQuery = useQuery({
    queryKey: ['console', 'traces', 'steps', startedAfter],
    queryFn: () => listRunSteps({ started_after: startedAfter, page_size: STEP_SAMPLE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const stepsByRun = useMemo(() => {
    const map = new Map<string, RunStepResponse[]>()
    ;(stepsQuery.data?.items || []).forEach((step) => {
      const list = map.get(step.run_id)
      if (list) list.push(step)
      else map.set(step.run_id, [step])
    })
    return map
  }, [stepsQuery.data])

  const traces = useMemo(() => {
    const runs = (runsQuery.data?.items || []).filter((run) => run.trace_id)
    return runs.map((run) => {
      const steps = stepsByRun.get(run.id) || []
      return {
        trace_id: run.trace_id as string,
        root_op: run.mode,
        run_id: run.id,
        subject_id: subjectName(run.subject_id),
        span_count: steps.length || run.observe_summary?.step_count || 0,
        breakdown: breakdownFor(steps),
        duration_ms: run.duration_ms ?? null,
        started_at: run.started_at,
      }
    })
  }, [runsQuery.data, stepsByRun, subjectName])

  const rows = traces.filter((row) => {
    if (slowOnly && (row.duration_ms ?? 0) <= 5000) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.trace_id, row.root_op, row.run_id, row.subject_id].some((value) =>
      String(value).toLowerCase().includes(query),
    )
  })

  const durations = traces
    .map((row) => row.duration_ms)
    .filter((value): value is number => value != null)
    .sort((a, b) => a - b)
  const p95 = durations.length
    ? formatDuration(durations[Math.min(durations.length - 1, Math.floor(durations.length * 0.95))])
    : '—'
  const slowest = traces.reduce<(typeof traces)[number] | null>(
    (worst, row) => (!worst || (row.duration_ms ?? 0) > (worst.duration_ms ?? 0) ? row : worst),
    null,
  )
  const totalSpans = traces.reduce((sum, row) => sum + row.span_count, 0)

  return (
    <Workbench
      title={t('console.traces.title')}
      description={t('console.traces.description')}
      actions={<Seg options={RANGES} value={range} onChange={setRange} />}
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.traces.tiles.spans', { range })}
            value={runsQuery.data ? String(totalSpans) : '—'}
            na={!runsQuery.data}
            sub={<span className="mono dimmer">{traces.length} traces on this page</span>}
          />
          <StatTile
            label={t('console.traces.tiles.p95')}
            value={p95}
            na={durations.length === 0}
            sub={<span className="mono dimmer">run duration</span>}
          />
          <StatTile
            label={t('console.traces.tiles.slowest')}
            value={<span style={{ fontSize: 15 }}>{slowest?.root_op || '—'}</span>}
            na={!slowest}
            sub={
              <span className="mono dimmer">
                {slowest ? formatDuration(slowest.duration_ms) : '—'}
              </span>
            }
          />
          {/* BACKEND-PENDING: prototype figure — no span-level error
              aggregation endpoint; see mocks/tiles.ts. */}
          <StatTile
            label={t('console.traces.tiles.errors')}
            value={mockTiles.traceErrorSpans.value}
            sub={<span className="mono dimmer">{mockTiles.traceErrorSpans.sub}</span>}
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
            {rows.length === 0 ? (
              <DataStateRow
                colSpan={8}
                isPending={runsQuery.isPending}
                isError={runsQuery.isError}
              />
            ) : (
              rows.map((row) => (
                <TableRow
                  key={`${row.trace_id}:${row.run_id}`}
                  className="rowlink cursor-pointer"
                  onClick={() => navigate(`/observe/traces/${row.trace_id}`)}
                >
                  <TableCell>
                    <span className="runid">{row.trace_id}</span>
                  </TableCell>
                  <TableCell className="mono dim">{row.root_op}</TableCell>
                  <TableCell>
                    <span className="runid">{row.run_id}</span>
                  </TableCell>
                  <TableCell>
                    <span
                      className="idm"
                      style={{ '--c': catColor(row.subject_id) } as React.CSSProperties}
                    >
                      <i />
                      {row.subject_id}
                    </span>
                  </TableCell>
                  <TableCell className="num dim">{row.span_count}</TableCell>
                  <TableCell>
                    <TBar slices={row.breakdown} />
                  </TableCell>
                  <TableCell className="num dim">{formatDuration(row.duration_ms)}</TableCell>
                  <TableCell className="num dimmer">{clockTime(row.started_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager
          summary={
            <>
              {t('console.traces.pageSummary', { count: rows.length })}
              <TBarLegend slices={['policy', 'model', 'tool', 'artifact']} />
            </>
          }
        />
      </WorkbenchPanel>
    </Workbench>
  )
}
