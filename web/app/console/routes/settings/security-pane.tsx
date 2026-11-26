import { useEffect, useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton, StatusChip } from '../../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { relativeTime } from '../../adapters/palette'
import { onWriteError, useDiagnosticsQuery, useSettingsIdentity, useWorkspaceQuery } from './shared'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listSessions, revokeAllSessions, revokeSession } from '@/services/auth-service'
import {
  updateWorkspace,
  type PiiAction,
  type UnpricedCallPolicy,
  type WorkspaceContentCapture,
} from '@/services/identity-service'
import { getWorkspaceEgressPolicy } from '@/services/security-service'

export function SecurityPane() {
  const { t } = useTranslation()
  const [ipAllowlist, setIpAllowlist] = useState('')

  const { workspaceId } = useSettingsIdentity(false)
  const workspaceQuery = useWorkspaceQuery(workspaceId)
  // Read from the cache only: the About pane is the one that fetches it.
  const diagnostics = useDiagnosticsQuery(false).data

  // The workspace egress policy is the only allowlist the platform stores.
  const egressQuery = useQuery({
    queryKey: ['console', 'settings', 'egress'],
    queryFn: () => getWorkspaceEgressPolicy(),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  // Sessions are only read on the security pane; ending one takes effect
  // immediately, including the one making this request.
  const sessionsQuery = useQuery({
    queryKey: ['console', 'settings', 'sessions'],
    queryFn: () => listSessions(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const sessions = sessionsQuery.data || []

  const revokeOne = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'revoke-session'],
    mutationFn: (sessionId: string) => revokeSession(sessionId, { suppressErrorToast: true }),
    onSuccess: () => {
      void sessionsQuery.refetch()
      toast.success('Session ended')
    },
    onError: onWriteError('Failed to end that session'),
  })

  const revokeAll = useMutation<unknown, unknown, void>({
    mutationKey: ['console', 'settings', 'revoke-all-sessions'],
    mutationFn: () => revokeAllSessions(true, { suppressErrorToast: true }),
    onSuccess: (result) => {
      void sessionsQuery.refetch()
      const count = (result as { revoked: number }).revoked
      toast.success(
        count
          ? `Signed out of ${count} other ${count === 1 ? 'session' : 'sessions'}`
          : 'No other sessions were signed in',
      )
    },
    onError: onWriteError('Failed to sign out everywhere'),
  })

  const requireMfaMutation = useMutation<{ require_mfa?: boolean }, unknown, boolean>({
    mutationKey: ['console', 'settings', 'require-mfa'],
    mutationFn: (required: boolean) =>
      updateWorkspace(workspaceId, { require_mfa: required }, { suppressErrorToast: true }),
    onSuccess: (workspace) => {
      void workspaceQuery.refetch()
      toast.success(
        workspace.require_mfa
          ? 'Members now need a second factor to reach this workspace'
          : 'A second factor is no longer required here',
      )
    },
    onError: onWriteError('Failed to change the two-factor requirement'),
  })

  const contentCaptureMutation = useMutation<
    { content_capture?: WorkspaceContentCapture },
    unknown,
    WorkspaceContentCapture
  >({
    mutationKey: ['console', 'settings', 'content-capture'],
    mutationFn: (mode: WorkspaceContentCapture) =>
      updateWorkspace(workspaceId, { content_capture: mode }, { suppressErrorToast: true }),
    onSuccess: (workspace) => {
      void workspaceQuery.refetch()
      toast.success(
        workspace.content_capture === 'metadata_only'
          ? t('console.settings.securityPane.contentCaptureOff')
          : t('console.settings.securityPane.contentCaptureOn'),
      )
    },
    onError: onWriteError('Failed to change what runs record'),
  })

  const piiMutation = useMutation<
    unknown,
    unknown,
    { field: 'pii_action_inbound' | 'pii_action_outbound'; action: PiiAction | null }
  >({
    mutationKey: ['console', 'settings', 'pii-actions'],
    mutationFn: ({ field, action }) =>
      updateWorkspace(
        workspaceId,
        field === 'pii_action_inbound'
          ? { pii_action_inbound: action }
          : { pii_action_outbound: action },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void workspaceQuery.refetch()
      toast.success(t('console.settings.securityPane.piiSaved'))
    },
    onError: onWriteError('Failed to change how personal data is handled'),
  })

  const unpricedMutation = useMutation<unknown, unknown, UnpricedCallPolicy>({
    mutationKey: ['console', 'settings', 'unpriced-call-policy'],
    mutationFn: (policy) =>
      updateWorkspace(workspaceId, { unpriced_call_policy: policy }, { suppressErrorToast: true }),
    onSuccess: () => {
      void workspaceQuery.refetch()
      toast.success(t('console.settings.securityPane.unpricedSaved'))
    },
    onError: onWriteError('Failed to change how unpriced calls are handled'),
  })

  const selfApprovalMutation = useMutation<unknown, unknown, boolean>({
    mutationKey: ['console', 'settings', 'self-approval'],
    mutationFn: (forbid) =>
      updateWorkspace(workspaceId, { forbid_self_approval: forbid }, { suppressErrorToast: true }),
    onSuccess: () => {
      void workspaceQuery.refetch()
      toast.success(t('console.settings.securityPane.selfApprovalSaved'))
    },
    onError: onWriteError('Failed to change who may approve their own requests'),
  })

  useEffect(() => {
    if (egressQuery.data) setIpAllowlist((egressQuery.data.allowlist || []).join('\n'))
  }, [egressQuery.data])

  return (
    <div className="panel">
      <div className="panel-head">
        <h2>{t('console.settings.security')}</h2>
      </div>
      <div className="frow">
        <label htmlFor="settings-field-4">
          {t('console.settings.securityPane.twoFactorPolicy')}
          <small>{t('console.settings.securityPane.twoFactorPolicyHint')}</small>
        </label>
        {/* Two states, not three: the server can require a second factor
            for this workspace or not. A per-role requirement would need a
            policy object that does not exist, and offering it here would
            be a control that quietly does nothing. */}
        <select
          id="settings-field-4"
          className="input"
          style={{ maxWidth: 280 }}
          value={workspaceQuery.data?.require_mfa ? 'required' : 'optional'}
          disabled={!workspaceQuery.data || requireMfaMutation.isPending}
          onChange={(event) => requireMfaMutation.mutate(event.target.value === 'required')}
        >
          <option value="optional">
            {t('console.settings.securityPane.twoFactorOptional')}
          </option>
          <option value="required">
            {t('console.settings.securityPane.twoFactorRequired')}
          </option>
        </select>
      </div>
      <div className="frow">
        <label htmlFor="settings-field-5">
          {t('console.settings.securityPane.contentCapture')}
          <small>{t('console.settings.securityPane.contentCaptureHint')}</small>
        </label>
        <select
          id="settings-field-5"
          className="input"
          style={{ maxWidth: 280 }}
          value={workspaceQuery.data?.content_capture ?? 'full'}
          disabled={!workspaceQuery.data || contentCaptureMutation.isPending}
          onChange={(event) =>
            contentCaptureMutation.mutate(event.target.value as WorkspaceContentCapture)
          }
        >
          <option value="full">{t('console.settings.securityPane.contentCaptureFull')}</option>
          <option value="metadata_only">
            {t('console.settings.securityPane.contentCaptureMetadataOnly')}
          </option>
        </select>
      </div>
      {(
        [
          [
            'pii_action_inbound',
            t('console.settings.securityPane.piiInbound'),
            t('console.settings.securityPane.piiInboundHint'),
          ],
          [
            'pii_action_outbound',
            t('console.settings.securityPane.piiOutbound'),
            t('console.settings.securityPane.piiOutboundHint'),
          ],
        ] as const
      ).map(([field, label, hint]) => (
        <div className="frow" key={field}>
          <label htmlFor={`settings-pii-${field}`}>
            {label}
            <small>{hint}</small>
          </label>
          <select
            id={`settings-pii-${field}`}
            className="input"
            style={{ maxWidth: 280 }}
            value={workspaceQuery.data?.[field] ?? ''}
            disabled={!workspaceQuery.data || piiMutation.isPending}
            onChange={(event) =>
              piiMutation.mutate({
                field,
                action: (event.target.value || null) as PiiAction | null,
              })
            }
          >
            <option value="">
              {t('console.settings.securityPane.piiDeployment', {
                action: workspaceQuery.data?.pii_action_default ?? 'observe',
              })}
            </option>
            <option value="observe">{t('console.settings.securityPane.piiObserve')}</option>
            <option value="redact">{t('console.settings.securityPane.piiRedact')}</option>
            <option value="block">{t('console.settings.securityPane.piiBlock')}</option>
          </select>
        </div>
      ))}
      <div className="frow">
        <label htmlFor="settings-field-6">
          {t('console.settings.securityPane.unpriced')}
          <small>{t('console.settings.securityPane.unpricedHint')}</small>
        </label>
        <select
          id="settings-field-6"
          className="input"
          style={{ maxWidth: 280 }}
          aria-label={t('console.settings.securityPane.unpriced')}
          value={workspaceQuery.data?.unpriced_call_policy ?? 'allow'}
          disabled={!workspaceQuery.data || unpricedMutation.isPending}
          onChange={(event) => unpricedMutation.mutate(event.target.value as UnpricedCallPolicy)}
        >
          <option value="allow">{t('console.settings.securityPane.unpricedAllow')}</option>
          <option value="refuse_when_budgeted">
            {t('console.settings.securityPane.unpricedRefuseWhenBudgeted')}
          </option>
          <option value="refuse">{t('console.settings.securityPane.unpricedRefuse')}</option>
        </select>
      </div>
      <div className="frow">
        <label htmlFor="settings-field-7">
          {t('console.settings.securityPane.selfApproval')}
          <small>{t('console.settings.securityPane.selfApprovalHint')}</small>
        </label>
        <select
          id="settings-field-7"
          className="input"
          style={{ maxWidth: 280 }}
          aria-label={t('console.settings.securityPane.selfApproval')}
          value={workspaceQuery.data?.forbid_self_approval ? 'forbid' : 'allow'}
          disabled={!workspaceQuery.data || selfApprovalMutation.isPending}
          onChange={(event) => selfApprovalMutation.mutate(event.target.value === 'forbid')}
        >
          <option value="allow">{t('console.settings.securityPane.selfApprovalAllow')}</option>
          <option value="forbid">{t('console.settings.securityPane.selfApprovalForbid')}</option>
        </select>
      </div>
      <div className="frow">
        <label>
          {t('console.settings.securityPane.sso')}
          <small>{t('console.settings.securityPane.ssoHint')}</small>
        </label>
        {/* Single sign-on is an Enterprise feature: the runtime reports it
            among the enabled feature keys when an installed extension
            provides it, and that extension owns its configuration. */}
        <StatusChip
          status="info"
          label={
            diagnostics?.edition?.enabled_features.includes('security.sso')
              ? t('console.settings.securityPane.ssoAvailable')
              : t('console.settings.securityPane.ssoEnterprise')
          }
        />
      </div>
      <div className="frow">
        <label htmlFor="settings-field-8">
          {t('console.settings.securityPane.ipAllowlist')}
          <small>{t('console.settings.securityPane.ipAllowlistHint')}</small>
        </label>
        {/* Sourced from the workspace egress policy — the only allowlist the
            platform stores. Note it governs outbound destinations, not
            inbound console/API access. Edits are local: this pane has no
            save control, so updateWorkspaceEgressPolicy stays unwired. */}
        <textarea
          id="settings-field-8"
          className="input"
          value={ipAllowlist}
          onChange={(event) => setIpAllowlist(event.target.value)}
        />
      </div>
      <div className="frow">
        <label>{t('console.settings.securityPane.auditAccess')}</label>
        {/* Audit log access follows the workspace role and is not
            settable in Community. */}
        <span className="mono dim">{t('console.settings.securityPane.auditAccessValue')}</span>
      </div>
      <div className="frow">
        <label style={{ color: 'var(--danger-foreground)' }}>
          {t('console.settings.securityPane.sessions')}
          <small>{t('console.settings.securityPane.sessionsHint')}</small>
        </label>
        <div style={{ display: 'grid', gap: 10 }}>
          {sessions.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('console.settings.securityPane.device')}</TableHead>
                  <TableHead>{t('console.settings.securityPane.lastSeen')}</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <div className="nm">{row.user_agent || t('console.settings.securityPane.unknownDevice')}</div>
                      <div className="sub mono">
                        {row.ip_address || '—'}
                        {row.current && ` · ${t('console.settings.securityPane.thisDevice')}`}
                      </div>
                    </TableCell>
                    <TableCell className="dim">{relativeTime(row.last_seen_at)}</TableCell>
                    <TableCell className="num">
                      {!row.current && (
                        <ConsoleButton
                          onClick={() => revokeOne.mutate(row.id)}
                          disabled={revokeOne.isPending}
                        >
                          {t('console.settings.securityPane.endSession')}
                        </ConsoleButton>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
          <div>
            <ConsoleButton
              style={{ color: 'var(--danger-foreground)' }}
              onClick={() => revokeAll.mutate(undefined)}
              disabled={revokeAll.isPending}
            >
              {t('console.settings.securityPane.signOutAll')}
            </ConsoleButton>
          </div>
        </div>
      </div>
    </div>
  )
}
