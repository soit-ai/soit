import { useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
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
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createSecret,
  deleteSecret,
  listSecrets,
  testSecret,
  updateSecret,
  type Secret,
} from '@/services/secrets-service'
import { requestErrorMessage } from '@/utils/request'

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

  const [creating, setCreating] = useState(false)
  const [rotating, setRotating] = useState<Secret | null>(null)
  const [deleting, setDeleting] = useState<Secret | null>(null)
  const [form, setForm] = useState({ name: '', description: '', value: '' })

  const secretsQuery = useQuery({
    queryKey: ['console', 'secrets'],
    queryFn: () => listSecrets({ limit: 200 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const afterWrite = () => {
    void secretsQuery.refetch()
    setCreating(false)
    setRotating(null)
    setDeleting(null)
    setForm({ name: '', description: '', value: '' })
  }
  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const createMutation = useMutation({
    mutationKey: ['console', 'secrets', 'create'],
    mutationFn: () =>
      createSecret(
        {
          name: form.name.trim(),
          description: form.description.trim() || undefined,
          value: form.value,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to create the secret'),
  })
  const rotateMutation = useMutation({
    mutationKey: ['console', 'secrets', 'rotate'],
    mutationFn: () =>
      updateSecret(
        rotating!.id,
        {
          description: form.description.trim() || undefined,
          // An empty box means "description only" — do not blank the value.
          ...(form.value ? { value: form.value } : {}),
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to rotate the secret'),
  })
  const deleteMutation = useMutation({
    mutationKey: ['console', 'secrets', 'delete'],
    mutationFn: () => deleteSecret(deleting!.id, { suppressErrorToast: true }),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to delete the secret'),
  })
  const testMutation = useMutation({
    mutationKey: ['console', 'secrets', 'test'],
    mutationFn: (secretId: string) => testSecret(secretId, { suppressErrorToast: true }),
    onSuccess: (result) => {
      if (result.ok) toast.success(result.message || t('console.secrets.testOk'))
      else toast.error(result.message || 'Credential rejected')
    },
    onError: onWriteError('Failed to test the secret'),
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
        <ConsoleButton
          variant="primary"
          onClick={() => {
            setForm({ name: '', description: '', value: '' })
            setCreating(true)
          }}
        >
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
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={7}
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
                    <TableCell className="num">
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          disabled={testMutation.isPending}
                          onClick={() => testMutation.mutate(row.id)}
                        >
                          {t('console.secrets.testAction')}
                        </ConsoleButton>
                        <ConsoleButton
                          size="sm"
                          onClick={() => {
                            setForm({
                              name: row.name,
                              description: row.description || '',
                              value: '',
                            })
                            setRotating(row)
                          }}
                        >
                          {t('console.secrets.rotate')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          style={{ color: 'var(--danger-foreground)' }}
                          onClick={() => setDeleting(row)}
                        >
                          {t('console.secrets.deleteAction')}
                        </ConsoleButton>
                      </span>
                    </TableCell>
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

      <ConsoleModal
        open={creating}
        onOpenChange={setCreating}
        title={t('console.secrets.newTitle')}
        note={t('console.secrets.createNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!form.name.trim() || !form.value}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.secrets.fields.name')}
            <small>{t('console.secrets.fields.nameHint')}</small>
          </label>
          <input
            className="input"
            value={form.name}
            onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.secrets.fields.description')}</label>
          <input
            className="input"
            value={form.description}
            onChange={(event) =>
              setForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.secrets.fields.value')}
            <small>{t('console.secrets.fields.valueHint')}</small>
          </label>
          <textarea
            className="input"
            value={form.value}
            onChange={(event) => setForm((state) => ({ ...state, value: event.target.value }))}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={rotating != null}
        onOpenChange={(open) => !open && setRotating(null)}
        title={t('console.secrets.editTitle')}
        note={t('console.secrets.rotateNote')}
        confirmLabel={t('console.common.save')}
        busy={rotateMutation.isPending}
        onConfirm={() => rotateMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.secrets.fields.name')}</label>
          <input
            className="input"
            value={`vault:${rotating?.name ?? ''}`}
            disabled
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.secrets.fields.description')}</label>
          <input
            className="input"
            value={form.description}
            onChange={(event) =>
              setForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.secrets.fields.value')}
            <small>{t('console.secrets.fields.valueRotateHint')}</small>
          </label>
          <textarea
            className="input"
            value={form.value}
            onChange={(event) => setForm((state) => ({ ...state, value: event.target.value }))}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('console.secrets.deleteTitle')}
        confirmLabel={t('console.secrets.deleteAction')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.secrets.deleteConfirm', { name: `vault:${deleting?.name ?? ''}` })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
