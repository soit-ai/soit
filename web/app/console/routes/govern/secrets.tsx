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
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import {
  mockSecretRotations,
  mockSecretTiles,
  mockSecretUsage,
  mockSecrets,
} from '../../mocks/govern'
import { useTranslation } from '@/i18n'

type SecretsTab = 'vault' | 'rotations' | 'usage'
type KindFilter = 'all' | 'apiKeys' | 'tokens' | 'configs'

const KIND_MATCH: Record<KindFilter, (kind: string) => boolean> = {
  all: () => true,
  apiKeys: (kind) => kind === 'API key',
  tokens: (kind) => kind === 'token',
  configs: (kind) => kind === 'kubeconfig',
}

// BACKEND-PENDING: secrets CRUD + test are live endpoints; rotations
// degrade to fixtures where the endpoint is absent.
export default function ConsoleSecrets() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<SecretsTab>('vault')
  const [filter, setFilter] = useState<KindFilter>('all')
  const [search, setSearch] = useState('')

  const rows = mockSecrets.filter((row) => {
    if (!KIND_MATCH[filter](row.kind)) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return row.ref.toLowerCase().includes(query)
  })

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
          <StatTile label={t('console.secrets.tiles.secrets')} value={mockSecretTiles.secrets.value} sub={<span className="mono dimmer">{mockSecretTiles.secrets.sub}</span>} />
          <StatTile label={t('console.secrets.tiles.resolutions')} value={mockSecretTiles.resolutions.value} sub={<span className="mono dimmer">{mockSecretTiles.resolutions.sub}</span>} />
          <StatTile label={t('console.secrets.tiles.rotation')} value={mockSecretTiles.rotation.value} sub={<span className="mono dimmer">{mockSecretTiles.rotation.sub}</span>} />
          <StatTile label={t('console.secrets.tiles.attention')} value={mockSecretTiles.attention.value} sub={<span className="mono dimmer">{mockSecretTiles.attention.sub}</span>} />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'vault', label: t('console.secrets.tabs.vault'), count: 4 },
            { id: 'rotations', label: t('console.secrets.tabs.rotations'), count: 3 },
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
                ['all', t('console.secrets.filters.all'), 4],
                ['apiKeys', t('console.secrets.filters.apiKeys'), 1],
                ['tokens', t('console.secrets.filters.tokens'), 2],
                ['configs', t('console.secrets.filters.configs'), 1],
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
              {rows.map((row) => (
                <TableRow key={row.ref} className="rowlink">
                  <TableCell className="mono">{row.ref}</TableCell>
                  <TableCell className="dim">{row.kind}</TableCell>
                  <TableCell className="num dim">{row.bound}</TableCell>
                  <TableCell className="num dim">{row.rotated}</TableCell>
                  <TableCell
                    className="num"
                    style={row.due_warn ? { color: 'var(--warning-foreground)' } : undefined}
                  >
                    {row.due}
                  </TableCell>
                  <TableCell className="num dimmer">{row.last_used}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.secrets.vaultNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'rotations' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.secrets.columns.time')}</TableHead>
                <TableHead>{t('console.secrets.columns.secret')}</TableHead>
                <TableHead>{t('console.secrets.columns.rotatedBy')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.rebound')}</TableHead>
                <TableHead>{t('console.secrets.columns.audit')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockSecretRotations.map((row) => (
                <TableRow key={row.audit}>
                  <TableCell className="num dimmer">{row.time}</TableCell>
                  <TableCell className="mono">{row.secret}</TableCell>
                  <TableCell className="dim">{row.by}</TableCell>
                  <TableCell className="num dim">{row.rebound}</TableCell>
                  <TableCell>
                    <a
                      className="runid"
                      href="/v2/govern/audit"
                      onClick={(event) => {
                        event.preventDefault()
                        navigate('/v2/govern/audit')
                      }}
                    >
                      {row.audit}
                    </a>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.secrets.rotationsNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'usage' && (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.secrets.columns.secret')}</TableHead>
                <TableHead>{t('console.secrets.columns.consumers')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.resolutions')}</TableHead>
                <TableHead className="num">{t('console.secrets.columns.denied')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {mockSecretUsage.map((row) => (
                <TableRow key={row.secret}>
                  <TableCell className="mono">{row.secret}</TableCell>
                  <TableCell>
                    <span className="scopes">
                      {row.consumers.map((consumer) => (
                        <span key={consumer} className="chip">
                          {consumer}
                        </span>
                      ))}
                    </span>
                  </TableCell>
                  <TableCell className="num dim">{row.resolutions}</TableCell>
                  <TableCell
                    className="num"
                    style={'denied_bad' in row && row.denied_bad ? { color: 'var(--danger-foreground)' } : undefined}
                  >
                    {row.denied}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          <Pager summary={t('console.secrets.usageNote')} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
