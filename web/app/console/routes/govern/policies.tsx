import { useMemo, useState } from 'react'

import { NavLink } from 'react-router'
import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  ConsoleTabs,
  DataStateNote,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconCopy,
  IconPlus,
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
import { compactNumber, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { mockTiles } from '../../mocks/tiles'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  diffPolicyRevisions,
  getEgressBlockSummary,
  getPolicyBundle,
  getWorkspaceEgressPolicy,
  getWorkspaceUsagePolicy,
  listPolicyRevisions,
  rollbackPolicyRevision,
  updateWorkspaceEgressPolicy,
  updateWorkspaceUsagePolicy,
  type PolicyRevision,
} from '@/services/security-service'
import { listRunAudits } from '@/services/run-service'
import { requestErrorMessage } from '@/utils/request'

type PolicyTab = 'rules' | 'bundles' | 'staged'
type RuleFilter = 'all' | 'grants' | 'intents' | 'egress' | 'budget' | 'approval'

const RULE_KIND: Record<Exclude<RuleFilter, 'all'>, string> = {
  grants: 'tool·grant',
  intents: 'intents',
  egress: 'egress',
  budget: 'budget',
  approval: 'approval',
}

interface PolicyRuleRow {
  id: string
  kind: string
  kind_color: string
  scope: string
}

/** How many limits a revision actually sets, which is what the row reports. */
function limitCount(document: PolicyRevision['document']): number {
  return [
    document.llm_rate_limit_per_minute,
    document.tool_rate_limit_per_minute,
    document.llm_daily_quota,
    document.tool_daily_quota,
  ].filter((value) => value != null).length
}

/** A policy value as one line: a rule list joins, a limit prints, empty is "none". */
function policyValue(value: unknown): string {
  if (value == null) return 'none'
  if (Array.isArray(value)) return value.length ? value.join(', ') : 'none'
  return String(value)
}

export default function ConsolePolicies() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<PolicyTab>('rules')
  const [filter, setFilter] = useState<RuleFilter>('all')
  const [search, setSearch] = useState('')

  const egressQuery = useQuery({
    queryKey: ['console', 'policies', 'egress'],
    queryFn: () => getWorkspaceEgressPolicy(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const usageQuery = useQuery({
    queryKey: ['console', 'policies', 'usage'],
    queryFn: () => getWorkspaceUsagePolicy(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // "Evaluations" is the number of governed gateway requests the policy path
  // ran over in the window; each leaves an audit row. Blocks are counted from
  // the same ledger, so the tile's two figures are the same measurement seen
  // from both sides.
  const since = new Date(Date.now() - 86_400_000).toISOString()
  const evaluationsQuery = useQuery({
    queryKey: ['console', 'policies', 'evaluations', since],
    queryFn: () => listRunAudits({ since, page_size: 1, with_total: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const blocksQuery = useQuery({
    queryKey: ['console', 'policies', 'blocks', since],
    queryFn: () => getEgressBlockSummary({ since }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const evaluations = evaluationsQuery.data?.total ?? null
  const blocks = blocksQuery.data

  // The revision ledger is the history: every save appends one, and each
  // carries the policy content, so the list and the diff read the same rows.
  const revisionsQuery = useQuery({
    queryKey: ['console', 'policies', 'revisions'],
    queryFn: () => listPolicyRevisions({ page_size: 25 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const bundleQuery = useQuery({
    queryKey: ['console', 'policies', 'bundle'],
    queryFn: () => getPolicyBundle(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const revisions = revisionsQuery.data?.items || []

  const [selected, setSelected] = useState<PolicyRevision | null>(null)
  const [restoring, setRestoring] = useState<PolicyRevision | null>(null)

  // A revision is compared with the one before it, which is the question a
  // reviewer is actually asking: what did this save change?
  const diffQuery = useQuery({
    queryKey: ['console', 'policies', 'diff', selected?.revision ?? 0],
    queryFn: () =>
      diffPolicyRevisions({
        from_revision: (selected?.revision ?? 1) - 1,
        to_revision: selected?.revision ?? 1,
      }),
    options: {
      enabled: !!selected && selected.revision > 1,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const rollbackMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'policies', 'rollback'],
    mutationFn: (revisionId) => rollbackPolicyRevision(revisionId),
    onSuccess: () => {
      setRestoring(null)
      setSelected(null)
      void revisionsQuery.refetch()
      void bundleQuery.refetch()
      void egressQuery.refetch()
      void usageQuery.refetch()
      toast.success(t('console.policies.history.restored'))
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to restore the policy'))
    },
  })

  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState({
    allowlist: '',
    blocklist: '',
    llm_rate: '',
    tool_rate: '',
    llm_quota: '',
    tool_quota: '',
  })

  const openEditor = () => {
    setDraft({
      allowlist: (egressQuery.data?.allowlist || []).join('\n'),
      blocklist: (egressQuery.data?.blocklist || []).join('\n'),
      llm_rate: usageQuery.data?.llm_rate_limit_per_minute?.toString() ?? '',
      tool_rate: usageQuery.data?.tool_rate_limit_per_minute?.toString() ?? '',
      llm_quota: usageQuery.data?.llm_daily_quota?.toString() ?? '',
      tool_quota: usageQuery.data?.tool_daily_quota?.toString() ?? '',
    })
    setEditing(true)
  }

  const asLines = (value: string) =>
    value
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)
  // An empty box means "no limit", which the API models as null — not zero.
  const asLimit = (value: string) => {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) && parsed >= 0 ? parsed : null
  }

  const saveMutation = useMutation({
    mutationKey: ['console', 'policies', 'save'],
    // Both surfaces are separate endpoints; a partial failure must still report.
    mutationFn: async () => {
      await updateWorkspaceEgressPolicy({
        allowlist: asLines(draft.allowlist),
        blocklist: asLines(draft.blocklist),
      })
      await updateWorkspaceUsagePolicy({
        llm_rate_limit_per_minute: asLimit(draft.llm_rate),
        tool_rate_limit_per_minute: asLimit(draft.tool_rate),
        llm_daily_quota: asLimit(draft.llm_quota),
        tool_daily_quota: asLimit(draft.tool_quota),
      })
    },
    onSuccess: () => {
      setEditing(false)
      void egressQuery.refetch()
      void usageQuery.refetch()
      void revisionsQuery.refetch()
      void bundleQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to save the policy'))
    },
  })

  // The security service stores configuration, not a rule ledger: each
  // allowlist/blocklist entry and each configured limit is one enforced rule.
  const allRules = useMemo<PolicyRuleRow[]>(() => {
    const rows: PolicyRuleRow[] = []
    const egress = egressQuery.data
    if (egress) {
      egress.allowlist.forEach((host) =>
        rows.push({
          id: `egress.allow:${host}`,
          kind: 'egress',
          kind_color: 'var(--cat-teal)',
          scope: egress.scope,
        }),
      )
      egress.blocklist.forEach((host) =>
        rows.push({
          id: `egress.block:${host}`,
          kind: 'egress',
          kind_color: 'var(--cat-pink)',
          scope: egress.scope,
        }),
      )
    }
    const usage = usageQuery.data
    if (usage) {
      const limits: Array<[string, number | null | undefined]> = [
        ['limits.llm_rate_per_minute', usage.llm_rate_limit_per_minute],
        ['limits.tool_rate_per_minute', usage.tool_rate_limit_per_minute],
        ['limits.llm_daily_quota', usage.llm_daily_quota],
        ['limits.tool_daily_quota', usage.tool_daily_quota],
      ]
      limits.forEach(([id, value]) => {
        if (value == null) return
        rows.push({
          id: `${id} = ${value}`,
          kind: 'budget',
          kind_color: 'var(--cat-amber)',
          scope: 'workspace',
        })
      })
    }
    return rows
  }, [egressQuery.data, usageQuery.data])

  const ruleCount = (kind: RuleFilter) =>
    kind === 'all'
      ? allRules.length
      : allRules.filter((rule) => rule.kind === RULE_KIND[kind]).length

  const rules = allRules.filter((rule) => {
    if (filter !== 'all' && rule.kind !== RULE_KIND[filter]) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [rule.id, rule.kind, rule.scope].some((value) => value.toLowerCase().includes(query))
  })

  return (
    <Workbench
      title={t('console.policies.title')}
      description={t('console.policies.description')}
      actions={
        <>
          {/* Bundles do not exist server-side, so "compare versions" has nothing
              to compare; the audit trail on the Bundles tab is the real history. */}
          <ConsoleButton onClick={() => setTab('bundles')}>
            <IconCopy />
            {t('console.policies.compare')}
          </ConsoleButton>
          <ConsoleButton
            variant="primary"
            disabled={!egressQuery.data && !usageQuery.data}
            onClick={openEditor}
          >
            <IconPlus />
            {t('console.policies.editRules')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          {/* The identifier is derived from the policy content, so it is the
              same one recorded against every request the policy refuses. */}
          <StatTile
            label={t('console.policies.tiles.active')}
            value={
              <span style={{ fontSize: 15 }}>
                {bundleQuery.data
                  ? bundleQuery.data.revision > 0
                    ? `r${bundleQuery.data.revision}`
                    : bundleQuery.data.bundle_id.slice(3, 11)
                  : '—'}
              </span>
            }
            na={!bundleQuery.data}
            sub={
              <span className="mono dimmer">
                {bundleQuery.data?.bundle_id || 'policy in force'}
              </span>
            }
          />
          <StatTile
            label={t('console.policies.tiles.rules')}
            value={egressQuery.data || usageQuery.data ? String(allRules.length) : '—'}
            na={!egressQuery.data && !usageQuery.data}
            sub={
              <span className="mono dimmer">
                {ruleCount('egress')} egress · {ruleCount('budget')} limits
              </span>
            }
          />
          <StatTile
            label={t('console.policies.tiles.evaluations')}
            value={evaluations == null ? '—' : compactNumber(evaluations)}
            na={evaluations == null}
            sub={
              <span className="mono dimmer">
                {t('console.policies.tiles.evaluationsSub', {
                  count: blocks?.total ?? 0,
                })}
              </span>
            }
          />
          <StatTile
            label={t('console.policies.tiles.attention')}
            value={String(egressQuery.data?.blocklist.length ?? 0)}
            sub={<span className="mono dimmer">blocked destinations</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'rules', label: t('console.policies.tabs.rules'), count: allRules.length },
            {
              id: 'bundles',
              label: t('console.policies.tabs.bundles'),
              count: revisions.length || undefined,
            },
            { id: 'staged', label: t('console.policies.tabs.staged') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'rules' ? (
          <>
            {(
              [
                ['all', t('console.policies.filters.all'), ruleCount('all')],
                ['grants', t('console.policies.filters.grants'), ruleCount('grants')],
                ['intents', t('console.policies.filters.intents'), ruleCount('intents')],
                ['egress', t('console.policies.filters.egress'), ruleCount('egress')],
                ['budget', t('console.policies.filters.budget'), ruleCount('budget')],
                ['approval', t('console.policies.filters.approval'), ruleCount('approval')],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.policies.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'rules' && (
        <WorkbenchPanel
          title={t('console.policies.rulesTitle')}
          hint={t('console.policies.rulesHint')}
          actions={
            <NavLink className="more" to="/govern/audit">
              {t('console.policies.auditLink')}
            </NavLink>
          }
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.policies.columns.rule')}</TableHead>
                <TableHead>{t('console.policies.columns.kind')}</TableHead>
                <TableHead>{t('console.policies.columns.scope')}</TableHead>
                <TableHead className="num">{t('console.policies.columns.evaluations')}</TableHead>
                <TableHead className="num">{t('console.policies.columns.blocked')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules.length === 0 ? (
                <DataStateRow
                  colSpan={5}
                  isPending={egressQuery.isPending || usageQuery.isPending}
                  isError={egressQuery.isError && usageQuery.isError}
                />
              ) : (
                rules.map((rule) => (
                  <TableRow key={rule.id} className="rowlink">
                    <TableCell className="mono">{rule.id}</TableCell>
                    <TableCell>
                      <span className="kind" style={{ '--c': rule.kind_color } as React.CSSProperties}>
                        <i />
                        {rule.kind}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{rule.scope}</TableCell>
                    {/* No per-rule counters in the security API. */}
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dim">—</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}

      {tab === 'bundles' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.policies.bundlesTitle')}
          hint={t('console.policies.bundlesHint')}
        >
          {revisions.length ? (
            revisions.map((entry) => (
              <a
                key={entry.id}
                className={cn(
                  'bundle',
                  entry.active && 'on',
                  selected?.id === entry.id && 'sel',
                )}
                onClick={() => setSelected(selected?.id === entry.id ? null : entry)}
              >
                <b>
                  r{entry.revision}{' '}
                  <StatusChip
                    status={entry.active ? 'published' : 'info'}
                    label={
                      entry.active
                        ? t('console.policies.history.inForce')
                        : t('console.policies.history.superseded')
                    }
                  />
                  {entry.restored_from_revision != null && (
                    <span className="mono dimmer" style={{ marginLeft: 6, fontSize: 10.5 }}>
                      {t('console.policies.history.restoredFrom', {
                        revision: entry.restored_from_revision,
                      })}
                    </span>
                  )}
                </b>
                <small>
                  {relativeTime(entry.created_at)} · {entry.created_by || 'system'} ·{' '}
                  {t('console.policies.history.rules', {
                    allowed: entry.document.egress_allowlist.length,
                    blocked: entry.document.egress_blocklist.length,
                    limits: limitCount(entry.document),
                  })}{' '}
                  · <span className="mono dimmer">{entry.bundle_id}</span>
                </small>
                {selected?.id === entry.id && (
                  <div style={{ marginTop: 8, display: 'grid', gap: 6 }}>
                    {entry.revision === 1 ? (
                      <span className="mono dimmer" style={{ fontSize: 11 }}>
                        {t('console.policies.history.firstRevision')}
                      </span>
                    ) : (
                      <>
                        <span className="dim" style={{ fontSize: 11 }}>
                          {t('console.policies.history.compare', {
                            revision: entry.revision - 1,
                          })}
                        </span>
                        {diffQuery.data?.changes.length ? (
                          diffQuery.data.changes.map((change) => (
                            <span
                              key={change.field}
                              className="mono"
                              style={{ fontSize: 11 }}
                            >
                              {change.field}: {policyValue(change.before)} →{' '}
                              {policyValue(change.after)}
                            </span>
                          ))
                        ) : (
                          <span className="mono dimmer" style={{ fontSize: 11 }}>
                            {t('console.policies.history.noChanges')}
                          </span>
                        )}
                      </>
                    )}
                    {!entry.active && (
                      <span>
                        <ConsoleButton
                          variant="ghost"
                          style={{ height: 22, fontSize: 10.5 }}
                          onClick={(event) => {
                            event.stopPropagation()
                            setRestoring(entry)
                          }}
                        >
                          {t('console.policies.history.restore')}
                        </ConsoleButton>
                      </span>
                    )}
                  </div>
                )}
              </a>
            ))
          ) : (
            <DataStateNote
              isPending={revisionsQuery.isPending}
              isError={revisionsQuery.isError}
            />
          )}
          {/* A policy can be in force without matching any recorded revision:
              a fresh install, or a change made outside the API. Saying so is
              better than pointing at the newest row and being wrong. */}
          {!!revisions.length && bundleQuery.data?.revision === 0 && (
            <div className="empty-note" style={{ marginTop: 8 }}>
              {t('console.policies.history.unrecorded')}
              <span className="mono">{bundleQuery.data.bundle_id}</span>
            </div>
          )}
        </WorkbenchPanel>
      )}

      {/* Staged rollout is a bundle concept; without bundles there is nothing
          to diff. Kept as a labelled empty state rather than a fake diff. */}
      {tab === 'staged' && (
        <WorkbenchPanel className="mt-3.5" title={t('console.policies.stagedTitle')}>
          <div className="empty-note">
            {t('console.common.empty')}
            <span className="mono">{t('console.policies.stagedNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={Boolean(restoring)}
        onOpenChange={(open) => {
          if (!open) setRestoring(null)
        }}
        title={t('console.policies.history.restoreTitle')}
        note={t('console.policies.history.restoreNote')}
        confirmLabel={t('console.policies.history.restore')}
        busy={rollbackMutation.isPending}
        onConfirm={() => restoring && rollbackMutation.mutate(restoring.id)}
      >
        <div className="mrow">
          <span className="mono dim" style={{ fontSize: 12 }}>
            r{restoring?.revision} · {restoring?.bundle_id}
          </span>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={editing}
        onOpenChange={setEditing}
        title={t('console.policies.editTitle')}
        note={t('console.policies.editNote')}
        confirmLabel={t('console.common.save')}
        busy={saveMutation.isPending}
        onConfirm={() => saveMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.policies.fields.allowlist')}
            <small>{t('console.policies.fields.allowlistHint')}</small>
          </label>
          <textarea
            className="input"
            value={draft.allowlist}
            onChange={(event) => setDraft((state) => ({ ...state, allowlist: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.policies.fields.blocklist')}
            <small>{t('console.policies.fields.blocklistHint')}</small>
          </label>
          <textarea
            className="input"
            value={draft.blocklist}
            onChange={(event) => setDraft((state) => ({ ...state, blocklist: event.target.value }))}
          />
        </div>
        {(
          [
            ['llm_rate', t('console.policies.fields.llmRate')],
            ['tool_rate', t('console.policies.fields.toolRate')],
            ['llm_quota', t('console.policies.fields.llmQuota')],
            ['tool_quota', t('console.policies.fields.toolQuota')],
          ] as const
        ).map(([key, label], index) => (
          <div className="mrow" key={key}>
            <label>
              {label}
              {index === 0 && <small>{t('console.policies.fields.limitsHint')}</small>}
            </label>
            <input
              className="input"
              inputMode="numeric"
              style={{ maxWidth: 140 }}
              value={draft[key]}
              onChange={(event) => setDraft((state) => ({ ...state, [key]: event.target.value }))}
            />
          </div>
        ))}
      </ConsoleModal>
    </Workbench>
  )
}
