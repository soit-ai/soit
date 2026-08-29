import { useEffect, useState } from 'react'

import { Navigate, useLocation, useParams } from 'react-router'
import { toast } from 'sonner'

import { ConsoleButton, DataStateRow, KeyValueList, StatTile, StatusChip } from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { listApiKeys, revokeApiKey } from '@/services/api-key-service'
import { getCreditBalance, listCreditEntries } from '@/services/billing-service'
import { getDiagnosticsSnapshot } from '@/services/diagnostics-service'
import {
  getCurrentUser,
  listWorkspaceMembers,
  updateCurrentUser,
} from '@/services/identity-service'
import {
  getNotificationPreferences,
  listNotificationEndpoints,
  updateNotificationPreferences,
} from '@/services/notification-service'
import { getWorkspaceEgressPolicy } from '@/services/security-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

type SettingsSection =
  | 'account'
  | 'team'
  | 'api'
  | 'security'
  | 'secrets'
  | 'notifications'
  | 'appearance'
  | 'billing'
  | 'about'

const SECTIONS: SettingsSection[] = [
  'account',
  'team',
  'api',
  'security',
  'secrets',
  'notifications',
  'appearance',
  'billing',
  'about',
]

/** A key unused for this long is flagged the way the prototype flagged it. */
const STALE_KEY_MS = 60 * 86_400_000

export default function ConsoleSettings() {
  const { t } = useTranslation()
  const { section } = useParams<{ section?: string }>()
  const location = useLocation()
  const navigate = useConsoleNavigate()

  const active = ((SECTIONS as string[]).includes(section || '')
    ? section
    : 'account') as SettingsSection
  const on = (target: SettingsSection) => Boolean(section) && active === target

  const [displayName, setDisplayName] = useState('')
  const [ipAllowlist, setIpAllowlist] = useState('')

  // Account + Team both need /me: the workspace id for the member list comes
  // from the signed-in identity rather than a URL param.
  const userQuery = useQuery({
    queryKey: ['console', 'settings', 'me'],
    queryFn: () => getCurrentUser(),
    options: {
      enabled: on('account') || on('team') || on('billing'),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  // The persisted user store is the app's own accessor for the active
  // workspace; localStorage is the same value request.ts sends as
  // X-Workspace-Id and only backs the store up on a cold load.
  const storedWorkspaceId = useUserStore((state) => state.currentUser?.workspace_id)
  const workspaceId =
    userQuery.data?.workspace_id ||
    storedWorkspaceId ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')

  const membersQuery = useQuery({
    queryKey: ['console', 'settings', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: {
      // The billing pane's seat count reads the same member list.
      enabled: (on('team') || on('billing')) && Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const keysQuery = useQuery({
    queryKey: ['console', 'settings', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: { enabled: on('api'), retry: false, refetchOnWindowFocus: false },
  })

  // The workspace egress policy is the only allowlist the platform stores.
  const egressQuery = useQuery({
    queryKey: ['console', 'settings', 'egress'],
    queryFn: () => getWorkspaceEgressPolicy(),
    options: { enabled: on('security'), retry: false, refetchOnWindowFocus: false },
  })

  const preferencesQuery = useQuery({
    queryKey: ['console', 'settings', 'notification-preferences'],
    queryFn: () => getNotificationPreferences(),
    options: { enabled: on('notifications'), retry: false, refetchOnWindowFocus: false },
  })
  const endpointsQuery = useQuery({
    queryKey: ['console', 'settings', 'notification-endpoints'],
    queryFn: () => listNotificationEndpoints(),
    options: { enabled: on('notifications'), retry: false, refetchOnWindowFocus: false },
  })

  const diagnosticsQuery = useQuery({
    queryKey: ['console', 'settings', 'diagnostics'],
    queryFn: () => getDiagnosticsSnapshot(),
    options: { enabled: on('about'), retry: false, refetchOnWindowFocus: false },
  })

  // Credits are the only billing object the platform stores; the seat count
  // reuses the member list rather than inventing a licence record.
  const balanceQuery = useQuery({
    queryKey: ['console', 'settings', 'credit-balance'],
    queryFn: () => getCreditBalance(),
    options: { enabled: on('billing'), retry: false, refetchOnWindowFocus: false },
  })
  const entriesQuery = useQuery({
    queryKey: ['console', 'settings', 'credit-entries'],
    queryFn: () => listCreditEntries({ page_size: 20 }),
    options: { enabled: on('billing'), retry: false, refetchOnWindowFocus: false },
  })

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

  const revokeMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'revoke-api-key'],
    mutationFn: (keyId: string) => revokeApiKey(keyId),
    onSuccess: () => {
      void keysQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to revoke the API key'))
    },
  })

  const preferences = preferencesQuery.data
  const categoryMutation = useMutation<unknown, unknown, { category: string; enabled: boolean }>({
    mutationKey: ['console', 'settings', 'update-notification-preferences'],
    mutationFn: ({ category, enabled }) => {
      if (!preferences) return Promise.reject(new Error('Preferences are not loaded yet'))
      return updateNotificationPreferences({
        delivery_mode: preferences.delivery_mode,
        categories: { ...preferences.categories, [category]: enabled },
        quiet_hours_enabled: preferences.quiet_hours_enabled,
        quiet_hours_start: preferences.quiet_hours_start,
        quiet_hours_end: preferences.quiet_hours_end,
        timezone: preferences.timezone,
      })
    },
    onSuccess: () => {
      void preferencesQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to update notification preferences'))
    },
  })

  useEffect(() => {
    if (userQuery.data) setDisplayName(userQuery.data.name || '')
  }, [userQuery.data])

  useEffect(() => {
    if (egressQuery.data) setIpAllowlist((egressQuery.data.allowlist || []).join('\n'))
  }, [egressQuery.data])

  if (!section) {
    return <Navigate to={`/v2/settings/account${location.search}`} replace />
  }

  const currentUser = userQuery.data
  const members = membersQuery.data || []
  const apiKeys = keysQuery.data?.items || []

  const endpoints = endpointsQuery.data || []
  const emailEndpoint = endpoints.find((item) => item.kind === 'email' && item.status === 'active')
  const chatEndpoint = endpoints.find((item) => item.kind !== 'email' && item.status === 'active')
  // Channel copy names the workspace's real endpoints. Per-row channel routing
  // has no backend — a preference carries one global delivery_mode plus the
  // endpoint list, so these labels describe where a category would land.
  const emailLabel = emailEndpoint ? `Email · ${emailEndpoint.display_target}` : 'Email'
  const chatLabel = chatEndpoint
    ? `${chatEndpoint.kind} · ${chatEndpoint.display_target}`
    : 'External endpoint'
  const categoryOn = (key: string) => Boolean(preferences?.categories?.[key])

  const diagnostics = diagnosticsQuery.data
  const creditEntries = entriesQuery.data?.items || []

  const commitDisplayName = () => {
    const next = displayName.trim()
    if (!next || next === (currentUser?.name || '')) return
    profileMutation.mutate(next)
  }

  return (
    <>
      <div className="page-head">
        <h1>{t('console.settings.title')}</h1>
        <p>{t('console.settings.description')}</p>
      </div>
      <div style={{ maxWidth: 860 }}>
        {active === 'account' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.account')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.accountPane.displayName')}
                <small>{t('console.settings.accountPane.displayNameHint')}</small>
              </label>
              <input
                className="input"
                value={displayName}
                onChange={(event) => setDisplayName(event.target.value)}
                onBlur={commitDisplayName}
              />
            </div>
            <div className="frow">
              <label>{t('console.settings.accountPane.email')}</label>
              <input className="input" value={currentUser?.email || ''} disabled />
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
              <label>{t('console.settings.accountPane.twoFactor')}</label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {/* BACKEND-PENDING: no MFA enrollment surface — status unknown,
                    and "Manage devices…" has nothing to open. */}
                <StatusChip status="na" label="—" />
                <ConsoleButton style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.accountPane.manageDevices')}
                </ConsoleButton>
              </div>
            </div>
            <div className="frow">
              <label style={{ color: 'var(--danger-foreground)' }}>
                {t('console.settings.accountPane.del')}
                <small>{t('console.settings.accountPane.delHint')}</small>
              </label>
              <div>
                {/* BACKEND-PENDING: no account-deletion request endpoint. */}
                <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                  {t('console.settings.accountPane.delBtn')}
                </ConsoleButton>
              </div>
            </div>
          </div>
        )}

        {active === 'team' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.team')}</h2>
              <span className="hint">
                {t('console.settings.teamPane.hint', { count: members.length })}
              </span>
              <span className="more">
                {/* BACKEND-PENDING: addWorkspaceMember needs an existing user id,
                    so there is no invite-by-email flow to open yet. */}
                <ConsoleButton variant="primary" style={{ height: 24, fontSize: 11 }}>
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
                        {/* BACKEND-PENDING: membership carries no MFA state. */}
                        <StatusChip status="na" label="—" />
                      </td>
                      {/* BACKEND-PENDING: no last-active timestamp on a member. */}
                      <td className="num dimmer">—</td>
                      <td className="num">
                        {member.user_id !== currentUser?.id && (
                          // BACKEND-PENDING: updateWorkspaceMemberRole exists but
                          // the role picker it needs is not part of this port.
                          <ConsoleButton variant="ghost" style={{ height: 22, fontSize: 10.5 }}>
                            {t('console.settings.teamPane.changeRole')}
                          </ConsoleButton>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.settings.teamPane.note')}</span>
            </div>
          </div>
        )}

        {active === 'api' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.api')}</h2>
              <span className="hint">{t('console.settings.apiPane.hint')}</span>
              <span className="more">
                {/* BACKEND-PENDING: createApiKey needs a name/scope dialog and a
                    one-time reveal, neither of which exists in this pane. */}
                <ConsoleButton variant="primary" style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.apiPane.create')}
                </ConsoleButton>
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t('console.settings.apiPane.columns.name')}</th>
                  <th>{t('console.settings.apiPane.columns.key')}</th>
                  <th>{t('console.settings.apiPane.columns.scopes')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.created')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.lastUsed')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {apiKeys.length === 0 ? (
                  <DataStateRow
                    colSpan={6}
                    isPending={keysQuery.isPending}
                    isError={keysQuery.isError}
                  />
                ) : (
                  apiKeys.map((key) => {
                    const stale =
                      !key.last_used_at || Date.now() - new Date(key.last_used_at).getTime() > STALE_KEY_MS
                    const lastUsed = relativeTime(key.last_used_at)
                    return (
                      <tr key={key.id}>
                        <td>
                          <b style={{ fontWeight: 600 }}>{key.name}</b>
                        </td>
                        <td className="mono dim">{`${key.key_prefix}…`}</td>
                        <td>
                          <span className="scopes">
                            {key.scopes.map((scope) => (
                              <span key={scope} className="chip">
                                {scope}
                              </span>
                            ))}
                          </span>
                        </td>
                        <td className="num dimmer">{key.created_at.slice(5, 10)}</td>
                        <td className="num" style={stale ? { color: 'var(--warning-foreground)' } : undefined}>
                          {stale ? lastUsed : <span className="dimmer">{lastUsed}</span>}
                        </td>
                        <td className="num">
                          <ConsoleButton
                            variant="ghost"
                            style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                            disabled={key.status === 'revoked' || revokeMutation.isPending}
                            onClick={() => revokeMutation.mutate(key.id)}
                          >
                            {t('console.settings.apiPane.revoke')}
                          </ConsoleButton>
                        </td>
                      </tr>
                    )
                  })
                )}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.settings.apiPane.note')}</span>
            </div>
          </div>
        )}

        {active === 'security' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.security')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.twoFactorPolicy')}
                <small>{t('console.settings.securityPane.twoFactorPolicyHint')}</small>
              </label>
              {/* BACKEND-PENDING: no 2FA policy resource — static prototype select. */}
              <select className="input" style={{ maxWidth: 280 }} defaultValue="required for admin & owner">
                <option>required for admin &amp; owner</option>
                <option>required for everyone</option>
                <option>optional</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.sso')}
                <small>{t('console.settings.securityPane.ssoHint')}</small>
              </label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {/* BACKEND-PENDING: no SSO/SAML configuration endpoint. */}
                <StatusChip status="info" label="NOT CONFIGURED" />
                <ConsoleButton style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.securityPane.configureSso')}
                </ConsoleButton>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.securityPane.sessionTimeout')}</label>
              {/* BACKEND-PENDING: session lifetime is not workspace-configurable. */}
              <select className="input" style={{ maxWidth: 200 }} defaultValue="12 hours">
                <option>12 hours</option>
                <option>24 hours</option>
                <option>7 days</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.securityPane.ipAllowlist')}
                <small>{t('console.settings.securityPane.ipAllowlistHint')}</small>
              </label>
              {/* Sourced from the workspace egress policy — the only allowlist the
                  platform stores. Note it governs outbound destinations, not
                  inbound console/API access. Edits are local: this pane has no
                  save control, so updateWorkspaceEgressPolicy stays unwired. */}
              <textarea
                className="input"
                value={ipAllowlist}
                onChange={(event) => setIpAllowlist(event.target.value)}
              />
            </div>
            <div className="frow">
              <label>{t('console.settings.securityPane.auditAccess')}</label>
              {/* BACKEND-PENDING: audit-log access is role-derived, not settable. */}
              <select className="input" style={{ maxWidth: 280 }} defaultValue="owner & admin">
                <option>owner &amp; admin</option>
                <option>owner only</option>
                <option>all members · read-only</option>
              </select>
            </div>
            <div className="frow">
              <label style={{ color: 'var(--danger-foreground)' }}>
                {t('console.settings.securityPane.sessions')}
                <small>{t('console.settings.securityPane.sessionsHint')}</small>
              </label>
              <div>
                {/* BACKEND-PENDING: no global session-revocation endpoint. */}
                <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
                  {t('console.settings.securityPane.signOutAll')}
                </ConsoleButton>
              </div>
            </div>
          </div>
        )}

        {active === 'secrets' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.secrets')}</h2>
            </div>
            <div style={{ padding: '18px 14px' }}>
              <p className="dim" style={{ fontSize: 12.5, maxWidth: 520, lineHeight: 1.6 }}>
                {t('console.settings.secretsPane.body')}
              </p>
              <ConsoleButton
                variant="primary"
                style={{ marginTop: 12 }}
                onClick={() => navigate('/v2/govern/secrets')}
              >
                {t('console.settings.secretsPane.open')}
              </ConsoleButton>
            </div>
          </div>
        )}

        {active === 'notifications' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.notifications')}</h2>
              <span className="hint">{t('console.settings.notificationsPane.hint')}</span>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.approvals')}
                <small>{t('console.settings.notificationsPane.approvalsHint')}</small>
              </label>
              <div className="checks">
                {/* BACKEND-PENDING: no approval category — the preference
                    vocabulary is system/security/account/agent/workflow/task. */}
                <label>
                  <input type="checkbox" defaultChecked />
                  {emailLabel}
                </label>
                <label>
                  <input type="checkbox" defaultChecked />
                  {chatLabel}
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.policyBlocks')}</label>
              <div className="checks">
                {/* Policy blocks map onto the "security" category — the only real
                    control here. Toggling it does not change delivery_mode. */}
                <label>
                  <input
                    type="checkbox"
                    checked={categoryOn('security')}
                    onChange={(event) =>
                      categoryMutation.mutate({ category: 'security', enabled: event.target.checked })
                    }
                  />
                  {chatLabel}
                </label>
                {/* BACKEND-PENDING: per-channel digest cadence has no backend. */}
                <label>
                  <input type="checkbox" />
                  {emailLabel}
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.budget')}</label>
              <div className="checks">
                {/* BACKEND-PENDING: no budget-threshold category or endpoint. */}
                <label>
                  <input type="checkbox" defaultChecked />
                  {chatLabel}
                </label>
                <label>
                  <input type="checkbox" defaultChecked />
                  {emailLabel}
                </label>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.notificationsPane.taskFailures')}</label>
              <div className="checks">
                {/* Maps onto the "task" category. */}
                <label>
                  <input
                    type="checkbox"
                    checked={categoryOn('task')}
                    onChange={(event) =>
                      categoryMutation.mutate({ category: 'task', enabled: event.target.checked })
                    }
                  />
                  {chatLabel}
                </label>
              </div>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.digest')}
                <small>{t('console.settings.notificationsPane.digestHint')}</small>
              </label>
              <div className="checks">
                {/* BACKEND-PENDING: no scheduled-digest preference. */}
                <label>
                  <input type="checkbox" defaultChecked />
                  {emailLabel}
                </label>
              </div>
            </div>
          </div>
        )}

        {/* BACKEND-PENDING: edition, seats and invoices have no server object;
            the credits ledger is the only real billing surface and backs the
            spend tile and the entries table below. */}
        {active === 'billing' && (
          <>
            <div className="tiles cols-3">
              <StatTile
                label={t('console.settings.billingPane.edition')}
                value="—"
                na
                sub={<span className="mono dimmer">no licence record</span>}
              />
              <StatTile
                label={t('console.settings.billingPane.seats')}
                value={membersQuery.data ? String(members.length) : '—'}
                na={!membersQuery.data}
                sub={<span className="mono dimmer">workspace members</span>}
              />
              <StatTile
                label={t('console.settings.billingPane.spend')}
                value={
                  balanceQuery.data
                    ? `${balanceQuery.data.consumed_total ?? '—'} ${balanceQuery.data.currency}`
                    : '—'
                }
                na={!balanceQuery.data}
                sub={
                  <span className="mono dimmer">
                    {balanceQuery.data
                      ? `balance ${balanceQuery.data.balance} ${balanceQuery.data.currency}`
                      : t('console.common.loading')}
                  </span>
                }
              />
            </div>
            <div className="panel">
              <div className="panel-head">
                <h2>{t('console.settings.billingPane.invoices')}</h2>
                <span className="hint">{t('console.settings.billingPane.invoicesHint')}</span>
              </div>
              <table>
                <thead>
                  <tr>
                    <th>{t('console.settings.billingPane.columns.invoice')}</th>
                    <th>{t('console.settings.billingPane.columns.period')}</th>
                    <th className="num">{t('console.settings.billingPane.columns.amount')}</th>
                    <th>{t('console.settings.billingPane.columns.status')}</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {creditEntries.length === 0 ? (
                    <tr>
                      <td colSpan={5}>
                        <div className="empty-note">
                          {entriesQuery.isPending
                            ? t('console.common.loading')
                            : entriesQuery.isError
                              ? t('console.common.loadError')
                              : t('console.common.empty')}
                        </div>
                      </td>
                    </tr>
                  ) : (
                    creditEntries.map((entry) => (
                      <tr key={entry.id}>
                        <td className="mono">{entry.id}</td>
                        <td className="dim">{entry.note || entry.source_ref || entry.kind}</td>
                        <td className="num dim">
                          {entry.amount} {entry.currency}
                        </td>
                        <td>
                          <StatusChip
                            status={entry.kind === 'grant' ? 'pass' : 'info'}
                            label={entry.kind.toUpperCase()}
                          />
                        </td>
                        <td className="num dimmer">{relativeTime(entry.created_at)}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
              <div className="pager">
                <span>{t('console.settings.billingPane.note')}</span>
              </div>
            </div>
          </>
        )}

        {/* Appearance is local UI preference, not server state — the console
            theme/density/locale live in the client, so there is nothing to
            fetch or persist through the API here. */}
        {active === 'appearance' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.appearance')}</h2>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.appearancePane.theme')}
                <small>{t('console.settings.appearancePane.themeHint')}</small>
              </label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="dark · default">
                <option>dark · default</option>
                <option>light</option>
                <option>follow system</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.density')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="comfortable">
                <option>comfortable</option>
                <option>compact</option>
              </select>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.language')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="English">
                <option>English</option>
                <option>Chinese (Simplified)</option>
              </select>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.appearancePane.accent')}
                <small>{t('console.settings.appearancePane.accentHint')}</small>
              </label>
              <div>
                <span className="chip">
                  <i style={{ background: 'var(--primary)' }} />
                  Signal Blue · fixed
                </span>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.appearancePane.timestamps')}</label>
              <select className="input" style={{ maxWidth: 220 }} defaultValue="UTC · absolute">
                <option>UTC · absolute</option>
                <option>local · relative</option>
              </select>
            </div>
          </div>
        )}

        {active === 'about' && (
          <div className="panel">
            <div className="panel-head">
              <h2>{t('console.settings.about')}</h2>
            </div>
            <KeyValueList
              items={[
                // BACKEND-PENDING: the web console ships no build/version stamp.
                { key: t('console.settings.aboutPane.console'), value: '—' },
                {
                  key: t('console.settings.aboutPane.runtime'),
                  value: diagnostics ? `soit-server ${diagnostics.version} · ${diagnostics.environment}` : '—',
                },
                // BACKEND-PENDING: /diagnostics reports no policy-engine version.
                { key: t('console.settings.aboutPane.policyEngine'), value: '—' },
                // Project fact, not workspace data.
                { key: t('console.settings.aboutPane.license'), value: 'Apache 2.0 · open source' },
                {
                  key: t('console.settings.aboutPane.repository'),
                  value: (
                    <a
                      className="runid"
                      href="https://github.com/soit-ai/soit"
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      github.com/soit-ai/soit
                    </a>
                  ),
                },
              ]}
            />
            <div className="code">
              <span className="k">$</span> soit diagnostics export
              {'\n'}
              <span className="s">{t('console.settings.aboutPane.diagNote')}</span>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
