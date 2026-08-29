import { useMemo, useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  DataStateNote,
  IconChevronRight,
  IconExport,
  KeyValueList,
  StatusChip,
  TBar,
  WorkbenchPanel,
  runStatusToConsole,
  type BreakdownSlice,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor } from '../../adapters/palette'
import { formatDurationMs } from '../../adapters/run-detail'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { listRunSteps, listRunsByTrace, type RunStepResponse } from '@/services/run-service'

const STEP_PAGE_SIZE = 400

/**
 * The platform has no standalone trace or span resource. A trace is the set of
 * runs sharing a trace_id, and run *steps* are its spans — so this screen
 * composes `/runs/trace/{id}` with `/runs/steps?trace_id=` rather than reading
 * a fictional span endpoint. Waterfall geometry mirrors the run ledger's
 * (see adapters/run-detail.ts) but is computed against the trace window, which
 * can span several runs.
 */
const STEP_KIND_COLOR: Record<string, string> = {
  policy: 'var(--cat-pink)',
  gate: 'var(--cat-pink)',
  model: 'var(--cat-blue)',
  llm: 'var(--cat-blue)',
  tool: 'var(--cat-cyan)',
  artifact: 'var(--cat-teal)',
  secret: 'var(--cat-slate)',
  knowledge: 'var(--cat-indigo)',
  workflow: 'var(--cat-purple)',
}

function stepHead(stepType: string): string {
  return stepType.split(/[_.·]/)[0]?.toLowerCase() || ''
}

function stepKindColor(stepType: string): string {
  return STEP_KIND_COLOR[stepHead(stepType)] || 'var(--cat-slate)'
}

/** Step types collapse into the four lanes the breakdown bar renders. */
function stepLane(stepType: string): BreakdownSlice['kind'] {
  const head = stepHead(stepType)
  if (head === 'policy' || head === 'gate') return 'policy'
  if (head === 'tool') return 'tool'
  if (head === 'artifact') return 'artifact'
  return 'model'
}

function msBetween(from?: string | null, to?: string | null): number | null {
  if (!from || !to) return null
  const start = new Date(from).getTime()
  const end = new Date(to).getTime()
  if (Number.isNaN(start) || Number.isNaN(end)) return null
  return end - start
}

function epoch(iso?: string | null): number | null {
  if (!iso) return null
  const value = new Date(iso).getTime()
  return Number.isNaN(value) ? null : value
}

function seconds(ms: number): string {
  return `${(ms / 1000).toFixed(1)}s`
}

function attributeValue(value: unknown): string {
  if (value == null) return '—'
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

interface TraceSpan {
  id: string
  name: string
  bold: boolean
  child: boolean
  expandable: boolean
  kind: string
  color: string
  left: number
  width: number
  duration: string
  detail: {
    span: Array<{ key: string; value: string; ok?: boolean }>
    attributes: Array<{ key: string; value: string }>
    events: Array<{ key: string; value: string }>
  }
}

export default function ConsoleTraceDetail() {
  const { t } = useTranslation()
  const { traceId } = useParams<{ traceId: string }>()
  const navigate = useConsoleNavigate()
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null)

  const runsQuery = useQuery({
    queryKey: ['console', 'trace-detail', 'runs', traceId],
    queryFn: () => listRunsByTrace(traceId as string, { page_size: 50 }),
    options: { enabled: Boolean(traceId), retry: false, refetchOnWindowFocus: false },
  })
  const stepsQuery = useQuery({
    queryKey: ['console', 'trace-detail', 'steps', traceId],
    queryFn: () => listRunSteps({ trace_id: traceId as string, page_size: STEP_PAGE_SIZE }),
    options: { enabled: Boolean(traceId), retry: false, refetchOnWindowFocus: false },
  })

  const runs = useMemo(() => runsQuery.data?.items || [], [runsQuery.data])
  const steps = useMemo(() => {
    const items = [...(stepsQuery.data?.items || [])]
    items.sort((a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime())
    return items
  }, [stepsQuery.data])

  const trace = useMemo(() => {
    // The trace window is the union of every run in the trace; steps fill any
    // gap when a run has not been closed out yet.
    const starts = [
      ...runs.map((run) => epoch(run.started_at)),
      ...steps.map((step) => epoch(step.started_at)),
    ].filter((value): value is number => value != null)
    const ends = [
      ...runs.map((run) => epoch(run.ended_at) ?? epoch(run.started_at)),
      ...steps.map((step) => epoch(step.ended_at) ?? epoch(step.started_at)),
    ].filter((value): value is number => value != null)
    const windowStart = starts.length ? Math.min(...starts) : 0
    const windowEnd = ends.length ? Math.max(...ends) : windowStart
    const windowMs = Math.max(1, windowEnd - windowStart)

    const rootRun = runs.find((run) => !run.parent_run_id) || runs[0] || null
    const failedRun = runs.find((run) => run.status === 'failed')
    const statusRun = failedRun || rootRun
    const subjectId = rootRun?.subject_id || '—'

    // Lane totals for the breakdown bar — real step durations, no estimates.
    const laneTotals = new Map<BreakdownSlice['kind'], number>()
    steps.forEach((step) => {
      const lane = stepLane(step.step_type)
      laneTotals.set(lane, (laneTotals.get(lane) || 0) + Math.max(msBetween(step.started_at, step.ended_at) ?? 0, 1))
    })
    const laneSum = [...laneTotals.values()].reduce((a, b) => a + b, 0) || 1
    const laneRows = [...laneTotals.entries()].sort((a, b) => b[1] - a[1])

    const spans: TraceSpan[] = steps.map((step: RunStepResponse) => {
      const startedAt = epoch(step.started_at)
      const duration = msBetween(step.started_at, step.ended_at)
      const left = startedAt == null ? 0 : ((startedAt - windowStart) / windowMs) * 100
      const width = duration == null ? 1 : (duration / windowMs) * 100
      const metrics = step.metrics_json || {}
      const offset = startedAt == null ? null : startedAt - windowStart

      return {
        id: step.id,
        name: step.node_id ? `${step.step_type} ${step.node_id}` : step.step_type,
        // Run steps are a flat sequence: there is no parent-span id on the
        // record, so nothing to bold as a root or expand into children.
        bold: false,
        child: false,
        expandable: false,
        kind: stepHead(step.step_type) || step.step_type,
        color: stepKindColor(step.step_type),
        left: Math.max(0, Math.min(100, left)),
        width: Math.max(1, Math.min(100 - Math.max(0, left), width)),
        duration: formatDurationMs(duration),
        detail: {
          span: [
            { key: 'Span id', value: step.step_id || step.id },
            // No parent-span reference on run steps.
            { key: 'Parent', value: '—' },
            { key: 'Kind', value: step.step_type },
            { key: 'Service', value: step.node_id || '—' },
            { key: 'Started', value: offset == null ? '—' : `+${(offset / 1000).toFixed(2)}s` },
            { key: 'Duration', value: formatDurationMs(duration) },
            {
              key: 'Status',
              value: step.status.toUpperCase(),
              ok: step.status === 'succeeded',
            },
          ],
          attributes: [
            { key: 'run_id', value: step.run_id },
            ...(step.input_summary ? [{ key: 'input', value: step.input_summary }] : []),
            ...(step.output_summary ? [{ key: 'output', value: step.output_summary }] : []),
            ...Object.entries(metrics).map(([key, value]) => ({
              key,
              value: attributeValue(value),
            })),
          ],
          // BACKEND-PENDING: there is no span-event resource — a step only
          // records its error, so that is the only event we can show honestly.
          events: [
            ...(step.error_code ? [{ key: 'error.code', value: step.error_code }] : []),
            ...(step.error_message ? [{ key: 'error.message', value: step.error_message }] : []),
          ],
        },
      }
    })

    return {
      id: traceId || '—',
      status: runStatusToConsole(statusRun?.status || 'unknown'),
      status_label: (statusRun?.status || '—').toUpperCase(),
      subject_id: subjectId,
      subject_color: catColor(rootRun?.subject_id),
      run_id: rootRun?.id || '',
      meta: [
        {
          key: 'Root operation',
          value: rootRun ? `${rootRun.mode}${subjectId !== '—' ? ` / ${subjectId}` : ''}` : '—',
        },
        ...(rootRun
          ? [{ key: 'Run', value: rootRun.id, to: `/v2/observe/runs/${rootRun.id}` }]
          : [{ key: 'Run', value: '—' }]),
        { key: 'Spans', value: `${steps.length} · ${runs.length} runs` },
        { key: 'Duration', value: formatDurationMs(windowMs) },
        {
          key: 'Started',
          value: starts.length ? new Date(windowStart).toISOString().replace('T', ' ') : '—',
        },
        // BACKEND-PENDING: no trace-level evidence digest is exposed; artifact
        // digests live on the run detail payload.
        { key: 'Evidence digest', value: '—' },
      ] as Array<{ key: string; value: string; to?: string }>,
      ticks: [0, 1, 2, 3, 4].map((index) => seconds((windowMs * index) / 4)),
      breakdown: laneRows.map(([kind, value]) => ({
        kind,
        pct: (value / laneSum) * 100,
      })) satisfies BreakdownSlice[],
      breakdown_rows: laneRows.map(([kind, value]) => ({
        key: kind,
        value: `${(value / 1000).toFixed(2)}s · ${Math.round((value / laneSum) * 100)}%`,
      })),
      code: {
        command: `soit runs steps --trace ${traceId || ''}`,
        output: `${steps.length} spans · ${runs.length} runs on this trace`,
      },
      spans,
    }
  }, [runs, steps, traceId])

  const selected =
    selectedSpanId && trace.spans.some((span) => span.id === selectedSpanId)
      ? selectedSpanId
      : trace.spans[0]?.id

  const selectedSpan = trace.spans.find((span) => span.id === selected)

  if (!runsQuery.data || !stepsQuery.data) {
    return (
      <>
        <Backlink to="/v2/observe/traces">{t('console.traceDetail.back')}</Backlink>
        <div className="rd-head">
          <h1>{traceId}</h1>
        </div>
        <div className="panel">
          <DataStateNote
            isPending={runsQuery.isPending || stepsQuery.isPending}
            isError={runsQuery.isError || stepsQuery.isError}
          />
        </div>
      </>
    )
  }

  return (
    <>
      <Backlink to="/v2/observe/traces">{t('console.traceDetail.back')}</Backlink>

      <div className="rd-head">
        <h1>{trace.id}</h1>
        <StatusChip status={trace.status} label={trace.status_label} />
        <span className="chip">
          <i style={{ background: trace.subject_color }} />
          {trace.subject_id}
        </span>
        <span className="spacer" />
        <button
          type="button"
          className="btn"
          onClick={() => navigate(`/v2/observe/runs/${trace.run_id}`)}
        >
          <IconChevronRight />
          {t('console.traceDetail.openRun')}
        </button>
        {/* BACKEND-PENDING: no OTLP export endpoint — button stays inert. */}
        <button type="button" className="btn">
          <IconExport />
          {t('console.traceDetail.exportOtlp')}
        </button>
      </div>

      <div className="rd-meta">
        {trace.meta.map((item) => (
          <span key={item.key}>
            {item.key}
            <b>
              {'to' in item && item.to ? (
                <a
                  className="runid"
                  href={item.to as string}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(item.to as string)
                  }}
                >
                  {item.value}
                </a>
              ) : (
                item.value
              )}
            </b>
          </span>
        ))}
      </div>

      <div className="rdgrid">
        <WorkbenchPanel
          title={t('console.traceDetail.waterfall')}
          hint={t('console.traceDetail.waterfallHint')}
        >
          <div className="axisrow">
            <span>{t('console.traceDetail.axis.span')}</span>
            <span>{t('console.traceDetail.axis.kind')}</span>
            <span className="ticks">
              {trace.ticks.map((tick) => (
                <span key={tick}>{tick}</span>
              ))}
            </span>
            <span style={{ textAlign: 'right' }}>{t('console.traceDetail.axis.dur')}</span>
          </div>
          <ul className="spans">
            {trace.spans.map((span) => (
              <li
                key={span.id}
                className={cn(span.id === selected && 'sel')}
                onClick={() => setSelectedSpanId(span.id)}
              >
                <span
                  className={cn('sname', span.child && 'child')}
                  style={{ paddingLeft: span.child ? 42 : span.id === 'span_root' ? 0 : 16 }}
                >
                  {span.expandable && (
                    <span className="twist">
                      <IconChevronRight size={10} />
                    </span>
                  )}
                  {span.bold ? <b>{span.name}</b> : span.name}
                </span>
                <span className="kind" style={{ '--c': span.color } as React.CSSProperties}>
                  <i />
                  {span.kind}
                </span>
                <span className="wf">
                  <i
                    style={{ '--c': span.color, left: `${span.left}%`, width: `${span.width}%` } as React.CSSProperties}
                  />
                </span>
                <span className="sdur">{span.duration}</span>
              </li>
            ))}
          </ul>
          <CodeBlock command={trace.code.command} output={trace.code.output} />
        </WorkbenchPanel>

        <div className="rail">
          <WorkbenchPanel title={t('console.traceDetail.span')} hint={t('console.traceDetail.spanHint')}>
            <ul className="kv">
              {selectedSpan?.detail?.span.map((item) => (
                <li key={item.key}>
                  <span className="k">{item.key}</span>
                  <span className="v" style={item.ok ? { color: 'var(--success-foreground)' } : undefined}>
                    {item.value}
                  </span>
                </li>
              ))}
            </ul>
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.attributes')}>
            <KeyValueList items={selectedSpan?.detail?.attributes || []} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.spanEvents')}>
            <KeyValueList items={selectedSpan?.detail?.events || []} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.traceDetail.breakdown')}>
            <div style={{ padding: '12px 14px 4px' }}>
              <TBar slices={trace.breakdown} style={{ width: '100%' }} />
            </div>
            <KeyValueList items={trace.breakdown_rows} />
          </WorkbenchPanel>
        </div>
      </div>
    </>
  )
}
