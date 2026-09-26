import { useEffect, useState } from 'react'

import { Navigate, NavLink, useLocation, useParams } from 'react-router'
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
import {
  ApiKeyLimitFields,
  ApiKeyLimitsSummary,
  EMPTY_LIMITS_DRAFT,
  limitsDraftOf,
  limitsPayload,
  presentLimits,
  type ApiKeyLimitsDraft,
} from '../components/api-key-limits'
import { ClientEndpoints } from '../components/client-endpoints'
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
  updateApiKey,
  type ApiKeyItem,
  type ApiKeyScope,
} from '@/services/api-key-service'
import { getCreditBalance, listCreditEntries } from '@/services/billing-service'
import {
  cancelAccountDeletion,
  confirmMfaEnrolment,
  getAuthCapabilities,
  disableMfa,
  getAccountDeletionRequest,
  getMfaStatus,
  listSessions,
  revokeAllSessions,
  requestAccountDeletion,
  revokeSession,
  startMfaEnrolment,
} from '@/services/auth-service'
import { getDiagnosticsSnapshot } from '@/services/diagnostics-service'
import {
  addWorkspaceMember,
  changePassword,
  createInvitation,
  createServicePrincipal,
  deleteServicePrincipal,
  getCurrentUser,
  listInvitations,
  listServicePrincipals,
  listWorkspaceMembers,
  removeWorkspaceMember,
  revokeInvitation,
  updateCurrentUser,
  getWorkspace,
  updateServicePrincipal,
  updateWorkspace,
  updateWorkspaceMemberRole,
  type PiiAction,
  type ServicePrincipal,
  type ServicePrincipalRole,
  type WorkspaceContentCapture,
  type WorkspaceMember,
} from '@/services/identity-service'
import {
  createNotificationEndpoint,
  createWorkspaceEndpoint,
  deleteNotificationEndpoint,
  deleteWorkspaceEndpoint,
  getNotificationPreferences,
  listNotificationEndpoints,
  listWorkspaceEndpoints,
  testNotificationEndpoint,
  testWorkspaceEndpoint,
  updateNotificationEndpoint,
  updateNotificationPreferences,
  type NotificationEndpoint,
  type NotificationEndpointKind,
  type WorkspaceAlertCategory,
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

/**
 * Credits arrive as fixed-point decimal strings ("612.400000"). `magnitude`
 * drops the sign, for totals the label already says are consumption.
 */
function formatCredits(value: string, magnitude = false): string {
  const parsed = Number(value)
  if (!Number.isFinite(parsed)) return value
  return (magnitude ? Math.abs(parsed) : parsed).toLocaleString('en-US', {
    maximumFractionDigits: 2,
  })
}

/** The server's workspace role vocabulary (kernel/identity/rbac.py). */
const WORKSPACE_ROLES = ['Owner', 'Admin', 'Dev', 'Viewer'] as const
const API_KEY_SCOPES: ApiKeyScope[] = ['read', 'write', 'admin']
const API_KEY_LIFETIMES = [30, 90, 180, 365]
/** A principal can hold any workspace role except Owner. */
const PRINCIPAL_ROLES: ServicePrincipalRole[] = ['Viewer', 'Dev', 'Admin']

interface KeyForm {
  name: string
  scope: ApiKeyScope
  expiresInDays: number
  /** Empty issues the key to the signed-in member. */
  principalId: string
  limits: ApiKeyLimitsDraft
}

const EMPTY_KEY_FORM: KeyForm = {
  name: '',
  scope: 'read',
  expiresInDays: 90,
  principalId: '',
  limits: EMPTY_LIMITS_DRAFT,
}

const EMPTY_PRINCIPAL_FORM: { name: string; description: string; role: ServicePrincipalRole } = {
  name: '',
  description: '',
  role: 'Dev',
}
const ENDPOINT_KINDS: NotificationEndpointKind[] = [
  'email',
  'webhook',
  'slack',
  'teams',
  'discord',
  'telegram',
  'other',
]

/** Team channel subscriptions, in the order the dialog offers them. */
const TEAM_CHANNEL_CATEGORIES: WorkspaceAlertCategory[] = ['alert', 'task', 'security', 'system']

const EMPTY_CHANNEL_FORM: {
  name: string
  kind: NotificationEndpointKind
  url: string
  categories: WorkspaceAlertCategory[]
} = { name: '', kind: 'slack', url: '', categories: ['alert'] }

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
  const [inviteForm, setInviteForm] = useState({ userId: '', email: '', role: 'Dev' })
  const [roleTarget, setRoleTarget] = useState<WorkspaceMember | null>(null)
  const [roleDraft, setRoleDraft] = useState('Dev')
  const [removalTarget, setRemovalTarget] = useState<WorkspaceMember | null>(null)

  const [creatingKey, setCreatingKey] = useState(false)
  const [keyForm, setKeyForm] = useState<KeyForm>(EMPTY_KEY_FORM)
  const [rotateTarget, setRotateTarget] = useState<ApiKeyItem | null>(null)
  const [limitsTarget, setLimitsTarget] = useState<ApiKeyItem | null>(null)
  const [limitsDraft, setLimitsDraft] = useState<ApiKeyLimitsDraft>(EMPTY_LIMITS_DRAFT)
  const [creatingPrincipal, setCreatingPrincipal] = useState(false)
  const [principalForm, setPrincipalForm] = useState(EMPTY_PRINCIPAL_FORM)
  const [deletingPrincipal, setDeletingPrincipal] = useState<ServicePrincipal | null>(null)
  // The plaintext secret exists here and nowhere else, for exactly as long as
  // the reveal dialog is open: never logged, never toasted, never persisted.
  const [revealed, setRevealed] = useState<{ name: string; secret: string } | null>(null)
  const [secretCopied, setSecretCopied] = useState(false)

  const [creatingEndpoint, setCreatingEndpoint] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [deletingEndpoint, setDeletingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [endpointForm, setEndpointForm] = useState(EMPTY_ENDPOINT_FORM)
  const [creatingChannel, setCreatingChannel] = useState(false)
  const [deletingChannel, setDeletingChannel] = useState<NotificationEndpoint | null>(null)
  const [channelForm, setChannelForm] = useState(EMPTY_CHANNEL_FORM)

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
      // The billing pane's seat count and the API pane's principal owners read
      // the same member list.
      enabled: (on('team') || on('billing') || on('api')) && Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const keysQuery = useQuery({
    queryKey: ['console', 'settings', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: { enabled: on('api'), retry: false, refetchOnWindowFocus: false },
  })
  const principalsQuery = useQuery({
    queryKey: ['console', 'settings', 'service-principals'],
    queryFn: () => listServicePrincipals({ suppressErrorToast: true }),
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
  // Owners and admins only: anyone else is answered 403, which the panel
  // explains rather than reporting as a failure.
  const channelsQuery = useQuery({
    queryKey: ['console', 'settings', 'team-channels'],
    queryFn: () => listWorkspaceEndpoints({ suppressErrorToast: true }),
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
    queryFn: () => listCreditEntries({ limit: 20 }),
    options: { enabled: on('billing'), retry: false, refetchOnWindowFocus: false },
  })

  const workspaceQuery = useQuery({
    queryKey: ['console', 'settings', 'workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId),
    options: {
      // Both panes read it: Account renames the workspace, Security sets its
      // two-factor requirement.
      enabled: (on('account') || on('security')) && Boolean(workspaceId),
      retry: false,
      refetchOnWindowFocus: false,
    },
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
    options: { enabled: active === 'account', retry: false, refetchOnWindowFocus: false },
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

  // Closing an account is a request with a pause, not a button that deletes.
  const [closureOpen, setClosureOpen] = useState(false)
  const [closureReason, setClosureReason] = useState('')

  const closureQuery = useQuery({
    queryKey: ['console', 'settings', 'closure'],
    queryFn: () => getAccountDeletionRequest({ suppressErrorToast: true }),
    options: { enabled: active === 'account', retry: false, refetchOnWindowFocus: false },
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

  // Inviting by address needs a mail outlet; the console asks rather than
  // offering a flow that would end in a dropped message.
  const capabilities = useQuery({
    queryKey: ['console', 'settings', 'auth-capabilities'],
    queryFn: () => getAuthCapabilities({ suppressErrorToast: true }),
    options: { enabled: on('team'), retry: false, refetchOnWindowFocus: false },
  })
  const canMail = capabilities.data?.mail_enabled === true

  const invitationsQuery = useQuery({
    queryKey: ['console', 'settings', 'invitations', workspaceId],
    queryFn: () => listInvitations(workspaceId, { suppressErrorToast: true }),
    options: {
      enabled: on('team') && Boolean(workspaceId) && canMail,
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

  const newKeyLimits = limitsPayload(keyForm.limits)
  const createKeyMutation = useMutation({
    mutationKey: ['console', 'settings', 'create-api-key'],
    mutationFn: () =>
      createApiKey(
        {
          name: keyForm.name.trim(),
          scopes: [keyForm.scope],
          expires_in_days: keyForm.expiresInDays,
          ...(keyForm.principalId ? { principal_id: keyForm.principalId } : {}),
          ...presentLimits(newKeyLimits),
        },
        { suppressErrorToast: true },
      ),
    onSuccess: (result) => {
      void keysQuery.refetch()
      setCreatingKey(false)
      setKeyForm(EMPTY_KEY_FORM)
      setSecretCopied(false)
      setRevealed({ name: result.item.name, secret: result.api_key })
    },
    onError: onWriteError('Failed to create the API key'),
  })

  const editedLimits = limitsPayload(limitsDraft)
  const limitsMutation = useMutation({
    mutationKey: ['console', 'settings', 'api-key-limits'],
    mutationFn: () =>
      updateApiKey(limitsTarget!.id, editedLimits ?? {}, { suppressErrorToast: true }),
    onSuccess: () => {
      void keysQuery.refetch()
      setLimitsTarget(null)
      toast.success(t('console.settings.apiPane.limits.saved'))
    },
    onError: onWriteError('Failed to change the key limits'),
  })

  const createPrincipalMutation = useMutation({
    mutationKey: ['console', 'settings', 'create-service-principal'],
    mutationFn: () =>
      createServicePrincipal(
        {
          name: principalForm.name.trim(),
          workspace_role: principalForm.role,
          ...(principalForm.description.trim()
            ? { description: principalForm.description.trim() }
            : {}),
        },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void principalsQuery.refetch()
      setCreatingPrincipal(false)
      setPrincipalForm(EMPTY_PRINCIPAL_FORM)
    },
    onError: onWriteError('Failed to create the service principal'),
  })

  const principalStatusMutation = useMutation<unknown, unknown, ServicePrincipal>({
    mutationKey: ['console', 'settings', 'service-principal-status'],
    mutationFn: (principal: ServicePrincipal) =>
      updateServicePrincipal(
        principal.id,
        { status: principal.status === 'active' ? 'disabled' : 'active' },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void principalsQuery.refetch()
    },
    onError: onWriteError('Failed to change the service principal'),
  })

  const deletePrincipalMutation = useMutation({
    mutationKey: ['console', 'settings', 'delete-service-principal'],
    mutationFn: () => deleteServicePrincipal(deletingPrincipal!.id, { suppressErrorToast: true }),
    onSuccess: () => {
      void principalsQuery.refetch()
      void keysQuery.refetch()
      setDeletingPrincipal(null)
    },
    onError: onWriteError('Failed to delete the service principal'),
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

  const createChannelMutation = useMutation({
    mutationKey: ['console', 'settings', 'create-team-channel'],
    mutationFn: () =>
      createWorkspaceEndpoint(
        {
          name: channelForm.name.trim(),
          kind: channelForm.kind,
          url: channelForm.url.trim(),
          categories: channelForm.categories,
        },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      void channelsQuery.refetch()
      setCreatingChannel(false)
      setChannelForm(EMPTY_CHANNEL_FORM)
    },
    onError: onWriteError('Failed to add the team channel'),
  })

  const deleteChannelMutation = useMutation({
    mutationKey: ['console', 'settings', 'delete-team-channel'],
    mutationFn: () => deleteWorkspaceEndpoint(deletingChannel!.id, { suppressErrorToast: true }),
    onSuccess: () => {
      void channelsQuery.refetch()
      setDeletingChannel(null)
    },
    onError: onWriteError('Failed to delete the team channel'),
  })

  const testChannelMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'settings', 'test-team-channel'],
    mutationFn: (endpointId: string) =>
      testWorkspaceEndpoint(endpointId, { suppressErrorToast: true }),
    onSuccess: () => {
      void channelsQuery.refetch()
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
  const principals = principalsQuery.data || []
  const principalName = (principalId?: string | null) =>
    principals.find((item) => item.id === principalId)?.name || principalId || ''
  const memberName = (userId: string) => {
    const member = members.find((item) => item.user_id === userId)
    return member?.name || member?.email || userId
  }

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
  // A category the stored preference predates is on, as the server treats it.
  const categoryOn = (key: string) => preferences?.categories?.[key] ?? true
  const channels = Array.isArray(channelsQuery.data) ? channelsQuery.data : []
  const channelsForbidden =
    (channelsQuery.error as { response?: { status?: number } } | null)?.response?.status === 403

  const diagnostics = diagnosticsQuery.data
  const creditEntries = entriesQuery.data || []

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
        )}

        {active === 'team' && (
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
                    setKeyForm(EMPTY_KEY_FORM)
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
                  <th>{t('console.settings.apiPane.columns.limits')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.created')}</th>
                  <th className="num">{t('console.settings.apiPane.columns.lastUsed')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {apiKeys.length === 0 ? (
                  <DataStateRow
                    colSpan={7}
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
                          <b style={{ fontWeight: 600 }}>{key.name}</b>{' '}
                          <NavLink
                            className="mono dimmer"
                            style={{ fontSize: 10.5 }}
                            to={`/observe/runs?api_key_id=${encodeURIComponent(key.id)}`}
                          >
                            {t('console.settings.apiPane.viewRuns')}
                          </NavLink>
                          {key.principal_id && (
                            <span className="dimmer mono" style={{ display: 'block', fontSize: 10.5 }}>
                              {t('console.settings.apiPane.actsAs', {
                                name: principalName(key.principal_id),
                              })}
                            </span>
                          )}
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
                        <td>
                          <ApiKeyLimitsSummary limits={key} />
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
                              disabled={key.status === 'revoked'}
                              onClick={() => {
                                setLimitsDraft(limitsDraftOf(key))
                                setLimitsTarget(key)
                              }}
                            >
                              {t('console.settings.apiPane.editLimits')}
                            </ConsoleButton>
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

        {active === 'api' && <ClientEndpoints />}

        {active === 'api' && (
          <div className="panel" style={{ marginTop: 14 }}>
            <div className="panel-head">
              <h2>{t('console.settings.principalsPane.title')}</h2>
              <span className="hint">{t('console.settings.principalsPane.hint')}</span>
              <span className="more">
                <ConsoleButton
                  style={{ height: 24, fontSize: 11 }}
                  onClick={() => {
                    setPrincipalForm(EMPTY_PRINCIPAL_FORM)
                    setCreatingPrincipal(true)
                  }}
                >
                  {t('console.settings.principalsPane.create')}
                </ConsoleButton>
              </span>
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t('console.settings.principalsPane.columns.name')}</th>
                  <th>{t('console.settings.principalsPane.columns.role')}</th>
                  <th>{t('console.settings.principalsPane.columns.owner')}</th>
                  <th>{t('console.settings.principalsPane.columns.keys')}</th>
                  <th className="num">{t('console.settings.principalsPane.columns.status')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {principals.length === 0 ? (
                  <DataStateRow
                    colSpan={6}
                    isPending={principalsQuery.isPending}
                    isError={principalsQuery.isError}
                    emptyLabel={t('console.settings.principalsPane.empty')}
                  />
                ) : (
                  principals.map((principal) => {
                    const keyCount = apiKeys.filter(
                      (key) => key.principal_id === principal.id && key.status === 'active',
                    ).length
                    return (
                      <tr key={principal.id}>
                        <td>
                          <b style={{ fontWeight: 600 }}>{principal.name}</b>
                          {principal.description && (
                            <span className="dimmer" style={{ display: 'block', fontSize: 11 }}>
                              {principal.description}
                            </span>
                          )}
                        </td>
                        <td>
                          <span className="chip">{principal.workspace_role}</span>
                        </td>
                        <td className="dim">{memberName(principal.owner_user_id)}</td>
                        <td className="mono dim">{keyCount}</td>
                        <td className="num">
                          <StatusChip
                            status={principal.status === 'active' ? 'enabled' : 'disabled'}
                            label={
                              principal.status === 'active'
                                ? t('console.settings.principalsPane.active')
                                : t('console.settings.principalsPane.disabled')
                            }
                          />
                        </td>
                        <td className="num">
                          <span style={{ display: 'inline-flex', gap: 6 }}>
                            <ConsoleButton
                              variant="ghost"
                              style={{ height: 22, fontSize: 10.5 }}
                              disabled={principal.status !== 'active'}
                              onClick={() => {
                                setKeyForm({
                                  ...EMPTY_KEY_FORM,
                                  name: principal.name,
                                  principalId: principal.id,
                                })
                                setCreatingKey(true)
                              }}
                            >
                              {t('console.settings.principalsPane.issueKey')}
                            </ConsoleButton>
                            <ConsoleButton
                              variant="ghost"
                              style={{ height: 22, fontSize: 10.5 }}
                              disabled={principalStatusMutation.isPending}
                              onClick={() => principalStatusMutation.mutate(principal)}
                            >
                              {principal.status === 'active'
                                ? t('console.settings.principalsPane.disable')
                                : t('console.settings.principalsPane.enable')}
                            </ConsoleButton>
                            <ConsoleButton
                              variant="ghost"
                              style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                              onClick={() => setDeletingPrincipal(principal)}
                            >
                              {t('console.settings.principalsPane.delete')}
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
              <span>{t('console.settings.principalsPane.note')}</span>
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
              {/* Two states, not three: the server can require a second factor
                  for this workspace or not. A per-role requirement would need a
                  policy object that does not exist, and offering it here would
                  be a control that quietly does nothing. */}
              <select
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
              <label>
                {t('console.settings.securityPane.contentCapture')}
                <small>{t('console.settings.securityPane.contentCaptureHint')}</small>
              </label>
              <select
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
                <label>
                  {label}
                  <small>{hint}</small>
                </label>
                <select
                  className="input"
                  style={{ maxWidth: 280 }}
                  aria-label={label}
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
              <label>
                {t('console.settings.securityPane.sso')}
                <small>{t('console.settings.securityPane.ssoHint')}</small>
              </label>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                {/* BACKEND-PENDING: no SSO/SAML configuration endpoint. SSO is an
                    Enterprise feature (README, "Open source and commercial
                    editions"), so Community will not grow one. */}
                <StatusChip status="info" label="NOT CONFIGURED" />
                <ConsoleButton style={{ height: 24, fontSize: 11 }}>
                  {t('console.settings.securityPane.configureSso')}
                </ConsoleButton>
              </div>
            </div>
            <div className="frow">
              <label>{t('console.settings.securityPane.sessionTimeout')}</label>
              {/* BACKEND-PENDING: session lifetime is an instance setting
                  (ACCESS_TOKEN_EXPIRE_MINUTES), not a workspace one. Not built
                  rather than withheld: it needs a per-workspace override the
                  token issuer would have to read. */}
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
              {/* BACKEND-PENDING: audit-log access follows the workspace role.
                Making it settable is advanced RBAC, an Enterprise feature
                (README, "Open source and commercial editions"). */}
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
                    vocabulary is system/security/account/agent/workflow/task.
                    Not built: it needs a category the notification service
                    emits, not only one the console offers. */}
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
                {/* BACKEND-PENDING: per-channel digest cadence has no backend.
                    Not built: preferences are per category, not per channel. */}
                <label>
                  <input type="checkbox" />
                  {emailLabel}
                </label>
              </div>
            </div>
            <div className="frow">
              <label>
                {t('console.settings.notificationsPane.budget')}
                <small>{t('console.settings.notificationsPane.budgetHint')}</small>
              </label>
              <div className="checks">
                {/* Budget thresholds and low credit share the "alert"
                    category; they reach owners and admins. */}
                <label>
                  <input
                    type="checkbox"
                    checked={categoryOn('alert')}
                    onChange={(event) =>
                      categoryMutation.mutate({ category: 'alert', enabled: event.target.checked })
                    }
                  />
                  {t('console.settings.notificationsPane.budgetToMe')}
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
                {/* BACKEND-PENDING: no scheduled-digest preference. Not built:
                    notifications are delivered per event, never batched. */}
                <label>
                  <input type="checkbox" defaultChecked />
                  {emailLabel}
                </label>
              </div>
            </div>
          </div>
        )}

        {active === 'notifications' && (
          <div className="panel" style={{ marginTop: 14 }}>
            <div className="panel-head">
              <h2>{t('console.settings.teamChannels.title')}</h2>
              <span className="hint">{t('console.settings.teamChannels.hint')}</span>
              {!channelsForbidden && (
                <span className="more">
                  <ConsoleButton
                    style={{ height: 24, fontSize: 11 }}
                    onClick={() => {
                      setChannelForm(EMPTY_CHANNEL_FORM)
                      setCreatingChannel(true)
                    }}
                  >
                    {t('console.settings.teamChannels.add')}
                  </ConsoleButton>
                </span>
              )}
            </div>
            <table>
              <thead>
                <tr>
                  <th>{t('console.settings.teamChannels.columns.channel')}</th>
                  <th>{t('console.settings.teamChannels.columns.target')}</th>
                  <th>{t('console.settings.teamChannels.columns.receives')}</th>
                  <th className="num">{t('console.settings.teamChannels.columns.status')}</th>
                  <th className="num" />
                </tr>
              </thead>
              <tbody>
                {channels.length === 0 ? (
                  <DataStateRow
                    colSpan={5}
                    isPending={channelsQuery.isPending}
                    isError={channelsQuery.isError && !channelsForbidden}
                    emptyLabel={
                      channelsForbidden
                        ? t('console.settings.teamChannels.forbidden')
                        : t('console.settings.teamChannels.empty')
                    }
                  />
                ) : (
                  channels.map((channel) => (
                    <tr key={channel.id}>
                      <td>
                        <span className="chip">{channel.kind}</span>{' '}
                        <b style={{ fontWeight: 600 }}>{channel.name}</b>
                      </td>
                      <td className="mono dimmer" style={{ fontSize: 11 }}>
                        {channel.display_target}
                      </td>
                      <td>
                        <span className="scopes">
                          {(channel.categories?.length
                            ? channel.categories
                            : (['alert'] as WorkspaceAlertCategory[])
                          ).map(
                            (category) => (
                              <span key={category} className="chip">
                                {t(`console.settings.teamChannels.categories.${category}`)}
                              </span>
                            ),
                          )}
                        </span>
                      </td>
                      <td className="num">
                        <StatusChip status={channel.status === 'active' ? 'enabled' : 'disabled'} />
                      </td>
                      <td className="num">
                        <span style={{ display: 'inline-flex', gap: 6 }}>
                          <ConsoleButton
                            variant="ghost"
                            style={{ height: 22, fontSize: 10.5 }}
                            disabled={channel.status !== 'active' || testChannelMutation.isPending}
                            onClick={() => testChannelMutation.mutate(channel.id)}
                          >
                            {t('console.settings.notificationsPane.test')}
                          </ConsoleButton>
                          <ConsoleButton
                            variant="ghost"
                            style={{ height: 22, fontSize: 10.5, color: 'var(--danger-foreground)' }}
                            onClick={() => setDeletingChannel(channel)}
                          >
                            {t('console.settings.notificationsPane.remove')}
                          </ConsoleButton>
                        </span>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
            <div className="pager">
              <span>{t('console.settings.teamChannels.note')}</span>
            </div>
          </div>
        )}

        {/* BACKEND-PENDING: edition, seats and invoices have no server object;
            the credits ledger is the only real billing surface and backs the
            spend tile and the entries table below. Seats and invoicing belong
            to SOIT Cloud (README, "Open source and commercial editions"), so
            Community will not grow them. */}
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
                    ? `${formatCredits(balanceQuery.data.deducted_total, true)} cr`
                    : '—'
                }
                na={!balanceQuery.data}
                sub={
                  <span className="mono dimmer">
                    {balanceQuery.data
                      ? `balance ${formatCredits(balanceQuery.data.balance)} cr`
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
                        <td className="dim">{entry.note || entry.cost_entry_id || entry.kind}</td>
                        <td className="num dim">{formatCredits(entry.credits_delta)} cr</td>
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
                // Stamped from package.json at build time by Vite.
                { key: t('console.settings.aboutPane.console'), value: `soit-web ${__CONSOLE_VERSION__}` },
                {
                  key: t('console.settings.aboutPane.runtime'),
                  value: diagnostics ? `soit-server ${diagnostics.version} · ${diagnostics.environment}` : '—',
                },
                // BACKEND-PENDING: /diagnostics reports no policy-engine version. Not
                // built: policy is enforced by the runtime itself and carries no
                // separate version. The policy bundle identifier on the Policies
                // page is what identifies the rules in force.
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
        )}
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
        confirmDisabled={!keyForm.name.trim() || newKeyLimits == null}
        busy={createKeyMutation.isPending}
        onConfirm={() => createKeyMutation.mutate(undefined)}
      >
        {principals.length > 0 && (
          <div className="mrow">
            <label>
              {t('console.settings.apiPane.fields.issuedTo')}
              <small>{t('console.settings.apiPane.fields.issuedToHint')}</small>
            </label>
            <select
              className="input"
              value={keyForm.principalId}
              onChange={(event) =>
                setKeyForm((state) => ({ ...state, principalId: event.target.value }))
              }
            >
              <option value="">{t('console.settings.apiPane.fields.issuedToMe')}</option>
              {principals
                .filter((principal) => principal.status === 'active')
                .map((principal) => (
                  <option key={principal.id} value={principal.id}>
                    {`${principal.name} · ${principal.workspace_role}`}
                  </option>
                ))}
            </select>
          </div>
        )}
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
        <ApiKeyLimitFields
          draft={keyForm.limits}
          onChange={(limits) => setKeyForm((state) => ({ ...state, limits }))}
        />
      </ConsoleModal>

      <ConsoleModal
        open={limitsTarget != null}
        onOpenChange={(open) => !open && setLimitsTarget(null)}
        title={t('console.settings.apiPane.limits.title', { name: limitsTarget?.name ?? '' })}
        note={t('console.settings.apiPane.limits.note')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={editedLimits == null}
        busy={limitsMutation.isPending}
        onConfirm={() => limitsMutation.mutate(undefined)}
      >
        <ApiKeyLimitFields draft={limitsDraft} onChange={setLimitsDraft} />
      </ConsoleModal>

      <ConsoleModal
        open={creatingPrincipal}
        onOpenChange={setCreatingPrincipal}
        title={t('console.settings.principalsPane.createTitle')}
        note={t('console.settings.principalsPane.createNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={!principalForm.name.trim()}
        busy={createPrincipalMutation.isPending}
        onConfirm={() => createPrincipalMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>
            {t('console.settings.principalsPane.fields.name')}
            <small>{t('console.settings.principalsPane.fields.nameHint')}</small>
          </label>
          <input
            className="input"
            value={principalForm.name}
            onChange={(event) =>
              setPrincipalForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.principalsPane.fields.description')}</label>
          <input
            className="input"
            value={principalForm.description}
            onChange={(event) =>
              setPrincipalForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.settings.principalsPane.fields.role')}
            <small>{t('console.settings.principalsPane.fields.roleHint')}</small>
          </label>
          <select
            className="input"
            value={principalForm.role}
            onChange={(event) =>
              setPrincipalForm((state) => ({
                ...state,
                role: event.target.value as ServicePrincipalRole,
              }))
            }
          >
            {PRINCIPAL_ROLES.map((role) => (
              <option key={role} value={role}>
                {role}
              </option>
            ))}
          </select>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingPrincipal != null}
        onOpenChange={(open) => !open && setDeletingPrincipal(null)}
        title={t('console.settings.principalsPane.deleteTitle')}
        confirmLabel={t('console.settings.principalsPane.delete')}
        destructive
        busy={deletePrincipalMutation.isPending}
        onConfirm={() => deletePrincipalMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.settings.principalsPane.deleteConfirm', {
            name: deletingPrincipal?.name ?? '',
          })}
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
        open={creatingChannel}
        onOpenChange={setCreatingChannel}
        title={t('console.settings.teamChannels.createTitle')}
        note={t('console.settings.notificationsPane.endpointNote')}
        confirmLabel={t('console.common.create')}
        confirmDisabled={
          !channelForm.name.trim() || !channelForm.url.trim() || channelForm.categories.length === 0
        }
        busy={createChannelMutation.isPending}
        onConfirm={() => createChannelMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            className="input"
            value={channelForm.name}
            onChange={(event) => setChannelForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label>{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            className="input"
            value={channelForm.kind}
            onChange={(event) =>
              setChannelForm((state) => ({
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
            <small>{t('console.settings.teamChannels.urlHint')}</small>
          </label>
          <input
            className="input"
            value={channelForm.url}
            onChange={(event) => setChannelForm((state) => ({ ...state, url: event.target.value }))}
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
        <div className="mrow">
          <label>
            {t('console.settings.teamChannels.columns.receives')}
            <small>{t('console.settings.teamChannels.receivesHint')}</small>
          </label>
          <div className="checks">
            {TEAM_CHANNEL_CATEGORIES.map((category) => (
              <label key={category}>
                <input
                  type="checkbox"
                  checked={channelForm.categories.includes(category)}
                  onChange={(event) =>
                    setChannelForm((state) => ({
                      ...state,
                      categories: event.target.checked
                        ? TEAM_CHANNEL_CATEGORIES.filter(
                            (item) => item === category || state.categories.includes(item),
                          )
                        : state.categories.filter((item) => item !== category),
                    }))
                  }
                />
                {t(`console.settings.teamChannels.categories.${category}`)}
              </label>
            ))}
          </div>
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingChannel != null}
        onOpenChange={(open) => !open && setDeletingChannel(null)}
        title={t('console.settings.teamChannels.deleteTitle')}
        confirmLabel={t('console.settings.notificationsPane.remove')}
        destructive
        busy={deleteChannelMutation.isPending}
        onConfirm={() => deleteChannelMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.settings.teamChannels.deleteConfirm', { name: deletingChannel?.name ?? '' })}
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
