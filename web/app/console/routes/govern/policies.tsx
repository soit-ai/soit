import { useMemo, useState } from 'react'

import { NavLink } from 'react-router'

import {
  ConsoleButton,
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
import { relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  getWorkspaceEgressPolicy,
  getWorkspaceUsagePolicy,
  listEgressPolicyAudits,
} from '@/services/security-service'

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

// BACKEND-PENDING: bundles + staged diff have no server-side object — the
// runtime carries a policy_ref string only. Egress and usage rules are live.
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
  const auditsQuery = useQuery({
    queryKey: ['console', 'policies', 'audits'],
    queryFn: () => listEgressPolicyAudits({ page_size: 20 }),
    options: { retry: false, refetchOnWindowFocus: false },
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
          <ConsoleButton>
            <IconCopy />
            {t('console.policies.compare')}
          </ConsoleButton>
          <ConsoleButton variant="primary">
            <IconPlus />
            {t('console.policies.newBundle')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          {/* Bundle identity has no backend object; the scope of the live
              policy is the closest honest equivalent. */}
          <StatTile
            label={t('console.policies.tiles.active')}
            value={<span style={{ fontSize: 15 }}>{egressQuery.data?.scope || '—'}</span>}
            na={!egressQuery.data}
            sub={<span className="mono dimmer">policy scope in force</span>}
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
          {/* Per-rule evaluation counters are not reported by the API. */}
          <StatTile label={t('console.policies.tiles.evaluations')} value="—" na sub={<span className="mono dimmer">not reported</span>} />
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
            { id: 'bundles', label: t('console.policies.tabs.bundles') },
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
            <NavLink className="more" to="/v2/govern/audit">
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

      {/* Versioned bundles do not exist server-side. The egress audit trail is
          the real record of how the policy in force has changed over time. */}
      {tab === 'bundles' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.policies.bundlesTitle')}
          hint={t('console.policies.bundlesHint')}
        >
          {auditsQuery.data?.items?.length ? (
            auditsQuery.data.items.map((entry, index) => (
              <a key={entry.id} className={cn('bundle', index === 0 && 'on')}>
                <b>
                  {entry.scope}{' '}
                  <StatusChip
                    status={index === 0 ? 'published' : 'info'}
                    label={index === 0 ? 'IN FORCE' : 'SUPERSEDED'}
                  />
                </b>
                <small>
                  {relativeTime(entry.created_at)} · {entry.created_by || 'system'} ·{' '}
                  {entry.allowlist.length} allowed · {entry.blocklist.length} blocked
                </small>
              </a>
            ))
          ) : (
            <DataStateNote
              isPending={auditsQuery.isPending}
              isError={auditsQuery.isError}
            />
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
    </Workbench>
  )
}
