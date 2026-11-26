import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton, ConsoleModal, StatusChip } from '../../components'
import { relativeTime } from '../../adapters/palette'
import { onWriteError, useSettingsIdentity, useWorkspaceQuery } from './shared'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  cancelAccountDeletion,
  confirmMfaEnrolment,
  disableMfa,
  getAccountDeletionRequest,
  getMfaStatus,
  requestAccountDeletion,
  startMfaEnrolment,
} from '@/services/auth-service'
import { changePassword, updateCurrentUser, updateWorkspace } from '@/services/identity-service'
import { requestErrorMessage } from '@/utils/request'

export function AccountPane() {
  const { t } = useTranslation()
  const [displayName, setDisplayName] = useState('')

  const [passwordOpen, setPasswordOpen] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' })

  const { userQuery, workspaceId } = useSettingsIdentity(true)
  const workspaceQuery = useWorkspaceQuery(workspaceId)

  const [workspaceName, setWorkspaceName] = useState('')
  useEffect(() => {
    if (workspaceQuery.data?.name) setWorkspaceName(workspaceQuery.data.name)
  }, [workspaceQuery.data?.name])

  const workspaceMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'update-workspace'],
    mutationFn: (name: string) => updateWorkspace(workspaceId, { name }),
    onSuccess: () => {
      void workspaceQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to rename the workspace'))
    },
  })
  // Commit on blur, like the display-name row above it.
  const commitWorkspaceName = () => {
    const next = workspaceName.trim()
    if (!next || next === workspaceQuery.data?.name) return
    workspaceMutation.mutate(next)
  }

  const profileMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'update-me'],
    mutationFn: (name: string) => updateCurrentUser({ name }),
    onSuccess: () => {
      void userQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to update your profile'))
    },
  })

  // Second factor. Enrolment is two steps: a secret to scan, then a code that
  // proves the authenticator actually holds it.
  const [mfaSetup, setMfaSetup] = useState<{ secret: string; uri: string } | null>(null)
  const [mfaCode, setMfaCode] = useState('')
  const [recoveryCodes, setRecoveryCodes] = useState<string[] | null>(null)
  const [disablingMfa, setDisablingMfa] = useState(false)
  const [disableMfaPassword, setDisableMfaPassword] = useState('')

  const mfaQuery = useQuery({
    queryKey: ['console', 'settings', 'mfa'],
    queryFn: () => getMfaStatus({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const mfa = mfaQuery.data

  const enrolMfa = useMutation<{ secret: string; provisioning_uri: string }, unknown, void>({
    mutationKey: ['console', 'settings', 'mfa-setup'],
    mutationFn: () => startMfaEnrolment({ suppressErrorToast: true }),
    onSuccess: (result) => {
      setMfaCode('')
      setMfaSetup({ secret: result.secret, uri: result.provisioning_uri })
    },
    onError: onWriteError('Failed to start two-factor setup'),
  })

  const confirmMfa = useMutation<{ recovery_codes: string[] }, unknown, void>({
    mutationKey: ['console', 'settings', 'mfa-confirm'],
    mutationFn: () => confirmMfaEnrolment(mfaCode, { suppressErrorToast: true }),
    onSuccess: (result) => {
      setMfaSetup(null)
      setMfaCode('')
      // Shown once. They are stored as hashes, so this is the only chance to
      // write them down.
      setRecoveryCodes(result.recovery_codes)
      void mfaQuery.refetch()
    },
    onError: onWriteError('That code was not accepted'),
  })

  const turnOffMfa = useMutation<void, unknown, void>({
    mutationKey: ['console', 'settings', 'mfa-disable'],
    mutationFn: () => disableMfa(disableMfaPassword, { suppressErrorToast: true }),
    onSuccess: () => {
      setDisablingMfa(false)
      setDisableMfaPassword('')
      void mfaQuery.refetch()
      toast.success('Two-factor authentication is off')
    },
    onError: onWriteError('Password is incorrect'),
  })

  // Closing an account is a request with a pause, not a button that deletes.
  const [closureOpen, setClosureOpen] = useState(false)
  const [closureReason, setClosureReason] = useState('')

  const closureQuery = useQuery({
    queryKey: ['console', 'settings', 'closure'],
    queryFn: () => getAccountDeletionRequest({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const closureRequest = closureQuery.data

  const requestClosure = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'settings', 'request-closure'],
    mutationFn: () =>
      requestAccountDeletion(closureReason.trim() || undefined, { suppressErrorToast: true }),
    onSuccess: () => {
      setClosureOpen(false)
      void closureQuery.refetch()
    },
    onError: onWriteError('Failed to request closure'),
  })

  const cancelClosure = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'settings', 'cancel-closure'],
    mutationFn: () => cancelAccountDeletion({ suppressErrorToast: true }),
    onSuccess: () => {
      void closureQuery.refetch()
      toast.success('Your account will not be closed')
    },
    onError: onWriteError('Failed to withdraw the request'),
  })

  const passwordMutation = useMutation({
    mutationKey: ['console', 'settings', 'change-password'],
    mutationFn: () =>
      changePassword({
        current_password: passwordForm.current,
        new_password: passwordForm.next,
      }),
    onSuccess: () => {
      // Re-reading /me confirms the session survived the credential change.
      void userQuery.refetch()
      setPasswordOpen(false)
      setPasswordForm({ current: '', next: '', confirm: '' })
    },
    onError: onWriteError('Failed to change your password'),
  })

  useEffect(() => {
    if (userQuery.data) setDisplayName(userQuery.data.name || '')
  }, [userQuery.data])

  const currentUser = userQuery.data

  const commitDisplayName = () => {
    const next = displayName.trim()
    if (!next || next === (currentUser?.name || '')) return
    profileMutation.mutate(next)
  }

  return (
    <>
      <div className="panel">
        <div className="panel-head">
          <h2>{t('console.settings.account')}</h2>
        </div>
        <div className="frow">
          <label htmlFor="settings-field-1">
            {t('console.settings.accountPane.displayName')}
            <small>{t('console.settings.accountPane.displayNameHint')}</small>
          </label>
          <input
            id="settings-field-1"
            className="input"
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            onBlur={commitDisplayName}
          />
        </div>
        <div className="frow">
          <label htmlFor="settings-field-2">{t('console.settings.accountPane.email')}</label>
          <input id="settings-field-2" className="input" value={currentUser?.email || ''} disabled />
        </div>
        <div className="frow">
          <label>{t('console.settings.accountPane.role')}</label>
          <div>
            <span className="chip">
              <i style={{ background: 'var(--primary)' }} />
              {currentUser?.workspace_role || '—'}
            </span>
          </div>
        </div>
        <div className="frow">
          <label htmlFor="settings-field-3">
            {t('console.settings.accountPane.workspaceName')}
            <small>{t('console.settings.accountPane.workspaceNameHint')}</small>
          </label>
          <input
            id="settings-field-3"
            className="input"
            value={workspaceName}
            disabled={!workspaceQuery.data}
            onChange={(event) => setWorkspaceName(event.target.value)}
            onBlur={commitWorkspaceName}
          />
        </div>
        <div className="frow">
          <label>
            {t('console.settings.accountPane.password')}
            <small>{t('console.settings.accountPane.passwordHint')}</small>
          </label>
          <div>
            <ConsoleButton
              onClick={() => {
                setPasswordForm({ current: '', next: '', confirm: '' })
                setPasswordOpen(true)
              }}
            >
              {t('console.settings.accountPane.changePassword')}
            </ConsoleButton>
          </div>
        </div>
        <div className="frow">
          <label>
            {t('console.settings.accountPane.twoFactor')}
            <small>
              {mfa?.enabled
                ? t('console.settings.accountPane.twoFactorOnHint', {
                    count: mfa.recovery_codes_remaining,
                  })
                : t('console.settings.accountPane.twoFactorOffHint')}
            </small>
          </label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <StatusChip
              status={mfa ? (mfa.enabled ? 'pass' : 'warn') : 'na'}
              label={
                mfa
                  ? mfa.enabled
                    ? t('console.settings.accountPane.twoFactorOn')
                    : t('console.settings.accountPane.twoFactorOff')
                  : '—'
              }
            />
            {mfa?.enabled ? (
              <ConsoleButton
                style={{ height: 24, fontSize: 11 }}
                onClick={() => {
                  setDisableMfaPassword('')
                  setDisablingMfa(true)
                }}
              >
                {t('console.settings.accountPane.turnOffTwoFactor')}
              </ConsoleButton>
            ) : (
              <ConsoleButton
                style={{ height: 24, fontSize: 11 }}
                disabled={!mfa || enrolMfa.isPending}
                onClick={() => enrolMfa.mutate(undefined)}
              >
                {t('console.settings.accountPane.turnOnTwoFactor')}
              </ConsoleButton>
            )}
          </div>
        </div>
        <div className="frow">
          <label style={{ color: 'var(--danger-foreground)' }}>
            {t('console.settings.accountPane.del')}
            <small>{t('console.settings.accountPane.delHint')}</small>
          </label>
          <div style={{ display: 'grid', gap: 6, justifyItems: 'start' }}>
            {closureRequest ? (
              <>
                <span className="mono dim" style={{ fontSize: 11 }}>
                  {t('console.settings.accountPane.delPending', {
                    when: relativeTime(closureRequest.execute_after),
                  })}
                </span>
                <ConsoleButton
                  onClick={() => cancelClosure.mutate(undefined)}
                  disabled={cancelClosure.isPending}
                >
                  {t('console.settings.accountPane.delCancel')}
                </ConsoleButton>
              </>
            ) : (
              <ConsoleButton
                style={{ color: 'var(--danger-foreground)' }}
                onClick={() => {
                  setClosureReason('')
                  setClosureOpen(true)
                }}
              >
                {t('console.settings.accountPane.delBtn')}
              </ConsoleButton>
            )}
          </div>
        </div>
      </div>

      <ConsoleModal
        open={closureOpen}
        onOpenChange={setClosureOpen}
        title={t('console.settings.accountPane.delTitle')}
        note={t('console.settings.accountPane.delNote')}
        confirmLabel={t('console.settings.accountPane.delConfirm')}
        destructive
        busy={requestClosure.isPending}
        onConfirm={() => requestClosure.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="closure-reason">
            {t('console.settings.accountPane.delReason')}
          </label>
          <input
            id="closure-reason"
            className="input"
            value={closureReason}
            onChange={(event) => setClosureReason(event.target.value)}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={Boolean(mfaSetup)}
        onOpenChange={(open) => {
          if (!open) setMfaSetup(null)
        }}
        title={t('console.settings.accountPane.mfaSetupTitle')}
        note={t('console.settings.accountPane.mfaSetupNote')}
        confirmLabel={t('console.settings.accountPane.mfaConfirm')}
        confirmDisabled={mfaCode.trim().length < 6}
        busy={confirmMfa.isPending}
        onConfirm={() => confirmMfa.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.settings.accountPane.mfaSecret')}</label>
          {/* The secret in text, because not every authenticator scans and
              this is the only time it is available. */}
          <div className="mono" style={{ wordBreak: 'break-all', fontSize: 12 }}>
            {mfaSetup?.secret}
          </div>
        </div>
        <div className="mrow">
          <label>{t('console.settings.accountPane.mfaUri')}</label>
          <div className="mono dim" style={{ wordBreak: 'break-all', fontSize: 10.5 }}>
            {mfaSetup?.uri}
          </div>
        </div>
        <div className="mrow">
          <label htmlFor="mfa-code">{t('console.settings.accountPane.mfaCode')}</label>
          <input
            id="mfa-code"
            className="input"
            autoComplete="one-time-code"
            value={mfaCode}
            onChange={(event) => setMfaCode(event.target.value)}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={Boolean(recoveryCodes)}
        onOpenChange={(open) => {
          if (!open) setRecoveryCodes(null)
        }}
        title={t('console.settings.accountPane.recoveryTitle')}
        note={t('console.settings.accountPane.recoveryNote')}
        confirmLabel={t('console.common.done')}
        onConfirm={() => setRecoveryCodes(null)}
      >
        <div className="mrow">
          <div className="mono" style={{ display: 'grid', gap: 4, fontSize: 12 }}>
            {(recoveryCodes || []).map((code) => (
              <span key={code}>{code}</span>
            ))}
          </div>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={disablingMfa}
        onOpenChange={setDisablingMfa}
        title={t('console.settings.accountPane.mfaOffTitle')}
        note={t('console.settings.accountPane.mfaOffNote')}
        confirmLabel={t('console.settings.accountPane.mfaOffConfirm')}
        confirmDisabled={!disableMfaPassword}
        busy={turnOffMfa.isPending}
        onConfirm={() => turnOffMfa.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="mfa-off-password">
            {t('console.settings.accountPane.currentPassword')}
          </label>
          <input
            id="mfa-off-password"
            className="input"
            type="password"
            autoComplete="current-password"
            value={disableMfaPassword}
            onChange={(event) => setDisableMfaPassword(event.target.value)}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={passwordOpen}
        onOpenChange={setPasswordOpen}
        title={t('console.settings.accountPane.passwordTitle')}
        note={t('console.settings.accountPane.passwordNote')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={
          !passwordForm.current ||
          !passwordForm.next ||
          passwordForm.next !== passwordForm.confirm
        }
        busy={passwordMutation.isPending}
        onConfirm={() => passwordMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label htmlFor="settings-field-9">{t('console.settings.accountPane.currentPassword')}</label>
          <input
            id="settings-field-9"
            className="input"
            type="password"
            autoComplete="current-password"
            value={passwordForm.current}
            onChange={(event) =>
              setPasswordForm((state) => ({ ...state, current: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-10">{t('console.settings.accountPane.newPassword')}</label>
          <input
            id="settings-field-10"
            className="input"
            type="password"
            autoComplete="new-password"
            value={passwordForm.next}
            onChange={(event) =>
              setPasswordForm((state) => ({ ...state, next: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.accountPane.confirmPassword')}</label>
          <div>
            <input
              className="input"
              type="password"
              autoComplete="new-password"
              value={passwordForm.confirm}
              onChange={(event) =>
                setPasswordForm((state) => ({ ...state, confirm: event.target.value }))
              }
            />
            {passwordForm.confirm && passwordForm.confirm !== passwordForm.next && (
              <span
                style={{ display: 'block', marginTop: 4, fontSize: 11 }}
                className="dim"
              >
                {t('console.settings.accountPane.passwordMismatch')}
              </span>
            )}
          </div>
        </div>
      </ConsoleModal>
    </>
  )
}
