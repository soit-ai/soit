import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton, ConsoleModal, DataStateRow, StatusChip } from '../../components'
import { onWriteError } from './shared'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
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
import { requestErrorMessage } from '@/utils/request'

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

/** Personal delivery endpoints and categories, then the workspace's team channels. */
export function NotificationsPane() {
  const { t } = useTranslation()
  const [creatingEndpoint, setCreatingEndpoint] = useState(false)
  const [editingEndpoint, setEditingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [deletingEndpoint, setDeletingEndpoint] = useState<NotificationEndpoint | null>(null)
  const [endpointForm, setEndpointForm] = useState(EMPTY_ENDPOINT_FORM)
  const [creatingChannel, setCreatingChannel] = useState(false)
  const [deletingChannel, setDeletingChannel] = useState<NotificationEndpoint | null>(null)
  const [channelForm, setChannelForm] = useState(EMPTY_CHANNEL_FORM)

  const preferencesQuery = useQuery({
    queryKey: ['console', 'settings', 'notification-preferences'],
    queryFn: () => getNotificationPreferences(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const endpointsQuery = useQuery({
    queryKey: ['console', 'settings', 'notification-endpoints'],
    queryFn: () => listNotificationEndpoints(),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  // Owners and admins only: anyone else is answered 403, which the panel
  // explains rather than reporting as a failure.
  const channelsQuery = useQuery({
    queryKey: ['console', 'settings', 'team-channels'],
    queryFn: () => listWorkspaceEndpoints({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
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

  const endpoints = endpointsQuery.data || []
  const chatEndpoint = endpoints.find((item) => item.kind !== 'email' && item.status === 'active')
  // Channel copy names the workspace's real endpoint. Per-row channel routing
  // has no backend — a preference carries one global delivery_mode plus the
  // endpoint list, so the label describes where a category would land.
  const chatLabel = chatEndpoint
    ? `${chatEndpoint.kind} · ${chatEndpoint.display_target}`
    : 'External endpoint'
  // A category the stored preference predates is on, as the server treats it.
  const categoryOn = (key: string) => preferences?.categories?.[key] ?? true
  const channels = Array.isArray(channelsQuery.data) ? channelsQuery.data : []
  const channelsForbidden =
    (channelsQuery.error as { response?: { status?: number } } | null)?.response?.status === 403

  return (
    <>
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
      </div>

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
          <label htmlFor="settings-field-23">{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            id="settings-field-23"
            className="input"
            value={channelForm.name}
            onChange={(event) => setChannelForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-24">{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            id="settings-field-24"
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
          <label htmlFor="settings-field-25">
            {t('console.settings.notificationsPane.endpointFields.url')}
            <small>{t('console.settings.teamChannels.urlHint')}</small>
          </label>
          <input
            id="settings-field-25"
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
          <label htmlFor="settings-field-26">{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            id="settings-field-26"
            className="input"
            value={endpointForm.name}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-27">{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            id="settings-field-27"
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
          <label htmlFor="settings-field-28">
            {t('console.settings.notificationsPane.endpointFields.url')}
            <small>{t('console.settings.notificationsPane.endpointFields.urlHint')}</small>
          </label>
          <input
            id="settings-field-28"
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
          <label htmlFor="settings-field-29">{t('console.settings.notificationsPane.endpointFields.name')}</label>
          <input
            id="settings-field-29"
            className="input"
            value={endpointForm.name}
            onChange={(event) =>
              setEndpointForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-30">{t('console.settings.notificationsPane.endpointFields.kind')}</label>
          <select
            id="settings-field-30"
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
          <label htmlFor="settings-field-31">{t('console.settings.notificationsPane.endpointFields.status')}</label>
          <select
            id="settings-field-31"
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
          <label htmlFor="settings-field-32">
            {t('console.settings.notificationsPane.endpointFields.url')}
            <small>{t('console.settings.notificationsPane.endpointFields.urlEditHint')}</small>
          </label>
          <input
            id="settings-field-32"
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
