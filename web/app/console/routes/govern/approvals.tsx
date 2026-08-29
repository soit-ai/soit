import { useMemo, useState } from 'react'

import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleTabs,
  DataStateRow,
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
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { relativeTime } from '../../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  listApprovals,
  resolveApproval,
  type ApprovalResponse,
} from '@/services/observe-service'
import { requestErrorMessage } from '@/utils/request'

const PAGE_SIZE = 50

/** Elapsed wait for a pending request, or turnaround for a decided one. */
function elapsed(from?: string | null, to?: string | null): string {
  if (!from) return '—'
  const start = new Date(from).getTime()
  const end = to ? new Date(to).getTime() : Date.now()
  if (Number.isNaN(start) || Number.isNaN(end)) return '—'
  const minutes = Math.max(0, Math.round((end - start) / 60_000))
  if (minutes < 60) return `${minutes}m`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function median(values: number[]): string {
  if (values.length === 0) return '—'
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  const value =
    sorted.length % 2 === 0 ? (sorted[middle - 1] + sorted[middle]) / 2 : sorted[middle]
  const minutes = Math.round(value / 60_000)
  if (minutes < 60) return `${minutes}m`
  return `${(minutes / 60).toFixed(1)}h`
}

function decisionStatus(status: ApprovalResponse['status']) {
  if (status === 'approved') return { status: 'pass' as const, label: 'APPROVED' }
  if (status === 'rejected') return { status: 'blocked' as const, label: 'REJECTED' }
  if (status === 'canceled') return { status: 'info' as const, label: 'CANCELED' }
  return { status: 'running' as const, label: 'PENDING' }
}

export default function ConsoleApprovals() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [tab, setTab] = useState<'pending' | 'decided'>('pending')

  const pendingQuery = useQuery({
    queryKey: ['console', 'approvals', 'pending'],
    queryFn: () => listApprovals({ status: 'pending', page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // The API filters by a single status, so the decided view merges the three
  // terminal states rather than asking for "everything that is not pending".
  const decidedQuery = useQuery({
    queryKey: ['console', 'approvals', 'decided'],
    queryFn: async () => {
      const [approved, rejected, canceled] = await Promise.all([
        listApprovals({ status: 'approved', page_size: PAGE_SIZE }),
        listApprovals({ status: 'rejected', page_size: PAGE_SIZE }),
        listApprovals({ status: 'canceled', page_size: PAGE_SIZE }),
      ])
      return [...approved.items, ...rejected.items, ...canceled.items].sort((a, b) =>
        String(b.resolved_at || b.created_at).localeCompare(String(a.resolved_at || a.created_at)),
      )
    },
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const pending = pendingQuery.data?.items || []
  const decided = decidedQuery.data || []

  const resolveMutation = useMutation({
    mutationKey: ['console', 'approvals', 'resolve'],
    mutationFn: ({ id, status }: { id: string; status: 'approved' | 'rejected' }) =>
      resolveApproval(id, { status }, { suppressErrorToast: true }),
    onSuccess: () => {
      void pendingQuery.refetch()
      void decidedQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to resolve the approval'))
    },
  })

  const turnarounds = useMemo(
    () =>
      decided
        .filter((row) => row.resolved_at)
        .map((row) => new Date(row.resolved_at as string).getTime() - new Date(row.created_at).getTime())
        .filter((value) => Number.isFinite(value) && value >= 0),
    [decided],
  )

  const oldestPending = useMemo(() => {
    if (pending.length === 0) return null
    return pending.reduce((oldest, row) =>
      row.created_at < oldest.created_at ? row : oldest,
    )
  }, [pending])

  const contextLinks = (row: ApprovalResponse) =>
    [
      row.run_id ? { label: row.run_id, to: `/observe/runs/${row.run_id}` } : null,
      row.task_id ? { label: row.task_id, to: `/execute/tasks/${row.task_id}` } : null,
    ].filter(Boolean) as Array<{ label: string; to: string }>

  return (
    <Workbench
      title={t('console.approvals.title')}
      description={t('console.approvals.description')}
      actions={<ConsoleButton>{t('console.approvals.notificationRules')}</ConsoleButton>}
      tiles={
        <StatTileGrid>
          <StatTile
            label={t('console.approvals.tiles.pending')}
            value={pendingQuery.data ? String(pending.length) : '—'}
            na={!pendingQuery.data}
            sub={
              <span className="mono dimmer">
                {oldestPending
                  ? `oldest ${elapsed(oldestPending.created_at)}`
                  : t('console.common.empty')}
              </span>
            }
          />
          <StatTile
            label={t('console.approvals.tiles.decided')}
            value={decidedQuery.data ? String(decided.length) : '—'}
            na={!decidedQuery.data}
            sub={
              <span className="mono dimmer">
                {decided.filter((row) => row.status === 'approved').length} approved ·{' '}
                {decided.filter((row) => row.status === 'rejected').length} rejected
              </span>
            }
          />
          <StatTile
            label={t('console.approvals.tiles.median')}
            value={median(turnarounds)}
            na={turnarounds.length === 0}
            sub={<span className="mono dimmer">request → decision</span>}
          />
          <StatTile
            label={t('console.approvals.tiles.escalations')}
            value={String(pending.filter((row) => elapsed(row.created_at).includes('h')).length)}
            sub={<span className="mono dimmer">pending over an hour</span>}
          />
        </StatTileGrid>
      }
      tabs={
        <ConsoleTabs
          items={[
            { id: 'pending', label: t('console.approvals.tabs.pending'), count: pending.length },
            { id: 'decided', label: t('console.approvals.tabs.decided'), count: decided.length },
          ]}
          value={tab}
          onChange={setTab}
        />
      }
    >
      {tab === 'pending' ? (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.approvals.columns.request')}</TableHead>
                <TableHead>{t('console.approvals.columns.gate')}</TableHead>
                <TableHead>{t('console.approvals.columns.requestedBy')}</TableHead>
                <TableHead className="num">{t('console.approvals.columns.waiting')}</TableHead>
                <TableHead>{t('console.approvals.columns.context')}</TableHead>
                <TableHead className="num" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {pending.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={pendingQuery.isPending}
                  isError={pendingQuery.isError}
                />
              ) : (
                pending.map((row) => {
                  const waiting = elapsed(row.created_at)
                  return (
                    <TableRow key={row.id}>
                      <TableCell>
                        <b style={{ fontWeight: 600 }}>{row.title || row.id}</b>
                        <br />
                        <span className="dimmer" style={{ fontSize: 11 }}>
                          {row.agent_id || row.thread_id || '—'}
                        </span>
                      </TableCell>
                      <TableCell className="mono dim">{row.policy_ref || '—'}</TableCell>
                      <TableCell className="dim">{row.requested_by || '—'}</TableCell>
                      <TableCell
                        className="num"
                        style={waiting.includes('h') ? { color: 'var(--warning-foreground)' } : undefined}
                      >
                        {waiting}
                      </TableCell>
                      <TableCell>
                        {contextLinks(row).length === 0
                          ? '—'
                          : contextLinks(row).map((item, index) => (
                              <span key={item.label}>
                                {index > 0 && ' · '}
                                <a
                                  className="runid"
                                  href={item.to}
                                  onClick={(event) => {
                                    event.preventDefault()
                                    navigate(item.to)
                                  }}
                                >
                                  {item.label}
                                </a>
                              </span>
                            ))}
                      </TableCell>
                      <TableCell className="num">
                        <span style={{ display: 'inline-flex', gap: 6 }}>
                          <ConsoleButton
                            variant="primary"
                            size="sm"
                            disabled={resolveMutation.isPending}
                            onClick={() =>
                              resolveMutation.mutate({ id: row.id, status: 'approved' })
                            }
                          >
                            {t('console.approvals.approve')}
                          </ConsoleButton>
                          <ConsoleButton
                            size="sm"
                            disabled={resolveMutation.isPending}
                            onClick={() =>
                              resolveMutation.mutate({ id: row.id, status: 'rejected' })
                            }
                          >
                            {t('console.approvals.reject')}
                          </ConsoleButton>
                        </span>
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.approvals.pendingNote')} />
        </WorkbenchPanel>
      ) : (
        <WorkbenchPanel className="mt-3.5">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('console.approvals.columns.time')}</TableHead>
                <TableHead>{t('console.approvals.columns.request')}</TableHead>
                <TableHead>{t('console.approvals.columns.gate')}</TableHead>
                <TableHead>{t('console.approvals.columns.decidedBy')}</TableHead>
                <TableHead className="num">{t('console.approvals.columns.took')}</TableHead>
                <TableHead>{t('console.approvals.columns.decision')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {decided.length === 0 ? (
                <DataStateRow
                  colSpan={6}
                  isPending={decidedQuery.isPending}
                  isError={decidedQuery.isError}
                />
              ) : (
                decided.map((row) => {
                  const decision = decisionStatus(row.status)
                  return (
                    <TableRow key={row.id}>
                      <TableCell className="num dimmer">
                        {relativeTime(row.resolved_at || row.created_at)}
                      </TableCell>
                      <TableCell className="dim">{row.title || row.id}</TableCell>
                      <TableCell className="mono dim">{row.policy_ref || '—'}</TableCell>
                      <TableCell className="dim">{row.resolved_by || '—'}</TableCell>
                      <TableCell className="num dim">
                        {elapsed(row.created_at, row.resolved_at)}
                      </TableCell>
                      <TableCell>
                        <StatusChip status={decision.status} label={decision.label} />
                        {row.resolution_note && (
                          <>
                            {' '}
                            <span className="dimmer" style={{ fontSize: 10.5 }}>
                              {row.resolution_note}
                            </span>
                          </>
                        )}
                      </TableCell>
                    </TableRow>
                  )
                })
              )}
            </TableBody>
          </Table>
          <Pager summary={t('console.approvals.decidedNote')} />
        </WorkbenchPanel>
      )}
    </Workbench>
  )
}
