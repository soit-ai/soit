import { useMemo, useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  DataStateRow,
  FilterChip,
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
import { money } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listAgents } from '@/services/agent-service'
import { listApiKeys } from '@/services/api-key-service'
import {
  createBudget,
  deleteBudget,
  listBudgetStatuses,
  updateBudget,
  type BudgetPeriod,
  type BudgetScope,
  type BudgetStatus,
} from '@/services/billing-service'
import { listServicePrincipals, listWorkspaceMembers } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

type StateFilter = 'all' | 'atRisk' | 'exhausted' | 'disabled'

const SCOPES: BudgetScope[] = ['workspace', 'api_key', 'user', 'agent']
const PERIODS: BudgetPeriod[] = ['month', 'day']
const DEFAULT_THRESHOLDS = '50, 80, 100'

interface BudgetForm {
  name: string
  scopeKind: BudgetScope
  scopeId: string
  period: BudgetPeriod
  amount: string
  currency: string
  thresholds: string
  hardStop: boolean
}

const EMPTY_FORM: BudgetForm = {
  name: '',
  scopeKind: 'workspace',
  scopeId: '',
  period: 'month',
  amount: '',
  currency: 'USD',
  thresholds: DEFAULT_THRESHOLDS,
  hardStop: true,
}

/** Thresholds are whole percentages between 1 and 100, at most five. */
function thresholdsOf(text: string): number[] | null {
  const items = text
    .split(/[\s,]+/)
    .map((item) => item.trim())
    .filter(Boolean)
  if (items.length > 5) return null
  const values = items.map(Number)
  if (values.some((value) => !Number.isInteger(value) || value < 1 || value > 100)) return null
  return Array.from(new Set(values)).sort((a, b) => a - b)
}

function amountOf(text: string): string | null {
  const trimmed = text.trim().replaceAll(',', '')
  return /^\d+(\.\d{1,6})?$/.test(trimmed) && Number(trimmed) > 0 ? trimmed : null
}

const percentOf = (status: BudgetStatus) => Number(status.percent) || 0

/** "in 5h" / "in 3d": when a period resets, in the tone of relativeTime. */
function untilLabel(iso: string): string {
  const delta = new Date(iso).getTime() - Date.now()
  if (Number.isNaN(delta)) return iso
  if (delta <= 0) return 'now'
  const hours = Math.floor(delta / 3_600_000)
  if (hours < 1) return `in ${Math.max(1, Math.floor(delta / 60_000))}m`
  if (hours < 48) return `in ${hours}h`
  return `in ${Math.floor(hours / 24)}d`
}

export default function ConsoleBudgets() {
  const { t } = useTranslation()
  const [filter, setFilter] = useState<StateFilter>('all')
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<BudgetStatus | null>(null)
  const [deleting, setDeleting] = useState<BudgetStatus | null>(null)
  const [form, setForm] = useState<BudgetForm>(EMPTY_FORM)

  const workspaceId =
    useUserStore((state) => state.currentUser?.workspace_id) ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')

  const statusesQuery = useQuery({
    queryKey: ['console', 'budgets', 'statuses'],
    queryFn: () => listBudgetStatuses({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // What a budget can be scoped to, so a scope reads as a name, not an id.
  const keysQuery = useQuery({
    queryKey: ['console', 'budgets', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const membersQuery = useQuery({
    queryKey: ['console', 'budgets', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: { enabled: Boolean(workspaceId), retry: false, refetchOnWindowFocus: false },
  })
  const principalsQuery = useQuery({
    queryKey: ['console', 'budgets', 'service-principals'],
    queryFn: () => listServicePrincipals({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const agentsQuery = useQuery({
    queryKey: ['console', 'budgets', 'agents'],
    queryFn: () => listAgents({ page_size: 100 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const targets = useMemo(() => {
    const byScope: Record<BudgetScope, { id: string; name: string }[]> = {
      workspace: [],
      api_key: (keysQuery.data?.items || [])
        .filter((key) => key.status === 'active')
        .map((key) => ({ id: key.id, name: `${key.name} · ${key.key_prefix}…` })),
      user: [
        ...(membersQuery.data || []).map((member) => ({
          id: member.user_id,
          name: member.name || member.email,
        })),
        ...(principalsQuery.data || []).map((principal) => ({
          id: principal.id,
          name: `${principal.name} · ${t('console.budgets.principal')}`,
        })),
      ],
      agent: (agentsQuery.data?.items || []).map((agent) => ({ id: agent.id, name: agent.name })),
    }
    return byScope
  }, [keysQuery.data, membersQuery.data, principalsQuery.data, agentsQuery.data, t])

  const scopeLabel = (status: BudgetStatus) => {
    const { scope_kind: kind, scope_id: id } = status.budget
    if (kind === 'workspace') return t('console.budgets.scopes.workspace')
    const name = targets[kind as BudgetScope]?.find((item) => item.id === id)?.name
    return `${t(`console.budgets.scopes.${kind as BudgetScope}`)} · ${name || id}`
  }

  const afterWrite = () => {
    void statusesQuery.refetch()
    setCreating(false)
    setEditing(null)
    setDeleting(null)
    setForm(EMPTY_FORM)
  }
  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  const amount = amountOf(form.amount)
  const thresholds = thresholdsOf(form.thresholds)
  const formValid =
    Boolean(form.name.trim()) &&
    amount != null &&
    thresholds != null &&
    /^[A-Z]{3}$/.test(form.currency) &&
    (form.scopeKind === 'workspace' || Boolean(form.scopeId))

  const createMutation = useMutation({
    mutationKey: ['console', 'budgets', 'create'],
    mutationFn: () =>
      createBudget(
        {
          name: form.name.trim(),
          scope_kind: form.scopeKind,
          ...(form.scopeKind === 'workspace' ? {} : { scope_id: form.scopeId }),
          period: form.period,
          amount: amount!,
          currency: form.currency,
          thresholds: thresholds!,
          hard_stop: form.hardStop,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to create the budget'),
  })
  const updateMutation = useMutation({
    mutationKey: ['console', 'budgets', 'update'],
    mutationFn: () =>
      updateBudget(
        editing!.budget.id,
        {
          name: form.name.trim(),
          amount: amount!,
          thresholds: thresholds!,
          hard_stop: form.hardStop,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to change the budget'),
  })
  const toggleMutation = useMutation<unknown, unknown, BudgetStatus>({
    mutationKey: ['console', 'budgets', 'toggle'],
    mutationFn: (status: BudgetStatus) =>
      updateBudget(
        status.budget.id,
        { status: status.budget.status === 'active' ? 'disabled' : 'active' },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void statusesQuery.refetch()
    },
    onError: onWriteError('Failed to change the budget'),
  })
  const deleteMutation = useMutation({
    mutationKey: ['console', 'budgets', 'delete'],
    mutationFn: () => deleteBudget(deleting!.budget.id, { suppressErrorToast: true }),
    onSuccess: afterWrite,
    onError: onWriteError('Failed to delete the budget'),
  })

  const statuses = statusesQuery.data || []
  const active = statuses.filter((status) => status.budget.status === 'active')
  const atRisk = active.filter((status) => percentOf(status) >= 80 && percentOf(status) < 100)
  const exhausted = active.filter((status) => percentOf(status) >= 100)
  const overForecast = active.filter(
    (status) => Number(status.forecast) > Number(status.budget.amount),
  )
  const rows = statuses.filter((status) => {
    if (filter === 'atRisk') return atRisk.includes(status)
    if (filter === 'exhausted') return exhausted.includes(status)
    if (filter === 'disabled') return status.budget.status !== 'active'
    return true
  })

  const openEdit = (status: BudgetStatus) => {
    setForm({
      name: status.budget.name,
      scopeKind: status.budget.scope_kind as BudgetScope,
      scopeId: status.budget.scope_id || '',
      period: status.budget.period as BudgetPeriod,
      amount: String(Number(status.budget.amount)),
      currency: status.budget.currency,
      thresholds: status.budget.thresholds.join(', '),
      hardStop: status.budget.hard_stop,
    })
    setEditing(status)
  }

  const formRows = (editable: boolean) => (
    <>
      <div className="mrow">
        <label>{t('console.budgets.fields.name')}</label>
        <input
          className="input"
          value={form.name}
          onChange={(event) => setForm((state) => ({ ...state, name: event.target.value }))}
        />
      </div>
      <div className="mrow">
        <label>
          {t('console.budgets.fields.scope')}
          <small>{t('console.budgets.fields.scopeHint')}</small>
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <select
            className="input"
            value={form.scopeKind}
            disabled={!editable}
            onChange={(event) =>
              setForm((state) => ({
                ...state,
                scopeKind: event.target.value as BudgetScope,
                scopeId: '',
              }))
            }
          >
            {SCOPES.map((scope) => (
              <option key={scope} value={scope}>
                {t(`console.budgets.scopes.${scope}`)}
              </option>
            ))}
          </select>
          {form.scopeKind !== 'workspace' && (
            <select
              className="input"
              aria-label={t('console.budgets.fields.target')}
              value={form.scopeId}
              disabled={!editable}
              onChange={(event) => setForm((state) => ({ ...state, scopeId: event.target.value }))}
            >
              <option value="">{t('console.budgets.fields.pickTarget')}</option>
              {targets[form.scopeKind].map((target) => (
                <option key={target.id} value={target.id}>
                  {target.name}
                </option>
              ))}
              {form.scopeId &&
                !targets[form.scopeKind].some((target) => target.id === form.scopeId) && (
                  <option value={form.scopeId}>{form.scopeId}</option>
                )}
            </select>
          )}
        </div>
      </div>
      <div className="mrow">
        <label>{t('console.budgets.fields.period')}</label>
        <select
          className="input"
          value={form.period}
          disabled={!editable}
          onChange={(event) =>
            setForm((state) => ({ ...state, period: event.target.value as BudgetPeriod }))
          }
        >
          {PERIODS.map((period) => (
            <option key={period} value={period}>
              {t(`console.budgets.periods.${period}`)}
            </option>
          ))}
        </select>
      </div>
      <div className="mrow">
        <label>
          {t('console.budgets.fields.amount')}
          <small>{t('console.budgets.fields.amountHint')}</small>
        </label>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            className="input"
            inputMode="decimal"
            value={form.amount}
            placeholder="100"
            onChange={(event) => setForm((state) => ({ ...state, amount: event.target.value }))}
          />
          <input
            className="input"
            aria-label={t('console.budgets.fields.currency')}
            value={form.currency}
            disabled={!editable}
            maxLength={3}
            style={{ width: 72, fontFamily: 'var(--font-mono)' }}
            onChange={(event) =>
              setForm((state) => ({ ...state, currency: event.target.value.toUpperCase() }))
            }
          />
        </div>
      </div>
      <div className="mrow">
        <label>
          {t('console.budgets.fields.thresholds')}
          <small>{t('console.budgets.fields.thresholdsHint')}</small>
        </label>
        <input
          className="input"
          value={form.thresholds}
          onChange={(event) => setForm((state) => ({ ...state, thresholds: event.target.value }))}
          style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
        />
      </div>
      <div className="mrow">
        <label>
          {t('console.budgets.fields.hardStop')}
          <small>{t('console.budgets.fields.hardStopHint')}</small>
        </label>
        <select
          className="input"
          value={form.hardStop ? 'stop' : 'warn'}
          onChange={(event) =>
            setForm((state) => ({ ...state, hardStop: event.target.value === 'stop' }))
          }
        >
          <option value="stop">{t('console.budgets.fields.stop')}</option>
          <option value="warn">{t('console.budgets.fields.warnOnly')}</option>
        </select>
      </div>
    </>
  )

  return (
    <Workbench
      title={t('console.budgets.title')}
      description={t('console.budgets.description')}
      actions={
        <ConsoleButton
          variant="primary"
          onClick={() => {
            setForm(EMPTY_FORM)
            setCreating(true)
          }}
        >
          <IconPlus />
          {t('console.budgets.create')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.budgets.tiles.active')}
            value={statusesQuery.data ? String(active.length) : '—'}
            na={!statusesQuery.data}
            sub={
              <span className="mono dimmer">
                {t('console.budgets.tiles.activeSub', { count: statuses.length })}
              </span>
            }
          />
          <StatTile
            label={t('console.budgets.tiles.atRisk')}
            value={statusesQuery.data ? String(atRisk.length) : '—'}
            na={!statusesQuery.data}
            sub={<span className="mono dimmer">{t('console.budgets.tiles.atRiskSub')}</span>}
          />
          <StatTile
            label={t('console.budgets.tiles.exhausted')}
            value={statusesQuery.data ? String(exhausted.length) : '—'}
            na={!statusesQuery.data}
            sub={<span className="mono dimmer">{t('console.budgets.tiles.exhaustedSub')}</span>}
          />
          <StatTile
            label={t('console.budgets.tiles.forecast')}
            value={statusesQuery.data ? String(overForecast.length) : '—'}
            na={!statusesQuery.data}
            sub={<span className="mono dimmer">{t('console.budgets.tiles.forecastSub')}</span>}
          />
        </StatTileGrid>
      }
      filters={
        <>
          {(
            [
              ['all', t('console.budgets.filters.all'), statuses.length],
              ['atRisk', t('console.budgets.filters.atRisk'), atRisk.length],
              ['exhausted', t('console.budgets.filters.exhausted'), exhausted.length],
              [
                'disabled',
                t('console.budgets.filters.disabled'),
                statuses.length - active.length,
              ],
            ] as const
          ).map(([value, label, count]) => (
            <FilterChip
              key={value}
              active={filter === value}
              count={count}
              onClick={() => setFilter(value)}
            >
              {label}
            </FilterChip>
          ))}
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.budgets.columns.name')}</TableHead>
              <TableHead>{t('console.budgets.columns.scope')}</TableHead>
              <TableHead>{t('console.budgets.columns.spent')}</TableHead>
              <TableHead className="num">{t('console.budgets.columns.forecast')}</TableHead>
              <TableHead className="num">{t('console.budgets.columns.resets')}</TableHead>
              <TableHead className="num">{t('console.budgets.columns.onLimit')}</TableHead>
              <TableHead className="num" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <DataStateRow
                colSpan={7}
                isPending={statusesQuery.isPending}
                isError={statusesQuery.isError}
                emptyLabel={t('console.budgets.empty')}
              />
            ) : (
              rows.map((status) => {
                const { budget } = status
                const percent = percentOf(status)
                const tone =
                  percent >= 100
                    ? 'var(--danger-foreground)'
                    : percent >= 80
                      ? 'var(--warning-foreground)'
                      : 'var(--primary)'
                const disabled = budget.status !== 'active'
                return (
                  <TableRow key={budget.id} style={disabled ? { opacity: 0.6 } : undefined}>
                    <TableCell>
                      <b style={{ fontWeight: 600 }}>{budget.name}</b>
                      <span className="dimmer mono" style={{ display: 'block', fontSize: 10.5 }}>
                        {t(`console.budgets.periods.${budget.period as BudgetPeriod}`)} ·{' '}
                        {budget.thresholds.map((value) => `${value}%`).join(' ')}
                      </span>
                    </TableCell>
                    <TableCell className="dim">{scopeLabel(status)}</TableCell>
                    <TableCell>
                      <span className="progress" title={`${status.percent}%`}>
                        <span className="track">
                          <i style={{ width: `${Math.min(percent, 100)}%`, background: tone }} />
                        </span>
                        <em>
                          {money(Number(status.spent), budget.currency)} /{' '}
                          {money(Number(budget.amount), budget.currency)}
                        </em>
                      </span>
                    </TableCell>
                    <TableCell
                      className="num"
                      style={
                        Number(status.forecast) > Number(budget.amount)
                          ? { color: 'var(--warning-foreground)' }
                          : undefined
                      }
                    >
                      {money(Number(status.forecast), budget.currency)}
                    </TableCell>
                    <TableCell className="num dimmer">{untilLabel(status.resets_at)}</TableCell>
                    <TableCell className="num">
                      {disabled ? (
                        <StatusChip status="disabled" />
                      ) : budget.hard_stop ? (
                        <StatusChip status="block" label={t('console.budgets.stops')} />
                      ) : (
                        <StatusChip status="warn" label={t('console.budgets.warns')} />
                      )}
                    </TableCell>
                    <TableCell className="num">
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton size="sm" onClick={() => openEdit(status)}>
                          {t('console.budgets.edit')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          disabled={toggleMutation.isPending}
                          onClick={() => toggleMutation.mutate(status)}
                        >
                          {disabled ? t('console.budgets.enable') : t('console.budgets.disable')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          size="sm"
                          style={{ color: 'var(--danger-foreground)' }}
                          onClick={() => setDeleting(status)}
                        >
                          {t('console.budgets.delete')}
                        </ConsoleButton>
                      </span>
                    </TableCell>
                  </TableRow>
                )
              })
            )}
          </TableBody>
        </Table>
        <Pager summary={t('console.budgets.note')} />
      </WorkbenchPanel>

      <ConsoleModal
        open={creating}
        onOpenChange={setCreating}
        title={t('console.budgets.createTitle')}
        note={t('console.budgets.createNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!formValid}
        busy={createMutation.isPending}
        onConfirm={() => createMutation.mutate(undefined)}
      >
        {formRows(true)}
      </ConsoleModal>

      <ConsoleModal
        open={editing != null}
        onOpenChange={(open) => !open && setEditing(null)}
        title={t('console.budgets.editTitle')}
        note={t('console.budgets.editNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!formValid}
        busy={updateMutation.isPending}
        onConfirm={() => updateMutation.mutate(undefined)}
      >
        {formRows(false)}
      </ConsoleModal>

      <ConsoleModal
        open={deleting != null}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={t('console.budgets.deleteTitle')}
        confirmLabel={t('console.budgets.delete')}
        destructive
        busy={deleteMutation.isPending}
        onConfirm={() => deleteMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.budgets.deleteConfirm', { name: deleting?.budget.name ?? '' })}
        </div>
      </ConsoleModal>
    </Workbench>
  )
}
