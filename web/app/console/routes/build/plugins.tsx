import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
  ConsoleToggle,
  FilterChip,
  FilterSearch,
  IconExport,
  IconPlus,
  Pager,
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
import { useTranslation } from '@/i18n'

type PlTab = 'installed' | 'market' | 'incidents' | 'recycle'
type PlFilter = 'all' | 'mcp' | 'tools' | 'skills' | 'disabled'

type PluginKind = 'mcp' | 'tools' | 'skills'
type RiskLevel = 'lo' | 'md' | 'hi'

interface MockPlugin {
  id: string
  color: string
  kind: PluginKind
  kind_label: string
  source: string
  version: string
  version_note?: string
  risk: RiskLevel
  risk_label: string
  scopes: string[]
  agents: string
  calls: string
  enabled: boolean
}

// BACKEND-PENDING: plugin-registry list replaces the fixtures.
const MOCK_PLUGINS: MockPlugin[] = [
  { id: 'k8s-toolkit', color: 'var(--cat-cyan)', kind: 'mcp', kind_label: 'MCP server · soit-labs', source: 'marketplace', version: 'v1.4.2 · pinned', version_note: '1.5.0 available', risk: 'md', risk_label: 'MEDIUM', scopes: ['k8s.read', 'k8s.rollout', 'k8s.logs'], agents: '2', calls: '1,204', enabled: true },
  { id: 'helpdesk-api', color: 'var(--cat-indigo)', kind: 'tools', kind_label: 'tool pack · builtin', source: 'builtin', version: 'v2.0.1', risk: 'lo', risk_label: 'LOW', scopes: ['tickets.read', 'tickets.write'], agents: '1', calls: '3,411', enabled: true },
  { id: 'vault-secrets', color: 'var(--cat-slate)', kind: 'mcp', kind_label: 'MCP server · builtin', source: 'builtin', version: 'v0.9.8', risk: 'lo', risk_label: 'LOW', scopes: ['secrets.ref'], agents: '5', calls: '2,880', enabled: true },
  { id: 'web-fetch', color: 'var(--cat-blue)', kind: 'tools', kind_label: 'tool pack · soit-labs', source: 'marketplace', version: 'v1.1.0 · pinned', risk: 'md', risk_label: 'MEDIUM', scopes: ['net.egress · allowlist'], agents: '3', calls: '866', enabled: true },
  { id: 'erp-connector', color: 'var(--cat-pink)', kind: 'mcp', kind_label: 'MCP server · finance team', source: 'upload', version: 'v3.2.0 · pinned', risk: 'hi', risk_label: 'HIGH', scopes: ['finance.journal.post · approval'], agents: '1', calls: '14', enabled: true },
  { id: 'cdn-tools', color: 'var(--cat-amber)', kind: 'tools', kind_label: 'tool pack · community', source: 'marketplace', version: 'v0.3.1', risk: 'md', risk_label: 'MEDIUM', scopes: ['cdn.purge · no grant'], agents: '0', calls: '0', enabled: false },
  { id: 'incident-writeup', color: 'var(--cat-teal)', kind: 'skills', kind_label: 'skill · soit-labs', source: 'marketplace', version: 'v1.2.0 · pinned', risk: 'lo', risk_label: 'LOW', scopes: ['prompt pack · no tool scopes'], agents: '2', calls: '37', enabled: true },
  { id: 'runbook-triage', color: 'var(--cat-purple)', kind: 'skills', kind_label: 'skill · community', source: 'marketplace', version: 'v0.4.1 · pinned', risk: 'md', risk_label: 'MEDIUM', scopes: ['uses k8s.read · via k8s-toolkit'], agents: '1', calls: '18', enabled: true },
]

const MOCK_MARKET = [
  { id: 's3-tools', color: 'var(--cat-cyan)', meta: 'tool pack · soit-labs · v2.1.0', description: 'Object storage read/write with per-bucket scopes and size caps.', risk: 'lo' as RiskLevel, risk_label: 'LOW', scopes: ['s3.read', 's3.write'] },
  { id: 'jira-connector', color: 'var(--cat-indigo)', meta: 'MCP server · community · v1.8.4', description: 'Issue create/update/search. Writes are idempotent and audited.', risk: 'md' as RiskLevel, risk_label: 'MEDIUM', scopes: ['jira.read', 'jira.write'] },
  { id: 'pagerduty-tools', color: 'var(--cat-amber)', meta: 'tool pack · community · v0.9.2', description: 'Trigger, acknowledge and resolve incidents from governed runs.', risk: 'hi' as RiskLevel, risk_label: 'HIGH', scopes: ['pd.incidents · approval'] },
  { id: 'postmortem-writer', color: 'var(--cat-cyan)', meta: 'skill · soit-labs · v2.0.3', description: 'Structured incident postmortems drafted from run evidence, timeline and citations included.', risk: 'lo' as RiskLevel, risk_label: 'LOW', scopes: ['prompt pack · no tool scopes'] },
]

export default function ConsolePlugins() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<PlTab>('installed')
  const [filter, setFilter] = useState<PlFilter>('all')
  const [search, setSearch] = useState('')
  const [enabled, setEnabled] = useState<Record<string, boolean>>(() =>
    Object.fromEntries(MOCK_PLUGINS.map((plugin) => [plugin.id, plugin.enabled])),
  )

  const rows = MOCK_PLUGINS.filter((row) => {
    if (filter === 'disabled') {
      if (enabled[row.id]) return false
    } else if (filter !== 'all' && row.kind !== filter) {
      return false
    }
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.id, ...row.scopes].some((value) => value.toLowerCase().includes(query))
  })

  return (
    <Workbench
      title={t('console.plugins.title')}
      description={t('console.plugins.description')}
      actions={
        <>
          <ConsoleButton>
            <IconExport />
            {t('console.plugins.upload')}
          </ConsoleButton>
          <ConsoleButton variant="primary" onClick={() => setTab('market')}>
            <IconPlus />
            {t('console.plugins.installMarket')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.plugins.tiles.plugins')} value="8" sub={<span className="mono dimmer">3 MCP · 3 tools · 2 skills · 1 disabled</span>} />
          <StatTile label={t('console.plugins.tiles.invocations')} value="8,430" delta={{ direction: 'up', label: '+6.4%' }} sub="tool calls + skill uses" />
          <StatTile label={t('console.plugins.tiles.updates')} value="1" sub={<span className="mono dimmer">k8s-toolkit 1.4.2 → 1.5.0</span>} />
          <StatTile label={t('console.plugins.tiles.highRisk')} value="1" sub={<span className="mono dimmer">finance.journal.post · approval-gated</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'installed', label: t('console.plugins.tabs.installed'), count: 8 },
            { id: 'market', label: t('console.plugins.tabs.market') },
            { id: 'incidents', label: t('console.plugins.tabs.incidents'), count: 1 },
            { id: 'recycle', label: t('console.plugins.tabs.recycle') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'installed' ? (
          <>
            {(
              [
                ['all', t('console.plugins.filters.all'), 8],
                ['mcp', t('console.plugins.filters.mcp'), 3],
                ['tools', t('console.plugins.filters.tools'), 3],
                ['skills', t('console.plugins.filters.skills'), 2],
                ['disabled', t('console.plugins.filters.disabled'), 1],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.plugins.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'installed' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.plugins.columns.plugin')}</TableHead>
                <TableHead>{t('console.plugins.columns.source')}</TableHead>
                <TableHead>{t('console.plugins.columns.version')}</TableHead>
                <TableHead>{t('console.plugins.columns.risk')}</TableHead>
                <TableHead>{t('console.plugins.columns.scopes')}</TableHead>
                <TableHead className="num">{t('console.plugins.columns.agents')}</TableHead>
                <TableHead className="num">{t('console.plugins.columns.calls')}</TableHead>
                <TableHead>{t('console.plugins.columns.enabled')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.id} className="rowlink">
                  <TableCell>
                    <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
                      <i />
                      <span>
                        <b style={{ fontWeight: 600 }}>{row.id}</b>
                        <br />
                        <span className="dimmer" style={{ fontSize: 10.5 }}>
                          {row.kind_label}
                        </span>
                      </span>
                    </span>
                  </TableCell>
                  <TableCell className="dim">{row.source}</TableCell>
                  <TableCell>
                    <span className="mono dim">{row.version}</span>
                    {row.version_note && (
                      <>
                        <br />
                        <span className="mono dimmer" style={{ fontSize: 10 }}>
                          {row.version_note}
                        </span>
                      </>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`risk ${row.risk}`}>{row.risk_label}</span>
                  </TableCell>
                  <TableCell>
                    <span className="scopes">
                      {row.scopes.map((scope) => (
                        <span key={scope} className="chip">
                          {scope}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="num dim">{row.agents}</TableCell>
                  <TableCell className="num dim">{row.calls}</TableCell>
                  <TableCell>
                    <ConsoleToggle
                      on={!!enabled[row.id]}
                      label={row.id}
                      onChange={(next) => setEnabled((state) => ({ ...state, [row.id]: next }))}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.plugins.installedNote')}>
            <ConsoleButton size="sm">{t('console.plugins.reviewUpdate')}</ConsoleButton>
          </Pager>
        </WorkbenchPanel>
      )}

      {tab === 'market' && (
        <div className="mt-3.5">
          <div className="cards">
            {MOCK_MARKET.map((item) => (
              <div key={item.id} className="acard">
                <div className="acard-top">
                  <span className="aavatar" style={{ '--c': item.color } as React.CSSProperties} />
                  <span>
                    <b>{item.id}</b>
                    <span className="mono">{item.meta}</span>
                  </span>
                </div>
                <p>{item.description}</p>
                <div className="acard-foot">
                  <span className={`risk ${item.risk}`}>{item.risk_label}</span>
                  <span className="scopes" style={{ marginLeft: 8 }}>
                    {item.scopes.map((scope) => (
                      <span key={scope} className="chip">
                        {scope}
                      </span>
                    ))}
                  </span>
                  <span className="spacer" />
                  <ConsoleButton>{t('console.plugins.install')}</ConsoleButton>
                </div>
              </div>
            ))}
          </div>
          <p className="dim" style={{ marginTop: 10, fontSize: 11.5 }}>
            {t('console.plugins.marketNote')}
          </p>
        </div>
      )}

      {tab === 'incidents' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.plugins.columns.plugin')}</TableHead>
                <TableHead>{t('console.plugins.columns.incident')}</TableHead>
                <TableHead className="num">{t('console.plugins.columns.affected')}</TableHead>
                <TableHead>{t('console.plugins.columns.evidence')}</TableHead>
                <TableHead className="num">{t('console.plugins.columns.status')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              <TableRow>
                <TableCell>
                  <span className="idm" style={{ '--c': 'var(--cat-pink)' } as React.CSSProperties}>
                    <i />
                    erp-connector
                  </span>
                </TableCell>
                <TableCell className="dim">
                  timeout spike 08-27 14:00–14:40Z · upstream ERP maintenance window
                </TableCell>
                <TableCell className="num dim">23</TableCell>
                <TableCell>
                  <a
                    className="runid"
                    href="/v2/observe/runs/run_01J9KCYW7N"
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/v2/observe/runs/run_01J9KCYW7N')
                    }}
                  >
                    run_01J9KCYW7N
                  </a>
                </TableCell>
                <TableCell className="num">
                  <StatusChip status="info" label="RESOLVED" />
                </TableCell>
              </TableRow>
            </TableBody>
          </Table>
          <Pager summary={t('console.plugins.incidentsNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'recycle' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.plugins.recycleEmpty')}
            <span className="mono">{t('console.plugins.recycleNote')}</span>
          </div>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
