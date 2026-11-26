import { useState } from 'react'

import { NavLink } from 'react-router'
import { toast } from 'sonner'

import { ConsoleButton, ConsoleModal, DataStateRow, StatusChip } from '../../components'
import {
  ApiKeyLimitFields,
  ApiKeyLimitsSummary,
  EMPTY_LIMITS_DRAFT,
  limitsDraftOf,
  limitsPayload,
  presentLimits,
  type ApiKeyLimitsDraft,
} from '../../components/api-key-limits'
import { ClientEndpoints } from '../../components/client-endpoints'
import { relativeTime } from '../../adapters/palette'
import { onWriteError, useMembersQuery, useSettingsIdentity } from './shared'
import { useMutation, useQuery } from '@/hooks/use-query'
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
import {
  createServicePrincipal,
  deleteServicePrincipal,
  listServicePrincipals,
  updateServicePrincipal,
  type ServicePrincipal,
  type ServicePrincipalRole,
} from '@/services/identity-service'
import { requestErrorMessage } from '@/utils/request'

/** A key unused for this long is flagged the way the prototype flagged it. */
const STALE_KEY_MS = 60 * 86_400_000

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

/** API keys, the client endpoints they reach, and the service principals that hold them. */
export function ApiPane() {
  const { t } = useTranslation()
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

  const { workspaceId } = useSettingsIdentity(false)
  const membersQuery = useMembersQuery(workspaceId)

  const keysQuery = useQuery({
    queryKey: ['console', 'settings', 'api-keys'],
    queryFn: () => listApiKeys({ page_size: 100 }),
    options: { retry: false, refetchOnWindowFocus: false },
  })
  const principalsQuery = useQuery({
    queryKey: ['console', 'settings', 'service-principals'],
    queryFn: () => listServicePrincipals({ suppressErrorToast: true }),
    options: { retry: false, refetchOnWindowFocus: false },
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

  const members = membersQuery.data || []
  const apiKeys = keysQuery.data?.items || []
  const principals = principalsQuery.data || []
  const principalName = (principalId?: string | null) =>
    principals.find((item) => item.id === principalId)?.name || principalId || ''
  const memberName = (userId: string) => {
    const member = members.find((item) => item.user_id === userId)
    return member?.name || member?.email || userId
  }

  return (
    <>
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

      <ClientEndpoints />

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
            <label htmlFor="settings-field-15">
              {t('console.settings.apiPane.fields.issuedTo')}
              <small>{t('console.settings.apiPane.fields.issuedToHint')}</small>
            </label>
            <select
              id="settings-field-15"
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
          <label htmlFor="settings-field-16">
            {t('console.settings.apiPane.fields.name')}
            <small>{t('console.settings.apiPane.fields.nameHint')}</small>
          </label>
          <input
            id="settings-field-16"
            className="input"
            value={keyForm.name}
            onChange={(event) => setKeyForm((state) => ({ ...state, name: event.target.value }))}
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-17">
            {t('console.settings.apiPane.fields.scope')}
            <small>{t('console.settings.apiPane.fields.scopeHint')}</small>
          </label>
          <select
            id="settings-field-17"
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
          <label htmlFor="settings-field-18">{t('console.settings.apiPane.fields.expires')}</label>
          <select
            id="settings-field-18"
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
          <label htmlFor="settings-field-19">
            {t('console.settings.principalsPane.fields.name')}
            <small>{t('console.settings.principalsPane.fields.nameHint')}</small>
          </label>
          <input
            id="settings-field-19"
            className="input"
            value={principalForm.name}
            onChange={(event) =>
              setPrincipalForm((state) => ({ ...state, name: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-20">{t('console.settings.principalsPane.fields.description')}</label>
          <input
            id="settings-field-20"
            className="input"
            value={principalForm.description}
            onChange={(event) =>
              setPrincipalForm((state) => ({ ...state, description: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label htmlFor="settings-field-21">
            {t('console.settings.principalsPane.fields.role')}
            <small>{t('console.settings.principalsPane.fields.roleHint')}</small>
          </label>
          <select
            id="settings-field-21"
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
          <label htmlFor="settings-field-22">{t('console.settings.apiPane.fields.name')}</label>
          <input id="settings-field-22" className="input" value={revealed?.name ?? ''} disabled />
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
    </>
  )
}
