import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Checkbox } from '@/components/ui/checkbox'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { useTranslation } from '@/i18n'
import { toast } from 'sonner'
import { storage } from '@/utils/storage'
import {
  getWorkflow,
  createWorkflowVersion,
  exportWorkflowDsl,
  listWorkflowReleases,
  listWorkflowVersions,
  publishWorkflowVersion,
  type WorkflowRelease,
  type WorkflowVersion,
} from '@/services/workflow-service'
import { listRuns, type RunResponse } from '@/services/run-service'
import { useNavigate } from '@/hooks/use-navigate'
import type { TranslationKey } from '@/i18n/types'

type ChecklistItem = {
  key: string
  labelKey: string
  group: 'acceptance' | 'release'
}

type ChecklistState = Record<string, boolean>

const checklistItems: ChecklistItem[] = [
  { key: 'acceptance_end_to_end', labelKey: 'workflow.detail.publish.checklist.acceptance.endToEnd', group: 'acceptance' },
  { key: 'acceptance_tests', labelKey: 'workflow.detail.publish.checklist.acceptance.tests', group: 'acceptance' },
  { key: 'acceptance_observe', labelKey: 'workflow.detail.publish.checklist.acceptance.observe', group: 'acceptance' },
  { key: 'acceptance_docs', labelKey: 'workflow.detail.publish.checklist.acceptance.docs', group: 'acceptance' },
  { key: 'release_migrations', labelKey: 'workflow.detail.publish.checklist.release.migrations', group: 'release' },
  { key: 'release_env', labelKey: 'workflow.detail.publish.checklist.release.env', group: 'release' },
  { key: 'release_compose', labelKey: 'workflow.detail.publish.checklist.release.compose', group: 'release' },
  { key: 'release_docs', labelKey: 'workflow.detail.publish.checklist.release.apiDocs', group: 'release' },
  { key: 'release_ui', labelKey: 'workflow.detail.publish.checklist.release.ui', group: 'release' },
  { key: 'release_security', labelKey: 'workflow.detail.publish.checklist.release.security', group: 'release' },
  { key: 'release_changelog', labelKey: 'workflow.detail.publish.checklist.release.changelog', group: 'release' },
]

const buildChecklistState = (items: ChecklistItem[]): ChecklistState =>
  items.reduce<ChecklistState>((acc, item) => {
    acc[item.key] = false
    return acc
  }, {})

function Page() {
  const { t } = useTranslation()
  const { id: workflowId } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const [workflowName, setWorkflowName] = useState('')
  const [workflowDescription, setWorkflowDescription] = useState('')
  const [currentVersionId, setCurrentVersionId] = useState<string | null>(null)
  const [updatedAt, setUpdatedAt] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [publishing, setPublishing] = useState(false)
  const [publishingVersionId, setPublishingVersionId] = useState<string | null>(null)
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [versions, setVersions] = useState<WorkflowVersion[]>([])
  const [releases, setReleases] = useState<WorkflowRelease[]>([])
  const [versionsLoading, setVersionsLoading] = useState(false)
  const [releasesLoading, setReleasesLoading] = useState(false)
  const [checklistState, setChecklistState] = useState<ChecklistState>(() => buildChecklistState(checklistItems))
  const [checklistReady, setChecklistReady] = useState(false)

  const checklistStorageKey = workflowId ? `workflow_publish_checklist_${workflowId}` : 'workflow_publish_checklist'

  const acceptanceItems = useMemo(
    () => checklistItems.filter((item) => item.group === 'acceptance'),
    []
  )
  const releaseItems = useMemo(
    () => checklistItems.filter((item) => item.group === 'release'),
    []
  )

  const resolvedCount = checklistItems.reduce((count, item) => count + (checklistState[item.key] ? 1 : 0), 0)
  const resolvedPercent = checklistItems.length ? Math.round((resolvedCount / checklistItems.length) * 100) : 0
  const allResolved = resolvedCount === checklistItems.length

  const fetchWorkflow = async () => {
    if (!workflowId) return
    try {
      setLoading(true)
      const data = await getWorkflow(workflowId)
      setWorkflowName(data.name || '')
      setWorkflowDescription(data.description || '')
      setCurrentVersionId(data.current_version_id || null)
      setUpdatedAt(data.updated_at || null)
    } catch (error) {
      toast.error(t('workflow.detail.publish.toast.fetchError'))
      console.error('Failed to fetch workflow:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchRuns = async () => {
    if (!workflowId) return
    try {
      const data = await listRuns({
        mode: 'workflow',
        subject_kind: 'workflow',
        subject_id: workflowId,
        page_size: 5,
      })
      setRuns(data.items || [])
    } catch (error) {
      console.error('Failed to fetch workflow runs:', error)
    }
  }

  const fetchVersions = async () => {
    if (!workflowId) return
    try {
      setVersionsLoading(true)
      const data = await listWorkflowVersions(workflowId, { page_size: 20 })
      setVersions(data.items || [])
    } catch (error) {
      console.error('Failed to fetch workflow versions:', error)
    } finally {
      setVersionsLoading(false)
    }
  }

  const fetchReleases = async () => {
    if (!workflowId) return
    try {
      setReleasesLoading(true)
      const data = await listWorkflowReleases(workflowId, { page_size: 20 })
      setReleases(data.items || [])
    } catch (error) {
      console.error('Failed to fetch workflow releases:', error)
    } finally {
      setReleasesLoading(false)
    }
  }

  const refreshData = async () => {
    await Promise.all([fetchWorkflow(), fetchRuns(), fetchVersions(), fetchReleases()])
  }

  useEffect(() => {
    refreshData()
  }, [workflowId])

  useEffect(() => {
    let isMounted = true
    const loadChecklist = async () => {
      if (!workflowId) return
      const stored = await storage.get(checklistStorageKey)
      if (!isMounted) return
      if (stored && typeof stored === 'object') {
        setChecklistState({ ...buildChecklistState(checklistItems), ...stored })
      } else {
        setChecklistState(buildChecklistState(checklistItems))
      }
      setChecklistReady(true)
    }
    loadChecklist()
    return () => {
      isMounted = false
    }
  }, [workflowId])

  useEffect(() => {
    if (!checklistReady || !workflowId) return
    storage.set(checklistStorageKey, checklistState)
  }, [checklistReady, checklistState, workflowId])

  const handleChecklistToggle = (key: string, checked: boolean | string) => {
    const resolved = checked === true
    setChecklistState((prev) => ({ ...prev, [key]: resolved }))
  }

  const handleChecklistReset = () => {
    setChecklistState(buildChecklistState(checklistItems))
  }

  const handleChecklistMarkAll = () => {
    const nextState = checklistItems.reduce<ChecklistState>((acc, item) => {
      acc[item.key] = true
      return acc
    }, {})
    setChecklistState(nextState)
  }

  const handleCopyWorkflowId = async () => {
    if (!workflowId) return
    try {
      await navigator.clipboard.writeText(workflowId)
      toast.success(t('workflow.detail.publish.toast.copySuccess'))
    } catch (error) {
      toast.error(t('workflow.detail.publish.toast.copyError'))
      console.error('Failed to copy workflow id:', error)
    }
  }

  const handleExportDsl = async () => {
    if (!workflowId) return
    try {
      const data = await exportWorkflowDsl(workflowId, { format: 'json' })
      const payload = typeof data.dsl === 'string' ? data.dsl : JSON.stringify(data.dsl, null, 2)
      const blob = new Blob([payload], { type: 'application/json' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `workflow_${workflowId}_dsl.json`
      link.click()
      window.URL.revokeObjectURL(url)
      toast.success(t('workflow.detail.publish.toast.exportSuccess'))
    } catch (error) {
      toast.error(t('workflow.detail.publish.toast.exportError'))
      console.error('Failed to export DSL:', error)
    }
  }

  const handlePublish = async () => {
    if (!workflowId) return
    if (!allResolved) {
      toast.error(t('workflow.detail.publish.toast.checklistRequired'))
      return
    }
    try {
      setPublishing(true)
      const dslPayload = await exportWorkflowDsl(workflowId, { format: 'json' })
      if (!dslPayload || typeof dslPayload.dsl !== 'object') {
        toast.error(t('workflow.detail.publish.toast.noVersion'))
        return
      }
      const version = await createWorkflowVersion(workflowId, {
        graph_json: dslPayload.dsl as Record<string, any>,
        created_by: 'web-ui',
      })
      await publishWorkflowVersion(workflowId, version.id)
      toast.success(t('workflow.detail.publish.toast.publishSuccess'))
      await refreshData()
      navigate(`/workflow/${workflowId}/monitor`)
    } catch (error) {
      toast.error(t('workflow.detail.publish.toast.publishError'))
      console.error('Failed to publish workflow:', error)
    } finally {
      setPublishing(false)
    }
  }

  const handlePublishVersion = async (versionId: string) => {
    if (!workflowId) return
    try {
      setPublishingVersionId(versionId)
      await publishWorkflowVersion(workflowId, versionId)
      toast.success(t('workflow.detail.publish.toast.publishSuccess'))
      await refreshData()
    } catch (error) {
      toast.error(t('workflow.detail.publish.toast.publishError'))
      console.error('Failed to publish workflow version:', error)
    } finally {
      setPublishingVersionId(null)
    }
  }

  const formatTimestamp = (value?: string | null) => {
    if (!value) return '-'
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return value
    return parsed.toLocaleString()
  }

  const statusBadge = currentVersionId ? (
    <Badge className="bg-emerald-500">{t('workflow.common.published')}</Badge>
  ) : (
    <Badge variant="outline">{t('workflow.common.unpublished')}</Badge>
  )

  const releaseActionLabel = (action: string) => {
    if (action === 'rollback') {
      return t('workflow.detail.publish.history.action.rollback')
    }
    return t('workflow.detail.publish.history.action.publish')
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.publish.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.publish.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-medium">{workflowName || t('workflow.detail.publish.fields.untitled')}</div>
            {statusBadge}
          </div>
          <div className="text-sm text-muted-foreground">
            {workflowDescription || t('workflow.detail.publish.fields.noDescription')}
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="grid gap-2">
              <div className="text-xs text-muted-foreground">{t('workflow.detail.publish.fields.workflowId')}</div>
              <div className="flex items-center gap-2">
                <Input value={workflowId || ''} readOnly />
                <Button variant="outline" onClick={handleCopyWorkflowId} disabled={!workflowId}>
                  {t('workflow.detail.publish.actions.copy')}
                </Button>
              </div>
            </div>
            <div className="grid gap-2">
              <div className="text-xs text-muted-foreground">{t('workflow.detail.publish.fields.currentVersion')}</div>
              <Input value={currentVersionId || '-'} readOnly />
            </div>
            <div className="grid gap-2">
              <div className="text-xs text-muted-foreground">{t('workflow.detail.publish.fields.updatedAt')}</div>
              <Input value={updatedAt || '-'} readOnly />
            </div>
            <div className="flex items-end gap-2">
              <Button variant="outline" onClick={refreshData} disabled={loading}>
                {t('workflow.detail.publish.actions.refresh')}
              </Button>
              <Button variant="outline" onClick={handleExportDsl} disabled={!currentVersionId}>
                {t('workflow.detail.publish.actions.exportDsl')}
              </Button>
            </div>
          </div>
          <div className="grid gap-2 text-xs text-muted-foreground">
            <div>{t('workflow.detail.publish.fields.runSummary', { count: runs.length })}</div>
            {!currentVersionId && (
              <div>{t('workflow.detail.publish.fields.noVersion')}</div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.panel.checklist')}</CardTitle>
          <CardDescription>
            {allResolved ? t('workflow.panel.checklistResolved') : t('workflow.panel.checklistTip')}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{t('workflow.detail.publish.checklist.progress', { resolved: resolvedCount, total: checklistItems.length })}</span>
              <span>{resolvedPercent}%</span>
            </div>
            <Progress value={resolvedPercent} />
          </div>
          <div className="grid gap-6 md:grid-cols-2">
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.publish.checklist.groups.acceptance')}</div>
              {acceptanceItems.map((item) => (
                <label key={item.key} className="flex items-start gap-3 text-sm">
                  <Checkbox
                    checked={checklistState[item.key] || false}
                    onCheckedChange={(checked) => handleChecklistToggle(item.key, checked)}
                  />
                  <span className="leading-5">{t(item.labelKey as TranslationKey)}</span>
                </label>
              ))}
            </div>
            <div className="space-y-3">
              <div className="text-sm font-medium">{t('workflow.detail.publish.checklist.groups.release')}</div>
              {releaseItems.map((item) => (
                <label key={item.key} className="flex items-start gap-3 text-sm">
                  <Checkbox
                    checked={checklistState[item.key] || false}
                    onCheckedChange={(checked) => handleChecklistToggle(item.key, checked)}
                  />
                  <span className="leading-5">{t(item.labelKey as TranslationKey)}</span>
                </label>
              ))}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={handleChecklistMarkAll}>
              {t('workflow.detail.publish.checklist.actions.markAll')}
            </Button>
            <Button variant="ghost" onClick={handleChecklistReset}>
              {t('workflow.detail.publish.checklist.actions.reset')}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.publish.versions.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.publish.versions.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {versionsLoading ? (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.publish.versions.loading')}</div>
          ) : versions.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.publish.versions.empty')}</div>
          ) : (
            <div className="space-y-3">
              {versions.map((version) => {
                const isCurrent = version.id === currentVersionId
                return (
                  <div key={version.id} className="rounded-lg border p-3 flex flex-col gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="text-sm font-medium">{version.id}</div>
                      {isCurrent ? (
                        <Badge className="bg-emerald-500">{t('workflow.detail.publish.versions.status.current')}</Badge>
                      ) : (
                        <Badge variant="outline">{t('workflow.detail.publish.versions.status.draft')}</Badge>
                      )}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {t('workflow.detail.publish.versions.meta', {
                        author: version.created_by || '-',
                        time: formatTimestamp(version.created_at),
                      })}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        onClick={() => handlePublishVersion(version.id)}
                        disabled={isCurrent || publishingVersionId === version.id}
                      >
                        {publishingVersionId === version.id
                          ? t('workflow.detail.publish.versions.publishing')
                          : t('workflow.detail.publish.versions.publish')}
                      </Button>
                      <Button
                        variant="ghost"
                        onClick={() => navigator.clipboard.writeText(version.id)}
                      >
                        {t('workflow.detail.publish.versions.copyId')}
                      </Button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.publish.history.title')}</CardTitle>
          <CardDescription>{t('workflow.detail.publish.history.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {releasesLoading ? (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.publish.history.loading')}</div>
          ) : releases.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t('workflow.detail.publish.history.empty')}</div>
          ) : (
            <div className="space-y-3">
              {releases.map((release) => (
                <div key={release.id} className="rounded-lg border p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <Badge variant={release.action === 'rollback' ? 'outline' : 'default'}>
                        {releaseActionLabel(release.action)}
                      </Badge>
                      <span className="text-sm font-medium">{release.to_version_id}</span>
                    </div>
                    <span className="text-xs text-muted-foreground">{formatTimestamp(release.created_at)}</span>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    {release.from_version_id
                      ? t('workflow.detail.publish.history.transition', {
                          from: release.from_version_id,
                          to: release.to_version_id,
                        })
                      : t('workflow.detail.publish.history.targetOnly', { to: release.to_version_id })}
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {t('workflow.detail.publish.history.meta', {
                      author: release.created_by || '-',
                      status: release.status,
                    })}
                  </div>
                  {release.notes && (
                    <div className="mt-2 rounded-md bg-muted px-2 py-1 text-xs text-muted-foreground">
                      {release.notes}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t('workflow.detail.publish.actions.sectionTitle')}</CardTitle>
          <CardDescription>{t('workflow.detail.publish.actions.sectionDescription')}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-3">
          <Button onClick={handlePublish} disabled={!allResolved || publishing || !workflowId}>
            {publishing ? t('workflow.detail.publish.actions.publishing') : t('workflow.detail.publish.actions.publish')}
          </Button>
          <Button
            variant="outline"
            onClick={() => workflowId && navigate(`/workflow/${workflowId}/monitor`)}
            disabled={!workflowId}
          >
            {t('workflow.detail.publish.actions.run')}
          </Button>
          <div className="text-xs text-muted-foreground">
            {t('workflow.detail.publish.actions.hint')}
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
