import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { DataStateRow } from './data-state'
import { ConsoleModal } from './modal'
import { StatusChip } from './status-chip'
import { ConsoleToggle } from './toggle'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from './ui'
import { WorkbenchPanel } from './workbench'
import {
  CUSTOM_SCHEDULE,
  SCHEDULE_PRESETS,
  bytesToMb,
  configFromFieldValues,
  countsSummary,
  cronForPreset,
  defaultFieldValues,
  fieldValuesFromConfig,
  isActiveRun,
  limitsFromInputs,
  missingRequiredFields,
  relativeFuture,
  runDuration,
  schedulePresetOf,
  syncRunStatus,
  type FieldValues,
  type LimitInputs,
} from '../adapters/knowledge-sources'
import { relativeTime } from '../adapters/palette'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  cancelKnowledgeSyncRun,
  createKnowledgeSource,
  deleteKnowledgeSource,
  getKnowledgeSyncRun,
  listKnowledgeConnectors,
  listKnowledgeSources,
  listKnowledgeSyncRuns,
  syncKnowledgeSource,
  testKnowledgeSource,
  testKnowledgeSourceDraft,
  updateKnowledgeSource,
  type KnowledgeConnector,
  type KnowledgeSource,
  type KnowledgeSourceTestResult,
  type KnowledgeSyncRun,
} from '@/services/knowledge-service'
import { listSecrets } from '@/services/secrets-service'
import { requestErrorMessage } from '@/utils/request'

const SOURCES_POLL_MS = 4000

/**
 * A knowledge base's sources. Shared by the detail page, which shows the count
 * and the next sync in its header, and by the Sources tab. While any source has
 * a sync queued or running the list refreshes itself.
 */
export function useKnowledgeSources(knowledgeId: string) {
  return useQuery({
    queryKey: ['console', 'knowledge', 'sources', knowledgeId],
    queryFn: () => listKnowledgeSources(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
      refetchInterval: (query) =>
        (query.state.data as KnowledgeSource[] | undefined)?.some((source) => source.active_run_id)
          ? SOURCES_POLL_MS
          : false,
    },
  })
}

interface SourceForm {
  mode: 'create' | 'edit'
  id: string
  name: string
  kind: string
  secretId: string
  fields: FieldValues
  preset: string
  cron: string
  timezone: string
  enabled: boolean
  deleteRemoved: boolean
  limits: LimitInputs
  /** The limit boxes as the form opened, so an edit sends only what changed. */
  limitsBaseline?: LimitInputs
}

function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

function emptyForm(connector: KnowledgeConnector | undefined): SourceForm {
  return {
    mode: 'create',
    id: '',
    name: '',
    kind: connector?.kind ?? '',
    secretId: '',
    fields: defaultFieldValues(connector),
    preset: 'manual',
    cron: '',
    timezone: browserTimezone(),
    enabled: true,
    deleteRemoved: false,
    limits: { maxItems: '', maxItemMb: '', maxTotalMb: '' },
  }
}

function formFromSource(source: KnowledgeSource, connector: KnowledgeConnector | undefined): SourceForm {
  const limits: LimitInputs = {
    maxItems: String(source.limits.max_items),
    maxItemMb: bytesToMb(source.limits.max_item_bytes),
    maxTotalMb: bytesToMb(source.limits.max_total_bytes),
  }
  return {
    mode: 'edit',
    id: source.id,
    name: source.name,
    kind: source.connector_kind,
    secretId: source.secret_id ?? '',
    fields: fieldValuesFromConfig(connector, source.config),
    preset: schedulePresetOf(source.schedule_cron),
    cron: source.schedule_cron ?? '',
    timezone: source.schedule_timezone || 'UTC',
    enabled: source.enabled,
    deleteRemoved: source.delete_removed,
    limits,
    limitsBaseline: limits,
  }
}

/**
 * Build › Knowledge › a library › Sources: the external systems the library is
 * synced from, each with its schedule, last sync and run history.
 */
export function KnowledgeSourcesPanel({ knowledgeId }: { knowledgeId: string }) {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [form, setForm] = useState<SourceForm | null>(null)
  const [draftTest, setDraftTest] = useState<KnowledgeSourceTestResult | null>(null)
  const [rowTest, setRowTest] = useState<{ name: string; result: KnowledgeSourceTestResult } | null>(null)
  const [historyOf, setHistoryOf] = useState<KnowledgeSource | null>(null)
  const [deleting, setDeleting] = useState<KnowledgeSource | null>(null)

  const sourcesQuery = useKnowledgeSources(knowledgeId)
  const sources = sourcesQuery.data || []
  const connectorsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'connectors'],
    queryFn: listKnowledgeConnectors,
    options: { retry: false, refetchOnWindowFocus: false, staleTime: 5 * 60_000 },
  })
  const connectors = connectorsQuery.data || []
  const connectorOf = (kind: string) => connectors.find((entry) => entry.kind === kind)
  const activeConnector = form ? connectorOf(form.kind) : undefined

  const needsSecret = activeConnector != null && activeConnector.secret !== 'none'
  const secretsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'sources', 'secret-options'],
    queryFn: () => listSecrets({ limit: 200 }),
    options: { enabled: form != null && needsSecret, retry: false, refetchOnWindowFocus: false },
  })
  const secrets = secretsQuery.data || []

  const refresh = () => {
    void sourcesQuery.refetch()
  }
  const onError = (key: Parameters<typeof t>[0]) => (error: unknown) => {
    toast.error(requestErrorMessage(error, t(key)))
  }

  const cron = form ? cronForPreset(form.preset, form.cron) : ''
  const requestBody = () => {
    const current = form!
    const limits = limitsFromInputs(current.limits, current.limitsBaseline)
    return {
      name: current.name.trim(),
      config: configFromFieldValues(activeConnector, current.fields),
      secret_id: current.secretId || null,
      schedule_cron: cron || null,
      schedule_timezone: current.timezone.trim() || 'UTC',
      enabled: current.enabled,
      delete_removed: current.deleteRemoved,
      ...(limits ? { limits } : {}),
    }
  }

  const saveMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'source', 'save', knowledgeId],
    mutationFn: () => {
      const body = requestBody()
      return form!.mode === 'edit'
        ? updateKnowledgeSource(knowledgeId, form!.id, body)
        : createKnowledgeSource(knowledgeId, { ...body, connector_kind: form!.kind })
    },
    onSuccess: () => {
      setForm(null)
      setDraftTest(null)
      refresh()
    },
    onError: onError('console.knowDetail.sources.errors.save'),
  })

  const toggleMutation = useMutation<unknown, unknown, { source: KnowledgeSource; enabled: boolean }>({
    mutationKey: ['console', 'knowledge', 'source', 'toggle', knowledgeId],
    mutationFn: ({ source, enabled }) => updateKnowledgeSource(knowledgeId, source.id, { enabled }),
    onSuccess: refresh,
    onError: onError('console.knowDetail.sources.errors.toggle'),
  })

  const deleteMutation = useMutation({
    mutationKey: ['console', 'knowledge', 'source', 'delete', knowledgeId],
    mutationFn: () => deleteKnowledgeSource(knowledgeId, deleting!.id),
    onSuccess: () => {
      setDeleting(null)
      refresh()
    },
    onError: onError('console.knowDetail.sources.errors.remove'),
  })

  const syncMutation = useMutation<unknown, unknown, KnowledgeSource>({
    mutationKey: ['console', 'knowledge', 'source', 'sync', knowledgeId],
    mutationFn: (source) => syncKnowledgeSource(knowledgeId, source.id),
    onSuccess: () => {
      toast.success(t('console.knowDetail.sources.syncQueued'))
      refresh()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, t('console.knowDetail.sources.errors.sync')))
      refresh()
    },
  })

  const rowTestMutation = useMutation<
    { name: string; result: KnowledgeSourceTestResult },
    unknown,
    KnowledgeSource
  >({
    mutationKey: ['console', 'knowledge', 'source', 'test', knowledgeId],
    mutationFn: async (source) => ({
      name: source.name,
      result: await testKnowledgeSource(knowledgeId, source.id),
    }),
    onSuccess: setRowTest,
    onError: onError('console.knowDetail.sources.errors.test'),
  })

  const draftTestMutation = useMutation<KnowledgeSourceTestResult, unknown, void>({
    mutationKey: ['console', 'knowledge', 'source', 'test-draft', knowledgeId],
    mutationFn: () =>
      testKnowledgeSourceDraft(knowledgeId, {
        connector_kind: form!.kind,
        config: configFromFieldValues(activeConnector, form!.fields),
        secret_id: form!.secretId || null,
      }),
    onSuccess: (result) => setDraftTest(result),
    onError: onError('console.knowDetail.sources.errors.test'),
  })

  const openCreate = () => {
    setDraftTest(null)
    setForm(emptyForm(connectors[0]))
  }
  const openEdit = (source: KnowledgeSource) => {
    setDraftTest(null)
    setForm(formFromSource(source, connectorOf(source.connector_kind)))
  }
  const patchForm = (patch: Partial<SourceForm>) => setForm((state) => (state ? { ...state, ...patch } : state))
  const setField = (key: string, value: string | boolean) =>
    setForm((state) => (state ? { ...state, fields: { ...state.fields, [key]: value } } : state))
  const changeKind = (kind: string) => {
    setDraftTest(null)
    setForm((state) =>
      state
        ? { ...state, kind, secretId: '', fields: defaultFieldValues(connectorOf(kind)) }
        : state,
    )
  }

  const missing = form ? missingRequiredFields(activeConnector, form.fields) : []
  const secretMissing = needsSecret && activeConnector?.secret === 'required' && !form?.secretId
  const saveDisabled =
    !form ||
    !form.name.trim() ||
    !activeConnector ||
    missing.length > 0 ||
    secretMissing ||
    (form.preset === CUSTOM_SCHEDULE && !cron)

  const scheduleLabel = (source: KnowledgeSource): string => {
    if (!source.schedule_cron) return t('console.knowDetail.sources.manualOnly')
    const preset = SCHEDULE_PRESETS.find((entry) => entry.cron === source.schedule_cron)
    return preset ? t(preset.labelKey) : source.schedule_cron
  }

  return (
    <>
      <WorkbenchPanel
        title={t('console.knowDetail.sources.title')}
        hint={t('console.knowDetail.sources.hint')}
        actions={
          <ConsoleButton
            variant="primary"
            style={{ height: 24, fontSize: 11 }}
            disabled={connectors.length === 0}
            onClick={openCreate}
          >
            {t('console.knowDetail.sources.add')}
          </ConsoleButton>
        }
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.knowDetail.sources.columns.source')}</TableHead>
              <TableHead>{t('console.knowDetail.sources.columns.schedule')}</TableHead>
              <TableHead>{t('console.knowDetail.sources.columns.enabled')}</TableHead>
              <TableHead>{t('console.knowDetail.sources.columns.lastSync')}</TableHead>
              <TableHead className="num">{t('console.knowDetail.sources.columns.next')}</TableHead>
              <TableHead className="num" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {sources.length === 0 ? (
              <DataStateRow
                colSpan={6}
                isPending={sourcesQuery.isPending}
                isError={sourcesQuery.isError}
                emptyLabel={t('console.knowDetail.sources.empty')}
              />
            ) : (
              sources.map((source) => (
                <TableRow key={source.id} data-testid="knowledge-source-row">
                  <TableCell>
                    <b style={{ fontWeight: 600 }}>{source.name}</b>
                    <span className="dimmer" style={{ display: 'block', fontSize: 11 }}>
                      {connectorOf(source.connector_kind)?.label ?? source.connector_kind}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{scheduleLabel(source)}</TableCell>
                  <TableCell>
                    <ConsoleToggle
                      on={source.enabled}
                      label={t('console.knowDetail.sources.toggleLabel', { name: source.name })}
                      onChange={(enabled) => toggleMutation.mutate({ source, enabled })}
                    />
                  </TableCell>
                  <TableCell>
                    {source.active_run_id ? (
                      <StatusChip status="running" />
                    ) : source.last_status ? (
                      <StatusChip status={syncRunStatus(source.last_status)} />
                    ) : (
                      <span className="dimmer">{t('console.knowDetail.sources.neverSynced')}</span>
                    )}
                    {source.last_sync_at && !source.active_run_id && (
                      <span className="dimmer" style={{ marginLeft: 8, fontSize: 11 }}>
                        {relativeTime(source.last_sync_at)}
                        {countsSummary(source.last_counts) && ` · ${countsSummary(source.last_counts)}`}
                        {source.last_counts.truncated && ` · ${t('console.knowDetail.sources.truncatedChip')}`}
                      </span>
                    )}
                    {source.last_status === 'failed' && source.last_error && !source.active_run_id && (
                      <span
                        className="dimmer"
                        title={source.last_error}
                        style={{
                          display: 'block',
                          fontSize: 11,
                          maxWidth: 320,
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                          color: 'var(--danger-foreground)',
                        }}
                      >
                        {source.last_error}
                      </span>
                    )}
                  </TableCell>
                  <TableCell className="num dimmer">
                    {source.enabled && source.schedule_cron ? relativeFuture(source.next_sync_at) : '—'}
                  </TableCell>
                  <TableCell className="num">
                    <span style={{ display: 'inline-flex', gap: 6 }}>
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        disabled={syncMutation.isPending || !source.enabled || Boolean(source.active_run_id)}
                        onClick={() => syncMutation.mutate(source)}
                      >
                        {t('console.knowDetail.sources.syncNow')}
                      </ConsoleButton>
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        disabled={rowTestMutation.isPending}
                        onClick={() => rowTestMutation.mutate(source)}
                      >
                        {t('console.knowDetail.sources.test')}
                      </ConsoleButton>
                      <ConsoleButton variant="ghost" size="sm" onClick={() => setHistoryOf(source)}>
                        {t('console.knowDetail.sources.history')}
                      </ConsoleButton>
                      <ConsoleButton variant="ghost" size="sm" onClick={() => openEdit(source)}>
                        {t('console.knowDetail.sources.edit')}
                      </ConsoleButton>
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        style={{ color: 'var(--danger-foreground)' }}
                        onClick={() => setDeleting(source)}
                      >
                        {t('console.knowDetail.sources.del')}
                      </ConsoleButton>
                    </span>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </WorkbenchPanel>

      <ConsoleModal
        open={form != null}
        onOpenChange={(open) => !open && setForm(null)}
        title={t(
          form?.mode === 'edit'
            ? 'console.knowDetail.sources.editTitle'
            : 'console.knowDetail.sources.createTitle',
        )}
        note={t('console.knowDetail.sources.createNote')}
        confirmLabel={t(form?.mode === 'edit' ? 'console.common.save' : 'console.common.create')}
        confirmDisabled={saveDisabled}
        busy={saveMutation.isPending}
        onConfirm={() => saveMutation.mutate(undefined)}
      >
        {form && (
          <>
            <div className="mrow">
              <label>{t('console.knowDetail.sources.fields.name')}</label>
              <input
                className="input"
                aria-label={t('console.knowDetail.sources.fields.name')}
                value={form.name}
                onChange={(event) => patchForm({ name: event.target.value })}
              />
            </div>
            <div className="mrow">
              <label>{t('console.knowDetail.sources.fields.kind')}</label>
              <div>
                <select
                  className="input"
                  aria-label={t('console.knowDetail.sources.fields.kind')}
                  value={form.kind}
                  disabled={form.mode === 'edit'}
                  onChange={(event) => changeKind(event.target.value)}
                >
                  {connectors.map((entry) => (
                    <option key={entry.kind} value={entry.kind}>
                      {entry.label}
                    </option>
                  ))}
                </select>
                {activeConnector && (
                  <span className="dimmer" style={{ display: 'block', fontSize: 11, marginTop: 4 }}>
                    {activeConnector.description}
                  </span>
                )}
              </div>
            </div>

            {activeConnector?.fields.map((field) => (
              <div className="mrow" key={field.key}>
                <label>
                  {field.label}
                  {field.required && ' *'}
                  {field.help && <small>{field.help}</small>}
                </label>
                <ConnectorFieldInput
                  field={field}
                  value={form.fields[field.key]}
                  onChange={(value) => setField(field.key, value)}
                />
              </div>
            ))}

            {needsSecret && activeConnector && (
              <div className="mrow">
                <label>
                  {t('console.knowDetail.sources.fields.secret')}
                  {activeConnector.secret === 'required' && ' *'}
                  {activeConnector.secret_help && <small>{activeConnector.secret_help}</small>}
                </label>
                <div>
                  <select
                    className="input"
                    aria-label={t('console.knowDetail.sources.fields.secret')}
                    value={form.secretId}
                    onChange={(event) => patchForm({ secretId: event.target.value })}
                  >
                    <option value="">
                      {activeConnector.secret === 'required'
                        ? t('console.knowDetail.sources.fields.secretPick')
                        : t('console.knowDetail.sources.fields.secretNone')}
                    </option>
                    {secrets.map((secret) => (
                      <option key={secret.id} value={secret.id}>
                        {secret.name}
                      </option>
                    ))}
                  </select>
                  <a
                    href="/govern/secrets"
                    className="dimmer"
                    style={{ display: 'inline-block', fontSize: 11, marginTop: 4 }}
                    onClick={(event) => {
                      event.preventDefault()
                      navigate('/govern/secrets')
                    }}
                  >
                    {t('console.knowDetail.sources.fields.manageSecrets')}
                  </a>
                </div>
              </div>
            )}

            <div className="mrow">
              <label>{t('console.knowDetail.sources.fields.schedule')}</label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <select
                  className="input"
                  aria-label={t('console.knowDetail.sources.fields.schedule')}
                  value={form.preset}
                  onChange={(event) => patchForm({ preset: event.target.value })}
                >
                  {SCHEDULE_PRESETS.map((preset) => (
                    <option key={preset.key} value={preset.key}>
                      {t(preset.labelKey)}
                    </option>
                  ))}
                  <option value={CUSTOM_SCHEDULE}>{t('console.knowDetail.sources.schedule.custom')}</option>
                </select>
                {form.preset === CUSTOM_SCHEDULE && (
                  <input
                    className="input"
                    aria-label={t('console.knowDetail.sources.fields.cron')}
                    placeholder="*/30 * * * *"
                    value={form.cron}
                    onChange={(event) => patchForm({ cron: event.target.value })}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
                  />
                )}
                {form.preset === CUSTOM_SCHEDULE && (
                  <span className="dimmer" style={{ fontSize: 11 }}>
                    {t('console.knowDetail.sources.fields.cronHint')}
                  </span>
                )}
              </div>
            </div>
            {form.preset !== 'manual' && (
              <div className="mrow">
                <label>
                  {t('console.knowDetail.sources.fields.timezone')}
                  <small>{t('console.knowDetail.sources.fields.timezoneHint')}</small>
                </label>
                <input
                  className="input"
                  aria-label={t('console.knowDetail.sources.fields.timezone')}
                  value={form.timezone}
                  onChange={(event) => patchForm({ timezone: event.target.value })}
                  style={{ maxWidth: 240 }}
                />
              </div>
            )}

            <div className="mrow">
              <label>{t('console.knowDetail.sources.fields.deleteRemoved')}</label>
              <div className="checks">
                <label>
                  <input
                    type="checkbox"
                    checked={form.deleteRemoved}
                    onChange={(event) => patchForm({ deleteRemoved: event.target.checked })}
                  />
                  {t('console.knowDetail.sources.fields.deleteRemovedHint')}
                </label>
              </div>
            </div>
            <div className="mrow">
              <label>{t('console.knowDetail.sources.fields.enabled')}</label>
              <div className="checks">
                <label>
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={(event) => patchForm({ enabled: event.target.checked })}
                  />
                  {t('console.knowDetail.sources.fields.enabledHint')}
                </label>
              </div>
            </div>
            <div className="mrow">
              <label>
                {t('console.knowDetail.sources.fields.limits')}
                <small>{t('console.knowDetail.sources.fields.limitsHint')}</small>
              </label>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(
                  [
                    ['maxItems', 'maxItems'],
                    ['maxItemMb', 'maxItemMb'],
                    ['maxTotalMb', 'maxTotalMb'],
                  ] as const
                ).map(([key, label]) => (
                  <input
                    key={key}
                    className="input"
                    type="number"
                    min={1}
                    placeholder={t(`console.knowDetail.sources.fields.${label}`)}
                    aria-label={t(`console.knowDetail.sources.fields.${label}`)}
                    value={form.limits[key]}
                    onChange={(event) =>
                      patchForm({ limits: { ...form.limits, [key]: event.target.value } })
                    }
                    style={{ width: 150 }}
                  />
                ))}
              </div>
            </div>

            <div className="mrow">
              <label />
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <ConsoleButton
                  style={{ alignSelf: 'flex-start' }}
                  disabled={draftTestMutation.isPending || missing.length > 0 || secretMissing || !activeConnector}
                  onClick={() => draftTestMutation.mutate(undefined)}
                >
                  {draftTestMutation.isPending
                    ? t('console.knowDetail.sources.testing.running')
                    : t('console.knowDetail.sources.testing.button')}
                </ConsoleButton>
                {draftTest && <TestResult result={draftTest} />}
              </div>
            </div>
          </>
        )}
      </ConsoleModal>

      <ConsoleModal
        open={rowTest != null}
        onOpenChange={(open) => !open && setRowTest(null)}
        title={t('console.knowDetail.sources.testing.button')}
        note={rowTest?.name}
        confirmLabel={t('console.knowDetail.sources.close')}
        onConfirm={() => setRowTest(null)}
      >
        <div style={{ padding: '8px 16px 12px' }}>{rowTest && <TestResult result={rowTest.result} />}</div>
      </ConsoleModal>

      <ConsoleModal
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('console.knowDetail.sources.deleteTitle')}
        confirmLabel={t('console.knowDetail.sources.del')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.knowDetail.sources.deleteConfirm', { name: deleting?.name ?? '' })}
        </div>
      </ConsoleModal>

      <SyncHistoryModal
        knowledgeId={knowledgeId}
        source={historyOf}
        onClose={() => setHistoryOf(null)}
        onChanged={refresh}
      />
    </>
  )
}

function ConnectorFieldInput({
  field,
  value,
  onChange,
}: {
  field: KnowledgeConnector['fields'][number]
  value: string | boolean | undefined
  onChange: (value: string | boolean) => void
}) {
  switch (field.type) {
    case 'boolean':
      return (
        <div className="checks">
          <label>
            <input
              type="checkbox"
              aria-label={field.label}
              checked={value === true}
              onChange={(event) => onChange(event.target.checked)}
            />
            {field.label}
          </label>
        </div>
      )
    case 'string_list':
    case 'text':
      return (
        <textarea
          className="input"
          aria-label={field.label}
          rows={field.type === 'string_list' ? 3 : 4}
          placeholder={field.placeholder ?? undefined}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5, resize: 'vertical' }}
        />
      )
    case 'select':
      return (
        <select
          className="input"
          aria-label={field.label}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
        >
          {field.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      )
    case 'integer':
      return (
        <input
          className="input"
          type="number"
          aria-label={field.label}
          min={field.minimum ?? undefined}
          max={field.maximum ?? undefined}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
          style={{ maxWidth: 160 }}
        />
      )
    default:
      return (
        <input
          className="input"
          aria-label={field.label}
          placeholder={field.placeholder ?? undefined}
          value={typeof value === 'string' ? value : ''}
          onChange={(event) => onChange(event.target.value)}
        />
      )
  }
}

function TestResult({ result }: { result: KnowledgeSourceTestResult }) {
  const { t } = useTranslation()
  return (
    <div data-testid="source-test-result" style={{ fontSize: 12, lineHeight: 1.55 }}>
      <StatusChip
        status={result.ok ? 'pass' : 'failed'}
        label={t(result.ok ? 'console.knowDetail.sources.testing.ok' : 'console.knowDetail.sources.testing.failed')}
      />
      <div className={result.ok ? 'dim' : undefined} style={{ marginTop: 6, color: result.ok ? undefined : 'var(--danger-foreground)' }}>
        {result.message}
      </div>
      {result.ok && (
        <div style={{ marginTop: 8 }}>
          <span className="dimmer" style={{ fontSize: 11 }}>
            {t('console.knowDetail.sources.testing.sample')}
          </span>
          {result.sample.length === 0 ? (
            <div className="dimmer">{t('console.knowDetail.sources.testing.sampleNone')}</div>
          ) : (
            <ul className="mono dim" style={{ margin: '4px 0 0', paddingLeft: 16, fontSize: 11 }}>
              {result.sample.map((item) => (
                <li key={item.external_id}>{item.external_id}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

const HISTORY_POLL_MS = 3000

function SyncHistoryModal({
  knowledgeId,
  source,
  onClose,
  onChanged,
}: {
  knowledgeId: string
  source: KnowledgeSource | null
  onClose: () => void
  onChanged: () => void
}) {
  const { t } = useTranslation()
  const [selected, setSelected] = useState<string | null>(null)
  const sourceId = source?.id ?? ''

  const runsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'sources', knowledgeId, sourceId, 'runs'],
    queryFn: () => listKnowledgeSyncRuns(knowledgeId, sourceId, { limit: 20 }),
    options: {
      enabled: Boolean(sourceId),
      retry: false,
      refetchOnWindowFocus: false,
      refetchInterval: (query) =>
        (query.state.data as KnowledgeSyncRun[] | undefined)?.some(isActiveRun) ? HISTORY_POLL_MS : false,
    },
  })
  const runs = runsQuery.data || []
  const detailQuery = useQuery({
    queryKey: ['console', 'knowledge', 'sources', knowledgeId, sourceId, 'run', selected],
    queryFn: () => getKnowledgeSyncRun(knowledgeId, sourceId, selected!),
    options: { enabled: Boolean(sourceId && selected), retry: false, refetchOnWindowFocus: false },
  })
  const detail = detailQuery.data

  const cancelMutation = useMutation<unknown, unknown, KnowledgeSyncRun>({
    mutationKey: ['console', 'knowledge', 'source', 'cancel', knowledgeId],
    mutationFn: (run) => cancelKnowledgeSyncRun(knowledgeId, sourceId, run.id),
    onSuccess: () => {
      void runsQuery.refetch()
      onChanged()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, t('console.knowDetail.sources.errors.cancel')))
    },
  })

  const close = () => {
    setSelected(null)
    onClose()
  }

  return (
    <ConsoleModal
      open={source != null}
      onOpenChange={(open) => !open && close()}
      className="console-modal-wide"
      title={`${t('console.knowDetail.sources.historyTitle')} · ${source?.name ?? ''}`}
      note={t('console.knowDetail.sources.historyNote')}
      confirmLabel={t('console.knowDetail.sources.close')}
      onConfirm={close}
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>{t('console.knowDetail.sources.historyColumns.started')}</TableHead>
            <TableHead>{t('console.knowDetail.sources.historyColumns.trigger')}</TableHead>
            <TableHead>{t('console.knowDetail.sources.historyColumns.status')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.added')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.updated')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.unchanged')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.removed')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.failed')}</TableHead>
            <TableHead className="num">{t('console.knowDetail.sources.historyColumns.took')}</TableHead>
            <TableHead className="num" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {runs.length === 0 ? (
            <DataStateRow
              colSpan={10}
              isPending={runsQuery.isPending}
              isError={runsQuery.isError}
              emptyLabel={t('console.knowDetail.sources.historyEmpty')}
            />
          ) : (
            runs.map((run) => (
              <TableRow
                key={run.id}
                data-testid="sync-run-row"
                className="rowlink"
                onClick={() => setSelected(selected === run.id ? null : run.id)}
              >
                <TableCell className="dim">{relativeTime(run.started_at ?? run.created_at)}</TableCell>
                <TableCell className="dim">
                  {run.trigger === 'schedule'
                    ? t('console.knowDetail.sources.triggers.schedule')
                    : t('console.knowDetail.sources.triggers.manual')}
                </TableCell>
                <TableCell>
                  <StatusChip status={syncRunStatus(run.status)} />
                  {run.cancel_requested && isActiveRun(run) && (
                    <span className="dimmer" style={{ marginLeft: 6, fontSize: 11 }}>
                      {t('console.knowDetail.sources.cancelRequested')}
                    </span>
                  )}
                </TableCell>
                <TableCell className="num dim">{run.added_count}</TableCell>
                <TableCell className="num dim">{run.updated_count}</TableCell>
                <TableCell className="num dim">{run.unchanged_count}</TableCell>
                <TableCell className="num dim">{run.removed_count}</TableCell>
                <TableCell className="num dim">{run.failed_count}</TableCell>
                <TableCell className="num dimmer">{runDuration(run)}</TableCell>
                <TableCell className="num" onClick={(event) => event.stopPropagation()}>
                  {isActiveRun(run) && !run.cancel_requested && (
                    <ConsoleButton
                      variant="ghost"
                      size="sm"
                      disabled={cancelMutation.isPending}
                      onClick={() => cancelMutation.mutate(run)}
                    >
                      {t('console.knowDetail.sources.cancel')}
                    </ConsoleButton>
                  )}
                </TableCell>
              </TableRow>
            ))
          )}
        </TableBody>
      </Table>

      {selected && detail && (
        <div data-testid="sync-run-detail" style={{ padding: '10px 16px 12px', fontSize: 12, lineHeight: 1.55 }}>
          {detail.error_message && (
            <div style={{ color: 'var(--danger-foreground)', marginBottom: 6 }}>
              {detail.error_code ? `${detail.error_code}: ` : ''}
              {detail.error_message}
            </div>
          )}
          {detail.truncated && <div className="dimmer">{t('console.knowDetail.sources.detail.truncated')}</div>}
          {detail.skipped_count > 0 && (
            <div className="dimmer">
              {t('console.knowDetail.sources.detail.skipped', { count: detail.skipped_count })}
            </div>
          )}
          <div className="dimmer" style={{ marginTop: 6, fontSize: 11 }}>
            {t('console.knowDetail.sources.detail.outcomes')}
          </div>
          {detail.outcomes.length === 0 ? (
            <div className="dimmer">{t('console.knowDetail.sources.detail.none')}</div>
          ) : (
            <ul className="mono" style={{ margin: '4px 0 0', paddingLeft: 0, listStyle: 'none', fontSize: 11 }}>
              {detail.outcomes.map((outcome) => (
                <li key={`${outcome.outcome}:${outcome.external_id}`} style={{ display: 'flex', gap: 8 }}>
                  <span style={{ minWidth: 64 }} className={outcome.outcome === 'failed' ? undefined : 'dim'}>
                    {outcome.outcome}
                  </span>
                  <span style={{ flex: 1, wordBreak: 'break-all' }}>{outcome.external_id}</span>
                  {(outcome.error || outcome.detail) && (
                    <span
                      className="dimmer"
                      style={{ color: outcome.error ? 'var(--danger-foreground)' : undefined }}
                    >
                      {outcome.error || outcome.detail}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </ConsoleModal>
  )
}
