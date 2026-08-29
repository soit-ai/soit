import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  ConsoleTabs,
  DataStateNote,
  DataStateRow,
  FilterChip,
  FilterSearch,
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
import { catColor, compactNumber, latency } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createProvider,
  createProviderModel,
  deleteProvider,
  deleteProviderModel,
  getModelWorkbenchModels,
  getModelWorkbenchOverview,
  getModelWorkbenchProviders,
  getProvider,
  getProviderSupportMatrix,
  testModelConnection,
  updateProvider,
  updateProviderModel,
  type ModelWorkbenchModelRow,
  type ModelWorkbenchProviderRow,
} from '@/services/provider-service'
import type { ProviderConfig } from '@/features/model-config/types'
import { requestErrorMessage } from '@/utils/request'

type MdTab = 'providers' | 'library' | 'usage'
type MdFilter = 'all' | 'chat' | 'embedding' | 'rerank'

const PAGE_SIZE = 200

/** The prototype's capability chips map onto workbench `model_type` values. */
const FILTER_MODEL_TYPE: Record<'chat' | 'embedding' | 'rerank', string> = {
  chat: 'llm',
  embedding: 'embedding',
  rerank: 'rerank',
}

/** "200k" / "8k" — the prototype's context stamp. */
function contextWindow(tokens?: number | null): string {
  if (tokens == null) return '—'
  if (tokens >= 1000) return `${Math.round(tokens / 1000)}k`
  return String(tokens)
}

function money(amount?: number | null, currency?: string | null): string {
  if (amount == null) return '—'
  const value = amount.toFixed(2)
  if (!currency) return value
  return currency.toUpperCase() === 'USD' ? `$${value}` : `${value} ${currency}`
}

const EMPTY_PROVIDER_FORM = {
  name: '',
  kind: '',
  adapterBackend: 'native' as ProviderConfig['adapterBackend'],
  baseUrl: '',
  credentialSecretId: '',
}

const EMPTY_MODEL_FORM = {
  providerId: '',
  modelId: '',
  displayName: '',
  description: '',
  contextWindow: '',
  maxOutputTokens: '',
  testInput: '',
}

/** "" and a non-numeric string both mean "do not send a number". */
function numberOrUndefined(value: string): number | undefined {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : undefined
}

export default function ConsoleModels() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<MdTab>('providers')
  const [filter, setFilter] = useState<MdFilter>('all')
  const [search, setSearch] = useState('')

  const [creatingProvider, setCreatingProvider] = useState(false)
  // The full provider record, not the workbench row: an update sends the whole
  // config, so editing has to start from what the provider actually holds.
  const [editingProvider, setEditingProvider] = useState<ProviderConfig | null>(null)
  const [loadingProvider, setLoadingProvider] = useState<string | null>(null)
  const [deletingProvider, setDeletingProvider] = useState<ModelWorkbenchProviderRow | null>(null)
  const [providerForm, setProviderForm] = useState(EMPTY_PROVIDER_FORM)

  const [creatingModel, setCreatingModel] = useState(false)
  const [editingModel, setEditingModel] = useState<ModelWorkbenchModelRow | null>(null)
  const [deletingModel, setDeletingModel] = useState<ModelWorkbenchModelRow | null>(null)
  const [modelForm, setModelForm] = useState(EMPTY_MODEL_FORM)

  // The overview carries the summary and both tab counters, so it backs the
  // tiles and the tab bar on every tab; the two list queries only run for the
  // tab that renders them.
  const overviewQuery = useQuery({
    queryKey: ['console', 'models', 'overview'],
    queryFn: () => getModelWorkbenchOverview(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // The Library tab needs the provider list too — a new model has to be filed
  // under one — so both write tabs load it.
  const providersQuery = useQuery({
    queryKey: ['console', 'models', 'providers'],
    queryFn: () => getModelWorkbenchProviders({ page_size: PAGE_SIZE }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
      enabled: tab === 'providers' || tab === 'library',
    },
  })
  const modelsQuery = useQuery({
    queryKey: ['console', 'models', 'library'],
    queryFn: () => getModelWorkbenchModels({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false, enabled: tab === 'library' },
  })
  // The kind and adapter-backend choices are whatever the deployment reports;
  // only fetched while a provider dialog is open.
  const presetsQuery = useQuery({
    queryKey: ['console', 'models', 'support-matrix'],
    queryFn: () => getProviderSupportMatrix(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
      enabled: creatingProvider || editingProvider != null,
    },
  })

  const refetchAll = () => {
    void overviewQuery.refetch()
    void providersQuery.refetch()
    void modelsQuery.refetch()
  }
  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const providerPayload = (): ProviderConfig => ({
    ...(editingProvider || { id: '', status: 'active' as const }),
    name: providerForm.name.trim(),
    kind: providerForm.kind.trim(),
    adapterBackend: providerForm.adapterBackend,
    // An empty box leaves the stored value alone — the service drops falsy
    // optionals rather than sending an explicit null.
    baseUrl: providerForm.baseUrl.trim(),
    credentialSecretId: providerForm.credentialSecretId.trim(),
  })

  const createProviderMutation = useMutation({
    mutationKey: ['console', 'models', 'provider', 'create'],
    mutationFn: () => createProvider(providerPayload()),
    onSuccess: () => {
      setCreatingProvider(false)
      setProviderForm(EMPTY_PROVIDER_FORM)
      refetchAll()
    },
    onError: onWriteError('Failed to create the provider'),
  })
  const updateProviderMutation = useMutation({
    mutationKey: ['console', 'models', 'provider', 'update'],
    mutationFn: () => updateProvider(editingProvider!.id, providerPayload()),
    onSuccess: () => {
      setEditingProvider(null)
      setProviderForm(EMPTY_PROVIDER_FORM)
      refetchAll()
    },
    onError: onWriteError('Failed to save the provider'),
  })
  const deleteProviderMutation = useMutation({
    mutationKey: ['console', 'models', 'provider', 'delete'],
    mutationFn: () => deleteProvider(deletingProvider!.id),
    onSuccess: () => {
      setDeletingProvider(null)
      refetchAll()
    },
    onError: onWriteError('Failed to delete the provider'),
  })

  const createModelMutation = useMutation({
    mutationKey: ['console', 'models', 'model', 'create'],
    mutationFn: () =>
      createProviderModel(modelForm.providerId, {
        modelId: modelForm.modelId.trim(),
        displayName: modelForm.displayName.trim() || undefined,
        description: modelForm.description.trim() || undefined,
        contextWindow: numberOrUndefined(modelForm.contextWindow),
        maxOutputTokens: numberOrUndefined(modelForm.maxOutputTokens),
        source: 'local',
      }),
    onSuccess: () => {
      setCreatingModel(false)
      setModelForm(EMPTY_MODEL_FORM)
      refetchAll()
    },
    onError: onWriteError('Failed to create the model'),
  })
  const updateModelMutation = useMutation({
    mutationKey: ['console', 'models', 'model', 'update'],
    mutationFn: () =>
      updateProviderModel(editingModel!.provider_id, editingModel!.id, {
        displayName: modelForm.displayName.trim(),
        description: modelForm.description.trim(),
        contextWindow: numberOrUndefined(modelForm.contextWindow),
        maxOutputTokens: numberOrUndefined(modelForm.maxOutputTokens),
      }),
    onSuccess: () => {
      setEditingModel(null)
      setModelForm(EMPTY_MODEL_FORM)
      refetchAll()
    },
    onError: onWriteError('Failed to save the model'),
  })
  const deleteModelMutation = useMutation({
    mutationKey: ['console', 'models', 'model', 'delete'],
    mutationFn: () => deleteProviderModel(deletingModel!.provider_id, deletingModel!.id),
    onSuccess: () => {
      setDeletingModel(null)
      refetchAll()
    },
    onError: onWriteError('Failed to delete the model'),
  })
  const testMutation = useMutation({
    mutationKey: ['console', 'models', 'test'],
    mutationFn: (row: ModelWorkbenchModelRow) =>
      testModelConnection(
        row.provider_id,
        row.model_id,
        modelForm.testInput.trim(),
        // The endpoint is split by call shape, and `model_type` is the only
        // signal the workbench row carries about which one applies.
        row.model_type === 'embedding' ? 'embeddings' : 'chat',
      ),
    onSuccess: (result: { success?: boolean; message?: string } | null) => {
      if (result?.success) toast.success(result.message || t('console.models.testOk'))
      else toast.error(result?.message || t('console.models.testFailed'))
    },
    onError: onWriteError('Failed to test the model connection'),
  })

  const openProviderEditor = async (row: ModelWorkbenchProviderRow) => {
    setLoadingProvider(row.id)
    try {
      const config = await getProvider(row.id)
      setProviderForm({
        name: config.name,
        kind: config.kind,
        adapterBackend: config.adapterBackend,
        baseUrl: config.baseUrl || '',
        credentialSecretId: config.credentialSecretId || '',
      })
      setEditingProvider(config)
    } catch (error) {
      toast.error(requestErrorMessage(error, 'Failed to load the provider'))
    } finally {
      setLoadingProvider(null)
    }
  }

  const openModelEditor = (row: ModelWorkbenchModelRow) => {
    setModelForm({
      providerId: row.provider_id,
      modelId: row.model_id,
      displayName: row.display_name || '',
      description: row.description || '',
      contextWindow: row.context_window == null ? '' : String(row.context_window),
      maxOutputTokens: row.max_output_tokens == null ? '' : String(row.max_output_tokens),
      testInput: '',
    })
    setEditingModel(row)
  }

  const summary = overviewQuery.data?.summary
  const modelTabs = overviewQuery.data?.model_tabs
  const providerTabs = overviewQuery.data?.provider_tabs
  const providers = providersQuery.data?.items || []
  const libraryTabs = modelsQuery.data?.tabs
  const usage = overviewQuery.data?.top_models || []

  const matchesSearch = (row: ModelWorkbenchModelRow) => {
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.model_id, row.display_name, row.provider_name, row.provider_slug]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(query))
  }

  const rows = (modelsQuery.data?.items || []).filter((row) => {
    if (filter !== 'all' && row.model_type !== FILTER_MODEL_TYPE[filter]) return false
    return matchesSearch(row)
  })

  return (
    <Workbench
      title={t('console.models.title')}
      description={t('console.models.description')}
      actions={
        <ConsoleButton
          variant="primary"
          onClick={() => {
            setProviderForm(EMPTY_PROVIDER_FORM)
            setCreatingProvider(true)
          }}
        >
          <IconPlus />
          {t('console.models.addProvider')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.models.tiles.providers')}
            value={summary ? String(summary.total_providers) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {summary ? `${summary.online_providers} online` : t('console.common.loading')}
              </span>
            }
          />
          <StatTile
            label={t('console.models.tiles.models')}
            value={summary ? String(summary.total_models) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                {modelTabs
                  ? `${modelTabs.text} text · ${modelTabs.embedding} embedding · ${modelTabs.rerank} rerank`
                  : t('console.common.loading')}
              </span>
            }
          />
          {/* The workbench aggregates run cost month-to-date; there is no 24h
              bucket behind it, so the sub row states the real window. */}
          <StatTile
            label={t('console.models.tiles.tokens')}
            value={summary ? compactNumber(summary.month_tokens) : '—'}
            na={!summary}
            sub={<span className="mono dimmer">month to date</span>}
          />
          <StatTile
            label={t('console.models.tiles.spend')}
            value={summary ? money(summary.month_cost_amount, summary.currency) : '—'}
            na={!summary}
            sub={
              <span className="mono dimmer">
                month to date · p50 {latency(summary?.avg_latency_ms)}
              </span>
            }
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'providers', label: t('console.models.tabs.providers'), count: providerTabs?.all },
            { id: 'library', label: t('console.models.tabs.library'), count: modelTabs?.all },
            { id: 'usage', label: t('console.models.tabs.usage') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'library' ? (
          <>
            {(
              [
                ['all', t('console.models.filters.all'), libraryTabs?.all],
                ['chat', t('console.models.filters.chat'), libraryTabs?.text],
                ['embedding', t('console.models.filters.embedding'), libraryTabs?.embedding],
                ['rerank', t('console.models.filters.rerank'), libraryTabs?.rerank],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.models.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'providers' &&
        (providers.length === 0 ? (
          <WorkbenchPanel className="mt-3.5">
            <DataStateNote
              isPending={providersQuery.isPending}
              isError={providersQuery.isError}
            />
          </WorkbenchPanel>
        ) : (
          <div className="cards mt-3.5">
            {providers.map((provider) => (
              <div key={provider.id} className="acard">
                <div className="acard-top">
                  <span
                    className="aavatar"
                    style={{ '--c': catColor(provider.id) } as React.CSSProperties}
                  />
                  <span>
                    <b>{provider.name}</b>
                    {/* Credential references live in Secrets and are not part of
                        the workbench row; kind + status is what it carries. */}
                    <span className="mono">
                      {[provider.kind, provider.status].filter(Boolean).join(' · ')}
                    </span>
                  </span>
                </div>
                <div className="acard-stats">
                  {(
                    [
                      [String(provider.total_models), 'models'],
                      [compactNumber(provider.month_tokens), 'tokens · mtd'],
                      [money(provider.month_cost_amount, provider.currency), 'spend · mtd'],
                    ] as const
                  ).map(([value, label]) => (
                    <span key={label}>
                      <b>{value}</b>
                      {label}
                    </span>
                  ))}
                </div>
                <div className="acard-foot">
                  {/* No "default provider" flag exists; the dot marks online. */}
                  <span className="chip">
                    {provider.status === 'online' && <i style={{ background: 'var(--primary)' }} />}
                    {provider.available_models} / {provider.total_models} available
                  </span>
                  <span className="spacer" />
                  <ConsoleButton
                    size="sm"
                    disabled={loadingProvider === provider.id}
                    onClick={() => void openProviderEditor(provider)}
                  >
                    {t('console.models.editProvider')}
                  </ConsoleButton>
                  <ConsoleButton
                    variant="ghost"
                    size="sm"
                    style={{ color: 'var(--danger-foreground)' }}
                    onClick={() => setDeletingProvider(provider)}
                  >
                    {t('console.models.deleteProvider')}
                  </ConsoleButton>
                </div>
              </div>
            ))}
          </div>
        ))}

      {tab === 'library' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.models.columns.model')}</TableHead>
                <TableHead>{t('console.models.columns.provider')}</TableHead>
                <TableHead>{t('console.models.columns.capabilities')}</TableHead>
                <TableHead className="num">{t('console.models.columns.context')}</TableHead>
                <TableHead className="num">{t('console.models.columns.price')}</TableHead>
                <TableHead>{t('console.models.columns.role')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={modelsQuery.isPending}
                  isError={modelsQuery.isError}
                />
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id} className="rowlink" onClick={() => openModelEditor(row)}>
                    <TableCell>
                      <span className="mono">{row.model_id}</span>
                    </TableCell>
                    <TableCell>
                      <span
                        className="idm"
                        style={{ '--c': catColor(row.provider_id) } as React.CSSProperties}
                      >
                        <i />
                        {row.provider_name || row.provider_slug}
                      </span>
                    </TableCell>
                    {/* The workbench row carries no capability list — only the
                        model's type, which is what the filter chips key on. */}
                    <TableCell>
                      <span className="scopes">
                        <span className="chip">{row.model_type}</span>
                      </span>
                    </TableCell>
                    <TableCell className="num dim">{contextWindow(row.context_window)}</TableCell>
                    {/* Only a single `unit_price` is exposed; there is no
                        input/output split to fill "$/1M in · out". */}
                    <TableCell className="num dim">
                      {row.unit_price == null ? '—' : money(row.unit_price, row.currency)}
                    </TableCell>
                    {/* No workspace-default / role assignment field exists. */}
                    <TableCell className="dim">—</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.models.libraryNote', { count: rows.length })}>
            <ConsoleButton
              size="sm"
              onClick={() => {
                setModelForm({
                  ...EMPTY_MODEL_FORM,
                  providerId: providers[0]?.id || '',
                })
                setCreatingModel(true)
              }}
            >
              {t('console.models.addModel')}
            </ConsoleButton>
          </Pager>
        </WorkbenchPanel>
      )}

      {tab === 'usage' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.models.usageTitle')}
          hint={t('console.models.usageHint')}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.models.columns.model')}</TableHead>
                <TableHead className="num">{t('console.models.columns.requests')}</TableHead>
                <TableHead className="num">{t('console.models.columns.tokensIn')}</TableHead>
                <TableHead className="num">{t('console.models.columns.tokensOut')}</TableHead>
                <TableHead className="num">{t('console.models.columns.p50')}</TableHead>
                <TableHead className="num">{t('console.models.columns.spend')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {usage.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={overviewQuery.isPending}
                  isError={overviewQuery.isError}
                />
              ) : (
                usage.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <span className="mono">{row.model_id}</span>
                    </TableCell>
                    <TableCell className="num dim">{compactNumber(row.month_calls)}</TableCell>
                    {/* `month_tokens` is a single total — the workbench does not
                        split prompt vs completion, so neither column has a
                        source of its own. */}
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dim">{latency(row.avg_latency_ms)}</TableCell>
                    <TableCell className="num dim">
                      {money(row.month_cost_amount, row.currency)}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.models.usageNote')} />
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={creatingProvider || editingProvider != null}
        onOpenChange={(open) => {
          if (open) return
          setCreatingProvider(false)
          setEditingProvider(null)
        }}
        title={
          editingProvider
            ? t('console.models.editProviderTitle')
            : t('console.models.addProviderTitle')
        }
        note={t('console.models.providerNote')}
        confirmLabel={editingProvider ? t('console.common.save') : t('console.common.create')}
        confirmDisabled={!providerForm.name.trim() || !providerForm.kind.trim()}
        busy={createProviderMutation.isPending || updateProviderMutation.isPending}
        onConfirm={() =>
          editingProvider
            ? updateProviderMutation.mutate(undefined)
            : createProviderMutation.mutate(undefined)
        }
      >
        <div className="mrow">
          <label>{t('console.models.providerFields.name')}</label>
          <input
            className="input"
            value={providerForm.name}
            onChange={(event) =>
              setProviderForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.models.providerFields.kind')}
            <small>{t('console.models.providerFields.kindHint')}</small>
          </label>
          {presetsQuery.data?.providerPresets?.length ? (
            <select
              className="input"
              value={providerForm.kind}
              onChange={(event) =>
                setProviderForm((state) => ({ ...state, kind: event.target.value }))
              }
            >
              <option value="" />
              {presetsQuery.data.providerPresets.map((preset) => (
                <option key={preset.provider_kind} value={preset.provider_kind}>
                  {preset.display_name}
                </option>
              ))}
            </select>
          ) : (
            // The support matrix is the only source of valid kinds; if it is
            // unreachable the field stays free-form rather than guessing a list.
            <input
              className="input"
              value={providerForm.kind}
              onChange={(event) =>
                setProviderForm((state) => ({ ...state, kind: event.target.value }))
              }
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            />
          )}
        </div>
        <div className="mrow">
          <label>{t('console.models.providerFields.adapter')}</label>
          <select
            className="input"
            value={providerForm.adapterBackend}
            onChange={(event) =>
              setProviderForm((state) => ({
                ...state,
                adapterBackend: event.target.value as ProviderConfig['adapterBackend'],
              }))
            }
          >
            <option value="native">native</option>
            <option value="litellm">litellm</option>
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.models.providerFields.baseUrl')}
            <small>{t('console.models.providerFields.baseUrlHint')}</small>
          </label>
          <input
            className="input"
            value={providerForm.baseUrl}
            onChange={(event) =>
              setProviderForm((state) => ({ ...state, baseUrl: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.models.providerFields.credential')}
            <small>{t('console.models.providerFields.credentialHint')}</small>
          </label>
          <input
            className="input"
            value={providerForm.credentialSecretId}
            onChange={(event) =>
              setProviderForm((state) => ({ ...state, credentialSecretId: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingProvider != null}
        onOpenChange={(open) => !open && setDeletingProvider(null)}
        title={t('console.models.deleteProviderTitle')}
        confirmLabel={t('console.models.deleteAction')}
        destructive
        busy={deleteProviderMutation.isPending}
        onConfirm={() => deleteProviderMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.models.deleteProviderConfirm', { name: deletingProvider?.name ?? '' })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={creatingModel}
        onOpenChange={setCreatingModel}
        title={t('console.models.newModelTitle')}
        note={t('console.models.modelNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!modelForm.providerId || !modelForm.modelId.trim()}
        busy={createModelMutation.isPending}
        onConfirm={() => createModelMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.models.modelFields.provider')}</label>
          <select
            className="input"
            value={modelForm.providerId}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, providerId: event.target.value }))
            }
          >
            <option value="" />
            {providers.map((provider) => (
              <option key={provider.id} value={provider.id}>
                {provider.name}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.models.modelFields.modelId')}
            <small>{t('console.models.modelFields.modelIdHint')}</small>
          </label>
          <input
            className="input"
            value={modelForm.modelId}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, modelId: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.displayName')}</label>
          <input
            className="input"
            value={modelForm.displayName}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, displayName: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.context')}</label>
          <input
            className="input"
            value={modelForm.contextWindow}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, contextWindow: event.target.value }))
            }
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={editingModel != null}
        onOpenChange={(open) => !open && setEditingModel(null)}
        title={t('console.models.modelTitle')}
        note={t('console.models.modelNote')}
        confirmLabel={t('console.common.save')}
        busy={updateModelMutation.isPending}
        onConfirm={() => updateModelMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.models.modelFields.modelId')}</label>
          {/* The provider's own id for the model is the record key — it is not
              patchable, so it is shown read-only. */}
          <input
            className="input"
            value={modelForm.modelId}
            disabled
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.displayName')}</label>
          <input
            className="input"
            value={modelForm.displayName}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, displayName: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.description')}</label>
          <input
            className="input"
            value={modelForm.description}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.context')}</label>
          <input
            className="input"
            value={modelForm.contextWindow}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, contextWindow: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.models.modelFields.maxOutput')}</label>
          <input
            className="input"
            value={modelForm.maxOutputTokens}
            onChange={(event) =>
              setModelForm((state) => ({ ...state, maxOutputTokens: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.models.modelFields.test')}
            <small>{t('console.models.modelFields.testHint')}</small>
          </label>
          <span style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <input
              className="input"
              value={modelForm.testInput}
              onChange={(event) =>
                setModelForm((state) => ({ ...state, testInput: event.target.value }))
              }
            />
            <ConsoleButton
              size="sm"
              disabled={!modelForm.testInput.trim() || testMutation.isPending}
              onClick={() => editingModel && testMutation.mutate(editingModel)}
            >
              {t('console.models.testAction')}
            </ConsoleButton>
          </span>
        </div>
        <div className="mrow">
          <label>
            {t('console.models.modelFields.del')}
            <small>{t('console.models.modelFields.delHint')}</small>
          </label>
          <ConsoleButton
            variant="ghost"
            size="sm"
            style={{ color: 'var(--danger-foreground)' }}
            onClick={() => {
              setDeletingModel(editingModel)
              setEditingModel(null)
            }}
          >
            {t('console.models.modelFields.delBtn')}
          </ConsoleButton>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingModel != null}
        onOpenChange={(open) => !open && setDeletingModel(null)}
        title={t('console.models.deleteModelTitle')}
        confirmLabel={t('console.models.deleteAction')}
        destructive
        busy={deleteModelMutation.isPending}
        onConfirm={() => deleteModelMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.models.deleteModelConfirm', { name: deletingModel?.model_id ?? '' })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
