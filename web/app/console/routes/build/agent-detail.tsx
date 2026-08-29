import { useEffect, useMemo, useState } from 'react'

import { useParams } from 'react-router'
import { toast } from 'sonner'

import {
  Backlink,
  CodeBlock,
  ConsoleButton,
  ConsoleModal,
  DataStateNote,
  IconExport,
  KeyValueList,
  StatTile,
  StatTileGrid,
  StatusChip,
  WorkbenchPanel,
  runStatusToConsole,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { catColor, compactNumber, latency, percent, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  createAgentVersion,
  deleteAgent,
  getAgent,
  getAgentWorkbenchItems,
  listAgentBindings,
  listAgentReleases,
  listAgentVersions,
  publishAgentVersion,
  updateAgent,
  type AgentVersion,
  type AgentVersionCreateRequest,
} from '@/services/agent-service'
import {
  getCapabilityPluginSourceLabel,
  getCapabilitySourceLabel,
  listAgentCapabilities,
  type AgentCapabilityItem,
} from '@/services/capability-service'
import { listRuns } from '@/services/run-service'
import { requestErrorMessage } from '@/utils/request'

type AgentTab = 'build' | 'monitor' | 'publish' | 'settings'

/**
 * `spec_json` is the soit agent runtime spec (agent_spec.schema.json):
 * { runtime, system_prompt, temperature, planner, bindings: { model_ref,
 * knowledge_refs, tool_refs, workflow_refs, skill_refs }, memory, limits,
 * policies }.
 */
function readSpec(version?: AgentVersion | null): Record<string, any> {
  const spec = version?.spec_json
  return spec && typeof spec === 'object' ? (spec as Record<string, any>) : {}
}

function readRecord(value: unknown): Record<string, any> {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as Record<string, any>) : {}
}

/** Editable form fields render the stored value, or blank when the spec omits it. */
function fieldValue(value: unknown): string {
  if (value == null || value === '') return ''
  return String(value)
}

/** A blank or unparseable box means "not set", never zero. */
function numberField(value: string): number | undefined {
  const trimmed = value.trim()
  if (!trimmed) return undefined
  const parsed = Number(trimmed)
  return Number.isFinite(parsed) ? parsed : undefined
}

function intField(value: string): number | undefined {
  const parsed = numberField(value)
  return parsed == null ? undefined : Math.round(parsed)
}

/** The timeout box reads back as the prototype writes it: `30s per run`, or `30`. */
function secondsField(value: string): number | undefined {
  const match = value.trim().match(/^\d+(?:\.\d+)?/)
  if (!match) return undefined
  const parsed = Math.round(Number(match[0]))
  return parsed >= 1 ? parsed : undefined
}

/**
 * Spec values the console has no control for are carried into the next
 * version rather than dropped — a draft save must not quietly reset limits
 * and policies the console never showed.
 */
function carryNumber(value: unknown): number | undefined {
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

function carryString(value: unknown): string | undefined {
  return typeof value === 'string' && value ? value : undefined
}

function carryRefs(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

/** The prototype's model list; no model-catalogue endpoint drives it yet. */
const MODEL_OPTIONS = ['claude-sonnet-5', 'claude-haiku-4.5', 'qwen3-235b']

interface DraftState {
  /** Agent-record fields — saved with `updateAgent`. */
  name: string
  description: string
  /** Version-spec fields — saved by creating a new `AgentVersion`. */
  modelRef: string
  temperature: string
  maxTokens: string
  systemPrompt: string
  budget: string
  timeout: string
  toolRefs: string[]
  skillRefs: string[]
  knowledgeRefs: string[]
}

const EMPTY_DRAFT: DraftState = {
  name: '',
  description: '',
  modelRef: '',
  temperature: '',
  maxTokens: '',
  systemPrompt: '',
  budget: '',
  timeout: '',
  toolRefs: [],
  skillRefs: [],
  knowledgeRefs: [],
}

function toggleRef(refs: string[], ref: string): string[] {
  return refs.includes(ref) ? refs.filter((item) => item !== ref) : [...refs, ref]
}

function formatDuration(ms?: number | null): string {
  if (ms == null) return '—'
  if (ms >= 60_000) return `${(ms / 60_000).toFixed(1)}m`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatStarted(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

/** Nearest-rank percentile over the durations of the runs actually fetched. */
function percentileMs(values: number[], p: number): number | null {
  if (values.length === 0) return null
  const sorted = [...values].sort((a, b) => a - b)
  const rank = Math.ceil((p / 100) * sorted.length) - 1
  return sorted[Math.min(sorted.length - 1, Math.max(0, rank))]
}

interface CapabilityRow {
  ref: string
  name: string
  detail: string
  bound: boolean
}

/**
 * The pickable catalog for one capability kind, with the boxes that this
 * version actually binds checked. A binding whose ref is no longer in the
 * catalog (uninstalled plugin, archived knowledge base) is still listed so the
 * grant stays visible rather than silently disappearing.
 */
function capabilityRows(
  kind: string,
  catalog: AgentCapabilityItem[],
  boundRefs: Set<string>,
  detailOf: (item: AgentCapabilityItem) => string,
): CapabilityRow[] {
  const rows = catalog
    .filter((item) => item.kind === kind)
    .map((item) => ({
      ref: item.ref,
      name: item.name || item.ref,
      detail: detailOf(item),
      bound: boundRefs.has(item.ref),
    }))
  const known = new Set(rows.map((row) => row.ref))
  for (const ref of boundRefs) {
    if (!known.has(ref)) rows.push({ ref, name: ref, detail: '', bound: true })
  }
  return rows
}

// BACKEND-PENDING: no per-run cost on the run record (/runs/costs/* only
// aggregates across a filter set), no per-agent spend total, and the agent
// record carries no trigger, output schema, rate limit, retry policy,
// on-failure target, budget-alert threshold, or governance bundle/gate/review
// fields — the "Governance preview" rail and those inputs have nothing to read.
// Everything else comes from agent-service (/agents/{id}, /versions, /releases,
// /bindings, /workbench/items), capability-service (/agents/capabilities) and
// run-service (/runs).
export default function ConsoleAgentDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<AgentTab>('build')
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT)
  const [publishTarget, setPublishTarget] = useState<AgentVersion | null>(null)
  const [deleting, setDeleting] = useState(false)

  const agentId = id && id !== 'new' ? id : undefined
  const enabled = Boolean(agentId)

  const agentQuery = useQuery({
    queryKey: ['console', 'agent', agentId],
    queryFn: () => getAgent(agentId as string),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const versionsQuery = useQuery({
    queryKey: ['console', 'agent', agentId, 'versions'],
    queryFn: () => listAgentVersions(agentId as string, { page_size: 20 }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const releasesQuery = useQuery({
    queryKey: ['console', 'agent', agentId, 'releases'],
    queryFn: () => listAgentReleases(agentId as string, { page_size: 20 }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const runsQuery = useQuery({
    queryKey: ['console', 'agent', agentId, 'runs'],
    queryFn: () =>
      listRuns({
        subject_kind: 'agent',
        subject_id: agentId,
        include_observe_summary: true,
        page_size: 20,
      }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const workbenchQuery = useQuery({
    queryKey: ['console', 'agents', 'workbench', 'items'],
    queryFn: () => getAgentWorkbenchItems({ page_size: 100 }),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const catalogQuery = useQuery({
    queryKey: ['console', 'agent', 'capabilities'],
    queryFn: () => listAgentCapabilities({ page_size: 200 }),
    options: { retry: false, refetchOnWindowFocus: false, staleTime: 5 * 60 * 1000 },
  })

  const agent = agentQuery.data
  const versions = versionsQuery.data?.items || []
  const releases = releasesQuery.data?.items || []
  const runs = runsQuery.data?.items || []
  const catalog = catalogQuery.data?.items || []

  // Agent versions carry a numeric `version`, so the rail needs no derived ordinal.
  const versionRail = useMemo(() => [...versions].sort((a, b) => b.version - a.version), [versions])

  const currentVersionId = agent?.current_version_id || null
  const publishedVersionId = agent?.published_version_id || null
  const currentVersion =
    versionRail.find((version) => version.id === currentVersionId) || versionRail[0] || null
  const publishedVersion = versionRail.find((version) => version.id === publishedVersionId) || null
  const hasDraftChanges = Boolean(
    currentVersionId && publishedVersionId && currentVersionId !== publishedVersionId,
  )

  /** Versions a release reverted — the only rollback signal the API exposes. */
  const rolledBackVersionIds = useMemo(
    () =>
      new Set(
        releases.filter((release) => release.status === 'rolled_back').map((release) => release.to_version_id),
      ),
    [releases],
  )

  const spec = readSpec(currentVersion)
  const specBindings = readRecord(spec.bindings)
  const limits = readRecord(spec.limits)
  const policies = readRecord(spec.policies)
  const memory = readRecord(spec.memory)
  const memoryPolicy = readRecord(memory.policy)

  // The Build tab edits the current editor state, so bind against that version.
  const bindingsQuery = useQuery({
    queryKey: ['console', 'agent', agentId, 'bindings', currentVersionId],
    queryFn: () =>
      listAgentBindings(agentId as string, currentVersionId ? { version_id: currentVersionId } : undefined),
    options: { enabled, retry: false, refetchOnWindowFocus: false },
  })
  const bindings = bindingsQuery.data || []

  /** Bindings mirror the spec ref lists: binding.target_key === capability.ref. */
  const boundRefs = useMemo(() => {
    const groups: Record<string, Set<string>> = { tool: new Set(), skill: new Set(), knowledge: new Set() }
    for (const binding of bindings) {
      const group = groups[binding.binding_type]
      if (group && binding.target_key) group.add(binding.target_key)
    }
    return groups
  }, [bindings])

  // The editor is seeded from what the server holds, and re-seeded after a
  // save so the boxes show what was actually stored.
  useEffect(() => {
    if (!agent) return
    setDraft((state) => ({
      ...state,
      name: agent.name || '',
      description: agent.description || '',
    }))
  }, [agent])

  useEffect(() => {
    const nextSpec = readSpec(currentVersion)
    const nextBindings = readRecord(nextSpec.bindings)
    const nextLimits = readRecord(nextSpec.limits)
    setDraft((state) => ({
      ...state,
      modelRef: fieldValue(nextBindings.model_ref),
      temperature: fieldValue(nextSpec.temperature),
      maxTokens: fieldValue(nextLimits.max_tokens),
      systemPrompt: fieldValue(nextSpec.system_prompt),
      budget: fieldValue(nextLimits.budget),
      timeout:
        typeof nextLimits.timeout_ms === 'number'
          ? `${Math.round(nextLimits.timeout_ms / 1000)}s per run`
          : '',
    }))
  }, [currentVersion])

  useEffect(() => {
    if (!bindingsQuery.data) return
    setDraft((state) => ({
      ...state,
      toolRefs: [...boundRefs.tool],
      skillRefs: [...boundRefs.skill],
      knowledgeRefs: [...boundRefs.knowledge],
    }))
  }, [bindingsQuery.data, boundRefs])

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  /**
   * A version is immutable, so "Save draft" writes a whole new one. Every
   * `AgentVersionCreate` field the console can reach is sent; the rest is
   * carried over from the version being edited.
   *
   * `rag_top_k`, `rag_strategy`, `context_window_messages` and
   * `context_window_chars` are accepted by the API but absent from
   * `AgentVersionCreateRequest`, so they cannot be carried through from here.
   */
  const buildVersionRequest = (): AgentVersionCreateRequest => ({
    system_prompt: draft.systemPrompt.trim() || undefined,
    temperature: numberField(draft.temperature),
    max_tokens_total: intField(draft.maxTokens),
    max_cost: numberField(draft.budget),
    max_runtime_seconds: secondsField(draft.timeout),
    max_iterations: carryNumber(limits.max_iterations),
    max_tool_calls: carryNumber(limits.max_tool_calls),
    max_llm_calls: carryNumber(limits.max_llm_calls),
    max_failures: carryNumber(limits.max_failures),
    cost_currency: carryString(policies.cost_currency),
    failure_strategy: carryString(policies.failure_strategy),
    verify: typeof policies.verify === 'boolean' ? policies.verify : undefined,
    memory_strategy: carryString(memory.type),
    memory_top_k: carryNumber(memoryPolicy.top_k),
    bindings: {
      model_ref: draft.modelRef,
      tool_refs: draft.toolRefs,
      skill_refs: draft.skillRefs,
      knowledge_refs: draft.knowledgeRefs,
      // The Build tab has no workflow picker, so the bound workflows are kept
      // as they are rather than being unbound by omission.
      workflow_refs: carryRefs(specBindings.workflow_refs),
    },
  })

  const saveDraftMutation = useMutation({
    mutationKey: ['console', 'agent', agentId, 'save-draft'],
    mutationFn: async () => {
      // Name and description live on the agent record, not the version spec,
      // so they only travel when the user actually changed them.
      const name = draft.name.trim()
      const description = draft.description.trim()
      if (name !== (agent?.name || '') || description !== (agent?.description || '')) {
        await updateAgent(agentId as string, { name, description })
      }
      return createAgentVersion(agentId as string, buildVersionRequest())
    },
    onSuccess: () => {
      void agentQuery.refetch()
      void versionsQuery.refetch()
      void bindingsQuery.refetch()
    },
    onError: onWriteError('Failed to save the draft'),
  })

  const publishMutation = useMutation({
    mutationKey: ['console', 'agent', agentId, 'publish'],
    mutationFn: () =>
      publishAgentVersion(agentId as string, { version_id: (publishTarget as AgentVersion).id }),
    onSuccess: () => {
      setPublishTarget(null)
      void agentQuery.refetch()
      void versionsQuery.refetch()
      void releasesQuery.refetch()
    },
    onError: onWriteError('Failed to publish the version'),
  })

  /** DELETE /agents/{id} only stamps `deleted_at` — the agent is archived. */
  const deleteMutation = useMutation({
    mutationKey: ['console', 'agent', agentId, 'delete'],
    mutationFn: () => deleteAgent(agentId as string),
    onSuccess: () => {
      setDeleting(false)
      void workbenchQuery.refetch()
      navigate('/build/agents')
    },
    onError: onWriteError('Failed to archive the agent'),
  })

  const isPaused = agent?.status === 'disabled'
  const statusMutation = useMutation({
    mutationKey: ['console', 'agent', agentId, 'status'],
    mutationFn: () =>
      updateAgent(agentId as string, { status: isPaused ? 'active' : 'disabled' }),
    onSuccess: () => {
      void agentQuery.refetch()
      void workbenchQuery.refetch()
    },
    onError: onWriteError('Failed to change the agent status'),
  })

  const toolRows = capabilityRows(
    'tool',
    catalog,
    boundRefs.tool,
    (item) => getCapabilityPluginSourceLabel(item) || getCapabilitySourceLabel(item),
  )
  const skillRows = capabilityRows('skill', catalog, boundRefs.skill, (item) =>
    [item.source_version, getCapabilityPluginSourceLabel(item)].filter(Boolean).join(' · '),
  )
  const knowledgeRows = capabilityRows('knowledge', catalog, boundRefs.knowledge, (item) => {
    const metadata = readRecord(item.metadata_json)
    const parts = []
    if (metadata.doc_count != null) parts.push(`${metadata.doc_count} docs`)
    if (metadata.chunk_count != null) parts.push(`${metadata.chunk_count} chunks`)
    return parts.join(' · ')
  })

  const capabilityState = {
    isPending: catalogQuery.isPending || bindingsQuery.isPending,
    isError: catalogQuery.isError || bindingsQuery.isError,
  }

  const workbenchRow = (workbenchQuery.data?.items || []).find((row) => row.id === agentId)
  const durations = runs
    .map((run) => run.duration_ms)
    .filter((value): value is number => typeof value === 'number')
  const p95 = percentileMs(durations, 95)
  const p50 = percentileMs(durations, 50)

  /** The outcome strip reads the fetched runs oldest → newest. */
  const outcomes = useMemo(
    () =>
      [...runs]
        .slice(0, 12)
        .reverse()
        .map((run) => (run.status === 'succeeded' ? 'ok' : run.status === 'failed' ? 'f' : 'd')),
    [runs],
  )

  const name = agent?.name || agentId || '—'

  return (
    <>
      <Backlink to="/build/agents">{t('console.agentDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <span className="chip">
          <i style={{ background: catColor(agentId) }} />
          {publishedVersion ? `v${publishedVersion.version} published` : 'unpublished'}
        </span>
        {hasDraftChanges && <StatusChip status="warn" label="DRAFT CHANGES" />}
        <span className="spacer" />
        <ConsoleButton
          // A version needs a model binding server-side, and the agent record
          // needs a name — neither can be sent blank.
          disabled={
            !agentId || !draft.name.trim() || !draft.modelRef || saveDraftMutation.isPending
          }
          onClick={() => saveDraftMutation.mutate(undefined)}
        >
          {t('console.agentDetail.saveDraft')}
        </ConsoleButton>
        {/* No dry-run endpoint exists for a draft version yet. */}
        <ConsoleButton>{t('console.agentDetail.runTest')}</ConsoleButton>
        <ConsoleButton
          variant="primary"
          disabled={!agentId || !currentVersion}
          onClick={() => currentVersion && setPublishTarget(currentVersion)}
        >
          <IconExport />
          {t('console.agentDetail.publish', {
            version: currentVersion ? `v${currentVersion.version}` : '',
          })}
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
                <input
                  className="input"
                  value={draft.name}
                  onChange={(event) =>
                    setDraft((state) => ({ ...state, name: event.target.value }))
                  }
                />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.description')}</label>
                <input
                  className="input"
                  value={draft.description}
                  onChange={(event) =>
                    setDraft((state) => ({ ...state, description: event.target.value }))
                  }
                />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.trigger')}</label>
                {/* The agent record has no trigger column and the runtime spec
                    carries none either; the option list stays the prototype's
                    and the choice is not saved anywhere. */}
                <select key={`trigger-${agent?.id}`} className="input" style={{ maxWidth: 220 }} defaultValue="">
                  <option>webhook</option>
                  <option>chat</option>
                  <option>schedule</option>
                  <option>api</option>
                </select>
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.model')}</label>
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                  {/* No model-catalogue endpoint drives this select yet; the
                      value comes from the version spec's bindings.model_ref.
                      A stored ref outside the prototype list is listed as-is so
                      saving a draft cannot silently rewrite the binding. */}
                  <select
                    className="input"
                    style={{ maxWidth: 220 }}
                    value={draft.modelRef}
                    onChange={(event) =>
                      setDraft((state) => ({ ...state, modelRef: event.target.value }))
                    }
                  >
                    {!draft.modelRef && <option value="">—</option>}
                    {draft.modelRef && !MODEL_OPTIONS.includes(draft.modelRef) && (
                      <option value={draft.modelRef}>{draft.modelRef}</option>
                    )}
                    {MODEL_OPTIONS.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                  <input
                    className="input"
                    value={draft.temperature}
                    onChange={(event) =>
                      setDraft((state) => ({ ...state, temperature: event.target.value }))
                    }
                    style={{ maxWidth: 90 }}
                    title="temperature"
                  />
                  <input
                    className="input"
                    value={draft.maxTokens}
                    onChange={(event) =>
                      setDraft((state) => ({ ...state, maxTokens: event.target.value }))
                    }
                    style={{ maxWidth: 120 }}
                    title="max output tokens"
                  />
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.fields.systemPrompt')}
                  <small>{t('console.agentDetail.fields.systemPromptHint')}</small>
                </label>
                <textarea
                  className="input"
                  style={{ minHeight: 120 }}
                  value={draft.systemPrompt}
                  onChange={(event) =>
                    setDraft((state) => ({ ...state, systemPrompt: event.target.value }))
                  }
                />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.outputSchema')}</label>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                  {/* The agent spec has no output-schema slot (only workflows
                      carry outputs_schema), so there is nothing to name here. */}
                  <span className="chip">—</span>
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
                  {toolRows.length === 0 ? (
                    <DataStateNote {...capabilityState} />
                  ) : (
                    toolRows.map((row) => (
                      <label key={row.ref}>
                        <input
                          type="checkbox"
                          checked={draft.toolRefs.includes(row.ref)}
                          onChange={() =>
                            setDraft((state) => ({
                              ...state,
                              toolRefs: toggleRef(state.toolRefs, row.ref),
                            }))
                          }
                        />
                        <span className="mono">{row.name}</span> {row.detail}
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.skills')}
                  <small>{t('console.agentDetail.skillsHint')}</small>
                </label>
                <div className="checks">
                  {skillRows.length === 0 ? (
                    <DataStateNote {...capabilityState} />
                  ) : (
                    skillRows.map((row) => (
                      <label key={row.ref}>
                        <input
                          type="checkbox"
                          checked={draft.skillRefs.includes(row.ref)}
                          onChange={() =>
                            setDraft((state) => ({
                              ...state,
                              skillRefs: toggleRef(state.skillRefs, row.ref),
                            }))
                          }
                        />
                        <span className="mono">{row.name}</span> {row.detail}
                      </label>
                    ))
                  )}
                </div>
              </div>
              <div className="frow">
                <label>
                  {t('console.agentDetail.knowledge')}
                  <small>{t('console.agentDetail.knowledgeHint')}</small>
                </label>
                <div className="checks">
                  {knowledgeRows.length === 0 ? (
                    <DataStateNote {...capabilityState} />
                  ) : (
                    knowledgeRows.map((row) => (
                      <label key={row.ref}>
                        <input
                          type="checkbox"
                          checked={draft.knowledgeRefs.includes(row.ref)}
                          onChange={() =>
                            setDraft((state) => ({
                              ...state,
                              knowledgeRefs: toggleRef(state.knowledgeRefs, row.ref),
                            }))
                          }
                        />
                        {row.name} <span className="mono dimmer">{row.detail}</span>
                      </label>
                    ))
                  )}
                </div>
              </div>
            </WorkbenchPanel>
          </div>

          <div className="rail">
            <WorkbenchPanel title={t('console.agentDetail.governance')}>
              {/* No policy-bundle, gate-preview, publish-review or secret-scope
                  field exists on the agent, its version spec, or its releases. */}
              <KeyValueList
                items={[
                  { key: 'Policy bundle', value: '—' },
                  { key: 'Gates that apply', value: '—' },
                  { key: 'Publish review', value: '—' },
                  { key: 'Secrets', value: '—' },
                ]}
              />
            </WorkbenchPanel>
            <WorkbenchPanel title={t('console.agentDetail.budget')}>
              <div className="frow" style={{ gridTemplateColumns: '1fr', gap: 5 }}>
                <label>{t('console.agentDetail.dailyCap')}</label>
                {/* spec.limits.budget is the per-run cost ceiling — the only
                    budget number the spec carries; there is no daily window. */}
                <input
                  className="input"
                  value={draft.budget}
                  onChange={(event) =>
                    setDraft((state) => ({ ...state, budget: event.target.value }))
                  }
                  style={{ maxWidth: 120 }}
                />
              </div>
              <div className="frow" style={{ gridTemplateColumns: '1fr', gap: 5 }}>
                <label>{t('console.agentDetail.alertAt')}</label>
                {/* No budget-alert threshold is stored anywhere, so this
                    select has nothing to save into. */}
                <select className="input" style={{ maxWidth: 120 }} defaultValue="">
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
            <StatTile
              label="Runs · 24h"
              value={workbenchRow ? compactNumber(workbenchRow.today_calls) : '—'}
              na={!workbenchRow}
              sub={<span className="mono dimmer">today</span>}
            />
            <StatTile
              label="Pass rate"
              value={workbenchRow ? percent(workbenchRow.success_rate) : '—'}
              na={!workbenchRow}
              sub={
                <span className="mono dimmer">
                  {workbenchRow ? `${workbenchRow.recent_exception_count} exceptions` : '—'}
                </span>
              }
            />
            {/* No per-agent spend total: /runs/costs/* reports token and time
                counters, and only a run detail carries a currency amount. */}
            <StatTile label="Spend · 24h" value="—" na sub={<span className="mono dimmer">—</span>} />
            <StatTile
              label="P95 duration"
              value={p95 == null ? '—' : latency(p95)}
              na={p95 == null}
              sub={<span className="mono dimmer">p50 {p50 == null ? '—' : latency(p50)}</span>}
            />
          </StatTileGrid>
          <WorkbenchPanel
            title={t('console.agentDetail.monitorRecent', { name })}
            actions={
              <a
                className="more"
                href="/observe/runs"
                onClick={(event) => {
                  event.preventDefault()
                  navigate('/observe/runs')
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
                {runs.length === 0 ? (
                  <tr>
                    <td colSpan={8}>
                      <DataStateNote isPending={runsQuery.isPending} isError={runsQuery.isError} />
                    </td>
                  </tr>
                ) : (
                  runs.map((run) => {
                    const observed = run.observe_summary
                    return (
                      <tr key={run.id} className="rowlink" onClick={() => navigate(`/observe/runs/${run.id}`)}>
                        <td>
                          <span className="runid">{run.id}</span>
                        </td>
                        <td className="dim">{run.mode}</td>
                        <td>
                          <span className="mono dimmer" style={{ fontSize: 10.5 }}>
                            {observed
                              ? `${observed.step_count} st · ${observed.tool_call_count} tool · ${observed.citation_count} cit · ${observed.audit_count} aud`
                              : '—'}
                          </span>
                        </td>
                        <td>
                          {/* Runs record audit entries, not gate pass/total. */}
                          <span className="mono dimmer">
                            {observed ? `${observed.audit_count} audits` : '—'}
                          </span>
                        </td>
                        <td className="num dim">{formatDuration(run.duration_ms)}</td>
                        {/* Per-run cost is not on the run record. */}
                        <td className="num dim">—</td>
                        <td>
                          <StatusChip status={runStatusToConsole(run.status)} />
                        </td>
                        <td className="num dimmer">{formatStarted(run.started_at)}</td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.agentDetail.lastOutcomes')}</span>
              <span className="hist" style={{ marginLeft: 10 }} aria-label={t('console.agentDetail.lastOutcomes')}>
                {outcomes.map((outcome, index) => (
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
          {versionRail.length === 0 ? (
            <DataStateNote isPending={versionsQuery.isPending} isError={versionsQuery.isError} />
          ) : (
            versionRail.map((version) => {
              const isPublished = version.id === publishedVersionId
              const isCurrent = version.id === currentVersionId
              const wasRolledBack = rolledBackVersionIds.has(version.id)
              return (
                <a
                  key={version.id}
                  className={cn('bundle', isPublished && 'on')}
                  onClick={() => !isPublished && setPublishTarget(version)}
                >
                  <b>
                    v{version.version}{' '}
                    <StatusChip
                      status={
                        isPublished
                          ? 'published'
                          : isCurrent
                            ? 'draft'
                            : wasRolledBack
                              ? 'rolled_back'
                              : 'info'
                      }
                    />
                  </b>
                  <small>
                    {version.status} · {version.created_by || '—'} · {relativeTime(version.created_at)} ·{' '}
                    {version.id}
                  </small>
                </a>
              )
            })
          )}
          <CodeBlock
            style={{ borderRadius: '0 0 10px 10px' }}
            command={`soit agent publish ${name}${currentVersion ? `@v${currentVersion.version}` : ''}`}
            output={`${bindings.length} bindings · ${releases.length} releases · runs switch on next trigger`}
          />
        </WorkbenchPanel>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel title={t('console.agentDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.owner')}</label>
            {/* `created_by` / `updated_by` are server-stamped audit columns and
                are not on `AgentUpdate`; this box cannot be saved. */}
            <input
              key={`owner-${agent?.id}`}
              className="input"
              defaultValue={agent?.updated_by || agent?.created_by || ''}
              style={{ maxWidth: 200 }}
            />
          </div>
          <div className="frow">
            <label>
              {t('console.agentDetail.settingsFields.channel')}
              <small>{t('console.agentDetail.settingsFields.channelHint')}</small>
            </label>
            {/* There is no channel column; an agent is callable in production
                exactly when it has a published version. */}
            <select
              key={`channel-${agent?.id}`}
              className="input"
              style={{ maxWidth: 240 }}
              defaultValue={publishedVersionId ? 'production' : 'draft only'}
            >
              <option>production</option>
              <option>draft only</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.rateLimit')}</label>
            {/* No rate-limit field on the agent or its spec — nothing to save. */}
            <input className="input" defaultValue="" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.retry')}</label>
            {/* No retry policy is stored; spec.limits.max_failures is a failure
                budget for a single run, not a retry schedule. Not saved. */}
            <input className="input" defaultValue="" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.timeout')}</label>
            {/* This one is real: spec.limits.timeout_ms. It is part of the
                version spec, so it ships with "Save draft" like the rest. */}
            <input
              className="input"
              value={draft.timeout}
              onChange={(event) =>
                setDraft((state) => ({ ...state, timeout: event.target.value }))
              }
              style={{ maxWidth: 200 }}
            />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.onFailure')}</label>
            {/* No notification target is stored on the agent — nothing to save. */}
            <input className="input" defaultValue="" style={{ maxWidth: 260 }} />
          </div>
          <div className="frow">
            <label style={{ color: 'var(--danger-foreground)' }}>
              {t('console.agentDetail.settingsFields.danger')}
              <small>{t('console.agentDetail.settingsFields.dangerHint')}</small>
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <ConsoleButton
                disabled={!agentId || statusMutation.isPending}
                onClick={() => statusMutation.mutate(undefined)}
              >
                {isPaused
                  ? t('console.agentDetail.settingsFields.resume')
                  : t('console.agentDetail.settingsFields.pause')}
              </ConsoleButton>
              <ConsoleButton
                style={{ color: 'var(--danger-foreground)' }}
                disabled={!agentId}
                onClick={() => setDeleting(true)}
              >
                {t('console.agentDetail.settingsFields.archive')}
              </ConsoleButton>
            </div>
          </div>
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={publishTarget != null}
        onOpenChange={(open) => !open && setPublishTarget(null)}
        title={t('console.agentDetail.publishTitle')}
        note={t('console.agentDetail.publishNote')}
        confirmLabel={t('console.agentDetail.publishAction')}
        busy={publishMutation.isPending}
        onConfirm={() => publishMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.agentDetail.publishConfirm', {
            name,
            version: publishTarget ? `v${publishTarget.version}` : '',
          })}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deleting}
        onOpenChange={setDeleting}
        title={t('console.agentDetail.archiveTitle')}
        note={t('console.agentDetail.archiveNote')}
        confirmLabel={t('console.agentDetail.settingsFields.archive')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.agentDetail.archiveConfirm', { name })}
        </div>
      </ConsoleModal>
    </>
  )
}
