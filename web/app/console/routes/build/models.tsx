import { useState } from 'react'

import {
  ConsoleButton,
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
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  getModelWorkbenchModels,
  getModelWorkbenchOverview,
  getModelWorkbenchProviders,
  type ModelWorkbenchModelRow,
} from '@/services/provider-service'

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

export default function ConsoleModels() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<MdTab>('providers')
  const [filter, setFilter] = useState<MdFilter>('all')
  const [search, setSearch] = useState('')

  // The overview carries the summary and both tab counters, so it backs the
  // tiles and the tab bar on every tab; the two list queries only run for the
  // tab that renders them.
  const overviewQuery = useQuery({
    queryKey: ['console', 'models', 'overview'],
    queryFn: () => getModelWorkbenchOverview(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const providersQuery = useQuery({
    queryKey: ['console', 'models', 'providers'],
    queryFn: () => getModelWorkbenchProviders({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false, enabled: tab === 'providers' },
  })
  const modelsQuery = useQuery({
    queryKey: ['console', 'models', 'library'],
    queryFn: () => getModelWorkbenchModels({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false, enabled: tab === 'library' },
  })

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
        <ConsoleButton variant="primary">
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
                  <TableRow key={row.id} className="rowlink">
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
          <Pager summary={t('console.models.libraryNote', { count: rows.length })} />
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
    </Workbench>
  )
}
