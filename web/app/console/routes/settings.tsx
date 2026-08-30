import { useEffect, useState } from 'react'

import { Navigate, useLocation, useParams } from 'react-router'
import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  DataStateRow,
  KeyValueList,
  StatTile,
  StatusChip,
} from '../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../components/ui'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { mockTiles } from '../mocks/tiles'
import { useTranslation } from '@/i18n'
import {
  createApiKey,
  listApiKeys,
  revokeApiKey,
  rotateApiKey,
  type ApiKeyItem,
  type ApiKeyScope,
} from '@/services/api-key-service'
import { getCreditBalance, listCreditEntries } from '@/services/billing-service'
import { listSessions, revokeAllSessions, revokeSession } from '@/services/auth-service'
import { getDiagnosticsSnapshot } from '@/services/diagnostics-service'
import {
  addWorkspaceMember,
  changePassword,
  getCurrentUser,
  listWorkspaceMembers,
  removeWorkspaceMember,
  updateCurrentUser,
  getWorkspace,
  updateWorkspace,
  updateWorkspaceMemberRole,
  type WorkspaceMember,
} from '@/services/identity-service'
import {
  createNotificationEndpoint,
  deleteNotificationEndpoint,
  getNotificationPreferences,
  listNotificationEndpoints,
  testNotificationEndpoint,
  updateNotificationEndpoint,
  updateNotificationPreferences,
  type NotificationEndpoint,
  type NotificationEndpointKind,
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

/** The server's workspace role vocabulary (kernel/identity/rbac.py). */
const WORKSPACE_ROLES = ['Owner', 'Admin', 'Dev', 'Viewer'] as const
const API_KEY_SCOPES: ApiKeyScope[] = ['read', 'write', 'admin']
const API_KEY_LIFETIMES = [30, 90, 180, 365]
const ENDPOINT_KINDS: NotificationEndpointKind[] = [
  'email',
  'webhook',
  'slack',
  'teams',
  'discord',
  'telegram',
  'other',
]

const EMPTY_ENDPOINT_FORM: {
  name: string
  kind: NotificationEndpointKind
  url: string
  status: 'active' | 'disabled'
} = { name: '', kind: 'email', url: '', status: 'active' }

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

  const [passwordOpen, setPasswordOpen] = useState(false)
  const [passwordForm, setPasswordForm] = useState({ current: '', next: '', confirm: '' })

  const [inviting, setInviting] = useState(false)
  const [inviteForm, setInviteForm] = useState({ userId: '', role: 'Dev' })
  const [roleTarget, setRoleTarget] = useState<WorkspaceMember | null>(null)
  const [roleDraft, setRoleDraft] = useState('Dev')
  const [removalTarget, setRemovalTarget] = useState<WorkspaceMember | null>(null)

  const [creatingKey, setCreatingKey] = useState(false)
  const [keyForm, setKeyForm] = useState<{
    name: string
    scope: ApiKeyScope
    expiresInDays: number
  }>({ name: '', scope: 'read', expiresInDays: 90 })
  const [rotateTarget, setRotateTarget] = useState<ApiKeyItem | null>(null)
  // The plaintext secret exists here and nowhere else, for exactly as long as
  // the reveal dialog is open: never logged, never toasted, never persisted.
  const [revealed, setRevealed] = useState<{ name: string; secret: string } | null>(null)
  const [secretCopied, setSecretCopied] = useState(false)

  const [creatingEndpoint, setCreatingEndpoint] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [deletingEndpoint, setDeletingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [endpointForm, setEndpointForm] = useState(EMPTY_ENDPOINT_FORM)

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

  const workspaceQuery = useQuery({
    queryKey: ['console', 'settings', 'workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId),
    options: { enabled: on('account') && Boolean(workspaceId), retry: false, refetchOnWindowFocus: false },
  })
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

  const onWriteError = (fallback: string) => (error: unknown) => {
    toast.error(requestErrorMessage(error, fallback))
  }

  // Sessions are only read on the security pane; ending one takes effect
  // immediately, including the one making this request.
  const sessionsQuery = useQuery({
    queryKey: ['console', 'settings', 'sessions'],
    queryFn: () => listSessions(),
    options: { enabled: active === 'security', retry: false, refetchOnWindowFocus: false },
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
      setInviteForm({ userId: '', role: 'Dev' })
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

  const createKeyMutation = useMutation({
    mutationKey: ['console', 'settings', 'create-api-key'],
    mutationFn: () =>
      createApiKey({
        name: keyForm.name.trim(),
        scopes: [keyForm.scope],
        expires_in_days: keyForm.expiresInDays,
      }),
    onSuccess: (result) => {
      void keysQuery.refetch()
      setCreatingKey(false)
      setKeyForm({ name: '', scope: 'read', expiresInDays: 90 })
      setSecretCopied(false)
      setRevealed({ name: result.item.name, secret: result.api_key })
    },
    onError: onWriteError('Failed to create the API key'),
  })

  const rotateKeyMutation = useMutation({
    mutationKey: ['console', 'settings', 'rotate-api-key'],
    mutationFn: () => rotateApiKey(rotateTarget!.id),
    onSuccess: (result) => {
      void keysQuery.refetch()
      setRotateTarget(null)
      setSecretCopied(false)
      setRevealed({ name: result.item.name, secret: result.api_key })
    },
    onError: onWriteError('Failed to rotate the API key'),
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

  const createEndpointMutation = useMutation({
    mutationKey: ['console', 'settings', 'create-endpoint'],
    mutationFn: () =>
      createNotificationEndpoint({
        name: endpointForm.name.trim(),
        kind: endpointForm.kind,
        url: endpointForm.url.trim(),
      }),
    onSuccess: () => {
      void endpointsQuery.refetch()
      setCreatingEndpoint(false)
      setEndpointForm(EMPTY_ENDPOINT_FORM)
    },
    onError: onWriteError('Failed to create the endpoint'),
  })

  const updateEndpointMutation = useMutation({
    mutationKey: ['console', 'settings', 'update-endpoint'],
    mutationFn: () =>
      updateNotificationEndpoint(editingEndpoint!.id, {
        name: endpointForm.name.trim(),
        kind: endpointForm.kind,
        status: endpointForm.status,
        // The target is never shown back, so an empty box means "keep it" —
        // sending an empty url would blank a working destination.
        ...(endpointForm.url.trim() ? { url: endpointForm.url.trim() } : {}),
      }),
    onSuccess: () => {
      void endpointsQuery.refetch()
      setEditingEndpoint(null)
      setEndpointForm(EMPTY_ENDPOINT_FORM)
    },
    onError: onWriteError('Failed to update the endpoint'),
  })

  const deleteEndpointMutation = useMutation({
    mutationKey: ['console', 'settings', 'delete-endpoint'],
    mutationFn: () => deleteNotificationEndpoint(deletingEndpoint!.id),
    onSuccess: () => {
      void endpointsQuery.refetch()
      setDeletingEndpoint(null)
    },
    onError: onWriteError('Failed to delete the endpoint'),
  })

  const testEndpointMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'test-endpoint'],
    mutationFn: (endpointId: string) => testNotificationEndpoint(endpointId),
    onSuccess: () => {
      // A test only queues a delivery; the list is refetched because the
      // attempt can flip an endpoint out of "active" server-side.
      void endpointsQuery.refetch()
      toast.success(t('console.settings.notificationsPane.testQueued'))
    },
    onError: onWriteError('Failed to send the test notification'),
  })

  useEffect(() => {
    if (userQuery.data) setDisplayName(userQuery.data.name || '')
  }, [userQuery.data])

  useEffect(() => {
    if (egressQuery.data) setIpAllowlist((egressQuery.data.allowlist || []).join('\n'))
  }, [egressQuery.data])

  if (!section) {
    return <Navigate to={`/settings/account${location.search}`} replace />
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
              <label>
                {t('console.settings.accountPane.workspaceName')}
                <small>{t('console.settings.accountPane.workspaceNameHint')}</small>
              </label>
              <input
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
                {/* addWorkspaceMember takes an existing tenant user id — there is
                    no invite-by-email endpoint, so the dialog asks for the id. */}
                <ConsoleButton
                  variant="primary"
                  style={{ height: 24, fontSize: 11 }}
                  disabled={!workspaceId}
                  onClick={() => {
                    setInviteForm({ userId: '', role: 'Dev' })
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
                        {/* BACKEND-PENDING: membership carries no MFA state. */}
                        <StatusChip status="na" label="—" />
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
                <ConsoleButton
                  variant="primary"
                  style={{ height: 24, fontSize: 11 }}
                  onClick={() => {
                    setKeyForm({ name: '', scope: 'read', expiresInDays: 90 })
                    setCreatingKey(true)
                  }}
                >
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
                          <span style={{ display: 'inline-flex', gap: 6 }}>
                            <ConsoleButton
                              variant="ghost"
                              style={{ height: 22, fontSize: 10.5 }}
                              disabled={key.status === 'revoked' || rotateKeyMutation.isPending}
                              onClick={() => setRotateTarget(key)}
                            >
                              {t('console.settings.apiPane.rotate')}
                            </ConsoleButton>
                            <ConsoleButton
                              variant="ghost"
                              style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                              disabled={key.status === 'revoked' || revokeMutation.isPending}
                              onClick={() => revokeMutation.mutate(key.id)}
                            >
                              {t('console.settings.apiPane.revoke')}
                            </ConsoleButton>
                          </span>
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
                onClick={() => navigate('/govern/secrets')}
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
              <span className="more">
                <ConsoleButton
                  variant="primary"
                  style={{ height: 24, fontSize: 11 }}
                  onClick={() => {
                    setEndpointForm(EMPTY_ENDPOINT_FORM)
                    setCreatingEndpoint(true)
                  }}
                >
                  {t('console.settings.notificationsPane.addEndpoint')}
                </ConsoleButton>
              </span>
            </div>
            {/* The rows below name these endpoints, so the list they describe
                comes first — and it is the only real routing surface here. */}
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.endpoints')}
                <small>{t('console.settings.notificationsPane.endpointsHint')}</small>
              </label>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {endpoints.length === 0 ? (
                  <span className="dimmer" style={{ fontSize: 11.5 }}>
                    {endpointsQuery.isPending
                      ? t('console.common.loading')
                      : endpointsQuery.isError
                        ? t('console.common.loadError')
                        : t('console.settings.notificationsPane.noEndpoints')}
                  </span>
                ) : (
                  endpoints.map((endpoint) => (
                    <div
                      key={endpoint.id}
                      style={{ display: 'flex', gap: 8, alignItems: 'center' }}
                    >
                      <span className="chip">{endpoint.kind}</span>
                      <span style={{ fontSize: 12 }}>{endpoint.name}</span>
                      <span className="mono dimmer" style={{ fontSize: 11 }}>
                        {endpoint.display_target}
                      </span>
                      <StatusChip
                        status={endpoint.status === 'active' ? 'enabled' : 'disabled'}
                      />
                      <span style={{ display: 'inline-flex', gap: 6, marginLeft: 'auto' }}>
                        <ConsoleButton
                          variant="ghost"
                          style={{ height: 22, fontSize: 10.5 }}
                          disabled={
                            endpoint.status !== 'active' || testEndpointMutation.isPending
                          }
                          onClick={() => testEndpointMutation.mutate(endpoint.id)}
                        >
                          {t('console.settings.notificationsPane.test')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          style={{ height: 22, fontSize: 10.5 }}
                          onClick={() => {
                            setEndpointForm({
                              name: endpoint.name,
                              kind: endpoint.kind,
                              // The stored target is never returned in full, so
                              // the box starts empty and means "unchanged".
                              url: '',
                              status: endpoint.status,
                            })
                            setEditingEndpoint(endpoint)
                          }}
                        >
                          {t('console.settings.notificationsPane.edit')}
                        </ConsoleButton>
                        <ConsoleButton
                          variant="ghost"
                          style={{
                            height: 22,
                            fontSize: 10.5,
                            color: 'var(--danger-foreground)',
                          }}
                          onClick={() => setDeletingEndpoint(endpoint)}
                        >
                          {t('console.settings.notificationsPane.remove')}
                        </ConsoleButton>
                      </span>
                    </div>
                  ))
                )}
              </div>
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
                value={membersQuery.data ? `${members.length} / ${mockTiles.settingsSeats.value}` : '—'}
                na={!membersQuery.data}
                sub={<span className="mono dimmer">{mockTiles.settingsSeats.sub}</span>}
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
          <label>{t('console.settings.accountPane.currentPassword')}</label>
          <input
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
          <label>{t('console.settings.accountPane.newPassword')}</label>
          <input
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

      <ConsoleModal
        open={inviting}
        onOpenChange={setInviting}
        title={t('console.settings.teamPane.inviteTitle')}
        note={t('console.settings.teamPane.inviteNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!inviteForm.userId.trim()}
        busy={inviteMutation.isPending}
        onConfirm={() => inviteMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.settings.teamPane.memberId')}
            <small>{t('console.settings.teamPane.memberIdHint')}</small>
          </label>
          <input
            className="input"
            value={inviteForm.userId}
            onChange={(event) =>
              setInviteForm((state) => ({ ...state, userId: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.teamPane.columns.role')}</label>
          <select
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
          <label>{t('console.settings.teamPane.columns.member')}</label>
          <input
            className="input"
            value={roleTarget?.name || roleTarget?.email || ''}
            disabled
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.teamPane.columns.role')}</label>
          <select
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

      <ConsoleModal
        open={creatingKey}
        onOpenChange={setCreatingKey}
        title={t('console.settings.apiPane.createTitle')}
        note={t('console.settings.apiPane.createNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!keyForm.name.trim()}
        busy={createKeyMutation.isPending}
        onConfirm={() => createKeyMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.settings.apiPane.fields.name')}
            <small>{t('console.settings.apiPane.fields.nameHint')}</small>
          </label>
          <input
            className="input"
            value={keyForm.name}
            onChange={(event) => setKeyForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.settings.apiPane.fields.scope')}
            <small>{t('console.settings.apiPane.fields.scopeHint')}</small>
          </label>
          <select
            className="input"
            value={keyForm.scope}
            onChange={(event) =>
              setKeyForm((state) => ({ ...state, scope: event.target.value as ApiKeyScope }))
            }
          >
            {API_KEY_SCOPES.map((scope) => (
              <option key={scope} value={scope}>
                {scope}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>{t('console.settings.apiPane.fields.expires')}</label>
          <select
            className="input"
            value={String(keyForm.expiresInDays)}
            onChange={(event) =>
              setKeyForm((state) => ({ ...state, expiresInDays: Number(event.target.value) }))
            }
          >
            {API_KEY_LIFETIMES.map((days) => (
              <option key={days} value={days}>
                {t('console.settings.apiPane.expiresDays', { days })}
              </option>
            ))}
          </select>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={rotateTarget != null}
        onOpenChange={(open) => !open && setRotateTarget(null)}
        title={t('console.settings.apiPane.rotateTitle')}
        note={t('console.settings.apiPane.rotateNote')}
        confirmLabel={t('console.settings.apiPane.rotate')}
        destructive
        busy={rotateKeyMutation.isPending}
        onConfirm={() => rotateKeyMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.settings.apiPane.rotateConfirm', { name: rotateTarget?.name ?? '' })}
        </div>
      </ConsoleModal>

      {/* The one and only sighting of the plaintext secret. Dismissing the
          dialog drops it from memory; nothing else ever holds it. */}
      <ConsoleModal
        open={revealed != null}
        onOpenChange={(open) => {
          if (!open) {
            setRevealed(null)
            setSecretCopied(false)
          }
        }}
        title={t('console.settings.apiPane.revealTitle')}
        note={t('console.settings.apiPane.revealNote')}
        confirmLabel={t('console.settings.apiPane.revealDone')}
        onConfirm={() => {
          setRevealed(null)
          setSecretCopied(false)
        }}
      >
        <div className="mrow">
          <label>{t('console.settings.apiPane.fields.name')}</label>
          <input className="input" value={revealed?.name ?? ''} disabled />
        </div>
        <div className="mrow">
          <label>{t('console.settings.apiPane.columns.key')}</label>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              className="input"
              readOnly
              data-testid="revealed-api-key"
              value={revealed?.secret ?? ''}
              onFocus={(event) => event.currentTarget.select()}
              style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
            />
            <ConsoleButton
              onClick={() => {
                const secret = revealed?.secret
                if (!secret) return
                void navigator.clipboard
                  ?.writeText(secret)
                  .then(() => setSecretCopied(true))
                  .catch(() => undefined)
              }}
            >
              {secretCopied ? t('console.common.copied') : t('console.common.copy')}
            </ConsoleButton>
          </div>
        </div>
        <div style={{ padding: '4px 16px 12px', fontSize: 12, lineHeight: 1.6 }} className="dim">
          {t('console.settings.apiPane.revealHint')}
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={creatingEndpoint}
        onOpenChange={setCreatingEndpoint}
        title={t('console.settings.notificationsPane.endpointTitle')}
        note={t('console.settings.notificationsPane.endpointNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!endpointForm.name.trim() || !endpointForm.url.trim()}
        busy={createEndpointMutation.isPending}
        onConfirm={() => createEndpointMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            className="input"
            value={endpointForm.name}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            className="input"
            value={endpointForm.kind}
            onChange={(event) =>
              setEndpointForm((state) => ({
                ...state,
                kind: event.target.value as NotificationEndpointKind,
              }))
            }
          >
            {ENDPOINT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.settings.notificationsPane.endpointFields.url')}
            <small>{t('console.settings.notificationsPane.endpointFields.urlHint')}</small>
          </label>
          <input
            className="input"
            type="password"
            autoComplete="off"
            value={endpointForm.url}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, url: event.target.value }))
            }
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={editingEndpoint != null}
        onOpenChange={(open) => !open && setEditingEndpoint(null)}
        title={t('console.settings.notificationsPane.editEndpointTitle')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!endpointForm.name.trim()}
        busy={updateEndpointMutation.isPending}
        onConfirm={() => updateEndpointMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            className="input"
            value={endpointForm.name}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            className="input"
            value={endpointForm.kind}
            onChange={(event) =>
              setEndpointForm((state) => ({
                ...state,
                kind: event.target.value as NotificationEndpointKind,
              }))
            }
          >
            {ENDPOINT_KINDS.map((kind) => (
              <option key={kind} value={kind}>
                {kind}
              </option>
            ))}
          </select>
        </div>
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.status')}</label>
          <select
            className="input"
            value={endpointForm.status}
            onChange={(event) =>
              setEndpointForm((state) => ({
                ...state,
                status: event.target.value as 'active' | 'disabled',
              }))
            }
          >
            <option value="active">
              {t('console.settings.notificationsPane.statusActive')}
            </option>
            <option value="disabled">
              {t('console.settings.notificationsPane.statusDisabled')}
            </option>
          </select>
        </div>
        <div className="mrow">
          <label>
            {t('console.settings.notificationsPane.endpointFields.url')}
            <small>{t('console.settings.notificationsPane.endpointFields.urlEditHint')}</small>
          </label>
          <input
            className="input"
            type="password"
            autoComplete="off"
            value={endpointForm.url}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, url: event.target.value }))
            }
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingEndpoint != null}
        onOpenChange={(open) => !open && setDeletingEndpoint(null)}
        title={t('console.settings.notificationsPane.deleteEndpointTitle')}
        confirmLabel={t('console.settings.notificationsPane.remove')}
        destructive
        busy={deleteEndpointMutation.isPending}
        onConfirm={() => deleteEndpointMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.settings.notificationsPane.deleteEndpointConfirm', {
            name: deletingEndpoint?.name ?? '',
          })}
        </div>
      </ConsoleModal>
    </>
  )
}
