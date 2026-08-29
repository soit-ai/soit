import { useMemo, useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  ConsoleButton,
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
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  getAgent,
  getAgentWorkbenchItems,
  listAgentBindings,
  listAgentReleases,
  listAgentVersions,
  type AgentVersion,
} from '@/services/agent-service'
import {
  getCapabilityPluginSourceLabel,
  getCapabilitySourceLabel,
  listAgentCapabilities,
  type AgentCapabilityItem,
} from '@/services/capability-service'
import { listRuns } from '@/services/run-service'

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
      <Backlink to="/v2/build/agents">{t('console.agentDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <span className="chip">
          <i style={{ background: catColor(agentId) }} />
          {publishedVersion ? `v${publishedVersion.version} published` : 'unpublished'}
        </span>
        {hasDraftChanges && <StatusChip status="warn" label="DRAFT CHANGES" />}
        <span className="spacer" />
        <ConsoleButton>{t('console.agentDetail.saveDraft')}</ConsoleButton>
        <ConsoleButton>{t('console.agentDetail.runTest')}</ConsoleButton>
        <ConsoleButton variant="primary">
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
                <input key={`name-${agent?.id}`} className="input" defaultValue={agent?.name || ''} />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.description')}</label>
                <input
                  key={`desc-${agent?.id}`}
                  className="input"
                  defaultValue={agent?.description || ''}
                />
              </div>
              <div className="frow">
                <label>{t('console.agentDetail.fields.trigger')}</label>
                {/* The agent record has no trigger column and the runtime spec
                    carries none either; the option list stays the prototype's. */}
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
                      value comes from the version spec's bindings.model_ref. */}
                  <select
                    key={`model-${currentVersion?.id}`}
                    className="input"
                    style={{ maxWidth: 220 }}
                    defaultValue={fieldValue(specBindings.model_ref)}
                  >
                    <option>claude-sonnet-5</option>
                    <option>claude-haiku-4.5</option>
                    <option>qwen3-235b</option>
                  </select>
                  <input
                    key={`temp-${currentVersion?.id}`}
                    className="input"
                    defaultValue={fieldValue(spec.temperature)}
                    style={{ maxWidth: 90 }}
                    title="temperature"
                  />
                  <input
                    key={`maxtok-${currentVersion?.id}`}
                    className="input"
                    defaultValue={fieldValue(limits.max_tokens)}
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
                  key={`prompt-${currentVersion?.id}`}
                  className="input"
                  style={{ minHeight: 120 }}
                  defaultValue={fieldValue(spec.system_prompt)}
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
                        <input type="checkbox" defaultChecked={row.bound} />
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
                        <input type="checkbox" defaultChecked={row.bound} />
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
                        <input type="checkbox" defaultChecked={row.bound} />
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
                  key={`budget-${currentVersion?.id}`}
                  className="input"
                  defaultValue={fieldValue(limits.budget)}
                  style={{ maxWidth: 120 }}
                />
              </div>
              <div className="frow" style={{ gridTemplateColumns: '1fr', gap: 5 }}>
                <label>{t('console.agentDetail.alertAt')}</label>
                {/* No budget-alert threshold is stored anywhere. */}
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
                      <tr key={run.id} className="rowlink" onClick={() => navigate(`/v2/observe/runs/${run.id}`)}>
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
                <a key={version.id} className={cn('bundle', isPublished && 'on')}>
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
            {/* No rate-limit field on the agent or its spec. */}
            <input className="input" defaultValue="" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.retry')}</label>
            {/* No retry policy is stored; spec.limits.max_failures is a failure
                budget for a single run, not a retry schedule. */}
            <input className="input" defaultValue="" style={{ maxWidth: 200 }} />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.timeout')}</label>
            <input
              key={`timeout-${currentVersion?.id}`}
              className="input"
              defaultValue={
                typeof limits.timeout_ms === 'number' ? `${Math.round(limits.timeout_ms / 1000)}s per run` : ''
              }
              style={{ maxWidth: 200 }}
            />
          </div>
          <div className="frow">
            <label>{t('console.agentDetail.settingsFields.onFailure')}</label>
            {/* No notification target is stored on the agent. */}
            <input className="input" defaultValue="" style={{ maxWidth: 260 }} />
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
