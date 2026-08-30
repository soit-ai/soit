import { useMemo, useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  ConsoleTabs,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconExport,
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
import { catColor, relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAgentWorkbench } from '@/services/agent-service'
import {
  createResourceGrant,
  listResourceGrants,
  listWorkspaceMembers,
  revokeResourceGrant,
  type ResourceGrant,
} from '@/services/identity-service'
import { getKnowledgeWorkbench } from '@/services/knowledge-service'
import { getWorkflowWorkbench } from '@/services/workflow-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

type AccessTab = 'grants' | 'byResource' | 'changes'
type KindFilter = 'all' | 'agent' | 'workflow' | 'knowledge' | 'write'

/** The action vocabulary the server accepts on a grant. */
const ACTIONS = ['read', 'run', 'update', 'delete'] as const
type Action = (typeof ACTIONS)[number]

/** Anything beyond read means the holder can change the resource. */
const WRITE_ACTIONS: string[] = ['update', 'delete']

const RESOURCE_KINDS = ['agent', 'workflow', 'knowledge'] as const
type ResourceKind = (typeof RESOURCE_KINDS)[number]

interface Resource {
  kind: ResourceKind
  id: string
  name: string
  owner?: string | null
  updated_at?: string | null
}

/** A grant joined to the resource it protects, which the API does not return. */
interface GrantRow extends ResourceGrant {
  resource: Resource
}

const PAGE_SIZE = 50

export default function ConsoleAccess() {
  const { t } = useTranslation()
  const [tab, setTab] = useState<AccessTab>('grants')
  const [filter, setFilter] = useState<KindFilter>('all')
  const [search, setSearch] = useState('')

  const workspaceId =
    useUserStore((state) => state.currentUser?.workspace_id) ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')

  // Grants are addressed per resource, so the page first has to know which
  // resources exist before it can ask who has access to them.
  const agentsQuery = useQuery({
    queryKey: ['console', 'access', 'agents'],
    queryFn: () => getAgentWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const workflowsQuery = useQuery({
    queryKey: ['console', 'access', 'workflows'],
    queryFn: () => getWorkflowWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const knowledgeQuery = useQuery({
    queryKey: ['console', 'access', 'knowledge'],
    queryFn: () => getKnowledgeWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const membersQuery = useQuery({
    queryKey: ['console', 'access', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: { enabled: Boolean(workspaceId), retry: false, refetchOnWindowFocus: false },
  })

  const resources = useMemo<Resource[]>(() => {
    const rows: Resource[] = []
    ;(agentsQuery.data?.items || []).forEach((row) =>
      rows.push({ kind: 'agent', id: row.id, name: row.name, owner: row.owner, updated_at: row.updated_at }),
    )
    ;(workflowsQuery.data?.items || []).forEach((row) =>
      rows.push({ kind: 'workflow', id: row.id, name: row.name, owner: row.owner, updated_at: row.updated_at }),
    )
    ;(knowledgeQuery.data?.items || []).forEach((row) =>
      rows.push({ kind: 'knowledge', id: row.id, name: row.name, owner: row.owner, updated_at: row.updated_at }),
    )
    return rows
  }, [agentsQuery.data, workflowsQuery.data, knowledgeQuery.data])

  // BACKEND-PENDING: /resource-grants requires resource_type and resource_id,
  // so there is no way to read a workspace's grants in one call. This fans out
  // over the resources above; a workspace-scoped listing would replace it.
  const resourceKey = resources.map((row) => `${row.kind}:${row.id}`).join(',')
  const grantsQuery = useQuery({
    queryKey: ['console', 'access', 'grants', resourceKey],
    queryFn: async () => {
      const settled = await Promise.all(
        resources.map((resource) =>
          listResourceGrants(resource.kind, resource.id, { suppressErrorToast: true })
            .then((grants) => grants.map((grant) => ({ ...grant, resource })))
            .catch(() => [] as GrantRow[]),
        ),
      )
      return settled.flat()
    },
    options: {
      enabled: resources.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const grants = useMemo(() => grantsQuery.data || [], [grantsQuery.data])
  const members = membersQuery.data || []
  const memberLabel = (userId: string) => {
    const member = members.find((row) => row.user_id === userId)
    return member?.name || member?.email || userId
  }
  const memberSub = (userId: string) => {
    const member = members.find((row) => row.user_id === userId)
    return [member?.email, member?.role].filter(Boolean).join(' · ') || userId
  }

  const isWrite = (grant: GrantRow) => grant.actions.some((a) => WRITE_ACTIONS.includes(a))

  const rows = grants.filter((grant) => {
    if (filter === 'write' && !isWrite(grant)) return false
    if (filter !== 'all' && filter !== 'write' && grant.resource.kind !== filter) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [memberLabel(grant.user_id), grant.resource.name, grant.resource.kind]
      .some((value) => String(value).toLowerCase().includes(query))
  })

  const countOfKind = (kind: ResourceKind) => grants.filter((g) => g.resource.kind === kind).length

  // Grouping the same grants by what they protect.
  const byResource = useMemo(() => {
    const map = new Map<string, { resource: Resource; grants: GrantRow[] }>()
    grants.forEach((grant) => {
      const key = `${grant.resource.kind}:${grant.resource.id}`
      const entry = map.get(key)
      if (entry) entry.grants.push(grant)
      else map.set(key, { resource: grant.resource, grants: [grant] })
    })
    return [...map.values()]
  }, [grants])

  const highestAction = (list: GrantRow[]): string => {
    const all = new Set(list.flatMap((g) => g.actions))
    for (const action of [...ACTIONS].reverse()) if (all.has(action)) return action
    return '—'
  }

  const [granting, setGranting] = useState(false)
  const [revoking, setRevoking] = useState<GrantRow | null>(null)
  const [form, setForm] = useState<{ user_id: string; kind: ResourceKind; resource_id: string; actions: Action[] }>({
    user_id: '',
    kind: 'agent',
    resource_id: '',
    actions: ['read'],
  })

  const afterWrite = () => {
    setGranting(false)
    setRevoking(null)
    void grantsQuery.refetch()
  }

  const grantMutation = useMutation({
    mutationKey: ['console', 'access', 'grant'],
    mutationFn: () =>
      createResourceGrant(
        {
          resource_type: form.kind,
          resource_id: effectiveResourceId,
          user_id: effectiveUserId.trim(),
          actions: form.actions,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to grant access'))
    },
  })

  const revokeMutation = useMutation({
    mutationKey: ['console', 'access', 'revoke'],
    mutationFn: () =>
      revokeResourceGrant(
        revoking!.resource.kind,
        revoking!.resource.id,
        revoking!.user_id,
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to revoke access'))
    },
  })

  const resourcesOfKind = resources.filter((row) => row.kind === form.kind)
  // The dialog can open before these queries settle, so fall back to the first
  // available option rather than leaving the form unsubmittable.
  const effectiveUserId = form.user_id || members[0]?.user_id || ''
  const effectiveResourceId = form.resource_id || resourcesOfKind[0]?.id || ''
  const scanning =
    agentsQuery.isPending || workflowsQuery.isPending || knowledgeQuery.isPending || grantsQuery.isPending
  const scanFailed = agentsQuery.isError && workflowsQuery.isError && knowledgeQuery.isError

  const toggleAction = (action: Action) =>
    setForm((state) => ({
      ...state,
      actions: state.actions.includes(action)
        ? state.actions.filter((a) => a !== action)
        : [...state.actions, action],
    }))

  return (
    <Workbench
      title={t('console.access.title')}
      description={t('console.access.description')}
      actions={
        <>
          <ConsoleButton>
            <IconExport />
            {t('console.common.export')}
          </ConsoleButton>
          <ConsoleButton
            variant="primary"
            disabled={resources.length === 0}
            onClick={() => {
              setForm({
                user_id: members[0]?.user_id || '',
                kind: 'agent',
                resource_id: resources.find((r) => r.kind === 'agent')?.id || '',
                actions: ['read'],
              })
              setGranting(true)
            }}
          >
            <IconPlus />
            {t('console.access.grant')}
          </ConsoleButton>
        </>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.access.tiles.grants')}
            value={grantsQuery.data ? String(grants.length) : '—'}
            na={!grantsQuery.data}
            sub={
              <span className="mono dimmer">
                {countOfKind('agent')} agents · {countOfKind('workflow')} workflows ·{' '}
                {countOfKind('knowledge')} knowledge
              </span>
            }
          />
          <StatTile
            label={t('console.access.tiles.people')}
            value={grantsQuery.data ? String(new Set(grants.map((g) => g.user_id)).size) : '—'}
            na={!grantsQuery.data}
            sub={<span className="mono dimmer">of {members.length} members</span>}
          />
          <StatTile
            label={t('console.access.tiles.resources')}
            value={grantsQuery.data ? String(byResource.length) : '—'}
            na={!grantsQuery.data}
            sub={<span className="mono dimmer">rest inherit workspace role</span>}
          />
          <StatTile
            label={t('console.access.tiles.writeCapable')}
            value={grantsQuery.data ? String(grants.filter(isWrite).length) : '—'}
            na={!grantsQuery.data}
            sub={<span className="mono dimmer">update or delete on a resource</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'grants', label: t('console.access.tabs.grants'), count: grants.length },
            { id: 'byResource', label: t('console.access.tabs.byResource'), count: byResource.length },
            { id: 'changes', label: t('console.access.tabs.changes') },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
      filters={
        tab === 'grants' ? (
          <>
            {(
              [
                ['all', t('console.access.filters.all'), grants.length],
                ['agent', t('console.access.filters.agents'), countOfKind('agent')],
                ['workflow', t('console.access.filters.workflows'), countOfKind('workflow')],
                ['knowledge', t('console.access.filters.knowledge'), countOfKind('knowledge')],
                ['write', t('console.access.filters.writeCapable'), grants.filter(isWrite).length],
              ] as const
            ).map(([value, label, count]) => (
              <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
                {label}
              </FilterChip>
            ))}
            <FilterSearch
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={t('console.access.filters.searchPlaceholder')}
            />
          </>
        ) : undefined
      }
    >
      {tab === 'grants' && (
        <WorkbenchPanel>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.access.columns.person')}</TableHead>
                <TableHead>{t('console.access.columns.resource')}</TableHead>
                <TableHead>{t('console.access.columns.kind')}</TableHead>
                <TableHead>{t('console.access.columns.actions')}</TableHead>
                <TableHead>{t('console.access.columns.grantedBy')}</TableHead>
                <TableHead className="num">{t('console.access.columns.granted')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.length === 0 ? (
                <DataStateRow
                  colSpan={7}
                  isPending={scanning}
                  isError={scanFailed}
                  emptyLabel={t('console.access.empty')}
                />
              ) : (
                rows.map((grant) => (
                  <TableRow key={`${grant.resource.kind}:${grant.resource.id}:${grant.user_id}`} className="rowlink">
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{memberLabel(grant.user_id)}</b>
                      <br />
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {memberSub(grant.user_id)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(grant.resource.id) } as React.CSSProperties}>
                        <i />
                        {grant.resource.name}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{grant.resource.kind}</TableCell>
                    <TableCell>
                      <span className="scopes">
                        {grant.actions.map((action) => (
                          <span key={action} className="chip">
                            {action}
                          </span>
                        ))}
                      </span>
                    </TableCell>
                    <TableCell className="dim">
                      {grant.created_by ? memberLabel(grant.created_by) : '—'}
                    </TableCell>
                    <TableCell className="num dimmer">{relativeTime(grant.created_at)}</TableCell>
                    <TableCell className="num">
                      <ConsoleButton
                        variant="ghost"
                        size="sm"
                        style={{ color: 'var(--danger-foreground)' }}
                        onClick={() => setRevoking(grant)}
                      >
                        {t('console.access.revoke')}
                      </ConsoleButton>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.access.grantsNote')} />
        </WorkbenchPanel>
      )}

      {tab === 'byResource' && (
        <WorkbenchPanel
          className="mt-3.5"
          title={t('console.access.byResourceTitle')}
          hint={t('console.access.byResourceHint')}
        >
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.access.columns.resource')}</TableHead>
                <TableHead>{t('console.access.columns.kind')}</TableHead>
                <TableHead>{t('console.access.columns.owner')}</TableHead>
                <TableHead className="num">{t('console.access.columns.people')}</TableHead>
                <TableHead>{t('console.access.columns.highest')}</TableHead>
                <TableHead className="num">{t('console.access.columns.lastChange')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {byResource.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={scanning}
                  isError={scanFailed}
                  emptyLabel={t('console.access.empty')}
                />
              ) : (
                byResource.map(({ resource, grants: list }) => (
                  <TableRow key={`${resource.kind}:${resource.id}`} className="rowlink">
                    <TableCell>
                      <span className="idm" style={{ '--c': catColor(resource.id) } as React.CSSProperties}>
                        <i />
                        {resource.name}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{resource.kind}</TableCell>
                    <TableCell className="dim">{resource.owner || '—'}</TableCell>
                    <TableCell className="num dim">
                      {new Set(list.map((g) => g.user_id)).size}
                    </TableCell>
                    <TableCell>
                      <span className="chip">{highestAction(list)}</span>
                    </TableCell>
                    <TableCell className="num dimmer">
                      {relativeTime(
                        list.map((g) => g.updated_at || g.created_at).sort().reverse()[0],
                      )}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.access.byResourceNote')} />
        </WorkbenchPanel>
      )}

      {/* Grant changes are not their own audit object: /runs/audits covers
          governed calls and /security/egress/audits covers policy edits, and
          neither records who granted what. */}
      {tab === 'changes' && (
        <WorkbenchPanel className="mt-3.5">
          <div className="empty-note">
            {t('console.access.changesEmpty')}
            <span className="mono">{t('console.access.changesNote')}</span>
          </div>
        </WorkbenchPanel>
      )}

      <ConsoleModal
        open={granting}
        onOpenChange={setGranting}
        title={t('console.access.grantTitle')}
        note={t('console.access.grantNote')}
        confirmLabel={t('console.access.grant')}
        confirmDisabled={!effectiveUserId || !effectiveResourceId || form.actions.length === 0}
        busy={grantMutation.isPending}
        onConfirm={() => grantMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.access.fields.person')}
            <small>{t('console.access.fields.personHint')}</small>
          </label>
          <select
            className="input"
            value={effectiveUserId}
            onChange={(event) => setForm((state) => ({ ...state, user_id: event.target.value }))}
          >
            {members.map((member) => (
              <option key={member.user_id} value={member.user_id}>
                {member.name || member.email || member.user_id}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>{t('console.access.fields.kind')}</label>
          <div className="checks" style={{ flexDirection: 'row', gap: 8 }}>
            {RESOURCE_KINDS.map((kind) => (
              <FilterChip
                key={kind}
                active={form.kind === kind}
                onClick={() =>
                  setForm((state) => ({
                    ...state,
                    kind,
                    resource_id: resources.find((r) => r.kind === kind)?.id || '',
                  }))
                }
              >
                {kind}
              </FilterChip>
            ))}
          </div>
        </div>
        <div className="mrow">
          <label>{t('console.access.fields.resource')}</label>
          <select
            className="input"
            value={effectiveResourceId}
            onChange={(event) => setForm((state) => ({ ...state, resource_id: event.target.value }))}
          >
            {resourcesOfKind.map((resource) => (
              <option key={resource.id} value={resource.id}>
                {resource.name}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.access.fields.actions')}
            <small>{t('console.access.fields.actionsHint')}</small>
          </label>
          <div className="checks">
            {ACTIONS.map((action) => (
              <label key={action}>
                <input
                  type="checkbox"
                  checked={form.actions.includes(action)}
                  onChange={() => toggleAction(action)}
                />
                {action}{' '}
                <span className="mono dimmer">
                  {t(`console.access.actionHints.${action}` as 'console.access.actionHints.read')}
                </span>
              </label>
            ))}
          </div>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={revoking != null}
        onOpenChange={(open) => !open && setRevoking(null)}
        title={t('console.access.revokeTitle')}
        confirmLabel={t('console.access.revoke')}
        destructive
        busy={revokeMutation.isPending}
        onConfirm={() => revokeMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.access.revokeConfirm', {
            user: revoking ? memberLabel(revoking.user_id) : '',
            resource: revoking?.resource.name ?? '',
          })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
