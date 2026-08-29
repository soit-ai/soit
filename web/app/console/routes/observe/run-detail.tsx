import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  IconCopy,
  IconExport,
  IconReplay,
  KeyValueList,
  KindChip,
  StatusChip,
  WorkbenchPanel,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { toRunDetailView, formatDurationMs } from '../../adapters/run-detail'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { getRunDetail } from '@/services/run-service'

type RunTab = 'ledger' | 'policy' | 'events' | 'artifacts' | 'raw'

export default function ConsoleRunDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<RunTab>('ledger')

  const detailQuery = useQuery({
    queryKey: ['console', 'run-detail', id],
    queryFn: () =>
      getRunDetail(id as string, {
        include_steps: true,
        include_artifacts: true,
        include_cost: true,
      }),
    options: { enabled: Boolean(id), retry: false, refetchOnWindowFocus: false },
  })

  if (!detailQuery.data) {
    return (
      <>
        <Backlink to="/v2/observe/runs">{t('console.runDetail.back')}</Backlink>
        <div className="rd-head">
          <h1>{id}</h1>
        </div>
        <div className="panel">
          <div className="empty-note">
            {detailQuery.isError ? t('console.common.loadError') : t('console.common.loading')}
          </div>
        </div>
      </>
    )
  }

  const run = toRunDetailView(detailQuery.data)

  const copyId = () => {
    void navigator.clipboard?.writeText(run.id).catch(() => undefined)
  }

  return (
    <>
      <Backlink to="/v2/observe/runs">{t('console.runDetail.back')}</Backlink>

      <div className="rd-head">
        <h1>{run.id}</h1>
        <StatusChip status={run.verdict} />
        <button type="button" className="btn ghost" title={t('console.runDetail.copyId')} onClick={copyId}>
          <IconCopy />
        </button>
        <span className="spacer" />
        <button type="button" className="btn">
          <IconReplay />
          {t('console.runDetail.replay')}
        </button>
        <button type="button" className="btn">
          <IconExport />
          {t('console.runDetail.evidenceBundle')}
        </button>
      </div>

      <div className="rd-meta">
        <span>
          Agent
          <b>
            <KindChip kind={run.subject_kind} label={run.subject_id} className="idm" />
          </b>
        </span>
        {run.meta.map((item) => (
          <span key={item.key}>
            {item.key}
            <b>{item.value}</b>
          </span>
        ))}
      </div>

      <div className="tabs">
        <button type="button" className={cn(tab === 'ledger' && 'on')} onClick={() => setTab('ledger')}>
          {t('console.runDetail.tabs.ledger')} <span className="mono">{run.tabs.ledger}</span>
        </button>
        <button type="button" className={cn(tab === 'policy' && 'on')} onClick={() => setTab('policy')}>
          {t('console.runDetail.tabs.policy')}{' '}
          <span className="mono">
            {t('console.runDetail.tabs.gatesChecks', { gates: run.tabs.gates, checks: run.tabs.checks })}
          </span>
        </button>
        <button type="button" className={cn(tab === 'events' && 'on')} onClick={() => setTab('events')}>
          {t('console.runDetail.tabs.events')} <span className="mono">{run.tabs.events}</span>
        </button>
        <button type="button" className={cn(tab === 'artifacts' && 'on')} onClick={() => setTab('artifacts')}>
          {t('console.runDetail.tabs.artifacts')} <span className="mono">{run.tabs.artifacts}</span>
        </button>
        <button type="button" className={cn(tab === 'raw' && 'on')} onClick={() => setTab('raw')}>
          {t('console.runDetail.tabs.raw')}
        </button>
      </div>

      <div className="rdgrid">
        <div>
          {tab === 'ledger' && (
            <WorkbenchPanel
              title={t('console.runDetail.stepLedger')}
              hint={t('console.runDetail.timelineHint', {
                duration: formatDurationMs(detailQuery.data.run.duration_ms),
              })}
            >
              <ul className="ledger">
                {run.ledger.map((step) => (
                  <li key={step.ix}>
                    <span className="ix">{step.ix}</span>
                    <span className="kind" style={{ '--c': step.kind_color } as React.CSSProperties}>
                      <i />
                      {step.kind}
                    </span>
                    <span className="what">
                      <b>{step.name}</b>
                      <small>{step.detail}</small>
                    </span>
                    <span className="wf">
                      <i style={{ '--c': step.kind_color, left: `${step.left}%`, width: `${step.width}%` } as React.CSSProperties} />
                    </span>
                    <span className="dur">{step.duration}</span>
                    <span className="st">
                      <StatusChip status={step.status} />
                    </span>
                  </li>
                ))}
              </ul>
              <CodeBlock command={run.ledger_code.command} output={run.ledger_code.output} />
            </WorkbenchPanel>
          )}

          {tab === 'policy' && (
            <WorkbenchPanel
              title={t('console.runDetail.policyEval')}
              hint={t('console.runDetail.evidenceCount', { count: run.evidence.length })}
            >
              {run.gates.map((gate) => (
                <div className="gate" key={gate.name}>
                  <div>
                    <span className="mono">{gate.name}</span>
                    <small>{gate.rule}</small>
                  </div>
                  <StatusChip status={gate.status} />
                </div>
              ))}

              <div className="panel-head" style={{ borderTop: '1px solid var(--border)' }}>
                <h2>{t('console.runDetail.evidenceMatrix')}</h2>
                <span className="hint">{t('console.runDetail.evidenceHint')}</span>
              </div>
              <div className="msummary">
                <StatusChip status="pass" label={`PASS ${run.evidence_summary.pass}`} />
                <StatusChip status="warn" label={`WARN ${run.evidence_summary.warn}`} />
                <StatusChip status="info" label={`N/A ${run.evidence_summary.na}`} />
              </div>
              <div className="matrix">
                {run.evidence.map((row) => (
                  <div className="mrow2" key={row.name}>
                    <span className="mname">{row.name}</span>
                    <span className="mdesc">
                      {row.description}
                      {row.refs && <span className="mrefs">{row.refs}</span>}
                      {row.refs_missing && (
                        <span className="mrefs">
                          <b>{row.refs_missing}</b>
                        </span>
                      )}
                    </span>
                    <StatusChip status={row.status} label={row.status === 'na' ? 'N/A' : undefined} />
                  </div>
                ))}
              </div>
              <CodeBlock>{run.policy_code}</CodeBlock>
            </WorkbenchPanel>
          )}

          {tab === 'events' && (
            <WorkbenchPanel
              title={t('console.runDetail.semanticTimeline')}
              hint={t('console.runDetail.semanticHint')}
            >
              <ul className="sem">
                {run.events.map((event) => (
                  <li key={event.ix}>
                    <span className="ix">{event.ix}</span>
                    <span className="etype">{event.type}</span>
                    <span className="ejson">{event.payload}</span>
                    <time>{event.at}</time>
                  </li>
                ))}
              </ul>
              <CodeBlock command={run.events_code.command} output={run.events_code.output} />
            </WorkbenchPanel>
          )}

          {tab === 'artifacts' && (
            <WorkbenchPanel
              title={t('console.runDetail.artifactsTitle')}
              hint={t('console.runDetail.artifactsHint')}
            >
              <table>
                <thead>
                  <tr>
                    <th>{t('console.runDetail.columns.name')}</th>
                    <th>{t('console.runDetail.columns.type')}</th>
                    <th>{t('console.runDetail.columns.digest')}</th>
                    <th className="num">{t('console.runDetail.columns.size')}</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {run.artifacts.map((artifact) => (
                    <tr key={artifact.name}>
                      <td className="mono">{artifact.name}</td>
                      <td className="dim">{artifact.type}</td>
                      <td className="mono dimmer">{artifact.digest}</td>
                      <td className="num dim">{artifact.size}</td>
                      <td className="num">
                        <button type="button" className="more">
                          {t('console.runDetail.download')}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </WorkbenchPanel>
          )}

          {tab === 'raw' && (
            <WorkbenchPanel title={t('console.runDetail.rawTitle')} hint={t('console.runDetail.rawHint')}>
              <CodeBlock style={{ borderTop: 'none', borderRadius: '0 0 10px 10px' }}>
                {run.raw}
              </CodeBlock>
            </WorkbenchPanel>
          )}
        </div>

        <div className="rail">
          <div className="panel verdict">
            <div className="verdict-row" style={{ justifyContent: 'space-between' }}>
              <h3>{t('console.runDetail.verdictTitle')}</h3>
              <span className="big">
                <i />
                {detailQuery.data.run.status.toUpperCase()}
              </span>
            </div>
            <p className="dim" style={{ marginTop: 8, fontSize: 12 }}>
              {run.verdict_note}
            </p>
          </div>

          <WorkbenchPanel title={t('console.runDetail.evidenceChain')}>
            <ul className="chain">
              {run.chain.map((item) => (
                <li key={item.title}>
                  <b>{item.title}</b>
                  <span>{item.detail}</span>
                </li>
              ))}
            </ul>
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.runDetail.costBreakdown')}>
            <KeyValueList items={run.cost_breakdown} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.runDetail.context')}>
            <ul className="kv">
              {run.context.map((item) => (
                <li key={item.key}>
                  <span className="k">{item.key}</span>
                  <span className={cn('v', item.link && 'link')}>
                    {'to' in item && item.to ? (
                      <a
                        className="runid"
                        onClick={(event) => {
                          event.preventDefault()
                          navigate(item.to as string)
                        }}
                        href={item.to as string}
                      >
                        {item.value}
                      </a>
                    ) : (
                      item.value
                    )}
                  </span>
                </li>
              ))}
            </ul>
          </WorkbenchPanel>
        </div>
      </div>
    </>
  )
}
