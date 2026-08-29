import { Suspense, lazy, useMemo, useState } from 'react'

import { useParams } from 'react-router'

import {
  Backlink,
  CodeBlock,
  ConsoleButton,
  DataStateNote,
  IconExport,
  StatusChip,
  WorkbenchPanel,
  runStatusToConsole,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { listRuns } from '@/services/run-service'
import {
  getCurrentWorkflowVersionOrNull,
  getWorkflow,
  getWorkflowCapabilities,
  listWorkflowVersions,
} from '@/services/workflow-service'

type WfTab = 'build' | 'monitor' | 'publish' | 'settings'

/**
 * The Build tab hosts the real interactive editor (ReactFlow canvas, node
 * library, properties panel) shared with the legacy `/workflow/:id/build` page.
 * It is lazy so `@xyflow/react`, dagre and the node registry never reach the
 * console's initial JavaScript — the other three tabs load without them.
 */
const WorkflowBuilderCanvas = lazy(() => import('./workflow-builder-canvas'))

interface GraphNode {
  id: string
  type: string
  name: string
  params: Record<string, unknown>
  x: number
  y: number
}

interface GraphEdge {
  id: string
  from: string
  to: string
  condition?: string
}

/**
 * `graph_json` is the soit workflow spec: { name, description, policy, graph:
 * { nodes, edges } } where each node carries { id, type, name, params, ui:
 * { position } } and each edge { id, from, to, condition }.
 */
function readGraph(graphJson: Record<string, any> | undefined) {
  const graph = (graphJson?.graph ?? {}) as { nodes?: any[]; edges?: any[] }
  const nodes: GraphNode[] = (Array.isArray(graph.nodes) ? graph.nodes : []).map(
    (node: any, index: number) => ({
      id: String(node?.id ?? `node-${index}`),
      type: String(node?.type ?? '—'),
      name: String(node?.name ?? node?.id ?? '—'),
      params:
        node?.params && typeof node.params === 'object' ? (node.params as Record<string, unknown>) : {},
      x: Number(node?.ui?.position?.x) || 0,
      y: Number(node?.ui?.position?.y) || 0,
    }),
  )
  const edges: GraphEdge[] = (Array.isArray(graph.edges) ? graph.edges : [])
    .map((edge: any, index: number) => ({
      id: String(edge?.id ?? `edge-${index}`),
      from: String(edge?.from ?? ''),
      to: String(edge?.to ?? ''),
      condition: typeof edge?.condition === 'string' ? edge.condition : undefined,
    }))
    .filter((edge) => edge.from && edge.to)
  return { nodes, edges }
}

function paramString(params: Record<string, unknown>, key: string): string {
  const value = params[key]
  if (value == null) return ''
  return typeof value === 'string' ? value : String(value)
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

// BACKEND-PENDING: per-run cost is not on the run record (only aggregate
// /runs/cost/* endpoints), and there is no publish-validation or legacy-node
// migration-target endpoint. Everything else on this page reads
// workflow-service (/workflows/{id}, /version/current, /versions,
// /capabilities) and run-service (/runs).
export default function ConsoleWorkflowDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<WfTab>('build')

  const workflowId = id && id !== 'new' && id !== 'new-draft' ? id : undefined
  const enabled = Boolean(workflowId)

  const workflowQuery = useQuery({
    queryKey: ['console', 'workflow', workflowId],
    queryFn: () => getWorkflow(workflowId as string),
    options: { retry: false, refetchOnWindowFocus: false, enabled },
  })
  const versionQuery = useQuery({
    queryKey: ['console', 'workflow', workflowId, 'version', 'current'],
    queryFn: () => getCurrentWorkflowVersionOrNull(workflowId as string),
    options: { retry: false, refetchOnWindowFocus: false, enabled },
  })
  const versionsQuery = useQuery({
    queryKey: ['console', 'workflow', workflowId, 'versions'],
    queryFn: () => listWorkflowVersions(workflowId as string, { page_size: 20 }),
    options: { retry: false, refetchOnWindowFocus: false, enabled },
  })
  const capabilitiesQuery = useQuery({
    queryKey: ['console', 'workflow', 'capabilities'],
    queryFn: getWorkflowCapabilities,
    options: { retry: false, refetchOnWindowFocus: false, staleTime: 5 * 60 * 1000 },
  })
  const runsQuery = useQuery({
    queryKey: ['console', 'workflow', workflowId, 'runs'],
    queryFn: () =>
      listRuns({
        mode: 'workflow',
        subject_kind: 'workflow',
        subject_id: workflowId,
        include_observe_summary: true,
        page_size: 20,
      }),
    options: { retry: false, refetchOnWindowFocus: false, enabled },
  })

  const workflow = workflowQuery.data
  const spec = versionQuery.data?.graph_json as Record<string, any> | undefined
  const { nodes, edges } = useMemo(() => readGraph(spec), [spec])

  const legacyTypes = useMemo(
    () => new Set(capabilitiesQuery.data?.compatibility_node_types || []),
    [capabilitiesQuery.data],
  )
  const legacyNodes = nodes.filter((node) => legacyTypes.has(node.type))

  // Versions carry no ordinal; derive a stable v1..vN from creation order so the
  // publish rail reads like the prototype's version ladder.
  const versions = versionsQuery.data?.items || []
  const orderedVersions = useMemo(
    () => [...versions].sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)),
    [versions],
  )
  const ordinalById = useMemo(
    () => new Map(orderedVersions.map((version, index) => [version.id, index + 1])),
    [orderedVersions],
  )
  const versionRail = [...orderedVersions].reverse()

  const publishedVersionId = workflow?.published_version_id || null
  const currentVersionId = workflow?.current_version_id || null
  const publishedOrdinal = publishedVersionId ? ordinalById.get(publishedVersionId) : undefined
  const currentOrdinal = currentVersionId ? ordinalById.get(currentVersionId) : undefined
  const hasDraftChanges = Boolean(
    currentVersionId && publishedVersionId && currentVersionId !== publishedVersionId,
  )

  const name = workflow?.name || workflowId || '—'
  const runs = runsQuery.data?.items || []
  const policyBundle =
    paramString((spec?.policy as Record<string, unknown>) || {}, 'bundle') ||
    paramString((spec?.policy as Record<string, unknown>) || {}, 'version') ||
    '—'

  return (
    <>
      <Backlink to="/build/workflows">{t('console.wfDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{name}</h1>
        <span className="chip">
          <i style={{ background: 'var(--primary)' }} />
          {publishedOrdinal ? `v${publishedOrdinal} published` : 'unpublished'}
        </span>
        {hasDraftChanges && <StatusChip status="warn" label="DRAFT CHANGES" />}
        <span className="spacer" />
        <ConsoleButton>{t('console.wfDetail.validate')}</ConsoleButton>
        <ConsoleButton variant="primary">
          <IconExport />
          {t('console.wfDetail.publish', {
            version: currentOrdinal ? `v${currentOrdinal}` : '',
          })}
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
          {/* Only shown when the current graph really does contain a node whose
              type is in /workflows/capabilities → compatibility_node_types. The
              migration target ("variable-assign@v2") has no endpoint. */}
          {legacyNodes.length > 0 && (
            <div className="warnbar">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 3 2 21h20L12 3ZM12 10v5M12 18.5v.5" />
              </svg>
              <span>
                {t('console.wfDetail.warnbarPrefix', { count: legacyNodes.length })}{' '}
                <span className="mono">{legacyNodes[0].id}</span>{' '}
                {t('console.wfDetail.warnbar')} <span className="mono">variable-assign@v2</span>{' '}
                {t('console.wfDetail.warnbarSuffix')}
              </span>
              <ConsoleButton>{t('console.wfDetail.migrate')}</ConsoleButton>
            </div>
          )}
          {/* The real builder, shared with the legacy page: ReactFlow canvas,
              node library and node properties inside the prototype frame. */}
          <Suspense
            fallback={
              <div className="wfshell wfshell-live">
                <div className="panel palette" />
                <div className="canvas-wrap wfcanvas">
                  <DataStateNote isPending />
                </div>
                <div className="panel inspector" />
              </div>
            }
          >
            <WorkflowBuilderCanvas workflowId={workflowId} />
          </Suspense>
        </>
      )}

      {tab === 'monitor' && (
        <WorkbenchPanel
          title={t('console.wfDetail.monitorTitle', { name })}
          actions={
            <a
              className="more"
              href="/observe/runs"
              onClick={(event) => {
                event.preventDefault()
                navigate('/observe/runs')
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
              {runs.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <DataStateNote isPending={runsQuery.isPending} isError={runsQuery.isError} />
                  </td>
                </tr>
              ) : (
                runs.map((run) => {
                  const warn = Boolean(run.error_code)
                  const audits = run.observe_summary?.audit_count
                  const policy = audits == null ? '—' : `${audits} audits`
                  return (
                    <tr key={run.id} className="rowlink" onClick={() => navigate(`/observe/runs/${run.id}`)}>
                      <td>
                        <span className="runid">{run.id}</span>
                      </td>
                      <td className="dim">{run.mode}</td>
                      <td className="num dim">{run.observe_summary?.step_count ?? '—'}</td>
                      <td>
                        <span className="mono" style={warn ? { color: 'var(--warning-foreground)' } : undefined}>
                          {warn ? policy : undefined}
                        </span>
                        {!warn && <span className="mono dimmer">{policy}</span>}
                      </td>
                      <td className="num dim">{formatDuration(run.duration_ms)}</td>
                      {/* Per-run cost is not on the run record; /runs/cost/* only
                          aggregates across a filter set. */}
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
        </WorkbenchPanel>
      )}

      {tab === 'publish' && (
        <WorkbenchPanel title={t('console.wfDetail.versions')} hint={t('console.wfDetail.versionsHint')}>
          {versionRail.length === 0 ? (
            <DataStateNote isPending={versionsQuery.isPending} isError={versionsQuery.isError} />
          ) : (
            versionRail.map((version) => {
              const isPublished = version.id === publishedVersionId
              const isCurrent = version.id === currentVersionId
              return (
                <a key={version.id} className={cn('bundle', isPublished && 'on')}>
                  <b>
                    v{ordinalById.get(version.id)}{' '}
                    <StatusChip status={isPublished ? 'published' : isCurrent ? 'draft' : 'info'} />
                  </b>
                  <small>
                    {version.created_by || '—'} · {relativeTime(version.created_at)} · {version.id}
                  </small>
                </a>
              )
            })
          )}
          <CodeBlock
            style={{ borderRadius: '0 0 10px 10px' }}
            command={`soit workflow publish ${name}${currentOrdinal ? `@v${currentOrdinal}` : ''}`}
            output={`${nodes.length} nodes · ${edges.length} edges · runs switch on next trigger`}
          />
        </WorkbenchPanel>
      )}

      {tab === 'settings' && (
        <WorkbenchPanel title={t('console.wfDetail.settingsTitle')}>
          <div className="frow">
            <label>{t('console.wfDetail.fields.name')}</label>
            <input key={`wf-name-${workflow?.id}`} className="input" defaultValue={workflow?.name || ''} />
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.description')}</label>
            <input
              key={`wf-desc-${workflow?.id}`}
              className="input"
              defaultValue={workflow?.description || workflow?.summary || ''}
            />
          </div>
          <div className="frow">
            <label>
              {t('console.wfDetail.fields.trigger')}
              <small>{t('console.wfDetail.fields.triggerHint')}</small>
            </label>
            {/* Trigger, concurrency, retry and policy bundle are not columns on
                the workflow record; they round-trip through metadata_json. */}
            <select
              key={`wf-trigger-${workflow?.id}`}
              className="input"
              defaultValue={paramString(workflow?.metadata_json || {}, 'trigger')}
            >
              <option>webhook · ticket.created</option>
              <option>schedule</option>
              <option>manual</option>
              <option>api</option>
            </select>
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.concurrency')}</label>
            <input
              key={`wf-concurrency-${workflow?.id}`}
              className="input"
              defaultValue={paramString(workflow?.metadata_json || {}, 'concurrency')}
              style={{ maxWidth: 200 }}
            />
          </div>
          <div className="frow">
            <label>{t('console.wfDetail.fields.retry')}</label>
            <input
              key={`wf-retry-${workflow?.id}`}
              className="input"
              defaultValue={paramString(workflow?.metadata_json || {}, 'retry')}
              style={{ maxWidth: 200 }}
            />
          </div>
          <div className="frow">
            <label>
              {t('console.wfDetail.fields.bundle')}
              <small>{t('console.wfDetail.fields.bundleHint')}</small>
            </label>
            <select key={`wf-bundle-${workflow?.id}`} className="input" defaultValue={policyBundle}>
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
