import { useState } from 'react'

import { NavLink } from 'react-router'

import {
  CodeBlock,
  ConsoleButton,
  ConsoleTabs,
  FilterChip,
  FilterSearch,
  IconCopy,
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
import {
  mockBundles,
  mockPolicyRuleCounts,
  mockPolicyRules,
  mockPolicyTiles,
  mockStagedDiff,
} from '../../mocks/govern'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

type PolicyTab = 'rules' | 'bundles' | 'staged'
type RuleFilter = 'all' | 'grants' | 'intents' | 'egress' | 'budget' | 'approval'

const RULE_KIND: Record<Exclude<RuleFilter, 'all'>, string> = {
  grants: 'tool·grant',
  intents: 'intents',
  egress: 'egress',
  budget: 'budget',
  approval: 'approval',
}

// BACKEND-PENDING: egress/usage rules become real; bundles + staged diff
// stay mock-first (backend keeps only a policy_ref string today).
export default function ConsolePolicies() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<PolicyTab>('rules')
  const [filter, setFilter] = useState<RuleFilter>('all')
  const [search, setSearch] = useState('')

  const rules = mockPolicyRules.filter((rule) => {
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
          <StatTile label={t('console.policies.tiles.active')} value={<span style={{ fontSize: 15 }}>{mockPolicyTiles.active.value}</span>} sub={<span className="mono dimmer">{mockPolicyTiles.active.sub}</span>} />
          <StatTile label={t('console.policies.tiles.rules')} value={mockPolicyTiles.rules.value} sub={<span className="mono dimmer">{mockPolicyTiles.rules.sub}</span>} />
          <StatTile label={t('console.policies.tiles.evaluations')} value={mockPolicyTiles.evaluations.value} sub={<span className="mono dimmer">{mockPolicyTiles.evaluations.sub}</span>} />
          <StatTile label={t('console.policies.tiles.attention')} value={mockPolicyTiles.attention.value} sub={<span className="mono dimmer">{mockPolicyTiles.attention.sub}</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'rules', label: t('console.policies.tabs.rules'), count: 7 },
            { id: 'bundles', label: t('console.policies.tabs.bundles'), count: 4 },
            { id: 'staged', label: t('console.policies.tabs.staged'), count: 1 },
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
                ['all', t('console.policies.filters.all'), mockPolicyRuleCounts.all],
                ['grants', t('console.policies.filters.grants'), mockPolicyRuleCounts.grants],
                ['intents', t('console.policies.filters.intents'), mockPolicyRuleCounts.intents],
                ['egress', t('console.policies.filters.egress'), mockPolicyRuleCounts.egress],
                ['budget', t('console.policies.filters.budget'), mockPolicyRuleCounts.budget],
                ['approval', t('console.policies.filters.approval'), mockPolicyRuleCounts.approval],
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
              {rules.map((rule) => (
                <TableRow key={rule.id} className="rowlink">
                  <TableCell className="mono">{rule.id}</TableCell>
                  <TableCell>
                    <span className="kind" style={{ '--c': rule.kind_color } as React.CSSProperties}>
                      <i />
                      {rule.kind}
                    </span>
                  </TableCell>
                  <TableCell className="dim">{rule.scope}</TableCell>
                  <TableCell className="num dim">{rule.evaluations}</TableCell>
                  <TableCell className="num dim">{rule.blocked}</TableCell>
                </TableRow>
              ))}
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
          {mockBundles.map((bundle) => (
            <a key={bundle.id} className={cn('bundle', bundle.active && 'on')}>
              <b>
                {bundle.id} <StatusChip status={bundle.status} label={bundle.status_label} />
              </b>
              <small>{bundle.note}</small>
            </a>
          ))}
          <CodeBlock
            style={{ borderRadius: '0 0 10px 10px' }}
            command="soit policy promote v2026.08.28-1 --to 50%"
            output="gate: zero blocked-regressions in staged cohort ✓"
          />
        </WorkbenchPanel>
      )}

      {tab === 'staged' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.policies.stagedTitle')}
          actions={
            <>
              <ConsoleButton size="sm" style={{ color: 'var(--danger-foreground)' }}>
                {t('console.policies.discard')}
              </ConsoleButton>
              <ConsoleButton size="sm" variant="primary">
                {t('console.policies.promote')}
              </ConsoleButton>
            </>
          }
        >
          <div className="diff">
            {mockStagedDiff.map((line, index) => (
              <span key={index}>
                <span className={line.kind}>{line.text}</span>
                {'comment' in line && line.comment && (
                  <>
                    {'    '}
                    <span className="cm">{line.comment}</span>
                  </>
                )}
                {'\n'}
              </span>
            ))}
          </div>
          <Pager summary={t('console.policies.stagedNote')} style={{ borderTop: '1px solid var(--border)' }} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
