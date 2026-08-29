import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  ConsoleButton,
  IconExport,
  StatusChip,
  WorkbenchPanel,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

type WfTab = 'build' | 'monitor' | 'publish' | 'settings'

const PALETTE = [
  { name: 'Trigger', color: 'var(--cat-amber)' },
  { name: 'Policy gate', color: 'var(--cat-pink)' },
  { name: 'Model call', color: 'var(--cat-blue)' },
  { name: 'Tool call', color: 'var(--cat-cyan)' },
  { name: 'Branch', color: 'var(--cat-indigo)' },
  { name: 'Human approval', color: 'var(--cat-purple)' },
  { name: 'Artifact', color: 'var(--cat-teal)' },
  { name: 'Subflow', color: 'var(--cat-slate)' },
]

// Static canvas mirroring the prototype ticket-escalation draft.
// BACKEND-PENDING: the interactive canvas migrates from the legacy
// routes/workflow/detail/build.tsx in the wiring pass; this mock keeps the
// shell, tabs and inspector shapes in place.
const NODES = [
  { id: 'trigger', kind: 'trigger', color: 'var(--cat-amber)', name: 'ticket.created', note: 'webhook · helpdesk', left: 16, top: 214, ports: ['out'] },
  { id: 'gate', kind: 'policy·gate', color: 'var(--cat-pink)', name: 'intent-screen', note: 'ops.intents.allowed', left: 208, top: 214, ports: ['in', 'out'] },
  { id: 'classify', kind: 'model·call', color: 'var(--cat-blue)', name: 'classify', note: 'claude-sonnet-5 · ticket_class.json', left: 400, top: 214, ports: ['in', 'out'], selected: true },
  { id: 'branch', kind: 'branch', color: 'var(--cat-indigo)', name: 'confidence', note: 'on classify.confidence', left: 592, top: 214, ports: ['in', 'out'] },
  { id: 'route', kind: 'tool·call', color: 'var(--cat-cyan)', name: 'helpdesk.route', note: 'assign queue + priority', left: 784, top: 110, ports: ['in', 'out'] },
  { id: 'notify', kind: 'tool·call', color: 'var(--cat-cyan)', name: 'slack.notify', note: '#support-oncall', left: 976, top: 110, ports: ['in'] },
  { id: 'review', kind: 'approval', color: 'var(--cat-purple)', name: 'human-review', note: 'low confidence → L2 queue', left: 784, top: 330, ports: ['in', 'out'] },
  { id: 'report', kind: 'artifact', color: 'var(--cat-teal)', name: 'triage-report', note: 'markdown · retained 90d', left: 976, top: 330, ports: ['in'] },
]

const EDGES = [
  { d: 'M176 246 C 192 246 192 246 208 246' },
  { d: 'M368 246 C 384 246 384 246 400 246', hot: true },
  { d: 'M560 246 C 576 246 576 246 592 246' },
  { d: 'M752 246 C 770 246 766 142 784 142' },
  { d: 'M752 246 C 770 246 766 362 784 362' },
  { d: 'M944 142 C 960 142 960 142 976 142' },
  { d: 'M944 362 C 960 362 960 362 976 362' },
]

const MONITOR_RUNS = [
  { id: 'run_01J9KD1T4H', trigger: 'webhook', steps: '6', policy: '2/2 gates', warn: false, duration: '3.8s', cost: '$0.015', status: 'pass' as const, label: 'PASS', started: '12:58:03Z' },
  { id: 'run_01J9KCV8N3', trigger: 'webhook', steps: '6', policy: '2/2 gates', warn: false, duration: '4.0s', cost: '$0.016', status: 'pass' as const, label: 'PASS', started: '11:44:56Z' },
  { id: 'run_01J9KCP2W8', trigger: 'webhook', steps: '8', policy: '2/2 · retry', warn: true, duration: '11.3s', cost: '$0.041', status: 'warn' as const, label: 'DEGRADED', started: '10:12:40Z' },
]

export default function ConsoleWorkflowDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<WfTab>('build')
  const [selectedNode, setSelectedNode] = useState('classify')
  const name = id && id !== 'new-draft' ? id : 'ticket-escalation'

  return (
    <>
      <Backlink to="/v2/build/workflows">{t('console.wfDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <span className="chip">
          <i style={{ background: 'var(--primary)' }} />
          v14 published
        </span>
        <StatusChip status="warn" label="DRAFT CHANGES" />
        <span className="spacer" />
        <ConsoleButton>{t('console.wfDetail.validate')}</ConsoleButton>
        <ConsoleButton variant="primary">
          <IconExport />
          {t('console.wfDetail.publish')}
        </ConsoleButton>
      </div>

      <div className="tabs">
        {(
          [
            ['build', t('console.wfDetail.tabs.build'), null],
            ['monitor', t('console.wfDetail.tabs.monitor'), '7d'],
            ['publish', t('console.wfDetail.tabs.publish'), null],
            ['settings', t('console.wfDetail.tabs.settings'), null],
          ] as const
        ).map(([value, label, count]) => (
          <button key={value} type="button" className={cn(tab === value && 'on')} onClick={() => setTab(value)}>
            {label}
            {count && <span className="mono">{count}</span>}
          </button>
        ))}
      </div>

      {tab === 'build' && (
        <>
          <div className="warnbar">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 3 2 21h20L12 3ZM12 10v5M12 18.5v.5" />
            </svg>
            <span>
              {t('console.wfDetail.warnbarPrefix')} <span className="mono">set_var_1</span>{' '}
              {t('console.wfDetail.warnbar')} <span className="mono">variable-assign@v2</span>{' '}
              {t('console.wfDetail.warnbarSuffix')}
            </span>
            <ConsoleButton>{t('console.wfDetail.migrate')}</ConsoleButton>
          </div>
          <div className="wfshell">
            <div className="panel palette">
              <div className="pcap">{t('console.wfDetail.nodesCap')}</div>
              {PALETTE.map((item) => (
                <div key={item.name} className="pitem" style={{ '--c': item.color } as React.CSSProperties}>
                  <i />
                  {item.name}
                </div>
              ))}
              <div className="phint">{t('console.wfDetail.paletteHint')}</div>
            </div>

            <div className="canvas-wrap">
              <div className="canvas">
                <svg className="edges" width="1160" height="520" viewBox="0 0 1160 520">
                  {EDGES.map((edge, index) => (
                    <path key={index} className={edge.hot ? 'hot' : undefined} d={edge.d} />
                  ))}
                  <text x="756" y="186">≥ 0.80</text>
                  <text x="756" y="326">&lt; 0.80</text>
                </svg>
                {NODES.map((node) => (
                  <div
                    key={node.id}
                    className={cn('node', selectedNode === node.id && 'sel')}
                    style={{ left: node.left, top: node.top }}
                    onClick={() => setSelectedNode(node.id)}
                  >
                    <span className="nk" style={{ '--c': node.color } as React.CSSProperties}>
                      <i />
                      {node.kind}
                    </span>
                    <b>{node.name}</b>
                    <small>{node.note}</small>
                    {node.ports.includes('in') && <span className="port in" />}
                    {node.ports.includes('out') && <span className="port out" />}
                  </div>
                ))}
              </div>
              <div className="canvas-tools">
                <button type="button" title="Zoom out">−</button>
                <button type="button" title="Zoom level">100%</button>
                <button type="button" title="Zoom in">+</button>
                <button type="button" title="Fit view">fit</button>
                <button type="button" title="Auto layout">auto</button>
              </div>
            </div>

            <div className="panel inspector">
              <div className="panel-head">
                <h2>classify</h2>
                <span className="hint">model·call</span>
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.fields.name')}</label>
                <input className="input" defaultValue="classify" />
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.fields.model')}</label>
                <select className="input" defaultValue="claude-sonnet-5">
                  <option>claude-sonnet-5</option>
                  <option>claude-haiku-4.5</option>
                  <option>qwen3-235b</option>
                </select>
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.fields.prompt')}</label>
                <textarea
                  className="input"
                  defaultValue="Classify the ticket into one of the queues in ticket_class.json. Return confidence 0–1. Cite the fields you used."
                />
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.fields.temperature')}</label>
                <input className="input" defaultValue="0.2" style={{ maxWidth: 90 }} />
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.fields.outputSchema')}</label>
                <div>
                  <span className="chip">ticket_class.json</span>
                </div>
              </div>
              <div className="frow">
                <label>{t('console.wfDetail.inspectorGovernance')}</label>
                <div className="dim" style={{ fontSize: 11.5 }}>
                  {t('console.wfDetail.inspectorGovNote')} <span className="mono">v2026.08.27-2</span>.{' '}
                  {t('console.wfDetail.inspectorGovNote2')}
                </div>
              </div>
              <div className="frow">
                <label />
                <ConsoleButton style={{ color: 'var(--danger-foreground)', maxWidth: 120 }}>
                  {t('console.wfDetail.deleteNode')}
                </ConsoleButton>
              </div>
            </div>
          </div>
        </>
      )}

      {tab === 'monitor' && (
        <WorkbenchPanel
          title={t('console.wfDetail.monitorTitle')}
          actions={
            <a
              className="more"
              href="/v2/observe/runs"
              onClick={(event) => {
                event.preventDefault()
                navigate('/v2/observe/runs')
              }}
            >
              {t('console.wfDetail.allRuns')}
            </a>
          }
        >
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Trigger</th>
                <th className="num">Steps</th>
                <th>Policy</th>
                <th className="num">Duration</th>
                <th className="num">Cost</th>
                <th>Status</th>
                <th className="num">Started</th>
              </tr>
            </thead>
            <tbody>
              {MONITOR_RUNS.map((run) => (
                <tr key={run.id} className="rowlink" onClick={() => navigate(`/v2/observe/runs/${run.id}`)}>
                  <td>
                    <span className="runid">{run.id}</span>
                  </td>
                  <td className="dim">{run.trigger}</td>
                  <td className="num dim">{run.steps}</td>
                  <td>
                    <span className="mono" style={run.warn ? { color: 'var(--warning-foreground)' } : undefined}>
                      {run.warn ? run.policy : undefined}
                    </span>
                    {!run.warn && <span className="mono dimmer">{run.policy}</span>}
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
        </WorkbenchPanel>
      )}

      {tab === 'publish' && (
        <WorkbenchPanel title={t('console.wfDetail.versions')} hint={t('console.wfDetail.versionsHint')}>
          <a className="bundle">
            <b>
              v15 <StatusChip status="warn" label="DRAFT" />
            </b>
            <small>current canvas · validation ✓ 0 errors · 2 nodes changed vs v14</small>
          </a>
          <a className="bundle on">
            <b>
              v14 <StatusChip status="pass" label="PUBLISHED" />
            </b>
            <small>production since 2026-08-26 · 1,822 runs · 99.2% success</small>
          </a>
          <a className="bundle">
            <b>
              v13 <StatusChip status="info" label="ARCHIVED" />
            </b>
            <small>rollback target · one-click revert</small>
          </a>
          <CodeBlock
            style={{ borderRadius: '0 0 10px 10px' }}
            command="soit workflow publish ticket-escalation@v15"
            output="validating 8 nodes … ✓ · diff vs v14: ~2 nodes · runs switch on next trigger"
          />
        </WorkbenchPanel>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel title={t('console.wfDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.wfDetail.fields.name')}</label>
            <input className="input" defaultValue={name} />
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.description')}</label>
            <input className="input" defaultValue="triage → enrich → route → notify" />
          </div>
          <div className="frow">
            <label>
              {t('console.wfDetail.fields.trigger')}
              <small>{t('console.wfDetail.fields.triggerHint')}</small>
            </label>
            <select className="input" defaultValue="webhook · ticket.created">
              <option>webhook · ticket.created</option>
              <option>schedule</option>
              <option>manual</option>
              <option>api</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.concurrency')}</label>
            <input className="input" defaultValue="4 parallel runs max" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.retry')}</label>
            <input className="input" defaultValue="3× · backoff 2ⁿ min" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>
              {t('console.wfDetail.fields.bundle')}
              <small>{t('console.wfDetail.fields.bundleHint')}</small>
            </label>
            <select className="input" defaultValue="workspace default (v2026.08.27-2)">
              <option>workspace default (v2026.08.27-2)</option>
              <option>pin v2026.08.27-2</option>
            </select>
          </div>
          <div className="frow">
            <label style={{ color: 'var(--danger-foreground)' }}>
              {t('console.wfDetail.fields.archive')}
              <small>{t('console.wfDetail.fields.archiveHint')}</small>
            </label>
            <div>
              <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                {t('console.wfDetail.fields.archiveBtn')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}
    </>
  )
}
