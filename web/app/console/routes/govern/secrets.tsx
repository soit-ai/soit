import { useState } from 'react'

import {
  ConsoleButton,
  ConsoleTabs,
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
import { relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listSecrets } from '@/services/secrets-service'

type SecretsTab = 'vault' | 'rotations' | 'usage'
type KindFilter = 'all' | 'apiKeys' | 'tokens' | 'configs'

/** The vault stores a name and a value; "kind" is a naming convention. */
function secretKind(name: string): string {
  const lower = name.toLowerCase()
  if (lower.includes('kubeconfig') || lower.includes('config')) return 'kubeconfig'
  if (lower.includes('token')) return 'token'
  if (lower.includes('key')) return 'API key'
  return 'secret'
}

const KIND_MATCH: Record<KindFilter, (kind: string) => boolean> = {
  all: () => true,
  apiKeys: (kind) => kind === 'API key',
  tokens: (kind) => kind === 'token',
  configs: (kind) => kind === 'kubeconfig',
}

export default function ConsoleSecrets() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<SecretsTab>('vault')
  const [filter, setFilter] = useState<KindFilter>('all')
  const [search, setSearch] = useState('')

  const secretsQuery = useQuery({
    queryKey: ['console', 'secrets'],
    queryFn: () => listSecrets({ limit: 200 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const secrets = secretsQuery.data || []
  const kindOf = (name: string) => secretKind(name)

  const rows = secrets.filter((row) => {
    if (!KIND_MATCH[filter](kindOf(row.name))) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return row.name.toLowerCase().includes(query)
  })

  const countByKind = (predicate: (kind: string) => boolean) =>
    secrets.filter((row) => predicate(kindOf(row.name))).length

  return (
    <Workbench
      title={t('console.secrets.title')}
      description={
        <>
          {t('console.secrets.descriptionPrefix')} <span className="mono">vault:name</span>{' '}
          {t('console.secrets.descriptionSuffix')}
        </>
      }
      actions={
        <ConsoleButton variant="primary">
          <IconPlus />
          {t('console.secrets.addSecret')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.secrets.tiles.secrets')}
            value={secretsQuery.data ? String(secrets.length) : '—'}
            na={!secretsQuery.data}
            sub={<span className="mono dimmer">referenced, never inlined</span>}
          />
          {/* Resolution counts are not exposed by the secrets API. */}
          <StatTile label={t('console.secrets.tiles.resolutions')} value="—" na sub={<span className="mono dimmer">not reported</span>} />
          <StatTile
            label={t('console.secrets.tiles.rotation')}
            value={
              secrets.some((row) => row.last_rotated_at)
                ? relativeTime(
                    secrets
                      .map((row) => row.last_rotated_at)
                      .filter(Boolean)
                      .sort()
                      .reverse()[0],
                  )
                : '—'
            }
            na={!secrets.some((row) => row.last_rotated_at)}
            sub={<span className="mono dimmer">most recent rotation</span>}
          />
          <StatTile
            label={t('console.secrets.tiles.attention')}
            value={String(secrets.filter((row) => !row.last_rotated_at).length)}
            sub={<span className="mono dimmer">never rotated</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'vault', label: t('console.secrets.tabs.vault'), count: secrets.length },
            { id: 'rotations', label: t('console.secrets.tabs.rotations') },
            { id: 'usage', label: t('console.secrets.tabs.usage') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'vault' ? (
          <>
            {(
              [
                ['all', t('console.secrets.filters.all'), secrets.length],
                ['apiKeys', t('console.secrets.filters.apiKeys'), countByKind((k) => k === 'API key')],
                ['tokens', t('console.secrets.filters.tokens'), countByKind((k) => k === 'token')],
                ['configs', t('console.secrets.filters.configs'), countByKind((k) => k === 'kubeconfig')],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.secrets.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'vault' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.secrets.columns.reference')}</TableHead>
                <TableHead>{t('console.secrets.columns.kind')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.bound')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.rotated')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.due')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.lastUsed')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={secretsQuery.isPending}
                  isError={secretsQuery.isError}
                />
              ) : (
                rows.map((row) => (
                  <TableRow key={row.id} className="rowlink">
                    <TableCell className="mono">vault:{row.name}</TableCell>
                    <TableCell className="dim">{kindOf(row.name)}</TableCell>
                    {/* Binding counts, rotation policy and last-use are not
                        surfaced by the secrets API. */}
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dim">{relativeTime(row.last_rotated_at)}</TableCell>
                    <TableCell className="num dim">—</TableCell>
                    <TableCell className="num dimmer">—</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.secrets.vaultNote')} />
        </WorkbenchPanel>
      )}

      {/* The vault records only last_rotated_at — there is no rotation history
          resource and no per-secret resolution counter to read. */}
      {tab === 'rotations' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.common.empty')}
            <span className="mono">{t('console.secrets.rotationsNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      {tab === 'usage' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.common.empty')}
            <span className="mono">{t('console.secrets.usageNote')}</span>
          </div>
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
