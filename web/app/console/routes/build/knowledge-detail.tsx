import { useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  ConsoleButton,
  FilterChip,
  IconReplay,
  IconSearch,
  StatTile,
  StatTileGrid,
  StatusChip,
  TaskProgress,
  WorkbenchPanel,
  type ConsoleStatus,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

type KdTab = 'documents' | 'chunks' | 'testing' | 'usages' | 'analytics' | 'settings'

const MOCK_DOCS = [
  { path: '/guides/getting-started.md', status: 'pass' as ConsoleStatus, label: 'INDEXED', chunks: '24', tokens: '11,204', updated: '8h ago', action: 'recrawl' },
  { path: '/reference/api/runs.md', status: 'pass' as ConsoleStatus, label: 'INDEXED', chunks: '61', tokens: '28,911', updated: '8h ago', action: 'recrawl' },
  { path: '/reference/policy-bundles.md', status: 'pass' as ConsoleStatus, label: 'INDEXED', chunks: '38', tokens: '17,530', updated: '8h ago', action: 'recrawl' },
  { path: '/changelog/2026-08.md', status: 'running' as ConsoleStatus, label: 'PENDING', chunks: '—', tokens: '—', updated: 'queued', action: null },
  { path: '/legacy/diagram-v0.pdf', status: 'failed' as ConsoleStatus, label: 'FAILED', chunks: '0', tokens: '0', updated: '8h ago', action: 'ocr' },
  { path: '/guides/deploy/helm.md', status: 'pass' as ConsoleStatus, label: 'INDEXED', chunks: '42', tokens: '19,884', updated: '8h ago', action: 'recrawl' },
]

const MOCK_CHUNKS = [
  { id: 'ck_4a91#12', doc: '/guides/getting-started.md', preview: 'Every run starts with a policy evaluation. The bundle active at trigger time decides which tools…', tokens: '486', status: 'pass' as ConsoleStatus, label: 'EMBEDDED' },
  { id: 'ck_4a91#13', doc: '/guides/getting-started.md', preview: 'Secrets are referenced as vault:name and resolved at call time; plaintext never enters the model…', tokens: '502', status: 'pass' as ConsoleStatus, label: 'EMBEDDED' },
  { id: 'ck_7c02#04', doc: '/reference/api/runs.md', preview: 'GET /api/v1/runs/{id}/evidence returns the machine-readable evidence matrix including gate…', tokens: '511', status: 'pass' as ConsoleStatus, label: 'EMBEDDED' },
  { id: 'ck_7c02#05', doc: '/reference/api/runs.md', preview: 'Replay executes the recorded step ledger against a policy bundle without re-calling external…', tokens: '478', status: 'running' as ConsoleStatus, label: 'RE-EMBEDDING' },
  { id: 'ck_b310#01', doc: '/reference/policy-bundles.md', preview: 'A bundle ships like code: draft, staged rollout on a percentage of runs, then active. Promotion…', tokens: '495', status: 'pass' as ConsoleStatus, label: 'EMBEDDED' },
]

const MOCK_RESULTS = [
  { score: 92, chunk: 'ck_4a91#13', doc: '/guides/getting-started.md', latency: '88ms', bold: 'Secrets are referenced as vault:name and resolved at call time', rest: '; rotating a value re-binds every referencing agent automatically — no config change, no restart. Plaintext never enters model context…' },
  { score: 81, chunk: 'ck_9d20#07', doc: '/guides/deploy/helm.md', latency: null, bold: null, rest: 'The rotation hook notifies bound consumers through the governance event feed; agents pick up the new version on their next secret.resolve span…' },
  { score: 64, chunk: 'ck_b310#01', doc: '/reference/policy-bundles.md', latency: null, bold: null, rest: 'A bundle ships like code: draft, staged rollout, active. Secret-boundary checks are part of the evidence matrix on every run…' },
]

const MOCK_USAGES = [
  { id: 'support-triage', color: 'var(--cat-cyan)', kind: 'agent', queries: '1,822', hit: '93%', cited: '406', last: 'just now' },
  { id: 'ops-copilot', color: 'var(--cat-purple)', kind: 'agent', queries: '344', hit: '86%', cited: '102', last: '4m ago' },
  { id: 'release-notes', color: 'var(--cat-pink)', kind: 'agent', queries: '96', hit: '81%', cited: '18', last: '1h ago' },
  { id: 'docs-nightly-sync', color: 'var(--cat-teal)', kind: 'workflow', queries: '119', hit: '—', cited: '96', last: '8h ago' },
]

const MOCK_TOP_QUERIES = [
  { query: 'reset workspace api key', count: '212', score: '0.88', status: 'pass' as ConsoleStatus, label: 'HIT' },
  { query: 'rotate secret without downtime', count: '147', score: '0.90', status: 'pass' as ConsoleStatus, label: 'HIT' },
  { query: 'export evidence bundle for audit', count: '98', score: '0.79', status: 'pass' as ConsoleStatus, label: 'HIT' },
  { query: 'pricing for enterprise tier', count: '64', score: '0.31', status: 'info' as ConsoleStatus, label: 'ZERO-HIT' },
  { query: 'sso scim provisioning steps', count: '41', score: '0.28', status: 'info' as ConsoleStatus, label: 'ZERO-HIT' },
]

// BACKEND-PENDING: knowledge-service detail (query endpoint powers testing).
export default function ConsoleKnowledgeDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<KdTab>('documents')
  const name = id || 'product-docs'

  return (
    <>
      <Backlink to="/v2/build/knowledge">{t('console.knowDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <StatusChip status="pass" label="SYNCED" />
        <span className="chip">
          <i style={{ background: 'var(--cat-blue)' }} />
          web crawl
        </span>
        <span className="spacer" />
        <ConsoleButton>
          <IconReplay />
          {t('console.knowDetail.syncNow')}
        </ConsoleButton>
        <ConsoleButton variant="primary">{t('console.knowDetail.addDocs')}</ConsoleButton>
      </div>

      <div className="rd-meta">
        <span>Source<b>https://docs.acme.io · depth 3</b></span>
        <span>Embedding<b>bge-m3 · self-hosted</b></span>
        <span>Chunking<b>auto · 512 tok / 64 overlap</b></span>
        <span>Sync<b>nightly 02:00Z</b></span>
        <span>
          Last sync
          <b>
            8h ago ·{' '}
            <a
              className="runid"
              href="/v2/observe/runs/run_01J9KCXK3B"
              onClick={(event) => {
                event.preventDefault()
                navigate('/v2/observe/runs/run_01J9KCXK3B')
              }}
            >
              run_01J9KCXK3B
            </a>
          </b>
        </span>
        <span>Bound to<b>3 agents · 1 workflow</b></span>
      </div>

      <div className="tabs">
        {(
          [
            ['documents', t('console.knowDetail.tabs.documents'), '1,204'],
            ['chunks', t('console.knowDetail.tabs.chunks'), '18,392'],
            ['testing', t('console.knowDetail.tabs.testing'), null],
            ['usages', t('console.knowDetail.tabs.usages'), '4'],
            ['analytics', t('console.knowDetail.tabs.analytics'), null],
            ['settings', t('console.knowDetail.tabs.settings'), null],
          ] as const
        ).map(([value, label, count]) => (
          <button key={value} type="button" className={cn(tab === value && 'on')} onClick={() => setTab(value)}>
            {label}
            {count && <span className="mono">{count}</span>}
          </button>
        ))}
      </div>

      {tab === 'documents' && (
        <WorkbenchPanel
          title={t('console.knowDetail.tabs.documents')}
          hint={t('console.knowDetail.documentsHint')}
          actions={
            <div className="fsearch" style={{ maxWidth: 240, height: 26 }}>
              <IconSearch size={12} style={{ color: 'var(--faint)' }} />
              <input placeholder={t('console.knowDetail.filterDocs')} />
            </div>
          }
        >
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.document')}</th>
                <th>{t('console.knowDetail.columns.status')}</th>
                <th className="num">{t('console.knowDetail.columns.chunks')}</th>
                <th className="num">{t('console.knowDetail.columns.tokens')}</th>
                <th className="num">{t('console.knowDetail.columns.updated')}</th>
                <th className="num" />
              </tr>
            </thead>
            <tbody>
              {MOCK_DOCS.map((doc) => (
                <tr key={doc.path} className="rowlink">
                  <td>
                    <span className="mono">{doc.path}</span>
                  </td>
                  <td>
                    <StatusChip status={doc.status} label={doc.label} />
                  </td>
                  <td className="num dim">{doc.chunks}</td>
                  <td className="num dim">{doc.tokens}</td>
                  <td className="num dimmer">{doc.updated}</td>
                  <td className="num">
                    {doc.action === 'recrawl' && (
                      <ConsoleButton variant="ghost" size="sm">
                        {t('console.knowDetail.recrawl')}
                      </ConsoleButton>
                    )}
                    {doc.action === 'ocr' && (
                      <ConsoleButton size="sm">{t('console.knowledge.reprocess')}</ConsoleButton>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.docsPager')}</span>
            <span className="spacer" />
            <ConsoleButton size="sm" disabled>
              {t('console.runs.prev')}
            </ConsoleButton>
            <ConsoleButton size="sm">{t('console.runs.next')}</ConsoleButton>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'chunks' && (
        <WorkbenchPanel title={t('console.knowDetail.chunksTitle')} hint={t('console.knowDetail.chunksHint')}>
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.chunk')}</th>
                <th>{t('console.knowDetail.columns.document')}</th>
                <th>{t('console.knowDetail.columns.preview')}</th>
                <th className="num">{t('console.knowDetail.columns.tokens')}</th>
                <th>{t('console.knowDetail.columns.embedding')}</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_CHUNKS.map((chunk) => (
                <tr key={chunk.id} className="rowlink">
                  <td>
                    <span className="mono">{chunk.id}</span>
                  </td>
                  <td className="mono dim">{chunk.doc}</td>
                  <td className="dim" style={{ maxWidth: 340, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {chunk.preview}
                  </td>
                  <td className="num dim">{chunk.tokens}</td>
                  <td>
                    <StatusChip status={chunk.status} label={chunk.label} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.chunksNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'testing' && (
        <WorkbenchPanel title={t('console.knowDetail.testingTitle')} hint={t('console.knowDetail.testingHint')}>
          <div style={{ display: 'flex', gap: 8, padding: '12px 14px', borderBottom: '1px solid var(--border)' }}>
            <div className="fsearch" style={{ maxWidth: 'none', flex: 1, height: 30 }}>
              <IconSearch size={12} style={{ color: 'var(--faint)' }} />
              <input defaultValue="how do I rotate a secret without breaking bound agents?" />
            </div>
            <FilterChip>top_k: 5</FilterChip>
            <FilterChip>rerank: on</FilterChip>
            <ConsoleButton variant="primary" style={{ height: 28 }}>
              {t('console.knowDetail.runQuery')}
            </ConsoleButton>
          </div>
          {MOCK_RESULTS.map((result) => (
            <div key={result.chunk} className="tres">
              <div className="tres-h">
                <TaskProgress pct={result.score} label={(result.score / 100).toFixed(2)} />
                <span className="mono">{result.chunk}</span>
                <span className="mono">{result.doc}</span>
                <span className="spacer" style={{ flex: 1 }} />
                {result.latency && (
                  <span className="mono" style={{ fontSize: 10, color: 'var(--faint)' }}>
                    {result.latency}
                  </span>
                )}
              </div>
              <p>
                {result.bold && <b>{result.bold}</b>}
                {result.rest}
              </p>
            </div>
          ))}
          <div className="pager">
            <span>{t('console.knowDetail.testingNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'usages' && (
        <WorkbenchPanel>
          <table>
            <thead>
              <tr>
                <th>{t('console.knowDetail.columns.consumer')}</th>
                <th>{t('console.knowDetail.columns.kind')}</th>
                <th className="num">{t('console.knowDetail.columns.queries')}</th>
                <th className="num">{t('console.knowDetail.columns.hitRate')}</th>
                <th className="num">{t('console.knowDetail.columns.cited')}</th>
                <th className="num">{t('console.knowDetail.columns.lastQuery')}</th>
              </tr>
            </thead>
            <tbody>
              {MOCK_USAGES.map((usage) => (
                <tr key={usage.id} className="rowlink">
                  <td>
                    <span className="idm" style={{ '--c': usage.color } as React.CSSProperties}>
                      <i />
                      {usage.id}
                    </span>
                  </td>
                  <td className="dim">{usage.kind}</td>
                  <td className="num dim">{usage.queries}</td>
                  <td className="num dim">{usage.hit}</td>
                  <td className="num dim">{usage.cited}</td>
                  <td className="num dimmer">{usage.last}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pager">
            <span>{t('console.knowDetail.usagesNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'analytics' && (
        <>
          <StatTileGrid>
            <StatTile label="Queries · 24h" value="2,381" delta={{ direction: 'up', label: '+11.4%' }} sub="vs prev 24h" />
            <StatTile label="Hit rate" value="91%" sub={<span className="mono dimmer">score ≥ 0.6 threshold</span>} />
            <StatTile label="P95 retrieval" value="212ms" sub={<span className="mono dimmer">embed 41 · search 96 · rerank 75</span>} />
            <StatTile label="Zero-hit queries" value="7.1%" sub={<span className="mono dimmer">169 queries · gap candidates</span>} />
          </StatTileGrid>
          <WorkbenchPanel title={t('console.knowDetail.topQueries')} hint={t('console.knowDetail.topQueriesHint')}>
            <table>
              <thead>
                <tr>
                  <th>{t('console.knowDetail.columns.query')}</th>
                  <th className="num">{t('console.knowDetail.columns.count')}</th>
                  <th className="num">{t('console.knowDetail.columns.avgScore')}</th>
                  <th>{t('console.knowDetail.columns.outcome')}</th>
                </tr>
              </thead>
              <tbody>
                {MOCK_TOP_QUERIES.map((row) => (
                  <tr key={row.query}>
                    <td className="dim">{row.query}</td>
                    <td className="num dim">{row.count}</td>
                    <td className="num dim">{row.score}</td>
                    <td>
                      <StatusChip status={row.status} label={row.label} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </WorkbenchPanel>
        </>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel title={t('console.knowDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.knowDetail.fields.name')}</label>
            <input className="input" defaultValue={name} />
          </div>
          <div className="frow">
            <label>
              {t('console.knowDetail.fields.source')}
              <small>{t('console.knowDetail.fields.sourceHint')}</small>
            </label>
            <input className="input" defaultValue="https://docs.acme.io" style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }} />
          </div>
          <div className="frow">
            <label>{t('console.knowDetail.fields.schedule')}</label>
            <select className="input" defaultValue="nightly 02:00Z">
              <option>nightly 02:00Z</option>
              <option>hourly</option>
              <option>manual only</option>
            </select>
          </div>
          <div className="frow">
            <label>
              {t('console.knowDetail.fields.chunking')}
              <small>{t('console.knowDetail.fields.chunkingHint')}</small>
            </label>
            <select className="input" defaultValue="auto · 512 tokens, 64 overlap">
              <option>auto · 512 tokens, 64 overlap</option>
              <option>auto · 1024 tokens</option>
              <option>by heading</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.knowDetail.fields.embedding')}</label>
            <select className="input" defaultValue="bge-m3 · vllm self-hosted">
              <option>bge-m3 · vllm self-hosted</option>
              <option>voyage-3</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.knowDetail.fields.threshold')}</label>
            <input className="input" defaultValue="score ≥ 0.60" style={{ maxWidth: 140 }} />
          </div>
          <div className="frow">
            <label style={{ color: 'var(--danger-foreground)' }}>
              {t('console.knowDetail.fields.del')}
              <small>{t('console.knowDetail.fields.delHint')}</small>
            </label>
            <div>
              <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                {t('console.knowDetail.fields.delBtn')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}
    </>
  )
}
