import { useMemo, useState } from 'react'

import {
  ConsoleButton,
  DataStateNote,
  Hist,
  IconBot,
  IconFileMark,
  IconKey,
  IconReplay,
  IconShieldX,
  IconWarnTriangle,
  Seg,
  StatTile,
  StatTileGrid,
  StatusChip,
  runStatusToConsole,
} from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { catColor, compactNumber, percent } from '../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAgentWorkbench } from '@/services/agent-service'
import { getObserveDashboard, type ObserveRange } from '@/services/observe-service'
import {
  listRunAudits,
  listRuns,
  type RunAuditLogResponse,
  type RunResponse,
} from '@/services/run-service'

const RANGES = ['1h', '24h', '7d', '30d'] as const
type Range = (typeof RANGES)[number]

const RANGE_MS: Record<Range, number> = {
  '1h': 3_600_000,
  '24h': 86_400_000,
  '7d': 7 * 86_400_000,
  '30d': 30 * 86_400_000,
}

/** The observe dashboard only models these windows. */
const OBSERVE_RANGE: Record<Range, ObserveRange> = {
  '1h': '1h',
  '24h': '24h',
  '7d': '7d',
  '30d': '7d',
}

const RUN_SAMPLE = 200
const BUCKETS = 24

function clockTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`
  return `${(ms / 1000).toFixed(1)}s`
}

type Outcome = 'pass' | 'degraded' | 'blocked'

function outcomeOf(status: string): Outcome {
  if (status === 'succeeded') return 'pass'
  if (status === 'failed' || status === 'cancelled' || status === 'canceled') return 'blocked'
  return 'degraded'
}

/** Bucket the sampled runs into equal slices across the selected window. */
function bucketRuns(runs: RunResponse[], windowMs: number): Array<[number, number, number]> {
  const now = Date.now()
  const start = now - windowMs
  const width = windowMs / BUCKETS
  const buckets: Array<[number, number, number]> = Array.from({ length: BUCKETS }, () => [0, 0, 0])
  runs.forEach((run) => {
    const at = new Date(run.started_at).getTime()
    if (Number.isNaN(at) || at < start) return
    const index = Math.min(BUCKETS - 1, Math.max(0, Math.floor((at - start) / width)))
    const outcome = outcomeOf(run.status)
    if (outcome === 'pass') buckets[index][0] += 1
    else if (outcome === 'degraded') buckets[index][1] += 1
    else buckets[index][2] += 1
  })
  return buckets
}

/** Gateway audits are the governance feed; tone them by recorded outcome. */
function auditTone(entry: RunAuditLogResponse): { className: string; Icon: typeof IconShieldX } {
  const outcome = (entry.outcome || '').toLowerCase()
  if (outcome && outcome !== 'succeeded' && outcome !== 'ok' && outcome !== 'pass') {
    return { className: 't-bad', Icon: IconShieldX }
  }
  const gateway = (entry.gateway_type || '').toLowerCase()
  if (gateway.includes('secret')) return { className: 't-info', Icon: IconKey }
  if (gateway.includes('budget') || gateway.includes('cost')) {
    return { className: 't-warn', Icon: IconWarnTriangle }
  }
  if (gateway.includes('policy') || gateway.includes('intent')) {
    return { className: 't-brand', Icon: IconFileMark }
  }
  return { className: 't-info', Icon: IconBot }
}

export default function ConsoleOverview() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<Range>('24h')

  const startedAfter = useMemo(
    () => new Date(Date.now() - RANGE_MS[range]).toISOString(),
    [range],
  )

  const dashboardQuery = useQuery({
    queryKey: ['console', 'overview', 'dashboard', range],
    queryFn: () => getObserveDashboard({ range: OBSERVE_RANGE[range] }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const runsQuery = useQuery({
    queryKey: ['console', 'overview', 'runs', startedAfter],
    queryFn: () =>
      listRuns({
        started_after: startedAfter,
        include_observe_summary: true,
        page_size: RUN_SAMPLE,
      }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const auditsQuery = useQuery({
    queryKey: ['console', 'overview', 'audits'],
    queryFn: () => listRunAudits({ page_size: 5 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const agentsQuery = useQuery({
    queryKey: ['console', 'overview', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: 4 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const runs = useMemo(() => runsQuery.data?.items || [], [runsQuery.data])
  const buckets = useMemo(() => bucketRuns(runs, RANGE_MS[range]), [runs, range])
  const bucketMax = Math.max(1, ...buckets.map(([p, d, b]) => p + d + b))

  const passCount = runs.filter((run) => outcomeOf(run.status) === 'pass').length
  const degradedCount = runs.filter((run) => outcomeOf(run.status) === 'degraded').length
  const blockedCount = runs.filter((run) => outcomeOf(run.status) === 'blocked').length
  const settled = passCount + blockedCount
  const durations = runs
    .map((run) => run.duration_ms)
    .filter((value): value is number => value != null)
    .sort((a, b) => a - b)
  const p95 = durations.length
    ? durations[Math.min(durations.length - 1, Math.floor(durations.length * 0.95))]
    : null
  const p50 = durations.length ? durations[Math.floor(durations.length * 0.5)] : null

  const recentRuns = runs.slice(0, 6)
  const audits = auditsQuery.data?.items || []
  const agents = agentsQuery.data?.items || []

  const spendCard = dashboardQuery.data?.metric_cards?.find((card) =>
    card.id.toLowerCase().includes('cost') || card.label.toLowerCase().includes('spend'),
  )

  // Per-agent outcome history has no endpoint; derive a real strip from the
  // sampled runs for that agent, newest last, and leave the rest blank.
  const histFor = (agentId: string) => {
    const own = runs
      .filter((run) => run.subject_id === agentId)
      .slice(0, 12)
      .reverse()
      .map((run) => {
        const outcome = outcomeOf(run.status)
        return outcome === 'pass' ? 'p' : outcome === 'degraded' ? 'd' : 'f'
      })
      .join('')
    return own.padStart(12, 'e')
  }

  return (
    <>
      <div className="page-head">
        <h1>{t('console.overview.title')}</h1>
        <span className="spacer" />
        <Seg options={RANGES} value={range} onChange={setRange} />
        <ConsoleButton
          onClick={() => {
            void runsQuery.refetch()
            void dashboardQuery.refetch()
            void auditsQuery.refetch()
            void agentsQuery.refetch()
          }}
        >
          <IconReplay />
          {t('console.overview.refresh')}
        </ConsoleButton>
      </div>

      <div>
        <StatTileGrid>
          <StatTile
            label={t('console.overview.tiles.runs')}
            value={runsQuery.data ? compactNumber(runs.length) : '—'}
            na={!runsQuery.data}
            sub={
              <span className="mono dimmer">
                {runs.length >= RUN_SAMPLE ? `first ${RUN_SAMPLE} in window` : `in the last ${range}`}
              </span>
            }
          />
          <StatTile
            label={t('console.overview.tiles.passRate')}
            value={settled > 0 ? percent(passCount / settled) : '—'}
            na={settled === 0}
            sub={
              <span className="mono dimmer">
                {passCount} pass · {degradedCount} in flight · {blockedCount} failed
              </span>
            }
          />
          <StatTile
            label={t('console.overview.tiles.spend')}
            value={spendCard?.value || '—'}
            na={!spendCard}
            sub={<span className="mono dimmer">{spendCard?.delta || 'from run cost entries'}</span>}
          />
          <StatTile
            label={t('console.overview.tiles.p95')}
            value={formatDuration(p95)}
            na={p95 == null}
            sub={<span className="mono dimmer">p50 {formatDuration(p50)}</span>}
          />
        </StatTileGrid>

        <div className="ovgrid">
          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.outcomesTitle')}</h2>
                <span className="hint">{t('console.overview.outcomesHint')}</span>
                <a
                  className="more"
                  href="/observe/runs"
                  onClick={(event) => {
                    event.preventDefault()
                    navigate('/observe/runs')
                  }}
                >
                  {t('console.overview.openRuns')}
                </a>
              </div>
              <div className="chartwrap">
                <div className="legend">
                  <span>
                    <i style={{ background: 'var(--success)', opacity: 0.75 }} />
                    {t('console.overview.legend.pass')}
                  </span>
                  <span>
                    <i style={{ background: 'var(--warning)' }} />
                    {t('console.overview.legend.degraded')}
                  </span>
                  <span>
                    <i style={{ background: 'var(--destructive)' }} />
                    {t('console.overview.legend.blocked')}
                  </span>
                </div>
                <div className="bars">
                  {buckets.map(([pass, degraded, blocked], index) => (
                    <div
                      key={index}
                      className="col"
                      title={`${pass} pass · ${degraded} in flight · ${blocked} failed`}
                    >
                      {(
                        [
                          [pass, 'b-pass'],
                          [degraded, 'b-deg'],
                          [blocked, 'b-blk'],
                        ] as const
                      ).map(
                        ([value, cls]) =>
                          value > 0 && (
                            <span
                              key={cls}
                              className={cls}
                              style={{ height: `${Math.max(2, (value / bucketMax) * 100)}%` }}
                            />
                          ),
                      )}
                    </div>
                  ))}
                </div>
                <div className="axis">
                  <span>−{range}</span>
                  <span />
                  <span />
                  <span />
                  <span>now</span>
                </div>
              </div>
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.recentRuns')}</h2>
                <a
                  className="more"
                  href="/observe/runs"
                  onClick={(event) => {
                    event.preventDefault()
                    navigate('/observe/runs')
                  }}
                >
                  {t('console.overview.viewAll')}
                </a>
              </div>
              {recentRuns.length === 0 ? (
                <DataStateNote isPending={runsQuery.isPending} isError={runsQuery.isError} />
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>{t('console.overview.columns.run')}</th>
                      <th>{t('console.overview.columns.agent')}</th>
                      <th>{t('console.overview.columns.status')}</th>
                      <th className="num">{t('console.overview.columns.duration')}</th>
                      <th className="num">{t('console.overview.columns.cost')}</th>
                      <th className="num">{t('console.overview.columns.started')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentRuns.map((run) => (
                      <tr
                        key={run.id}
                        className="rowlink"
                        onClick={() => navigate(`/observe/runs/${run.id}`)}
                      >
                        <td>
                          <span className="runid">{run.id}</span>
                        </td>
                        <td>
                          <span
                            className="idm"
                            style={{ '--c': catColor(run.subject_id) } as React.CSSProperties}
                          >
                            <i />
                            {run.subject_id || '—'}
                          </span>
                        </td>
                        <td>
                          <StatusChip status={runStatusToConsole(run.status)} />
                        </td>
                        <td className="num dim">{formatDuration(run.duration_ms)}</td>
                        {/* RunResponse carries no per-run cost; see the Runs
                            screen's cost overview for the aggregate. */}
                        <td className="num dim">—</td>
                        <td className="num dimmer">{clockTime(run.started_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>

          <div className="stack">
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.governanceTitle')}</h2>
                <a
                  className="more"
                  href="/govern/audit"
                  onClick={(event) => {
                    event.preventDefault()
                    navigate('/govern/audit')
                  }}
                >
                  {t('console.overview.auditLog')}
                </a>
              </div>
              {audits.length === 0 ? (
                <div className="empty-note">
                  {auditsQuery.isPending
                    ? t('console.common.loading')
                    : auditsQuery.isError
                      ? t('console.common.loadError')
                      : t('console.overview.governanceEmpty')}
                  <span className="mono">{t('console.overview.governanceEmptyNote')}</span>
                </div>
              ) : (
                <ul className="feed">
                  {audits.map((entry, index) => {
                    const tone = auditTone(entry)
                    return (
                      <li key={entry.audit_id || `${entry.run_id}:${index}`}>
                        <span className={`fico ${tone.className}`}>
                          <tone.Icon strokeWidth={2.2} />
                        </span>
                        <div>
                          <p>
                            <span className="mono">{entry.gateway_type || entry.step_type}</span>{' '}
                            {entry.preview || entry.step_type}
                          </p>
                          <time>
                            {clockTime(entry.timestamp)} · {entry.run_id}
                          </time>
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>

            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.activeAgents')}</h2>
                <a
                  className="more"
                  href="/build/agents"
                  onClick={(event) => {
                    event.preventDefault()
                    navigate('/build/agents')
                  }}
                >
                  {t('console.overview.allAgents')}
                </a>
              </div>
              {agents.length === 0 ? (
                <DataStateNote isPending={agentsQuery.isPending} isError={agentsQuery.isError} />
              ) : (
                <table>
                  <tbody>
                    {agents.map((agent) => (
                      <tr key={agent.id}>
                        <td>
                          <span
                            className="idm"
                            style={{ '--c': catColor(agent.id) } as React.CSSProperties}
                          >
                            <i />
                            {agent.name}
                          </span>
                        </td>
                        <td className="num">
                          <Hist pattern={histFor(agent.id)} label="recent run outcomes" />
                        </td>
                        <td className="num dim">{compactNumber(agent.today_calls)} runs</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
