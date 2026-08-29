import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  ConsoleButton,
  IconExport,
  KeyValueList,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

type AgentTab = 'build' | 'monitor' | 'publish' | 'settings'

// Mock editor state mirroring the prototype sample (support-triage draft).
// BACKEND-PENDING: agent-service versions/releases/publish/rollback exist.
const MOCK_PROMPT = `You triage inbound helpdesk tickets for Acme Robotics.

- Classify each ticket into a queue from ticket_class.json and set priority.
- Draft a reply grounded ONLY in cited knowledge chunks; never invent policy.
- Escalate to a human when confidence < 0.8 or the ticket mentions billing disputes.
- You cannot contact systems outside your tool grants — do not promise actions you cannot take.`

const MOCK_RECENT_RUNS = [
  { id: 'run_01J9KD84QF', trigger: 'webhook', observed: '4 st · 2 tool · 1 cit · 1 aud', policy: '2/2 gates', duration: '3.1s', cost: '$0.021', status: 'running' as const, label: 'RUNNING', started: '13:47:10Z' },
  { id: 'run_01J9KD5PWB', trigger: 'webhook', observed: '6 st · 2 tool · 1 cit · 1 aud', policy: '2/2 gates', duration: '4.4s', cost: '$0.017', status: 'pass' as const, label: 'PASS', started: '13:33:44Z' },
  { id: 'run_01J9KD1T4H', trigger: 'webhook', observed: '6 st · 2 tool · 1 cit · 1 aud', policy: '2/2 gates', duration: '3.8s', cost: '$0.015', status: 'pass' as const, label: 'PASS', started: '12:58:03Z' },
]

const MOCK_HIST: ('ok' | 'd' | 'f')[] = ['ok', 'ok', 'ok', 'd', 'ok', 'ok', 'ok', 'ok', 'f', 'ok', 'ok', 'ok']

export default function ConsoleAgentDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AgentTab>('build')
  const name = id && id !== 'new' ? id : 'support-triage'

  return (
    <>
      <Backlink to="/v2/build/agents">{t('console.agentDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <span className="chip">
          <i style={{ background: 'var(--primary)' }} />
          v12 published
        </span>
        <StatusChip status="warn" label="DRAFT CHANGES" />
        <span className="spacer" />
        <ConsoleButton>{t('console.agentDetail.saveDraft')}</ConsoleButton>
        <ConsoleButton>{t('console.agentDetail.runTest')}</ConsoleButton>
        <ConsoleButton variant="primary">
          <IconExport />
          {t('console.agentDetail.publish')}
        </ConsoleButton>
      </div>

      <div className="tabs">
        {(
          [
            ['build', t('console.agentDetail.tabs.build'), null],
            ['monitor', t('console.agentDetail.tabs.monitor'), '24h'],
            ['publish', t('console.agentDetail.tabs.publish'), null],
            ['settings', t('console.agentDetail.tabs.settings'), null],
          ] as const
        ).map(([value, label, count]) => (
          <button key={value} type="button" className={cn(tab === value && 'on')} onClick={() => setTab(value)}>
            {label}
            {count && <span className="mono">{count}</span>}
          </button>
        ))}
      </div>

      {tab === 'build' && (
        <div className="rdgrid">
          <div className="stack">
            <WorkbenchPanel title={t('console.agentDetail.definition')}>
              <div className="frow">
                <label>{t('console.agentDetail.fields.name')}</label>
                <input className="input" defaultValue={name} />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.description')}</label>
                <input className="input" defaultValue="Classifies inbound tickets, drafts replies, escalates on low confidence." />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.trigger')}</label>
                <select className="input" style={{ maxWidth: 220 }} defaultValue="webhook">
                  <option>webhook</option>
                  <option>chat</option>
                  <option>schedule</option>
                  <option>api</option>
                </select>
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.model')}</label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  <select className="input" style={{ maxWidth: 220 }} defaultValue="claude-sonnet-5">
                    <option>claude-sonnet-5</option>
                    <option>claude-haiku-4.5</option>
                    <option>qwen3-235b</option>
                  </select>
                  <input className="input" defaultValue="temp 0.2" style={{ maxWidth: 90 }} title="temperature" />
                  <input className="input" defaultValue="max 4,096 tok" style={{ maxWidth: 120 }} title="max output tokens" />
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.fields.systemPrompt')}
                  <small>{t('console.agentDetail.fields.systemPromptHint')}</small>
                </label>
                <textarea className="input" style={{ minHeight: 120 }} defaultValue={MOCK_PROMPT} />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.outputSchema')}</label>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  <span className="chip">ticket_class.json</span>
                  <ConsoleButton variant="ghost" size="sm">
                    {t('console.agentDetail.fields.editSchema')}
                  </ConsoleButton>
                </div>
              </div>
            </WorkbenchPanel>

            <WorkbenchPanel title={t('console.agentDetail.capabilities')} hint={t('console.agentDetail.capabilitiesHint')}>
              <div className="frow">
                <label>{t('console.agentDetail.toolGrants')}</label>
                <div className="checks">
                  <label>
                    <input type="checkbox" defaultChecked />
                    <span className="mono">g_45</span> tickets.read / tickets.write · helpdesk-api
                  </label>
                  <label>
                    <input type="checkbox" defaultChecked />
                    <span className="mono">web-fetch</span> net.egress · allowlist only
                  </label>
                  <label>
                    <input type="checkbox" />
                    <span className="mono">g_44</span> k8s.* on ns/staging
                  </label>
                  <label>
                    <input type="checkbox" />
                    <span className="mono">g_51</span> finance.journal.post · <span className="risk hi">HIGH</span> requires human approval
                  </label>
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.skills')}
                  <small>{t('console.agentDetail.skillsHint')}</small>
                </label>
                <div className="checks">
                  <label>
                    <input type="checkbox" defaultChecked />
                    <span className="mono">incident-writeup</span> v1.2.0 · postmortem structure
                  </label>
                  <label>
                    <input type="checkbox" />
                    <span className="mono">runbook-triage</span> v0.4.1 · uses k8s.read via k8s-toolkit
                  </label>
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.knowledge')}
                  <small>{t('console.agentDetail.knowledgeHint')}</small>
                </label>
                <div className="checks">
                  <label>
                    <input type="checkbox" defaultChecked />
                    product-docs <span className="mono dimmer">91% hit rate</span>
                  </label>
                  <label>
                    <input type="checkbox" defaultChecked />
                    support-macros
                  </label>
                  <label>
                    <input type="checkbox" />
                    runbooks
                  </label>
                </div>
              </div>
            </WorkbenchPanel>
          </div>

          <div className="rail">
            <WorkbenchPanel title={t('console.agentDetail.governance')}>
              <KeyValueList
                items={[
                  { key: 'Policy bundle', value: 'workspace default' },
                  { key: 'Gates that apply', value: 'intent-screen · tool-permission' },
                  { key: 'Publish review', value: 'not required · no scope change' },
                  { key: 'Secrets', value: 'by reference only' },
                ]}
              />
            </WorkbenchPanel>
            <WorkbenchPanel title={t('console.agentDetail.budget')}>
              <div className="frow" style={{ gridTemplateColumns: '1fr', gap: 5 }}>
                <label>{t('console.agentDetail.dailyCap')}</label>
                <input className="input" defaultValue="$12.00" style={{ maxWidth: 120 }} />
              </div>
              <div className="frow" style={{ gridTemplateColumns: '1fr', gap: 5 }}>
                <label>{t('console.agentDetail.alertAt')}</label>
                <select className="input" style={{ maxWidth: 120 }} defaultValue="80%">
                  <option>80%</option>
                  <option>50%</option>
                </select>
              </div>
            </WorkbenchPanel>
            <WorkbenchPanel title={t('console.agentDetail.testTitle')}>
              <div style={{ padding: '12px 14px' }}>
                <p className="dim" style={{ fontSize: 11.5, marginBottom: 9 }}>
                  {t('console.agentDetail.testNote')}
                </p>
                <ConsoleButton style={{ width: '100%', justifyContent: 'center' }}>
                  {t('console.agentDetail.runTest')}
                </ConsoleButton>
              </div>
            </WorkbenchPanel>
          </div>
        </div>
      )}

      {tab === 'monitor' && (
        <>
          <StatTileGrid>
            <StatTile label="Runs · 24h" value="412" delta={{ direction: 'up', label: '+8.6%' }} sub="vs prev 24h" />
            <StatTile label="Pass rate" value="98.3%" sub={<span className="mono dimmer">405 pass · 5 degraded · 2 blocked</span>} />
            <StatTile label="Spend · 24h" value="$11.20" sub={<span className="mono dimmer">cap $12.00/day · 93%</span>} />
            <StatTile label="P95 duration" value="4.9s" sub={<span className="mono dimmer">p50 2.1s</span>} />
          </StatTileGrid>
          <WorkbenchPanel
            title={t('console.agentDetail.monitorRecent')}
            actions={
              <a
                className="more"
                href="/v2/observe/runs"
                onClick={(event) => {
                  event.preventDefault()
                  navigate('/v2/observe/runs')
                }}
              >
                {t('console.agentDetail.allRuns')}
              </a>
            }
          >
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Trigger</th>
                  <th>Observed</th>
                  <th>Policy</th>
                  <th className="num">Duration</th>
                  <th className="num">Cost</th>
                  <th>Status</th>
                  <th className="num">Started</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_RECENT_RUNS.map((run) => (
                  <tr key={run.id} className="rowlink" onClick={() => navigate(`/v2/observe/runs/${run.id}`)}>
                    <td>
                      <span className="runid">{run.id}</span>
                    </td>
                    <td className="dim">{run.trigger}</td>
                    <td>
                      <span className="mono dimmer" style={{ fontSize: 10.5 }}>
                        {run.observed}
                      </span>
                    </td>
                    <td>
                      <span className="mono dimmer">{run.policy}</span>
                    </td>
                    <td className="num dim">{run.duration}</td>
                    <td className="num dim">{run.cost}</td>
                    <td>
                      <StatusChip status={run.status} label={run.label} />
                    </td>
                    <td className="num dimmer">{run.started}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.agentDetail.lastOutcomes')}</span>
              <span className="hist" style={{ marginLeft: 10 }} aria-label={t('console.agentDetail.lastOutcomes')}>
                {MOCK_HIST.map((outcome, index) => (
                  <i key={index} className={outcome === 'ok' ? undefined : outcome} />
                ))}
              </span>
              <span className="spacer" />
              <span>{t('console.agentDetail.monitorNote')}</span>
            </div>
          </WorkbenchPanel>
        </>
      )}

      {tab === 'publish' && (
        <WorkbenchPanel title={t('console.agentDetail.versions')} hint={t('console.agentDetail.versionsHint')}>
          <a className="bundle">
            <b>
              v13 <StatusChip status="warn" label="DRAFT" />
            </b>
            <small>current editor state · validation ✓ · adds web-fetch scope → publish review required</small>
          </a>
          <a className="bundle on">
            <b>
              v12 <StatusChip status="pass" label="PUBLISHED" />
            </b>
            <small>production since 2026-08-26 · 412 runs · 24h · 98.3% pass</small>
          </a>
          <a className="bundle">
            <b>
              v11 <StatusChip status="info" label="ARCHIVED" />
            </b>
            <small>rollback target · one-click revert</small>
          </a>
          <CodeBlock
            style={{ borderRadius: '0 0 10px 10px' }}
            command="soit agent publish support-triage@v13"
            output="scope change detected (adds net.egress) → queued for publish review · see Agents › Publish review"
          />
        </WorkbenchPanel>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel title={t('console.agentDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.owner')}</label>
            <input className="input" defaultValue="Wei" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>
              {t('console.agentDetail.settingsFields.channel')}
              <small>{t('console.agentDetail.settingsFields.channelHint')}</small>
            </label>
            <select className="input" style={{ maxWidth: 240 }} defaultValue="production">
              <option>production</option>
              <option>draft only</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.rateLimit')}</label>
            <input className="input" defaultValue="60 runs / hour" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.retry')}</label>
            <input className="input" defaultValue="2× · backoff 2ⁿ min" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.timeout')}</label>
            <input className="input" defaultValue="120s per run" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.onFailure')}</label>
            <input className="input" defaultValue="notify #support-oncall" style={{ maxWidth: 260 }} />
          </div>
          <div className="frow">
            <label style={{ color: 'var(--danger-foreground)' }}>
              {t('console.agentDetail.settingsFields.danger')}
              <small>{t('console.agentDetail.settingsFields.dangerHint')}</small>
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <ConsoleButton>{t('console.agentDetail.settingsFields.pause')}</ConsoleButton>
              <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                {t('console.agentDetail.settingsFields.archive')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}
    </>
  )
}
