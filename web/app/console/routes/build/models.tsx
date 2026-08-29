import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
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
import { useTranslation } from '@/i18n'

type MdTab = 'providers' | 'library' | 'usage'
type MdFilter = 'all' | 'chat' | 'embedding' | 'rerank'

interface MockModel {
  id: string
  provider: string
  provider_color: string
  capabilities: string[]
  context: string
  price: string
  role: React.ReactNode
  role_default?: boolean
}

// BACKEND-PENDING: model-registry list replaces the fixtures.
const MOCK_PROVIDERS = [
  {
    id: 'Anthropic',
    color: 'var(--cat-blue)',
    ref: 'key ref · vault:anthropic-prod',
    stats: [
      ['4', 'models'],
      ['1.9M', 'tokens · 24h'],
      ['$29.11', 'spend · 24h'],
    ],
    foot: { default: true, label: 'default · claude-sonnet-5' },
  },
  {
    id: 'Qwen · DashScope',
    color: 'var(--cat-purple)',
    ref: 'key ref · vault:dashscope',
    stats: [
      ['3', 'models'],
      ['0.8M', 'tokens · 24h'],
      ['$6.40', 'spend · 24h'],
    ],
    foot: { default: false, label: 'fallback tier' },
  },
  {
    id: 'vLLM · self-hosted',
    color: 'var(--cat-slate)',
    ref: 'endpoint · http://gpu-01:8000',
    stats: [
      ['2', 'models'],
      ['2.4M', 'tokens · 24h'],
      ['$0.00', 'metered'],
    ],
    foot: { default: false, label: 'embeddings · bge-m3' },
  },
]

const MOCK_MODELS: MockModel[] = [
  { id: 'claude-sonnet-5', provider: 'Anthropic', provider_color: 'var(--cat-blue)', capabilities: ['chat', 'tools', 'vision'], context: '200k', price: '3.00 · 15.00', role: 'workspace default', role_default: true },
  { id: 'claude-haiku-4.5', provider: 'Anthropic', provider_color: 'var(--cat-blue)', capabilities: ['chat', 'tools'], context: '200k', price: '1.00 · 5.00', role: 'light tasks' },
  { id: 'qwen3-235b', provider: 'DashScope', provider_color: 'var(--cat-purple)', capabilities: ['chat', 'tools'], context: '128k', price: '0.90 · 2.40', role: 'fallback tier' },
  { id: 'qwen3-30b-local', provider: 'vLLM', provider_color: 'var(--cat-slate)', capabilities: ['chat'], context: '32k', price: 'metered · 0', role: 'offline eval' },
  { id: 'bge-m3', provider: 'vLLM', provider_color: 'var(--cat-slate)', capabilities: ['embedding'], context: '8k', price: 'metered · 0', role: 'knowledge default' },
  { id: 'bge-reranker', provider: 'vLLM', provider_color: 'var(--cat-slate)', capabilities: ['rerank'], context: '8k', price: 'metered · 0', role: 'retrieval rerank' },
]

const MOCK_USAGE = [
  { id: 'claude-sonnet-5', requests: '1,942', tokens_in: '1.42M', tokens_out: '0.31M', p50: '1.8s', spend: '$24.63' },
  { id: 'claude-haiku-4.5', requests: '1,204', tokens_in: '0.36M', tokens_out: '0.09M', p50: '0.9s', spend: '$4.48' },
  { id: 'qwen3-235b', requests: '688', tokens_in: '0.61M', tokens_out: '0.17M', p50: '2.1s', spend: '$6.40' },
  { id: 'bge-m3', requests: '4,044', tokens_in: '2.10M', tokens_out: '—', p50: '88ms', spend: '$0.00' },
]

export default function ConsoleModels() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<MdTab>('providers')
  const [filter, setFilter] = useState<MdFilter>('all')
  const [search, setSearch] = useState('')

  const rows = MOCK_MODELS.filter((row) => {
    if (filter !== 'all' && !row.capabilities.includes(filter)) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [row.id, row.provider].some((value) => value.toLowerCase().includes(query))
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
          <StatTile label={t('console.models.tiles.providers')} value="3" sub={<span className="mono dimmer">all keys by vault reference</span>} />
          <StatTile label={t('console.models.tiles.models')} value="9" sub={<span className="mono dimmer">4 chat · 3 fallback · 2 embedding</span>} />
          <StatTile label={t('console.models.tiles.tokens')} value="5.1M" delta={{ direction: 'up', label: '+7.8%' }} sub="vs prev 24h" />
          <StatTile label={t('console.models.tiles.spend')} value="$35.51" sub={<span className="mono dimmer">self-hosted share 47% of tokens</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'providers', label: t('console.models.tabs.providers'), count: 3 },
            { id: 'library', label: t('console.models.tabs.library'), count: 9 },
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
                ['all', t('console.models.filters.all'), 9],
                ['chat', t('console.models.filters.chat'), 4],
                ['embedding', t('console.models.filters.embedding'), 2],
                ['rerank', t('console.models.filters.rerank'), 1],
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
      {tab === 'providers' && (
        <div className="cards mt-3.5">
          {MOCK_PROVIDERS.map((provider) => (
            <div key={provider.id} className="acard">
              <div className="acard-top">
                <span className="aavatar" style={{ '--c': provider.color } as React.CSSProperties} />
                <span>
                  <b>{provider.id}</b>
                  <span className="mono">{provider.ref}</span>
                </span>
              </div>
              <div className="acard-stats">
                {provider.stats.map(([value, label]) => (
                  <span key={label}>
                    <b>{value}</b>
                    {label}
                  </span>
                ))}
              </div>
              <div className="acard-foot">
                <span className="chip">
                  {provider.foot.default && <i style={{ background: 'var(--primary)' }} />}
                  {provider.foot.label}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

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
              {rows.map((row) => (
                <TableRow key={row.id} className="rowlink">
                  <TableCell>
                    <span className="mono">{row.id}</span>
                  </TableCell>
                  <TableCell>
                    <span className="idm" style={{ '--c': row.provider_color } as React.CSSProperties}>
                      <i />
                      {row.provider}
                    </span>
                  </TableCell>
                  <TableCell>
                    <span className="scopes">
                      {row.capabilities.map((capability) => (
                        <span key={capability} className="chip">
                          {capability}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="num dim">{row.context}</TableCell>
                  <TableCell className="num dim">{row.price}</TableCell>
                  <TableCell className={row.role_default ? undefined : 'dim'}>
                    {row.role_default ? (
                      <span className="chip">
                        <i style={{ background: 'var(--primary)' }} />
                        {row.role}
                      </span>
                    ) : (
                      row.role
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.models.libraryNote')} />
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
              {MOCK_USAGE.map((row) => (
                <TableRow key={row.id}>
                  <TableCell>
                    <span className="mono">{row.id}</span>
                  </TableCell>
                  <TableCell className="num dim">{row.requests}</TableCell>
                  <TableCell className="num dim">{row.tokens_in}</TableCell>
                  <TableCell className="num dim">{row.tokens_out}</TableCell>
                  <TableCell className="num dim">{row.p50}</TableCell>
                  <TableCell className="num dim">{row.spend}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.models.usageNote')} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
