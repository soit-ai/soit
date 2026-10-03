import { useState } from 'react'

import { toast } from 'sonner'

import { relativeTime } from '../adapters/palette'
import { ConsoleButton } from './button'
import { ConsoleModal } from './modal'
import { StatusChip, type ConsoleStatus } from './status-chip'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listWorkspaceMembers } from '@/services/identity-service'
import {
  delegateApproval,
  listApprovalDecisions,
  resolveApproval,
  type ApprovalDecisionEntry,
  type ApprovalResponse,
} from '@/services/observe-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

/** The history wording of each closing. */
const ACTION_KEYS = {
  approved: 'console.approvals.history.actions.approved',
  rejected: 'console.approvals.history.actions.rejected',
  canceled: 'console.approvals.history.actions.canceled',
  expired: 'console.approvals.history.actions.expired',
} as const

/** Roles whose holders can decide a request, and so can be handed one. */
const APPROVER_ROLES = ['Owner', 'Admin', 'Dev']

/** Server times carry no zone; they are UTC. */
export function parseServerTime(value?: string | null): number {
  if (!value) return Number.NaN
  const zoned = /[zZ]|[+-]\d\d:?\d\d$/.test(value) ? value : `${value}Z`
  return new Date(zoned).getTime()
}

export function approvalStatusChip(status: ApprovalResponse['status']): {
  status: ConsoleStatus
  label: string
} {
  if (status === 'approved') return { status: 'pass', label: 'APPROVED' }
  if (status === 'rejected') return { status: 'blocked', label: 'REJECTED' }
  if (status === 'canceled') return { status: 'cancelled', label: 'CANCELED' }
  if (status === 'expired') return { status: 'degraded', label: 'EXPIRED' }
  return { status: 'running', label: 'PENDING' }
}

/** Time left until the deadline (`45m`, `3h`, `2d`), whether it is close, and whether it passed. */
export function deadline(expiresAt?: string | null): { left: string; soon: boolean; overdue: boolean } | null {
  const end = parseServerTime(expiresAt)
  if (Number.isNaN(end)) return null
  const minutes = Math.round((end - Date.now()) / 60_000)
  if (minutes <= 0) return { left: '0m', soon: true, overdue: true }
  const soon = minutes <= 60
  if (minutes < 60) return { left: `${minutes}m`, soon, overdue: false }
  const hours = Math.round(minutes / 60)
  if (hours < 48) return { left: `${hours}h`, soon, overdue: false }
  return { left: `${Math.round(hours / 24)}d`, soon, overdue: false }
}

/** The deadline as a reader sees it: `due in 3h`, `overdue`, or nothing set. */
export function useDeadlineLabel() {
  const { t } = useTranslation()
  return (expiresAt?: string | null) => {
    const due = deadline(expiresAt)
    if (!due) return { text: t('console.approvals.noDeadline'), soon: false }
    if (due.overdue) return { text: t('console.approvals.overdue'), soon: true }
    return { text: t('console.approvals.dueIn', { left: due.left }), soon: due.soon }
  }
}

/** Members and roles that may decide, in one line; empty means any writer. */
export function approverNames(
  approval: Pick<ApprovalResponse, 'assignee_user_ids' | 'assignee_roles'>,
  label: (userId: string) => string = (userId) => userId,
): string[] {
  return [...(approval.assignee_user_ids || []).map(label), ...(approval.assignee_roles || [])]
}

/** The workspace's members, and a label that names a member id by name or email. */
export function useApprovalMembers(enabled: boolean) {
  const workspaceId =
    useUserStore((state) => state.currentUser?.workspace_id) ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')
  const query = useQuery({
    queryKey: ['console', 'approvals', 'members', workspaceId],
    // Names are a courtesy: without them the ids are shown, and no error.
    queryFn: () => listWorkspaceMembers(workspaceId, { suppressErrorToast: true }),
    options: { enabled: enabled && Boolean(workspaceId), retry: false, refetchOnWindowFocus: false },
  })
  const members = query.data || []
  const label = (userId: string) => {
    const found = members.find((item) => item.user_id === userId)
    return found ? found.name || found.email : userId
  }
  return { members, label }
}

function historyActor(entry: ApprovalDecisionEntry, label: (userId: string) => string): string {
  if (entry.actor_id === 'system') return 'system'
  const role = entry.actor_role ? ` (${entry.actor_role})` : ''
  return `${label(entry.actor_id || '—')}${role}`
}

/**
 * One approval request: what it asks, who may decide it, by when, and what
 * happened to it. An approver can hand it to another member who can decide;
 * an approver, the requester or an admin can cancel it. The server checks
 * both, whatever this dialog offers.
 */
export function ApprovalModal({
  approval,
  open,
  onOpenChange,
  onChanged,
}: {
  approval: ApprovalResponse
  open: boolean
  onOpenChange: (open: boolean) => void
  onChanged: () => void
}) {
  const { t } = useTranslation()
  const currentUserId = useUserStore((state) => state.currentUser?.id)
  const [target, setTarget] = useState('')
  const [note, setNote] = useState('')
  const { members, label } = useApprovalMembers(open)
  const pending = approval.status === 'pending'
  const canDecide = pending && approval.can_decide !== false
  const canCancel = pending && approval.can_cancel !== false

  const historyQuery = useQuery({
    queryKey: ['console', 'approvals', 'decisions', approval.id],
    queryFn: () => listApprovalDecisions(approval.id),
    options: { enabled: open, retry: false, refetchOnWindowFocus: false },
  })

  const delegateMutation = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'approvals', 'delegate', approval.id],
    mutationFn: () =>
      delegateApproval(approval.id, { user_id: target, note: note || undefined }, { suppressErrorToast: true }),
    onSuccess: () => {
      toast.success(t('console.approvals.modal.delegated'))
      setTarget('')
      setNote('')
      onChanged()
      onOpenChange(false)
    },
    onError: (error) => toast.error(requestErrorMessage(error, t('console.approvals.modal.delegateFailed'))),
  })
  const cancelMutation = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'approvals', 'cancel', approval.id],
    mutationFn: () =>
      resolveApproval(approval.id, { status: 'canceled', resolution_note: note || undefined }, { suppressErrorToast: true }),
    onSuccess: () => {
      toast.success(t('console.approvals.modal.canceled'))
      onChanged()
      onOpenChange(false)
    },
    onError: (error) => toast.error(requestErrorMessage(error, t('console.approvals.modal.cancelFailed'))),
  })

  const details = (approval.details_json || {}) as Record<string, unknown>
  const toolRef = typeof details.tool_ref === 'string' ? details.tool_ref : null
  const approvers = approverNames(approval, label)
  const deadlineLabel = useDeadlineLabel()
  const due = deadlineLabel(approval.expires_at)
  const chip = approvalStatusChip(approval.status)
  const candidates = members.filter(
    (item) =>
      APPROVER_ROLES.includes(item.role) &&
      item.user_id !== currentUserId &&
      !(approval.assignee_user_ids || []).includes(item.user_id),
  )
  const busy = delegateMutation.isPending || cancelMutation.isPending

  return (
    <ConsoleModal
      open={open}
      onOpenChange={onOpenChange}
      title={approval.title || t('console.approvals.modal.title')}
      note={canDecide ? t('console.approvals.modal.noteDecider') : t('console.approvals.modal.noteReadOnly')}
      confirmLabel={t('console.approvals.modal.delegate')}
      confirmDisabled={!canDecide || !target}
      busy={busy}
      onConfirm={() => delegateMutation.mutate()}
    >
      <div className="mrow">
        <label>{t('console.approvals.modal.status')}</label>
        <div>
          <StatusChip status={chip.status} label={chip.label} />
        </div>
      </div>
      {toolRef && (
        <div className="mrow">
          <label>{t('console.approvals.modal.tool')}</label>
          <span className="mono" style={{ overflowWrap: 'anywhere' }}>
            {toolRef}
          </span>
        </div>
      )}
      {!!details.parameters && (
        <div className="mrow">
          <label>{t('console.approvals.modal.parameters')}</label>
          <pre className="mono dim" style={{ fontSize: 11, whiteSpace: 'pre-wrap', margin: 0, overflowWrap: 'anywhere' }}>
            {JSON.stringify(details.parameters, null, 2)}
          </pre>
        </div>
      )}
      <div className="mrow">
        <label>{t('console.approvals.modal.approvers')}</label>
        <span style={{ overflowWrap: 'anywhere' }}>
          {approvers.length ? approvers.join(', ') : t('console.approvals.anyWriter')}
        </span>
      </div>
      <div className="mrow">
        <label>{t('console.approvals.modal.deadline')}</label>
        <span style={due.soon ? { color: 'var(--warning-foreground)' } : undefined}>{due.text}</span>
      </div>
      <div className="mrow">
        <label>{t('console.approvals.modal.history')}</label>
        <div style={{ display: 'grid', gap: 4 }}>
          {(historyQuery.data || []).length === 0 ? (
            <span className="dimmer">{t('console.approvals.modal.noHistory')}</span>
          ) : (
            (historyQuery.data || []).map((entry) => (
              <div key={entry.id} style={{ overflowWrap: 'anywhere' }}>
                <span className="mono dimmer" style={{ fontSize: 11 }}>
                  {relativeTime(entry.created_at)}
                </span>{' '}
                {entry.action === 'delegated'
                  ? t('console.approvals.history.delegated', {
                      actor: historyActor(entry, label),
                      to: (entry.assignees_after_json?.user_ids || []).map(label).join(', ') || '—',
                    })
                  : t('console.approvals.history.decided', {
                      actor: historyActor(entry, label),
                      action: t(ACTION_KEYS[entry.action as Exclude<typeof entry.action, 'delegated'>]),
                    })}
                {entry.note && <span className="dimmer"> · {entry.note}</span>}
              </div>
            ))
          )}
        </div>
      </div>
      {canDecide && (
        <div className="mrow">
          <label htmlFor="approval-delegate-member">{t('console.approvals.modal.delegateTo')}</label>
          <select
            id="approval-delegate-member"
            className="input"
            value={target}
            onChange={(event) => setTarget(event.target.value)}
          >
            <option value="">{t('console.approvals.modal.delegatePlaceholder')}</option>
            {candidates.map((item) => (
              <option key={item.user_id} value={item.user_id}>
                {item.name || item.email} · {item.role}
              </option>
            ))}
          </select>
        </div>
      )}
      {(canDecide || canCancel) && (
        <div className="mrow">
          <label htmlFor="approval-note">{t('console.approvals.modal.note')}</label>
          <input
            id="approval-note"
            className="input"
            value={note}
            maxLength={1000}
            placeholder={t('console.approvals.modal.notePlaceholder')}
            onChange={(event) => setNote(event.target.value)}
          />
        </div>
      )}
      {canCancel && (
        <div className="mrow">
          <label />
          <div>
            <ConsoleButton
              variant="ghost"
              size="sm"
              disabled={busy}
              style={{ color: 'var(--danger-foreground)' }}
              onClick={() => cancelMutation.mutate()}
            >
              {t('console.approvals.modal.cancelRequest')}
            </ConsoleButton>
          </div>
        </div>
      )}
    </ConsoleModal>
  )
}
