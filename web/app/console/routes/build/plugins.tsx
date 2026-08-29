import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
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
import {
  installPlugin,
  listPlugins,
  setPluginEnabled,
  uninstallPlugin,
  uploadPluginPackage,
  type Plugin,
} from '@/services/plugin-service'
import { requestErrorMessage } from '@/utils/request'

type PlTab = 'installed' | 'market' | 'incidents' | 'recycle'
type PlFilter = 'all' | 'mcp' | 'tools' | 'skills' | 'disabled' | 'available'

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
// wired until that API exists. Install/uninstall are wired on the Installed tab
// instead, against the registry rows that really exist: the "Not installed"
// chip lists registry plugins this workspace has not installed yet.
const MOCK_MARKET = [
  { id: 's3-tools', color: 'var(--cat-cyan)', meta: 'tool pack · soit-labs · v2.1.0', description: 'Object storage read/write with per-bucket scopes and size caps.', risk: 'lo', risk_label: 'LOW', scopes: ['s3.read', 's3.write'] },
  { id: 'jira-connector', color: 'var(--cat-indigo)', meta: 'MCP server · community · v1.8.4', description: 'Issue create/update/search. Writes are idempotent and audited.', risk: 'md', risk_label: 'MEDIUM', scopes: ['jira.read', 'jira.write'] },
  { id: 'pagerduty-tools', color: 'var(--cat-amber)', meta: 'tool pack · community · v0.9.2', description: 'Trigger, acknowledge and resolve incidents from governed runs.', risk: 'hi', risk_label: 'HIGH', scopes: ['pd.incidents · approval'] },
  { id: 'postmortem-writer', color: 'var(--cat-cyan)', meta: 'skill · soit-labs · v2.0.3', description: 'Structured incident postmortems drafted from run evidence, timeline and citations included.', risk: 'lo', risk_label: 'LOW', scopes: ['prompt pack · no tool scopes'] },
]

/** The upload endpoint rejects a package whose version is already registered. */
function isSameVersionConflict(error: unknown) {
  const data = (error as { response?: { data?: { details?: { reason?: string } } } } | null)?.response?.data
  return data?.details?.reason === 'same_version_exists'
}

export default function ConsolePlugins() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<PlTab>('installed')
  const [filter, setFilter] = useState<PlFilter>('all')
  const [search, setSearch] = useState('')
  const [enabledOverride, setEnabledOverride] = useState<Record<string, boolean>>({})

  const [uploadOpen, setUploadOpen] = useState(false)
  const [reinstallOpen, setReinstallOpen] = useState(false)
  const [packageFile, setPackageFile] = useState<File | null>(null)
  const [uninstalling, setUninstalling] = useState<Plugin | null>(null)

  const pluginsQuery = useQuery({
    queryKey: ['console', 'plugins', 'list'],
    queryFn: () => listPlugins({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const enabledMutation = useMutation({
    mutationKey: ['console', 'plugins', 'enabled'],
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => setPluginEnabled(id, enabled),
  })

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const installMutation = useMutation({
    mutationKey: ['console', 'plugins', 'install'],
    // The registry install takes an optional config; there is no per-plugin
    // config form in the prototype, so it installs with the plugin's defaults.
    mutationFn: (plugin: Plugin) => installPlugin(plugin.id, {}),
    onSuccess: () => {
      toast.success(t('console.plugins.installedToast'))
      void pluginsQuery.refetch()
    },
    onError: onWriteError('Failed to install the plugin'),
  })

  const uninstallMutation = useMutation({
    mutationKey: ['console', 'plugins', 'uninstall'],
    mutationFn: () => uninstallPlugin(uninstalling!.id),
    onSuccess: () => {
      toast.success(t('console.plugins.uninstalledToast'))
      setUninstalling(null)
      void pluginsQuery.refetch()
    },
    onError: onWriteError('Failed to uninstall the plugin'),
  })

  const uploadMutation = useMutation({
    mutationKey: ['console', 'plugins', 'upload'],
    mutationFn: (mode: 'auto' | 'reinstall') => uploadPluginPackage(packageFile!, mode),
    onSuccess: () => {
      toast.success(t('console.plugins.uploadedToast'))
      setUploadOpen(false)
      setReinstallOpen(false)
      setPackageFile(null)
      void pluginsQuery.refetch()
    },
    onError: (error: unknown) => {
      // Same behaviour as the legacy package dialog: an identical version is a
      // confirmable reinstall, not a failure.
      if (isSameVersionConflict(error)) {
        setUploadOpen(false)
        setReinstallOpen(true)
        return
      }
      toast.error(requestErrorMessage(error, 'Failed to upload the plugin package'))
    },
  })

  // The registry lists every plugin; this tab is the installed subset, with the
  // not-installed remainder reachable through its own chip so install has real
  // rows to act on.
  const items = pluginsQuery.data?.items || []
  const installed = items.filter((row) => row.installed)
  const available = items.filter((row) => !row.installed)
  const isEnabled = (row: Plugin) => enabledOverride[row.id] ?? row.enabled === true

  const countOfType = (kind: 'mcp' | 'tools' | 'skills') =>
    installed.filter((row) => row.plugin_type === FILTER_TYPE[kind]).length
  const disabledCount = installed.filter((row) => !isEnabled(row)).length

  const rows = (filter === 'available' ? available : installed).filter((row) => {
    if (filter === 'disabled') {
      if (isEnabled(row)) return false
    } else if (filter !== 'all' && filter !== 'available' && row.plugin_type !== FILTER_TYPE[filter]) {
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
          <ConsoleButton
            onClick={() => {
              setPackageFile(null)
              setUploadOpen(true)
            }}
          >
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
                ['available', t('console.plugins.filters.available'), available.length],
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
                      {row.installed ? (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
                          <ConsoleToggle
                            on={isEnabled(row)}
                            label={row.name}
                            onChange={(next) => toggle(row, next)}
                          />
                          <ConsoleButton
                            variant="ghost"
                            size="sm"
                            style={{ color: 'var(--danger-foreground)' }}
                            disabled={uninstallMutation.isPending}
                            onClick={() => setUninstalling(row)}
                          >
                            {t('console.plugins.uninstall')}
                          </ConsoleButton>
                        </span>
                      ) : (
                        <ConsoleButton
                          size="sm"
                          disabled={installMutation.isPending}
                          onClick={() => installMutation.mutate(row)}
                        >
                          {t('console.plugins.install')}
                        </ConsoleButton>
                      )}
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

      <ConsoleModal
        open={uploadOpen}
        onOpenChange={(open) => {
          setUploadOpen(open)
          if (!open) setPackageFile(null)
        }}
        title={t('console.plugins.uploadTitle')}
        note={t('console.plugins.uploadNote')}
        confirmLabel={t('console.plugins.uploadConfirm')}
        confirmDisabled={!packageFile}
        busy={uploadMutation.isPending}
        onConfirm={() => uploadMutation.mutate('auto')}
      >
        <div className="mrow">
          <label>
            {t('console.plugins.uploadFields.package')}
            <small>{t('console.plugins.uploadFields.packageHint')}</small>
          </label>
          <input
            className="input"
            type="file"
            accept=".zip,application/zip"
            aria-label={t('console.plugins.uploadFields.package')}
            onChange={(event) => setPackageFile(event.target.files?.[0] || null)}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={reinstallOpen}
        onOpenChange={(open) => {
          setReinstallOpen(open)
          if (!open) setPackageFile(null)
        }}
        title={t('console.plugins.reinstallTitle')}
        confirmLabel={t('console.plugins.reinstallAction')}
        busy={uploadMutation.isPending}
        onConfirm={() => uploadMutation.mutate('reinstall')}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.plugins.reinstallConfirm')}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={uninstalling != null}
        onOpenChange={(open) => !open && setUninstalling(null)}
        title={t('console.plugins.uninstallTitle')}
        confirmLabel={t('console.plugins.uninstall')}
        destructive
        busy={uninstallMutation.isPending}
        onConfirm={() => uninstallMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.plugins.uninstallConfirm', { name: uninstalling?.name ?? '' })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
