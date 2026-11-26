import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton, ConsoleModal, DataStateRow, StatusChip } from '../../components'
import { relativeTime } from '../../adapters/palette'
import { onWriteError, useMembersQuery, useSettingsIdentity } from './shared'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getAuthCapabilities } from '@/services/auth-service'
import {
  addWorkspaceMember,
  createInvitation,
  listInvitations,
  removeWorkspaceMember,
  revokeInvitation,
  updateWorkspaceMemberRole,
  type WorkspaceMember,
} from '@/services/identity-service'

/** The server's workspace role vocabulary (kernel/identity/rbac.py). */
const WORKSPACE_ROLES = ['Owner', 'Admin', 'Dev', 'Viewer'] as const

export function TeamPane() {
  const { t } = useTranslation()
  const [inviting, setInviting] = useState(false)
  const [inviteForm, setInviteForm] = useState({ userId: '', email: '', role: 'Dev' })
  const [roleTarget, setRoleTarget] = useState<WorkspaceMember | null>(null)
  const [roleDraft, setRoleDraft] = useState('Dev')
  const [removalTarget, setRemovalTarget] = useState<WorkspaceMember | null>(null)

  const { userQuery, workspaceId } = useSettingsIdentity(true)
  const membersQuery = useMembersQuery(workspaceId)

  // Inviting by address needs a mail outlet; the console asks rather than
  // offering a flow that would end in a dropped message.
  const capabilities = useQuery({
    queryKey: ['console', 'settings', 'auth-capabilities'],
    queryFn: () => getAuthCapabilities({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const canMail = capabilities.data?.mail_enabled === true

  const invitationsQuery = useQuery({
    queryKey: ['console', 'settings', 'invitations', workspaceId],
    queryFn: () => listInvitations(workspaceId, { suppressErrorToast: true }),
    options: {
      enabled: Boolean(workspaceId) && canMail,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const invitations = invitationsQuery.data || []

  const emailInvite = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'settings', 'invite-by-email'],
    mutationFn: () =>
      createInvitation(
        workspaceId,
        { email: inviteForm.email.trim(), role: inviteForm.role },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void invitationsQuery.refetch()
      setInviting(false)
      setInviteForm({ userId: '', email: '', role: 'Dev' })
      toast.success('Invitation sent')
    },
    onError: onWriteError('Failed to send the invitation'),
  })

  const revokeInvite = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'revoke-invitation'],
    mutationFn: (invitationId: string) =>
      revokeInvitation(invitationId, { suppressErrorToast: true }),
    onSuccess: () => {
      void invitationsQuery.refetch()
      toast.success('Invitation withdrawn')
    },
    onError: onWriteError('Failed to withdraw the invitation'),
  })

  const inviteMutation = useMutation({
    mutationKey: ['console', 'settings', 'add-member'],
    mutationFn: () =>
      addWorkspaceMember(workspaceId, {
        user_id: inviteForm.userId.trim(),
        role: inviteForm.role,
      }),
    onSuccess: () => {
      void membersQuery.refetch()
      setInviting(false)
      setInviteForm({ userId: '', email: '', role: 'Dev' })
    },
    onError: onWriteError('Failed to add the member'),
  })

  const roleMutation = useMutation({
    mutationKey: ['console', 'settings', 'member-role'],
    mutationFn: () => updateWorkspaceMemberRole(workspaceId, roleTarget!.user_id, roleDraft),
    onSuccess: () => {
      void membersQuery.refetch()
      setRoleTarget(null)
    },
    onError: onWriteError('Failed to change the member role'),
  })

  const removeMemberMutation = useMutation({
    mutationKey: ['console', 'settings', 'remove-member'],
    mutationFn: () => removeWorkspaceMember(workspaceId, removalTarget!.user_id),
    onSuccess: () => {
      void membersQuery.refetch()
      setRemovalTarget(null)
    },
    onError: onWriteError('Failed to remove the member'),
  })

  const currentUser = userQuery.data
  const members = membersQuery.data || []

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('console.settings.team')}</h2>
          <span className="hint">
            {t('console.settings.teamPane.hint', { count: members.length })}
          </span>
          <span className="more">
            <ConsoleButton
              variant="primary"
              style={{ height: 24, fontSize: 11 }}
              disabled={!workspaceId}
              onClick={() => {
                setInviteForm({ userId: '', email: '', role: 'Dev' })
                setInviting(true)
              }}
            >
              {t('console.settings.teamPane.invite')}
            </ConsoleButton>
          </span>
        </div>
        <table>
          <thead>
            <tr>
              <th>{t('console.settings.teamPane.columns.member')}</th>
              <th>{t('console.settings.teamPane.columns.role')}</th>
              <th>{t('console.settings.teamPane.columns.twoFactor')}</th>
              <th className="num">{t('console.settings.teamPane.columns.lastActive')}</th>
              <th className="num" />
            </tr>
          </thead>
          <tbody>
            {members.length === 0 ? (
              <DataStateRow
                colSpan={5}
                isPending={membersQuery.isPending}
                isError={membersQuery.isError}
              />
            ) : (
              members.map((member) => (
                <tr key={member.user_id}>
                  <td>
                    {member.status !== 'active' ? (
                      <span className="dim">{member.name || member.email}</span>
                    ) : (
                      <b style={{ fontWeight: 600 }}>{member.name || member.email}</b>
                    )}
                    <br />
                    <span className="dimmer" style={{ fontSize: 10.5 }}>
                      {member.email}
                    </span>
                  </td>
                  <td>
                    <span className="chip">
                      {member.user_id === currentUser?.id && (
                        <i style={{ background: 'var(--primary)' }} />
                      )}
                      {member.role}
                    </span>
                  </td>
                  <td>
                    <StatusChip
                      status={member.mfa_enabled ? 'pass' : 'warn'}
                      label={
                        member.mfa_enabled
                          ? t('console.settings.accountPane.twoFactorOn')
                          : t('console.settings.accountPane.twoFactorOff')
                      }
                    />
                  </td>
                  <td className="num dimmer">
                    {member.last_active_at ? relativeTime(member.last_active_at) : '—'}
                  </td>
                  <td className="num">
                    {/* The server refuses to remove the caller from their own
                        workspace, so self rows carry no actions at all. */}
                    {member.user_id !== currentUser?.id && (
                      <span style={{ display: 'inline-flex', gap: 6 }}>
                        <ConsoleButton
                          variant="ghost"
                          style={{ height: 22, fontSize: 10.5 }}
                          onClick={() => {
                            setRoleDraft(member.role)
                            setRoleTarget(member)
                          }}
                        >
                          {t('console.settings.teamPane.changeRole')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          style={{
                            height: 22,
                            fontSize: 10.5,
                            color: 'var(--danger-foreground)',
                          }}
                          onClick={() => setRemovalTarget(member)}
                        >
                          {t('console.settings.teamPane.remove')}
                        </ConsoleButton>
                      </span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
        {invitations.length > 0 && (
          <>
            <div className="panel-head" style={{ borderTop: '1px solid var(--border)' }}>
              <h2 style={{ fontSize: 12 }}>
                {t('console.settings.teamPane.pendingInvites')}
              </h2>
            </div>
            <table>
              <tbody>
                {invitations.map((invitation) => (
                  <tr key={invitation.id}>
                    <td>
                      <b style={{ fontWeight: 600 }}>{invitation.email}</b>
                      <br />
                      <span className="dimmer" style={{ fontSize: 10.5 }}>
                        {invitation.role} · expires {relativeTime(invitation.expires_at)}
                      </span>
                    </td>
                    <td className="num">
                      <ConsoleButton
                        variant="ghost"
                        style={{ height: 22, fontSize: 10.5 }}
                        onClick={() => revokeInvite.mutate(invitation.id)}
                        disabled={revokeInvite.isPending}
                      >
                        {t('console.settings.teamPane.withdrawInvite')}
                      </ConsoleButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
        <div className="pager">
          <span>{t('console.settings.teamPane.note')}</span>
        </div>
      </div>

      <ConsoleModal
        open={inviting}
        onOpenChange={setInviting}
        title={t('console.settings.teamPane.inviteTitle')}
        note={
          canMail
            ? t('console.settings.teamPane.inviteNoteMail')
            : t('console.settings.teamPane.inviteNote')
        }
        confirmLabel={t('console.common.create')}
        confirmDisabled={
          canMail ? !inviteForm.email.trim() : !inviteForm.userId.trim()
        }
        busy={inviteMutation.isPending || emailInvite.isPending}
        onConfirm={() =>
          canMail ? emailInvite.mutate(undefined) : inviteMutation.mutate(undefined)
        }
      >
        {/* Inviting by address needs a mail outlet. Without one the dialog
            keeps asking for a user id, because adding someone who already has
            an account is the only thing the deployment can actually do. */}
        {canMail ? (
          <div className="mrow">
            <label htmlFor="invite-email">
              {t('console.settings.teamPane.memberEmail')}
              <small>{t('console.settings.teamPane.memberEmailHint')}</small>
            </label>
            <input
              id="invite-email"
              className="input"
              type="email"
              value={inviteForm.email}
              onChange={(event) =>
                setInviteForm((state) => ({ ...state, email: event.target.value }))
              }
            />
          </div>
        ) : (
          <div className="mrow">
            <label htmlFor="settings-field-11">
              {t('console.settings.teamPane.memberId')}
              <small>{t('console.settings.teamPane.memberIdHint')}</small>
            </label>
            <input
              id="settings-field-11"
              className="input"
              value={inviteForm.userId}
              onChange={(event) =>
                setInviteForm((state) => ({ ...state, userId: event.target.value }))
              }
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            />
          </div>
        )}
        <div className="mrow">
          <label htmlFor="settings-field-12">{t('console.settings.teamPane.columns.role')}</label>
          <select
            id="settings-field-12"
            className="input"
            value={inviteForm.role}
            onChange={(event) =>
              setInviteForm((state) => ({ ...state, role: event.target.value }))
            }
          >
            {WORKSPACE_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={roleTarget != null}
        onOpenChange={(open) => !open && setRoleTarget(null)}
        title={t('console.settings.teamPane.changeRoleTitle')}
        note={t('console.settings.teamPane.changeRoleNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!roleDraft || roleDraft === roleTarget?.role}
        busy={roleMutation.isPending}
        onConfirm={() => roleMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="settings-field-13">{t('console.settings.teamPane.columns.member')}</label>
          <input
            id="settings-field-13"
            className="input"
            value={roleTarget?.name || roleTarget?.email || ''}
            disabled
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-14">{t('console.settings.teamPane.columns.role')}</label>
          <select
            id="settings-field-14"
            className="input"
            value={roleDraft}
            onChange={(event) => setRoleDraft(event.target.value)}
          >
            {WORKSPACE_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={removalTarget != null}
        onOpenChange={(open) => !open && setRemovalTarget(null)}
        title={t('console.settings.teamPane.removeTitle')}
        confirmLabel={t('console.settings.teamPane.remove')}
        destructive
        busy={removeMemberMutation.isPending}
        onConfirm={() => removeMemberMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.settings.teamPane.removeConfirm', {
            name: removalTarget?.name || removalTarget?.email || '',
          })}
        </div>
      </ConsoleModal>
    </>
  )
}
