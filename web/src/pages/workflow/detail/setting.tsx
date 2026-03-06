import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { useTranslation } from '@/i18n'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Switch } from '@/components/ui/switch'
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from 'sonner'
import { getWorkflow, updateWorkflow, deleteWorkflow } from '@/services/workflow'
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

type LimitSettings = {
  timeoutSeconds: number
  maxSteps: number
  maxRetries: number
}

type AccessSettings = {
  visibility: string
  allowAnonymous: boolean
}

type WorkflowMetadata = {
  limits?: {
    timeout_seconds?: number
    max_steps?: number
    max_retries?: number
  }
  access?: {
    visibility?: string
    allow_anonymous?: boolean
  }
  [key: string]: any
}

const defaultLimits: LimitSettings = {
  timeoutSeconds: 300,
  maxSteps: 60,
  maxRetries: 0,
}

const defaultAccess: AccessSettings = {
  visibility: 'workspace',
  allowAnonymous: false,
}

const grantActionOptions = ['read', 'run', 'update', 'delete']

function Page() {
  const { t } = useTranslation()
  const { id: workflowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [savingBasic, setSavingBasic] = useState(false)
  const [savingLimits, setSavingLimits] = useState(false)
  const [savingAccess, setSavingAccess] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [savingGrant, setSavingGrant] = useState(false)
  const [loadingGrants, setLoadingGrants] = useState(false)
  const [currentRole, setCurrentRole] = useState<string | null>(null)
  const [form, setForm] = useState({
    name: '',
    description: '',
  })
  const [limits, setLimits] = useState<LimitSettings>(defaultLimits)
  const [access, setAccess] = useState<AccessSettings>(defaultAccess)
  const [metadata, setMetadata] = useState<WorkflowMetadata>({})
  const [grants, setGrants] = useState<ResourceGrant[]>([])
  const [grantUserId, setGrantUserId] = useState('')
  const [grantActions, setGrantActions] = useState<string[]>(['read'])

  const applyMetadata = (meta?: WorkflowMetadata | null) => {
    const normalized: WorkflowMetadata = meta && typeof meta === 'object' ? meta : {}
    setMetadata(normalized)
    const limitsMeta = normalized.limits || {}
    setLimits({
      timeoutSeconds: Number(
        limitsMeta.timeout_seconds ?? (limitsMeta as any).timeoutSeconds ?? defaultLimits.timeoutSeconds
      ),
      maxSteps: Number(limitsMeta.max_steps ?? (limitsMeta as any).maxSteps ?? defaultLimits.maxSteps),
      maxRetries: Number(limitsMeta.max_retries ?? (limitsMeta as any).maxRetries ?? defaultLimits.maxRetries),
    })
    const accessMeta = normalized.access || {}
    setAccess({
      visibility: accessMeta.visibility ?? (accessMeta as any).visibility ?? defaultAccess.visibility,
      allowAnonymous: Boolean(
        accessMeta.allow_anonymous ?? (accessMeta as any).allowAnonymous ?? defaultAccess.allowAnonymous
      ),
    })
  }

  useEffect(() => {
    const fetchWorkflow = async () => {
      if (!workflowId) return
      try {
        setLoading(true)
        const data = await getWorkflow(workflowId)
        setForm({
          name: data.name || '',
          description: data.description || '',
        })
        applyMetadata(data.metadata_json || {})
      } catch (error) {
        toast.error(t('workflow.detail.setting.toast.fetchError'))
        console.error('Failed to fetch workflow settings:', error)
      } finally {
        setLoading(false)
      }
    }
    fetchWorkflow()
  }, [workflowId, t])

  useEffect(() => {
    const fetchPermissions = async () => {
      if (!workflowId) return
      try {
        setLoadingGrants(true)
        const [user, grantList] = await Promise.all([
          getCurrentUser(),
          listResourceGrants('workflow', workflowId),
        ])
        setCurrentRole(user.workspace_role || user.tenant_role || null)
        setGrants(grantList || [])
      } catch (error) {
        console.error('Failed to fetch workflow permissions:', error)
      } finally {
        setLoadingGrants(false)
      }
    }
    fetchPermissions()
  }, [workflowId])

  const handleSaveBasic = async () => {
    if (!workflowId) return
    if (!form.name.trim()) {
      toast.error(t('workflow.detail.setting.toast.nameRequired'))
      return
    }
    try {
      setSavingBasic(true)
      const updated = await updateWorkflow(workflowId, {
        name: form.name.trim(),
        description: form.description.trim() || undefined,
      })
      setForm({
        name: updated.name || '',
        description: updated.description || '',
      })
      applyMetadata(updated.metadata_json || {})
      toast.success(t('workflow.detail.setting.toast.saveSuccess'))
    } catch (error) {
      toast.error(t('workflow.detail.setting.toast.saveError'))
      console.error('Failed to update workflow:', error)
    } finally {
      setSavingBasic(false)
    }
  }

  const handleSaveLimits = async () => {
    if (!workflowId) return
    try {
      setSavingLimits(true)
      const nextMetadata: WorkflowMetadata = {
        ...metadata,
        limits: {
          timeout_seconds: limits.timeoutSeconds,
          max_steps: limits.maxSteps,
          max_retries: limits.maxRetries,
        },
        access: {
          visibility: access.visibility,
          allow_anonymous: access.allowAnonymous,
        },
      }
      const updated = await updateWorkflow(workflowId, { metadata_json: nextMetadata })
      applyMetadata(updated.metadata_json || nextMetadata)
      toast.success(t('workflow.detail.setting.toast.limitsSaved'))
    } catch (error) {
      toast.error(t('workflow.detail.setting.toast.limitsSaveError'))
      console.error('Failed to save limits:', error)
    } finally {
      setSavingLimits(false)
    }
  }

  const handleResetLimits = () => {
    setLimits(defaultLimits)
  }

  const handleSaveAccess = async () => {
    if (!workflowId) return
    try {
      setSavingAccess(true)
      const nextMetadata: WorkflowMetadata = {
        ...metadata,
        limits: {
          timeout_seconds: limits.timeoutSeconds,
          max_steps: limits.maxSteps,
          max_retries: limits.maxRetries,
        },
        access: {
          visibility: access.visibility,
          allow_anonymous: access.allowAnonymous,
        },
      }
      const updated = await updateWorkflow(workflowId, { metadata_json: nextMetadata })
      applyMetadata(updated.metadata_json || nextMetadata)
      toast.success(t('workflow.detail.setting.toast.accessSaved'))
    } catch (error) {
      toast.error(t('workflow.detail.setting.toast.accessSaveError'))
      console.error('Failed to save access settings:', error)
    } finally {
      setSavingAccess(false)
    }
  }

  const handleGrantActionToggle = (action: string, checked: boolean | string) => {
    const resolved = checked === true
    setGrantActions((prev) => {
      if (resolved) {
        return prev.includes(action) ? prev : [...prev, action]
      }
      return prev.filter((item) => item !== action)
    })
  }

  const handleCreateGrant = async () => {
    if (!workflowId) return
    if (!grantUserId.trim()) {
      toast.error(t('workflow.detail.setting.permissions.toast.userRequired'))
      return
    }
    if (grantActions.length === 0) {
      toast.error(t('workflow.detail.setting.permissions.toast.actionsRequired'))
      return
    }
    try {
      setSavingGrant(true)
      const grant = await createResourceGrant({
        resource_type: 'workflow',
        resource_id: workflowId,
        user_id: grantUserId.trim(),
        actions: grantActions,
      })
      setGrants((prev) => {
        const filtered = prev.filter((item) => item.user_id !== grant.user_id)
        return [grant, ...filtered]
      })
      setGrantUserId('')
      toast.success(t('workflow.detail.setting.permissions.toast.grantSaved'))
    } catch (error) {
      toast.error(t('workflow.detail.setting.permissions.toast.grantFailed'))
      console.error('Failed to save resource grant:', error)
    } finally {
      setSavingGrant(false)
    }
  }

  const handleRevokeGrant = async (userId: string) => {
    if (!workflowId) return
    try {
      await revokeResourceGrant('workflow', workflowId, userId)
      setGrants((prev) => prev.filter((item) => item.user_id !== userId))
      toast.success(t('workflow.detail.setting.permissions.toast.grantRevoked'))
    } catch (error) {
      toast.error(t('workflow.detail.setting.permissions.toast.grantRevokeFailed'))
      console.error('Failed to revoke resource grant:', error)
    }
  }

  const handleDelete = async () => {
    if (!workflowId) return
    try {
      setDeleting(true)
      await deleteWorkflow(workflowId)
      toast.success(t('workflow.detail.setting.toast.deleteSuccess'))
      navigate('/workflow')
    } catch (error) {
      toast.error(t('workflow.detail.setting.toast.deleteError'))
      console.error('Failed to delete workflow:', error)
    } finally {
      setDeleting(false)
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
              value={form.name}
              onChange={(event) => setForm((prev) => ({ ...prev, name: event.target.value }))}
              disabled={loading}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="workflow-description">{t('workflow.detail.setting.basic.descriptionLabel')}</Label>
            <Textarea
              id="workflow-description"
              value={form.description}
              onChange={(event) => setForm((prev) => ({ ...prev, description: event.target.value }))}
              disabled={loading}
            />
          </div>
          <Button onClick={handleSaveBasic} disabled={savingBasic || loading}>
            {savingBasic ? t('workflow.detail.setting.basic.saving') : t('workflow.detail.setting.basic.save')}
          </Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.setting.limits.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.setting.limits.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="grid gap-2">
              <Label htmlFor="workflow-timeout">{t('workflow.detail.setting.limits.timeoutLabel')}</Label>
              <Input
                id="workflow-timeout"
                type="number"
                min={10}
                value={limits.timeoutSeconds}
                onChange={(event) => setLimits((prev) => ({ ...prev, timeoutSeconds: Number(event.target.value || 0) }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-max-steps">{t('workflow.detail.setting.limits.maxStepsLabel')}</Label>
              <Input
                id="workflow-max-steps"
                type="number"
                min={1}
                value={limits.maxSteps}
                onChange={(event) => setLimits((prev) => ({ ...prev, maxSteps: Number(event.target.value || 0) }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="workflow-max-retries">{t('workflow.detail.setting.limits.maxRetriesLabel')}</Label>
              <Input
                id="workflow-max-retries"
                type="number"
                min={0}
                value={limits.maxRetries}
                onChange={(event) => setLimits((prev) => ({ ...prev, maxRetries: Number(event.target.value || 0) }))}
              />
            </div>
          </div>
          <div className="text-xs text-muted-foreground">
            {t('workflow.detail.setting.limits.localNotice')}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={handleSaveLimits} disabled={savingLimits}>
              {savingLimits ? t('workflow.detail.setting.limits.saving') : t('workflow.detail.setting.limits.save')}
            </Button>
            <Button variant="outline" onClick={handleResetLimits} disabled={savingLimits}>
              {t('workflow.detail.setting.limits.reset')}
            </Button>
          </div>
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
              value={access.visibility}
              onValueChange={(value) => setAccess((prev) => ({ ...prev, visibility: value }))}
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
          <div className="flex items-center justify-between rounded-md border p-3">
            <div>
              <div className="text-sm font-medium">{t('workflow.detail.setting.access.anonymousLabel')}</div>
              <div className="text-xs text-muted-foreground">{t('workflow.detail.setting.access.anonymousHint')}</div>
            </div>
            <Switch
              checked={access.allowAnonymous}
              onCheckedChange={(checked) => setAccess((prev) => ({ ...prev, allowAnonymous: checked }))}
            />
          </div>
          <Button onClick={handleSaveAccess} disabled={savingAccess}>
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
            {t('workflow.detail.setting.permissions.currentRole', { role: currentRole || '-' })}
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.setting.permissions.shareTitle')}</div>
              <div className="grid gap-2">
                <Label htmlFor="workflow-grant-user">{t('workflow.detail.setting.permissions.userLabel')}</Label>
                <Input
                  id="workflow-grant-user"
                  value={grantUserId}
                  onChange={(event) => setGrantUserId(event.target.value)}
                  placeholder={t('workflow.detail.setting.permissions.userPlaceholder')}
                />
              </div>
              <div className="space-y-2">
                <div className="text-xs text-muted-foreground">{t('workflow.detail.setting.permissions.actionsLabel')}</div>
                <div className="flex flex-wrap gap-3">
                  {grantActionOptions.map((action) => (
                    <label key={action} className="flex items-center gap-2 text-sm">
                      <Checkbox
                        checked={grantActions.includes(action)}
                        onCheckedChange={(checked) => handleGrantActionToggle(action, checked)}
                      />
                      <span>{t(`workflow.detail.setting.permissions.actions.${action}`)}</span>
                    </label>
                  ))}
                </div>
              </div>
              <Button onClick={handleCreateGrant} disabled={savingGrant}>
                {savingGrant
                  ? t('workflow.detail.setting.permissions.saving')
                  : t('workflow.detail.setting.permissions.save')}
              </Button>
            </div>
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.setting.permissions.listTitle')}</div>
              {loadingGrants ? (
                <div className="text-sm text-muted-foreground">{t('workflow.detail.setting.permissions.loading')}</div>
              ) : grants.length === 0 ? (
                <div className="text-sm text-muted-foreground">{t('workflow.detail.setting.permissions.empty')}</div>
              ) : (
                <div className="space-y-2">
                  {grants.map((grant) => (
                    <div key={grant.id} className="rounded-md border p-3 flex flex-col gap-2">
                      <div className="text-sm font-medium">{grant.user_id}</div>
                      <div className="text-xs text-muted-foreground">
                        {t('workflow.detail.setting.permissions.actionsValue', { actions: (grant.actions || []).join(', ') || '-' })}
                      </div>
                      <Button variant="ghost" onClick={() => handleRevokeGrant(grant.user_id)}>
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
          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive" disabled={deleting || loading}>
                {deleting ? t('workflow.detail.setting.danger.deleting') : t('workflow.detail.setting.danger.delete')}
              </Button>
            </AlertDialogTrigger>
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
