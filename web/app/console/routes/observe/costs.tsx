import { useMemo, useState } from 'react'

import {
  ConsoleButton,
  DataStateRow,
  FilterChip,
  Pager,
  Seg,
  StatTile,
  StatTileGrid,
  Workbench,
  WorkbenchPanel,
} from '../../components'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../../components/ui'
import { compactNumber } from '../../adapters/palette'
import {
  formatCurrencyAmounts,
  groupAmount,
  groupsToCsv,
  windowStart,
  type CostRange,
} from '../../adapters/cost-reconciliation'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { saveBlob } from '@/services/ledger-service'
import {
  getCostReconciliation,
  type CostGroupBy,
  type CostPricingStatus,
  type RunSource,
} from '@/services/run-service'

const RANGES: readonly CostRange[] = ['24h', '7d', '30d', 'month']
const GROUPS: readonly CostGroupBy[] = ['model', 'provider', 'tool', 'api_key', 'user', 'day']
const STATUSES: readonly CostPricingStatus[] = ['priced', 'estimated', 'free', 'unpriced']

/**
 * Observe › Costs: what the ledger recorded in a window, per currency and per
 * pricing status, grouped by model, provider, tool, key, principal or day, so
 * it can be set beside a provider's bill. Unpriced entries are counted apart,
 * never as zero, and currencies are never added together.
 */
export default function ConsoleCosts() {
  const { t } = useTranslation()
  const [range, setRange] = useState<CostRange>('7d')
  const [groupBy, setGroupBy] = useState<CostGroupBy>('model')
  const [status, setStatus] = useState<CostPricingStatus | null>(null)
  const [source, setSource] = useState<RunSource | null>(null)
  // The window is fixed when the range is picked, so refetches and the export
  // read the same rows the table shows.
  const since = useMemo(() => windowStart(range, new Date()), [range])

  const params = {
    since,
    group_by: groupBy,
    ...(status ? { pricing_status: status } : {}),
    ...(source ? { source } : {}),
  }
  const reconciliationQuery = useQuery({
    queryKey: ['console', 'costs', params],
    queryFn: () => getCostReconciliation(params),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const data = reconciliationQuery.data
  const groups = data?.groups || []
  const unpriced = data?.status_counts.unpriced ?? 0

  const exportCsv = () => {
    if (!data) return
    const blob = new Blob([groupsToCsv(groups, groupBy)], { type: 'text/csv;charset=utf-8' })
    saveBlob(blob, `soit-costs-${groupBy}-${since.slice(0, 10)}.csv`)
  }

  return (
    <Workbench
      title={t('console.costs.title')}
      description={t('console.costs.description')}
      actions={
        <>
          <Seg<CostRange>
            options={RANGES.map((value) => ({ value, label: t(`console.costs.ranges.${value}`) }))}
            value={range}
            onChange={setRange}
          />
          <ConsoleButton onClick={exportCsv} disabled={!groups.length}>
            {t('console.costs.exportCsv')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.costs.tiles.spend')}
            value={data ? formatCurrencyAmounts(data.amounts) : '—'}
            na={!data}
            sub={
              <span className="mono dimmer">
                {data
                  ? t('console.costs.tiles.spendSub', { count: data.entry_count - unpriced })
                  : ''}
              </span>
            }
          />
          <StatTile
            label={t('console.costs.tiles.estimated')}
            value={data ? formatCurrencyAmounts(data.estimated_amounts) : '—'}
            na={!data}
            sub={
              <span className="mono dimmer">
                {t('console.costs.tiles.estimatedSub', {
                  count: data?.status_counts.estimated ?? 0,
                })}
              </span>
            }
          />
          <StatTile
            label={t('console.costs.tiles.unpriced')}
            value={data ? compactNumber(unpriced) : '—'}
            na={!data}
            sub={<span className="mono dimmer">{t('console.costs.tiles.unpricedSub')}</span>}
          />
          <StatTile
            label={t('console.costs.tiles.bill')}
            value={t('console.costs.tiles.billNotChecked')}
            sub={<span className="mono dimmer">{t('console.costs.tiles.billSub')}</span>}
          />
        </StatTileGrid>
      }
      filters={
        <>
          <span className="dimmer" style={{ fontSize: 11.5 }}>
            {t('console.costs.filters.groupBy')}
          </span>
          {GROUPS.map((value) => (
            <FilterChip key={value} active={groupBy === value} onClick={() => setGroupBy(value)}>
              {t(`console.costs.groups.${value}`)}
            </FilterChip>
          ))}
          <span className="dimmer" style={{ fontSize: 11.5, marginLeft: 12 }}>
            {t('console.costs.filters.status')}
          </span>
          <FilterChip active={status === null} onClick={() => setStatus(null)}>
            {t('console.costs.filters.all')}
          </FilterChip>
          {STATUSES.map((value) => (
            <FilterChip
              key={value}
              active={status === value}
              count={data && !status ? data.status_counts[value] : undefined}
              onClick={() => setStatus(value)}
            >
              {t(`console.costs.statuses.${value}`)}
            </FilterChip>
          ))}
          <span className="dimmer" style={{ fontSize: 11.5, marginLeft: 12 }}>
            {t('console.costs.filters.source')}
          </span>
          <FilterChip active={source === null} onClick={() => setSource(null)}>
            {t('console.costs.filters.all')}
          </FilterChip>
          <FilterChip active={source === 'gateway'} onClick={() => setSource('gateway')}>
            {t('console.costs.filters.gateway')}
          </FilterChip>
          <FilterChip active={source === 'platform'} onClick={() => setSource('platform')}>
            {t('console.costs.filters.platform')}
          </FilterChip>
        </>
      }
    >
      <WorkbenchPanel
        title={t(`console.costs.groups.${groupBy}`)}
        hint={t('console.costs.groupsHint')}
      >
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t(`console.costs.groups.${groupBy}`)}</TableHead>
              <TableHead className="num">{t('console.costs.columns.entries')}</TableHead>
              <TableHead className="num">{t('console.costs.columns.amount')}</TableHead>
              <TableHead className="num">{t('console.costs.columns.estimated')}</TableHead>
              <TableHead className="num">{t('console.costs.columns.unpriced')}</TableHead>
              <TableHead className="num">{t('console.costs.columns.tokens')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {groups.length === 0 ? (
              <DataStateRow
                colSpan={6}
                isPending={reconciliationQuery.isPending}
                isError={reconciliationQuery.isError}
                emptyLabel={t('console.costs.empty')}
              />
            ) : (
              groups.map((group) => (
                <TableRow key={`${group.key ?? ''}|${group.currency ?? ''}`}>
                  <TableCell>
                    <span className="mono" style={{ overflowWrap: 'anywhere' }}>
                      {group.key ?? <span className="dimmer">{t('console.costs.noValue')}</span>}
                    </span>
                  </TableCell>
                  <TableCell className="num dim">{compactNumber(group.entry_count)}</TableCell>
                  <TableCell className="num mono">{groupAmount(group)}</TableCell>
                  <TableCell className="num dim">{group.estimated_count || '—'}</TableCell>
                  <TableCell className="num">
                    {group.unpriced_count ? (
                      <span style={{ color: 'var(--warning-foreground)' }}>{group.unpriced_count}</span>
                    ) : (
                      <span className="dimmer">—</span>
                    )}
                  </TableCell>
                  <TableCell className="num dim">{compactNumber(group.total_tokens)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager
          summary={
            data?.groups_truncated ? t('console.costs.truncated') : t('console.costs.pagerNote')
          }
        />
      </WorkbenchPanel>

      {data && data.unpriced_reasons.length > 0 && (
        <WorkbenchPanel title={t('console.costs.reasons.title')} hint={t('console.costs.reasons.hint')}>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.costs.reasons.reason')}</TableHead>
                <TableHead className="num">{t('console.costs.columns.entries')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.unpriced_reasons.map((item) => (
                <TableRow key={item.reason}>
                  <TableCell>
                    <span className="mono">{item.reason}</span>
                  </TableCell>
                  <TableCell className="num">{compactNumber(item.entry_count)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
