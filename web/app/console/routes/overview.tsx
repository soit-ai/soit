import { useState } from 'react'

import {
  ConsoleButton,
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
  type ConsoleStatus,
} from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { useTranslation } from '@/i18n'

type Range = '1h' | '24h' | '7d' | '30d'

// BACKEND-PENDING: overview aggregates come from run-service metrics.
const OUTCOME_BUCKETS: Array<[number, number, number]> = [
  [38, 1, 0], [31, 0, 0], [26, 1, 0], [22, 0, 1], [19, 0, 0], [24, 1, 0], [33, 0, 0], [41, 2, 1],
  [52, 1, 0], [61, 2, 1], [66, 1, 0], [58, 3, 1], [63, 1, 2], [71, 2, 0], [68, 1, 1], [74, 2, 0],
  [69, 1, 1], [62, 2, 0], [57, 1, 1], [64, 2, 2], [70, 1, 0], [66, 2, 1], [59, 1, 0], [48, 2, 3],
]

const MOCK_RECENT_RUNS = [
  { id: 'run_01J9KD84QF', agent: 'support-triage', color: 'var(--cat-cyan)', status: 'running' as ConsoleStatus, label: 'RUNNING', duration: '3.1s', cost: '$0.021', started: 'just now' },
  { id: 'run_01J9KD7Z2M', agent: 'ops-copilot', color: 'var(--cat-purple)', status: 'pass' as ConsoleStatus, label: 'PASS', duration: '8.9s', cost: '$0.038', started: '2m ago' },
  { id: 'run_01J9KD6H0T', agent: 'billing-audit', color: 'var(--cat-indigo)', status: 'blocked' as ConsoleStatus, label: 'BLOCKED', duration: '1.2s', cost: '$0.004', started: '9m ago' },
  { id: 'run_01J9KD5PWB', agent: 'support-triage', color: 'var(--cat-cyan)', status: 'pass' as ConsoleStatus, label: 'PASS', duration: '4.4s', cost: '$0.017', started: '14m ago' },
  { id: 'run_01J9KD4XN2', agent: 'kb-refresher', color: 'var(--cat-teal)', status: 'warn' as ConsoleStatus, label: 'DEGRADED', duration: '21.7s', cost: '$0.092', started: '22m ago' },
  { id: 'run_01J9KD3F7Q', agent: 'ops-copilot', color: 'var(--cat-purple)', status: 'pass' as ConsoleStatus, label: 'PASS', duration: '6.0s', cost: '$0.029', started: '31m ago' },
]

const MOCK_ACTIVE_AGENTS = [
  { id: 'support-triage', color: 'var(--cat-cyan)', hist: 'pppdppppfppp', runs: '412 runs' },
  { id: 'ops-copilot', color: 'var(--cat-purple)', hist: 'pppppdpppppp', runs: '287 runs' },
  { id: 'kb-refresher', color: 'var(--cat-teal)', hist: 'pdppdpppppdp', runs: '96 runs' },
  { id: 'billing-audit', color: 'var(--cat-indigo)', hist: 'ppfpppfppppf', runs: '64 runs' },
]

export default function ConsoleOverview() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [range, setRange] = useState<Range>('24h')
  const [demoEmpty, setDemoEmpty] = useState(false)

  const bucketMax = Math.max(...OUTCOME_BUCKETS.map(([p, d, b]) => p + d + b))

  return (
    <>
      <div className="page-head">
        <h1>{t('console.overview.title')}</h1>
        <span className="spacer" />
        <Seg options={['1h', '24h', '7d', '30d'] as const} value={range} onChange={setRange} />
        <ConsoleButton>
          <IconReplay />
          {t('console.overview.refresh')}
        </ConsoleButton>
        <ConsoleButton variant="ghost" onClick={() => setDemoEmpty((value) => !value)}>
          {t('console.overview.demoEmpty')}
        </ConsoleButton>
      </div>

      {demoEmpty ? (
        <div>
          <StatTileGrid>
            <StatTile label={t('console.overview.tiles.runs')} value="—" na sub={<span className="mono dimmer">no runs yet</span>} />
            <StatTile label={t('console.overview.tiles.passRate')} value="—" na sub={<span className="mono dimmer">measured after the first run</span>} />
            <StatTile label={t('console.overview.tiles.spend')} value="$0.00" sub={<span className="mono dimmer">budget $120.00/day</span>} />
            <StatTile label={t('console.overview.tiles.p95')} value="—" na sub={<span className="mono dimmer">no data</span>} />
          </StatTileGrid>
          <div className="panel" style={{ marginBottom: 12 }}>
            <div className="panel-head">
              <h2>{t('console.overview.onboardTitle')}</h2>
              <span className="hint">{t('console.overview.onboardHint')}</span>
            </div>
            <div className="onboard">
              <div className="ob-step done">
                <span className="obn">STEP 1 · DONE</span>
                <b>{t('console.overview.onboard.step1')}</b>
                <p>{t('console.overview.onboard.step1Note')}</p>
                <StatusChip status="pass" label="CONNECTED" />
              </div>
              <div className="ob-step">
                <span className="obn">STEP 2</span>
                <b>{t('console.overview.onboard.step2')}</b>
                <p>{t('console.overview.onboard.step2Note')}</p>
                <ConsoleButton
                  variant="primary"
                  style={{ height: 26, fontSize: 11.5 }}
                  onClick={() => navigate('/v2/build/agents/new')}
                >
                  {t('console.overview.onboard.newAgent')}
                </ConsoleButton>
              </div>
              <div className="ob-step">
                <span className="obn">STEP 3</span>
                <b>{t('console.overview.onboard.step3')}</b>
                <p>{t('console.overview.onboard.step3Note')}</p>
                <ConsoleButton style={{ height: 26, fontSize: 11.5 }} disabled>
                  {t('console.overview.onboard.waiting')}
                </ConsoleButton>
              </div>
            </div>
          </div>
          <div className="ovgrid">
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.recentRuns')}</h2>
              </div>
              <div className="empty-note">
                {t('console.overview.recentEmpty')}
                <span className="mono">{t('console.overview.recentEmptyNote')}</span>
              </div>
            </div>
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.overview.governanceTitle')}</h2>
              </div>
              <div className="empty-note">
                {t('console.overview.governanceEmpty')}
                <span className="mono">{t('console.overview.governanceEmptyNote')}</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div>
          <StatTileGrid>
            <StatTile
              label={t('console.overview.tiles.runs')}
              value="1,284"
              delta={{ direction: 'up', label: '+12.4%' }}
              sub="vs prev 24h"
              spark={
                <svg className="spark" width="88" height="26" viewBox="0 0 88 26">
                  <polyline
                    fill="none"
                    stroke="var(--chart-1)"
                    strokeWidth="1.5"
                    points="0,20 8,18 16,19 24,14 32,15 40,10 48,12 56,8 64,9 72,5 80,7 88,3"
                  />
                </svg>
              }
            />
            <StatTile
              label={t('console.overview.tiles.passRate')}
              value="96.4%"
              sub={<span className="mono dimmer">1,238 pass · 31 degraded · 15 blocked</span>}
            />
            <StatTile
              label={t('console.overview.tiles.spend')}
              value="$41.32"
              delta={{ direction: 'down', label: '−8.1%' }}
              sub="budget $120.00/day"
              spark={
                <svg className="spark" width="88" height="26" viewBox="0 0 88 26">
                  <polyline
                    fill="none"
                    stroke="var(--chart-2)"
                    strokeWidth="1.5"
                    points="0,8 8,10 16,7 24,12 32,11 40,14 48,13 56,16 64,15 72,18 80,17 88,19"
                  />
                </svg>
              }
            />
            <StatTile
              label={t('console.overview.tiles.p95')}
              value="8.2s"
              delta={{ direction: 'flat', label: '±0.0%' }}
              sub="p50 2.9s"
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
                    href="/v2/observe/runs"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/observe/runs')
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
                    {OUTCOME_BUCKETS.map(([pass, degraded, blocked], index) => (
                      <div
                        key={index}
                        className="col"
                        title={`${pass} pass · ${degraded} degraded · ${blocked} blocked/failed`}
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
                    <span>00:00</span>
                    <span>06:00</span>
                    <span>12:00</span>
                    <span>18:00</span>
                    <span>now</span>
                  </div>
                </div>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>{t('console.overview.recentRuns')}</h2>
                  <a
                    className="more"
                    href="/v2/observe/runs"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/observe/runs')
                    }}
                  >
                    {t('console.overview.viewAll')}
                  </a>
                </div>
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
                    {MOCK_RECENT_RUNS.map((run) => (
                      <tr
                        key={run.id}
                        className="rowlink"
                        onClick={() => navigate(`/v2/observe/runs/${run.id}`)}
                      >
                        <td>
                          <span className="runid">{run.id}</span>
                        </td>
                        <td>
                          <span className="idm" style={{ '--c': run.color } as React.CSSProperties}>
                            <i />
                            {run.agent}
                          </span>
                        </td>
                        <td>
                          <StatusChip status={run.status} label={run.label} />
                        </td>
                        <td className="num dim">{run.duration}</td>
                        <td className="num dim">{run.cost}</td>
                        <td className="num dimmer">{run.started}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div className="stack">
              <div className="panel">
                <div className="panel-head">
                  <h2>{t('console.overview.governanceTitle')}</h2>
                  <a
                    className="more"
                    href="/v2/govern/audit"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/govern/audit')
                    }}
                  >
                    {t('console.overview.auditLog')}
                  </a>
                </div>
                <ul className="feed">
                  <li>
                    <span className="fico t-bad">
                      <IconShieldX strokeWidth={2.2} />
                    </span>
                    <div>
                      <p>
                        <span className="mono">egress-allowlist</span> blocked tool call{' '}
                        <span className="mono">fetch_url</span> — destination not in allowlist.
                      </p>
                      <time>13:42:07Z · billing-audit</time>
                    </div>
                  </li>
                  <li>
                    <span className="fico t-warn">
                      <IconWarnTriangle strokeWidth={2.2} />
                    </span>
                    <div>
                      <p>
                        Budget threshold 80% reached for <span className="mono">ops-copilot</span> daily
                        cap.
                      </p>
                      <time>12:58:44Z · cost-guard</time>
                    </div>
                  </li>
                  <li>
                    <span className="fico t-brand">
                      <IconFileMark strokeWidth={2.2} />
                    </span>
                    <div>
                      <p>
                        Policy bundle <span className="mono">v2026.08.27-2</span> activated across
                        workspace.
                      </p>
                      <time>09:15:02Z · Jude</time>
                    </div>
                  </li>
                  <li>
                    <span className="fico t-info">
                      <IconKey strokeWidth={2.2} />
                    </span>
                    <div>
                      <p>
                        Secret <span className="mono">SLACK_BOT_TOKEN</span> rotated. 3 agents re-bound
                        by reference.
                      </p>
                      <time>08:03:19Z · secrets</time>
                    </div>
                  </li>
                  <li>
                    <span className="fico t-info">
                      <IconBot strokeWidth={2.2} />
                    </span>
                    <div>
                      <p>
                        Agent <span className="mono">release-notes</span> promoted to production
                        channel.
                      </p>
                      <time>07:40:56Z · Wei</time>
                    </div>
                  </li>
                </ul>
              </div>

              <div className="panel">
                <div className="panel-head">
                  <h2>{t('console.overview.activeAgents')}</h2>
                  <a
                    className="more"
                    href="/v2/build/agents"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/build/agents')
                    }}
                  >
                    {t('console.overview.allAgents')}
                  </a>
                </div>
                <table>
                  <tbody>
                    {MOCK_ACTIVE_AGENTS.map((agent) => (
                      <tr key={agent.id}>
                        <td>
                          <span className="idm" style={{ '--c': agent.color } as React.CSSProperties}>
                            <i />
                            {agent.id}
                          </span>
                        </td>
                        <td className="num">
                          <Hist pattern={agent.hist} label="last 12 run outcomes" />
                        </td>
                        <td className="num dim">{agent.runs}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
