import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from 'sonner'
import { getWorkflow, updateWorkflow, deleteWorkflow } from '@/services/workflow-service'
import { useNavigate } from '@/hooks/use-navigate'
import {
  createResourceGrant,
  getCurrentUser,
  listResourceGrants,
  revokeResourceGrant,
  type ResourceGrant,
} from '@/services/identity-service'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import type { TranslationKey } from '@/i18n/types'

type AccessSettings = {
  visibility: string
}

const defaultAccess: AccessSettings = {
  visibility: 'private',
}

const grantActionOptions = ['read', 'run', 'update', 'delete']

function Page() {
  const { t } = useTranslation()
  const { id: workflowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [hydratedWorkflowId, setHydratedWorkflowId] = useState<string | null>(null)
  const [savingBasic, setSavingBasic] = useState(false)
  const [savingAccess, setSavingAccess] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [deleteDialogTargetId, setDeleteDialogTargetId] = useState<string | null>(null)
  const [savingGrant, setSavingGrant] = useState(false)
  const [loadingGrants, setLoadingGrants] = useState(false)
  const [permissionsHydratedWorkflowId, setPermissionsHydratedWorkflowId] = useState<string | null>(null)
  const [permissionsLoadErrorWorkflowId, setPermissionsLoadErrorWorkflowId] = useState<string | null>(null)
  const [currentRole, setCurrentRole] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
  })
  const [access, setAccess] = useState<AccessSettings>(defaultAccess)
  const [grants, setGrants] = useState<ResourceGrant[]>([])
  const [grantUserId, setGrantUserId] = useState('')
  const [grantActions, setGrantActions] = useState<string[]>(['read'])
  const workflowRequestSequenceRef = useRef(0)
  const basicSaveSequenceRef = useRef(0)
  const accessSaveSequenceRef = useRef(0)
  const deleteSequenceRef = useRef(0)
  const permissionsRequestSequenceRef = useRef(0)
  const permissionsMutationSequenceRef = useRef(0)
  const permissionsHydratedWorkflowIdRef = useRef<string | null>(null)
  const loadingGrantsRef = useRef(false)
  const savingGrantRef = useRef(false)
  const deletingRef = useRef(false)
  const mountedRef = useRef(false)
  const currentWorkflowIdRef = useRef(workflowId)
  currentWorkflowIdRef.current = workflowId
  const settingsHydrated = Boolean(workflowId && hydratedWorkflowId === workflowId)
  const permissionsHydrated = Boolean(
    workflowId && permissionsHydratedWorkflowId === workflowId,
  )
  const permissionsLoadFailed = Boolean(
    workflowId && permissionsLoadErrorWorkflowId === workflowId,
  )
  const deleteDialogOpen = Boolean(
    workflowId && deleteDialogTargetId === workflowId,
  )

  const setPermissionsHydration = (targetWorkflowId: string | null) => {
    permissionsHydratedWorkflowIdRef.current = targetWorkflowId
    setPermissionsHydratedWorkflowId(targetWorkflowId)
  }

  const setPermissionsLoading = (nextLoading: boolean) => {
    loadingGrantsRef.current = nextLoading
    setLoadingGrants(nextLoading)
  }

  const setGrantSaving = (nextSaving: boolean) => {
    savingGrantRef.current = nextSaving
    setSavingGrant(nextSaving)
  }

  const setDeletePending = (nextDeleting: boolean) => {
    deletingRef.current = nextDeleting
    setDeleting(nextDeleting)
  }

  const isCurrentPermissionsState = (targetWorkflowId: string) => {
    return mountedRef.current
      && currentWorkflowIdRef.current === targetWorkflowId
      && permissionsHydratedWorkflowIdRef.current === targetWorkflowId
      && !loadingGrantsRef.current
  }

  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      basicSaveSequenceRef.current += 1
      accessSaveSequenceRef.current += 1
      deleteSequenceRef.current += 1
      permissionsRequestSequenceRef.current += 1
      permissionsMutationSequenceRef.current += 1
    }
  }, [])

  useEffect(() => {
    const requestSequence = ++workflowRequestSequenceRef.current
    let active = true

    const fetchWorkflow = async () => {
      setHydratedWorkflowId(null)
      setForm({ name: '', description: '' })
      setAccess(defaultAccess)
      setSavingBasic(false)
      setSavingAccess(false)
      setDeletePending(false)
      setDeleteDialogTargetId(null)
      basicSaveSequenceRef.current += 1
      accessSaveSequenceRef.current += 1
      deleteSequenceRef.current += 1
      if (!workflowId) {
        setLoading(false)
        return
      }
      try {
        setLoading(true)
        const data = await getWorkflow(workflowId, { suppressErrorToast: true })
        if (!active || requestSequence !== workflowRequestSequenceRef.current) return
        setForm({
          name: data.name || '',
          description: data.description || '',
        })
        setAccess({ visibility: data.visibility || defaultAccess.visibility })
        setHydratedWorkflowId(workflowId)
      } catch (error) {
        if (!active || requestSequence !== workflowRequestSequenceRef.current) return
        setHydratedWorkflowId(null)
        toast.error(t('workflow.detail.setting.toast.fetchError'))
        console.error('Failed to fetch workflow settings:', error)
      } finally {
        if (active && requestSequence === workflowRequestSequenceRef.current) {
          setLoading(false)
        }
      }
    }
    fetchWorkflow()
    return () => {
      active = false
      if (requestSequence === workflowRequestSequenceRef.current) {
        workflowRequestSequenceRef.current += 1
      }
    }
  }, [workflowId, t])

  useEffect(() => {
    const requestSequence = ++permissionsRequestSequenceRef.current
    permissionsMutationSequenceRef.current += 1
    let active = true

    const fetchPermissions = async () => {
      setPermissionsHydration(null)
      setPermissionsLoadErrorWorkflowId(null)
      setGrants([])
      setCurrentRole(null)
      setGrantUserId('')
      setGrantActions(['read'])
      setGrantSaving(false)
      setPermissionsLoading(Boolean(workflowId))
      if (!workflowId) return
      try {
        const [user, grantList] = await Promise.all([
          getCurrentUser({ suppressErrorToast: true }),
          listResourceGrants('workflow', workflowId, { suppressErrorToast: true }),
        ])
        if (
          !active
          || !mountedRef.current
          || requestSequence !== permissionsRequestSequenceRef.current
          || currentWorkflowIdRef.current !== workflowId
        ) return
        setCurrentRole(user.workspace_role || user.tenant_role || null)
        setGrants(grantList || [])
        setPermissionsHydration(workflowId)
      } catch (error) {
        if (
          !active
          || !mountedRef.current
          || requestSequence !== permissionsRequestSequenceRef.current
          || currentWorkflowIdRef.current !== workflowId
        ) return
        setPermissionsLoadErrorWorkflowId(workflowId)
        toast.error(t('workflow.detail.setting.permissions.toast.loadFailed'))
        console.error('Failed to fetch workflow permissions:', error)
      } finally {
        if (
          active
          && mountedRef.current
          && requestSequence === permissionsRequestSequenceRef.current
          && currentWorkflowIdRef.current === workflowId
        ) {
          setPermissionsLoading(false)
        }
      }
    }
    fetchPermissions()
    return () => {
      active = false
      if (requestSequence === permissionsRequestSequenceRef.current) {
        permissionsRequestSequenceRef.current += 1
      }
      permissionsMutationSequenceRef.current += 1
    }
  }, [workflowId, t])

  const handleSaveBasic = async () => {
    if (!workflowId || hydratedWorkflowId !== workflowId || loading || savingBasic) return
    if (!form.name.trim()) {
      toast.error(t('workflow.detail.setting.toast.nameRequired'))
      return
    }
    const targetWorkflowId = workflowId
    const saveSequence = ++basicSaveSequenceRef.current
    try {
      setSavingBasic(true)
      const updated = await updateWorkflow(targetWorkflowId, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      }, { suppressErrorToast: true })
      if (
        !mountedRef.current
        || saveSequence !== basicSaveSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      setForm({
        name: updated.name || '',
        description: updated.description || '',
      })
      toast.success(t('workflow.detail.setting.toast.saveSuccess'))
    } catch (error) {
      if (
        !mountedRef.current
        || saveSequence !== basicSaveSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      toast.error(t('workflow.detail.setting.toast.saveError'))
      console.error('Failed to update workflow:', error)
    } finally {
      if (
        mountedRef.current
        && saveSequence === basicSaveSequenceRef.current
        && currentWorkflowIdRef.current === targetWorkflowId
      ) {
        setSavingBasic(false)
      }
    }
  }

  const handleSaveAccess = async () => {
    if (!workflowId || hydratedWorkflowId !== workflowId || loading || savingAccess) return
    const targetWorkflowId = workflowId
    const saveSequence = ++accessSaveSequenceRef.current
    try {
      setSavingAccess(true)
      const updated = await updateWorkflow(
        targetWorkflowId,
        { visibility: access.visibility },
        { suppressErrorToast: true },
      )
      if (
        !mountedRef.current
        || saveSequence !== accessSaveSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      setAccess({ visibility: updated.visibility || defaultAccess.visibility })
      toast.success(t('workflow.detail.setting.toast.accessSaved'))
    } catch (error) {
      if (
        !mountedRef.current
        || saveSequence !== accessSaveSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      toast.error(t('workflow.detail.setting.toast.accessSaveError'))
      console.error('Failed to save access settings:', error)
    } finally {
      if (
        mountedRef.current
        && saveSequence === accessSaveSequenceRef.current
        && currentWorkflowIdRef.current === targetWorkflowId
      ) {
        setSavingAccess(false)
      }
    }
  }

  const handleGrantActionToggle = (action: string, checked: boolean | string) => {
    if (!workflowId || !isCurrentPermissionsState(workflowId) || savingGrantRef.current) return
    const resolved = checked === true
    setGrantActions((prev) => {
      if (resolved) {
        return prev.includes(action) ? prev : [...prev, action]
      }
      return prev.filter((item) => item !== action)
    })
  }

  const handleCreateGrant = async () => {
    if (
      !workflowId
      || !isCurrentPermissionsState(workflowId)
      || savingGrantRef.current
    ) return
    if (!grantUserId.trim()) {
      toast.error(t('workflow.detail.setting.permissions.toast.userRequired'))
      return
    }
    if (grantActions.length === 0) {
      toast.error(t('workflow.detail.setting.permissions.toast.actionsRequired'))
      return
    }
    const targetWorkflowId = workflowId
    const mutationSequence = ++permissionsMutationSequenceRef.current
    try {
      setGrantSaving(true)
      const grant = await createResourceGrant({
        resource_type: 'workflow',
        resource_id: targetWorkflowId,
        user_id: grantUserId.trim(),
        actions: grantActions,
      }, { suppressErrorToast: true })
      if (
        mutationSequence !== permissionsMutationSequenceRef.current
        || !isCurrentPermissionsState(targetWorkflowId)
      ) return
      setGrants((prev) => {
        const filtered = prev.filter((item) => item.user_id !== grant.user_id)
        return [grant, ...filtered]
      })
      setGrantUserId('')
      toast.success(t('workflow.detail.setting.permissions.toast.grantSaved'))
    } catch (error) {
      if (
        mutationSequence !== permissionsMutationSequenceRef.current
        || !isCurrentPermissionsState(targetWorkflowId)
      ) return
      toast.error(t('workflow.detail.setting.permissions.toast.grantFailed'))
      console.error('Failed to save resource grant:', error)
    } finally {
      if (
        mutationSequence === permissionsMutationSequenceRef.current
        && isCurrentPermissionsState(targetWorkflowId)
      ) {
        setGrantSaving(false)
      }
    }
  }

  const handleRevokeGrant = async (userId: string) => {
    if (
      !workflowId
      || !isCurrentPermissionsState(workflowId)
      || savingGrantRef.current
    ) return
    const targetWorkflowId = workflowId
    const mutationSequence = ++permissionsMutationSequenceRef.current
    try {
      setGrantSaving(true)
      await revokeResourceGrant(
        'workflow',
        targetWorkflowId,
        userId,
        { suppressErrorToast: true },
      )
      if (
        mutationSequence !== permissionsMutationSequenceRef.current
        || !isCurrentPermissionsState(targetWorkflowId)
      ) return
      setGrants((prev) => prev.filter((item) => item.user_id !== userId))
      toast.success(t('workflow.detail.setting.permissions.toast.grantRevoked'))
    } catch (error) {
      if (
        mutationSequence !== permissionsMutationSequenceRef.current
        || !isCurrentPermissionsState(targetWorkflowId)
      ) return
      toast.error(t('workflow.detail.setting.permissions.toast.grantRevokeFailed'))
      console.error('Failed to revoke resource grant:', error)
    } finally {
      if (
        mutationSequence === permissionsMutationSequenceRef.current
        && isCurrentPermissionsState(targetWorkflowId)
      ) {
        setGrantSaving(false)
      }
    }
  }

  const handleDelete = async () => {
    const targetWorkflowId = deleteDialogTargetId
    if (
      !mountedRef.current
      || !workflowId
      || !targetWorkflowId
      || targetWorkflowId !== workflowId
      || currentWorkflowIdRef.current !== targetWorkflowId
      || hydratedWorkflowId !== targetWorkflowId
      || loading
      || deletingRef.current
    ) return
    const deleteSequence = ++deleteSequenceRef.current
    setDeleteDialogTargetId(null)
    try {
      setDeletePending(true)
      await deleteWorkflow(targetWorkflowId, { suppressErrorToast: true })
      if (
        !mountedRef.current
        || deleteSequence !== deleteSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      toast.success(t('workflow.detail.setting.toast.deleteSuccess'))
      navigate('/workflow')
    } catch (error) {
      if (
        !mountedRef.current
        || deleteSequence !== deleteSequenceRef.current
        || currentWorkflowIdRef.current !== targetWorkflowId
      ) return
      toast.error(t('workflow.detail.setting.toast.deleteError'))
      console.error('Failed to delete workflow:', error)
    } finally {
      if (
        mountedRef.current
        && deleteSequence === deleteSequenceRef.current
        && currentWorkflowIdRef.current === targetWorkflowId
      ) {
        setDeletePending(false)
      }
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.setting.basic.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.basic.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2">
            <Label htmlFor="workflow-name">{t('workflow.detail.setting.basic.nameLabel')}</Label>
            <Input
              id="workflow-name"
              value={settingsHydrated ? form.name : ''}
              onChange={(event) => {
                if (!settingsHydrated || savingBasic) return
                setForm((prev) => ({ ...prev, name: event.target.value }))
              }}
              disabled={loading || !settingsHydrated || savingBasic}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="workflow-description">{t('workflow.detail.setting.basic.descriptionLabel')}</Label>
            <Textarea
              id="workflow-description"
              value={settingsHydrated ? form.description : ''}
              onChange={(event) => {
                if (!settingsHydrated || savingBasic) return
                setForm((prev) => ({ ...prev, description: event.target.value }))
              }}
              disabled={loading || !settingsHydrated || savingBasic}
            />
          </div>
          <Button onClick={handleSaveBasic} disabled={savingBasic || loading || !settingsHydrated}>
            {savingBasic ? t('workflow.detail.setting.basic.saving') : t('workflow.detail.setting.basic.save')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.setting.execution.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.execution.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <Button variant="outline" nativeButton={false} render={<Link to={`/workflow/${workflowId}/build`} />}>
            {t('workflow.detail.setting.execution.builderLink')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.setting.access.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.access.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-2 max-w-sm">
            <Label>{t('workflow.detail.setting.access.visibilityLabel')}</Label>
            <Select
              value={settingsHydrated ? access.visibility : defaultAccess.visibility}
              disabled={loading || !settingsHydrated || savingAccess}
              onValueChange={(value) => {
                if (!settingsHydrated || savingAccess) return
                setAccess((prev) => ({ ...prev, visibility: value ?? prev.visibility }))
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder={t('workflow.detail.setting.access.visibilityPlaceholder')} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="private">{t('workflow.detail.setting.access.visibilityOptions.private')}</SelectItem>
                <SelectItem value="workspace">{t('workflow.detail.setting.access.visibilityOptions.workspace')}</SelectItem>
                <SelectItem value="tenant">{t('workflow.detail.setting.access.visibilityOptions.tenant')}</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={handleSaveAccess}
            disabled={loading || !settingsHydrated || savingAccess}
          >
            {savingAccess ? t('workflow.detail.setting.access.saving') : t('workflow.detail.setting.access.save')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.setting.permissions.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.permissions.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="text-sm text-muted-foreground">
            {t('workflow.detail.setting.permissions.currentRole', {
              role: permissionsHydrated ? currentRole || '-' : '-',
            })}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.setting.permissions.shareTitle')}</div>
              <div className="grid gap-2">
                <Label htmlFor="workflow-grant-user">{t('workflow.detail.setting.permissions.userLabel')}</Label>
                <Input
                  id="workflow-grant-user"
                  value={permissionsHydrated ? grantUserId : ''}
                  onChange={(event) => {
                    if (!permissionsHydrated || savingGrant) return
                    setGrantUserId(event.target.value)
                  }}
                  placeholder={t('workflow.detail.setting.permissions.userPlaceholder')}
                  disabled={loadingGrants || !permissionsHydrated || savingGrant}
                />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">{t('workflow.detail.setting.permissions.actionsLabel')}</div>
                <div className="flex flex-wrap gap-3">
                  {grantActionOptions.map((action) => (
                    <label key={action} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={permissionsHydrated && grantActions.includes(action)}
                        onCheckedChange={(checked) => handleGrantActionToggle(action, checked)}
                        disabled={loadingGrants || !permissionsHydrated || savingGrant}
                      />
                      <span>{t(`workflow.detail.setting.permissions.actions.${action}` as TranslationKey)}</span>
                    </label>
                  ))}
                </div>
              </div>
              <Button
                onClick={handleCreateGrant}
                disabled={loadingGrants || !permissionsHydrated || savingGrant}
              >
                {savingGrant
                  ? t('workflow.detail.setting.permissions.saving')
                  : t('workflow.detail.setting.permissions.save')}
              </Button>
            </div>
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.setting.permissions.listTitle')}</div>
              {loadingGrants ? (
                <div className="text-sm text-muted-foreground">{t('workflow.detail.setting.permissions.loading')}</div>
              ) : permissionsLoadFailed ? (
                <div role="alert" className="text-sm text-destructive">
                  {t('workflow.detail.setting.permissions.toast.loadFailed')}
                </div>
              ) : !permissionsHydrated || grants.length === 0 ? (
                <div className="text-sm text-muted-foreground">{t('workflow.detail.setting.permissions.empty')}</div>
              ) : (
                <div className="space-y-2">
                  {grants.map((grant) => (
                    <div key={grant.id} className="rounded-md border p-3 flex flex-col gap-2">
                      <div className="text-sm font-medium">{grant.user_id}</div>
                      <div className="text-xs text-muted-foreground">
                        {t('workflow.detail.setting.permissions.actionsValue', { actions: (grant.actions || []).join(', ') || '-' })}
                      </div>
                      <Button
                        variant="ghost"
                        onClick={() => handleRevokeGrant(grant.user_id)}
                        disabled={loadingGrants || !permissionsHydrated || savingGrant}
                      >
                        {t('workflow.detail.setting.permissions.revoke')}
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="text-destructive">{t('workflow.detail.setting.danger.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.danger.description')}</CardDescription>
        </CardHeader>
        <CardContent>
          <AlertDialog
            open={deleteDialogOpen}
            onOpenChange={(open) => {
              if (!open) {
                setDeleteDialogTargetId(null)
                return
              }
              if (
                mountedRef.current
                && workflowId
                && hydratedWorkflowId === workflowId
                && !loading
                && !deletingRef.current
              ) {
                setDeleteDialogTargetId(workflowId)
              }
            }}
          >
            <AlertDialogTrigger render={<Button
                variant="destructive"
                disabled={deleting || loading || !settingsHydrated}
              >
                {deleting ? t('workflow.detail.setting.danger.deleting') : t('workflow.detail.setting.danger.delete')}
              </Button>} />
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>{t('workflow.detail.setting.danger.confirmTitle')}</AlertDialogTitle>
                <AlertDialogDescription>
                  {t('workflow.detail.setting.danger.confirmDescription')}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>{t('workflow.detail.setting.danger.cancel')}</AlertDialogCancel>
                <AlertDialogAction
                  onClick={handleDelete}
                  className="bg-destructive text-destructive-foreground"
                >
                  {t('workflow.detail.setting.danger.confirm')}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
