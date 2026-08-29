import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleTabs,
  ConsoleToggle,
  DataStateNote,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconExport,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
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
import { catColor } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listPlugins, setPluginEnabled, type Plugin } from '@/services/plugin-service'
import { requestErrorMessage } from '@/utils/request'

type PlTab = 'installed' | 'market' | 'incidents' | 'recycle'
type PlFilter = 'all' | 'mcp' | 'tools' | 'skills' | 'disabled'

const PAGE_SIZE = 100

/** The prototype's kind chips map onto the registry's `plugin_type` values. */
const FILTER_TYPE: Record<'mcp' | 'tools' | 'skills', Plugin['plugin_type']> = {
  mcp: 'mcp',
  tools: 'tool',
  skills: 'skill',
}

// BACKEND-PENDING: the marketplace is the one fixture left on this page —
// there is no marketplace/catalogue endpoint at all (plugin-service only lists
// the workspace registry), so browsing and installing remote packages cannot be
// wired until that API exists.
const MOCK_MARKET = [
  { id: 's3-tools', color: 'var(--cat-cyan)', meta: 'tool pack · soit-labs · v2.1.0', description: 'Object storage read/write with per-bucket scopes and size caps.', risk: 'lo', risk_label: 'LOW', scopes: ['s3.read', 's3.write'] },
  { id: 'jira-connector', color: 'var(--cat-indigo)', meta: 'MCP server · community · v1.8.4', description: 'Issue create/update/search. Writes are idempotent and audited.', risk: 'md', risk_label: 'MEDIUM', scopes: ['jira.read', 'jira.write'] },
  { id: 'pagerduty-tools', color: 'var(--cat-amber)', meta: 'tool pack · community · v0.9.2', description: 'Trigger, acknowledge and resolve incidents from governed runs.', risk: 'hi', risk_label: 'HIGH', scopes: ['pd.incidents · approval'] },
  { id: 'postmortem-writer', color: 'var(--cat-cyan)', meta: 'skill · soit-labs · v2.0.3', description: 'Structured incident postmortems drafted from run evidence, timeline and citations included.', risk: 'lo', risk_label: 'LOW', scopes: ['prompt pack · no tool scopes'] },
]

export default function ConsolePlugins() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<PlTab>('installed')
  const [filter, setFilter] = useState<PlFilter>('all')
  const [search, setSearch] = useState('')
  const [enabledOverride, setEnabledOverride] = useState<Record<string, boolean>>({})

  const pluginsQuery = useQuery({
    queryKey: ['console', 'plugins', 'list'],
    queryFn: () => listPlugins({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const enabledMutation = useMutation({
    mutationKey: ['console', 'plugins', 'enabled'],
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setPluginEnabled(id, enabled),
  })

  // The registry lists every plugin; this tab is the installed subset.
  const installed = (pluginsQuery.data?.items || []).filter((row) => row.installed)
  const isEnabled = (row: Plugin) => enabledOverride[row.id] ?? row.enabled === true

  const countOfType = (kind: 'mcp' | 'tools' | 'skills') =>
    installed.filter((row) => row.plugin_type === FILTER_TYPE[kind]).length
  const disabledCount = installed.filter((row) => !isEnabled(row)).length

  const rows = installed.filter((row) => {
    if (filter === 'disabled') {
      if (isEnabled(row)) return false
    } else if (filter !== 'all' && row.plugin_type !== FILTER_TYPE[filter]) {
      return false
    }
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.name, row.id, row.publisher]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  })

  const toggle = (row: Plugin, next: boolean) => {
    const previous = isEnabled(row)
    setEnabledOverride((state) => ({ ...state, [row.id]: next }))
    enabledMutation.mutate(
      { id: row.id, enabled: next },
      {
        onError: (error) => {
          setEnabledOverride((state) => ({ ...state, [row.id]: previous }))
          toast.error(requestErrorMessage(error, 'Failed to update plugin'))
        },
      },
    )
  }

  const listed = !pluginsQuery.isPending && !pluginsQuery.isError

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
          <StatTile
            label={t('console.plugins.tiles.plugins')}
            value={listed ? String(installed.length) : '—'}
            na={!listed}
            sub={
              <span className="mono dimmer">
                {listed
                  ? `${countOfType('mcp')} MCP · ${countOfType('tools')} tools · ${countOfType('skills')} skills · ${disabledCount} disabled`
                  : t('console.common.loading')}
              </span>
            }
          />
          {/* BACKEND-PENDING: no per-plugin invocation counters are exposed. */}
          <StatTile
            label={t('console.plugins.tiles.invocations')}
            value="—"
            na
            sub={<span className="mono dimmer">no invocation metrics endpoint</span>}
          />
          {/* BACKEND-PENDING: no version-check / available-upgrade endpoint. */}
          <StatTile
            label={t('console.plugins.tiles.updates')}
            value="—"
            na
            sub={<span className="mono dimmer">no upgrade-check endpoint</span>}
          />
          {/* BACKEND-PENDING: the plugin record carries no risk classification. */}
          <StatTile
            label={t('console.plugins.tiles.highRisk')}
            value="—"
            na
            sub={<span className="mono dimmer">no risk field on plugin records</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'installed', label: t('console.plugins.tabs.installed'), count: installed.length },
            { id: 'market', label: t('console.plugins.tabs.market') },
            { id: 'incidents', label: t('console.plugins.tabs.incidents') },
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
                ['all', t('console.plugins.filters.all'), installed.length],
                ['mcp', t('console.plugins.filters.mcp'), countOfType('mcp')],
                ['tools', t('console.plugins.filters.tools'), countOfType('tools')],
                ['skills', t('console.plugins.filters.skills'), countOfType('skills')],
                ['disabled', t('console.plugins.filters.disabled'), disabledCount],
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
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={8}
                  isPending={pluginsQuery.isPending}
                  isError={pluginsQuery.isError}
                />
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id} className="rowlink">
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(row.id) } as React.CSSProperties}>
                        <i />
                        <span>
                          <b style={{ fontWeight: 600 }}>{row.name}</b>
                          <br />
                          <span className="dimmer" style={{ fontSize: 10.5 }}>
                            {[row.plugin_type, row.publisher].filter(Boolean).join(' · ')}
                          </span>
                        </span>
                      </span>
                    </TableCell>
                    {/* No install provenance (marketplace / builtin / upload) is
                        persisted on the plugin record — `publisher` is shown in
                        the sub-label above instead. */}
                    <TableCell className="dim">—</TableCell>
                    <TableCell>
                      <span className="mono dim">{row.version || '—'}</span>
                    </TableCell>
                    {/* `manifest_json` / `spec_json` are free-form dicts with no
                        risk classification or declared tool scopes in the
                        schema, so neither column has a source. */}
                    <TableCell>
                      <span className="dim">—</span>
                    </TableCell>
                    <TableCell>
                      <span className="dim">—</span>
                    </TableCell>
                    {/* No agent-usage or invocation counters per plugin. */}
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dim">—</TableCell>
                    <TableCell>
                      <ConsoleToggle
                        on={isEnabled(row)}
                        label={row.name}
                        onChange={(next) => toggle(row, next)}
                      />
                    </TableCell>
                  </TableRow>
                ))
              )}
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

      {/* Plugin incidents have no server-side object: nothing correlates run
          failures back to the plugin that degraded them, and there is no
          incident list/detail endpoint. Show an honest empty state instead of
          the fixture row. */}
      {tab === 'incidents' && (
        <WorkbenchPanel className="mt-3.5">
          <DataStateNote emptyLabel={t('console.plugins.incidentsEmpty')} />
          <Pager summary={t('console.plugins.incidentsNote')} />
        </WorkbenchPanel>
      )}

      {/* Uninstall (DELETE /plugins/{id}/install) removes the installation
          without a soft-deleted listing, so there is nothing to enumerate. */}
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
