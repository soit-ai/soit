import { useState } from 'react'

import { toast } from 'sonner'

import { ConsoleButton } from './button'
import { ConsoleModal } from './modal'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import {
  createResourceGrant,
  listWorkspaceMembers,
  listWorkspaceResourceGrants,
  revokeResourceGrant,
} from '@/services/identity-service'
import { useUserStore } from '@/stores/user'
import { requestErrorMessage } from '@/utils/request'

/** The grant resource a restricted knowledge document is opened by. */
export const KNOWLEDGE_DOCUMENT_RESOURCE = 'knowledge_document'

/**
 * Who reads one document of a knowledge base. Unrestricted, every reader of
 * the base does; restricted, only the workspace's admins, the base's creator
 * and members holding a read grant on it. Restricting takes an admin or the
 * creator, granting takes an admin; the server refuses anyone else.
 */
export function DocumentAccessModal({
  open,
  onOpenChange,
  documentLabel,
  grantResourceId,
  restricted,
  toggling,
  onToggleRestriction,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  documentLabel: string
  grantResourceId: string
  restricted: boolean
  toggling: boolean
  onToggleRestriction: () => void
}) {
  const { t } = useTranslation()
  const [member, setMember] = useState('')
  const workspaceId =
    useUserStore((state) => state.currentUser?.workspace_id) ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')

  const grantsQuery = useQuery({
    queryKey: ['console', 'knowledge', 'document-grants', grantResourceId],
    queryFn: () =>
      listWorkspaceResourceGrants({ resource_type: KNOWLEDGE_DOCUMENT_RESOURCE, resource_id: grantResourceId }),
    options: { enabled: open && restricted, retry: false, refetchOnWindowFocus: false },
  })
  const membersQuery = useQuery({
    queryKey: ['console', 'knowledge', 'members', workspaceId],
    queryFn: () => listWorkspaceMembers(workspaceId),
    options: { enabled: open && restricted && Boolean(workspaceId), retry: false, refetchOnWindowFocus: false },
  })
  const grants = (grantsQuery.data || []).filter((grant) => grant.resource_id === grantResourceId)
  const members = membersQuery.data || []
  const label = (userId: string) => {
    const found = members.find((item) => item.user_id === userId)
    return found ? `${found.name || found.email} · ${found.role}` : userId
  }
  const granted = new Set(grants.map((grant) => grant.user_id))

  const grantMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'knowledge', 'document-grant'],
    mutationFn: (userId) =>
      createResourceGrant(
        { resource_type: KNOWLEDGE_DOCUMENT_RESOURCE, resource_id: grantResourceId, user_id: userId, actions: ['read'] },
        { suppressErrorToast: true },
      ),
    onSuccess: () => {
      setMember('')
      void grantsQuery.refetch()
      toast.success(t('console.knowDetail.access.granted'))
    },
    onError: (error) => toast.error(requestErrorMessage(error, t('console.knowDetail.access.grantFailed'))),
  })
  const revokeMutation = useMutation<unknown, unknown, string>({
    mutationKey: ['console', 'knowledge', 'document-revoke'],
    mutationFn: (userId) =>
      revokeResourceGrant(KNOWLEDGE_DOCUMENT_RESOURCE, grantResourceId, userId, { suppressErrorToast: true }),
    onSuccess: () => {
      void grantsQuery.refetch()
      toast.success(t('console.knowDetail.access.revoked'))
    },
    onError: (error) => toast.error(requestErrorMessage(error, t('console.knowDetail.access.revokeFailed'))),
  })

  return (
    <ConsoleModal
      open={open}
      onOpenChange={onOpenChange}
      title={t('console.knowDetail.access.title', { document: documentLabel })}
      note={restricted ? t('console.knowDetail.access.noteRestricted') : t('console.knowDetail.access.noteOpen')}
      confirmLabel={t('console.knowDetail.access.grant')}
      confirmDisabled={!restricted || !member}
      busy={grantMutation.isPending}
      onConfirm={() => grantMutation.mutate(member)}
    >
      <div className="mrow">
        <label>{t('console.knowDetail.access.status')}</label>
        <div className="flex items-center gap-2">
          <span className={restricted ? 'chip' : 'dim'}>
            {restricted ? t('console.knowDetail.restricted') : t('console.knowDetail.access.open')}
          </span>
          <ConsoleButton size="sm" disabled={toggling} onClick={onToggleRestriction}>
            {restricted ? t('console.knowDetail.liftRestriction') : t('console.knowDetail.restrict')}
          </ConsoleButton>
        </div>
      </div>
      {restricted && (
        <>
          <div className="mrow">
            <label>{t('console.knowDetail.access.readers')}</label>
            <div>
              {grants.length === 0 ? (
                <span className="dimmer">{t('console.knowDetail.access.none')}</span>
              ) : (
                grants.map((grant) => (
                  <div key={grant.user_id} className="flex items-center gap-2" style={{ marginBottom: 4 }}>
                    <span className="mono" style={{ overflowWrap: 'anywhere' }}>
                      {label(grant.user_id)}
                    </span>
                    <ConsoleButton
                      variant="ghost"
                      size="sm"
                      disabled={revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate(grant.user_id)}
                    >
                      {t('console.knowDetail.access.revoke')}
                    </ConsoleButton>
                  </div>
                ))
              )}
            </div>
          </div>
          <div className="mrow">
            <label htmlFor="document-access-member">{t('console.knowDetail.access.member')}</label>
            <select
              id="document-access-member"
              className="input"
              value={member}
              onChange={(event) => setMember(event.target.value)}
            >
              <option value="">{t('console.knowDetail.access.memberPlaceholder')}</option>
              {members
                .filter((item) => !granted.has(item.user_id))
                .map((item) => (
                  <option key={item.user_id} value={item.user_id}>
                    {item.name || item.email} · {item.role}
                  </option>
                ))}
            </select>
          </div>
        </>
      )}
    </ConsoleModal>
  )
}
