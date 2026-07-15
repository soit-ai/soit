import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { ArrowRight, Bot, Clock3, RefreshCw, Rocket, ScrollText, Settings2, Workflow } from 'lucide-react'
import { toast } from 'sonner'

import { PageStatus } from '@/components/common/page-status'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import {
  createAgentVersion,
  getAgent,
  listAgentBindings,
  listAgentReleases,
  listAgentVersions,
  publishAgentVersion,
  updateAgent,
  type AgentBinding,
  type AgentRelease,
  type AgentVersion,
} from '@/services/agent-service'
import {
  getCapabilityPluginSourceLabel,
  getCapabilitySourceLabel,
  listAgentCapabilities,
  type AgentCapabilityItem,
} from '@/services/capability-service'
import { getLatestRegressionReport } from '@/services/evaluation-service'
import { listKnowledgeBases } from '@/services/knowledge-service'
import { listModels, type ModelLibraryItem } from '@/services/provider-service'
import { listRuns, type RunResponse } from '@/services/run-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

const getCapabilityButtonClassName = (selected: boolean) =>
  cn(
    'h-auto min-h-[72px] w-full min-w-0 justify-start whitespace-normal px-3 py-2 text-left',
    selected ? 'shadow-none' : 'shadow-sm',
  )

const EMPTY_MODEL_CONFIGS: ModelLibraryItem[] = []

function AgentDetailPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const { agentId = '' } = useParams()
  const [savingProfile, setSavingProfile] = useState(false)
  const [creatingVersion, setCreatingVersion] = useState(false)
  const [publishingVersionId, setPublishingVersionId] = useState<string | null>(null)
  const [profileForm, setProfileForm] = useState({
    name: '',
    description: '',
    visibility: 'private',
    status: 'active',
  })
  const [draftForm, setDraftForm] = useState({
    systemPrompt: '',
    modelRef: '',
    temperature: '0.2',
    maxIterations: '8',
    knowledgeRefs: [] as string[],
    toolRefs: [] as string[],
    workflowRefs: [] as string[],
    skillRefs: [] as string[],
  })

  const {
    data: agent,
    isLoading: agentLoading,
    isError: agentLoadFailed,
    error: agentLoadError,
    refetch: refetchAgent,
  } = useQuery({
    queryKey: ['agents', agentId],
    queryFn: () => getAgent(agentId),
    options: {
      enabled: Boolean(agentId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: versionPage,
    isLoading: versionsLoading,
    refetch: refetchVersions,
  } = useQuery({
    queryKey: ['agents', agentId, 'versions'],
    queryFn: () => listAgentVersions(agentId, { page_size: 50 }),
    options: {
      enabled: Boolean(agentId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: releasePage,
    isLoading: releasesLoading,
    refetch: refetchReleases,
  } = useQuery({
    queryKey: ['agents', agentId, 'releases'],
    queryFn: () => listAgentReleases(agentId, { page_size: 20 }),
    options: {
      enabled: Boolean(agentId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: bindings = [],
    isLoading: bindingsLoading,
    refetch: refetchBindings,
  } = useQuery<AgentBinding[]>({
    queryKey: ['agents', agentId, 'bindings', agent?.published_version_id || agent?.current_version_id || 'all'],
    queryFn: () => {
      const versionId = agent?.published_version_id || agent?.current_version_id
      return listAgentBindings(agentId, versionId ? { version_id: versionId } : undefined)
    },
    options: {
      enabled: Boolean(agentId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: knowledgePage } = useQuery({
    queryKey: ['knowledge', 'options'],
    queryFn: () => listKnowledgeBases({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: modelConfigs = EMPTY_MODEL_CONFIGS } = useQuery<ModelLibraryItem[]>({
    queryKey: ['agent', 'models'],
    queryFn: () => listModels(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: runPage, isLoading: runsLoading } = useQuery({
    queryKey: ['agents', agentId, 'runs'],
    queryFn: () => listRuns({ subject_id: agentId, page_size: 5 }),
    options: {
      enabled: Boolean(agentId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: capabilityPage, isLoading: capabilityCatalogLoading } = useQuery({
    queryKey: ['capabilities', 'agent-assembly'],
    queryFn: () => listAgentCapabilities({ page_size: 200 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const versions = useMemo(
    () => [...(versionPage?.items || [])].sort((left, right) => right.version - left.version),
    [versionPage?.items],
  )
  const latestVersion = versions[0]
  const regressionVersionId = latestVersion?.id || agent?.current_version_id || agent?.published_version_id || undefined
  const { data: regressionReport, isLoading: regressionReportLoading } = useQuery({
    queryKey: ['evaluations', 'latest-regression-report', 'agent', agentId, regressionVersionId],
    queryFn: () => getLatestRegressionReport({
      subject_kind: 'agent',
      subject_id: agentId,
      subject_version_id: regressionVersionId,
    }),
    options: {
      enabled: Boolean(agentId && regressionVersionId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const releases = releasePage?.items || []
  const knowledgeOptions = knowledgePage?.items || []
  const capabilityCatalog = capabilityPage?.items || []
  const modelOptions = useMemo(
    () => modelConfigs.filter((item) => item.isActive && item.modelType === 'llm'),
    [modelConfigs],
  )
  const recentRuns = runPage?.items || []
  const bindingGroups = useMemo(
    () => ({
      model: bindings.filter((item) => item.binding_type === 'model'),
      knowledge: bindings.filter((item) => item.binding_type === 'knowledge'),
      workflow: bindings.filter((item) => item.binding_type === 'workflow'),
      skill: bindings.filter((item) => item.binding_type === 'skill'),
      tool: bindings.filter((item) => item.binding_type === 'tool'),
    }),
    [bindings],
  )
  const capabilityCatalogGroups = useMemo(
    () => ({
      model: capabilityCatalog.filter((item: AgentCapabilityItem) => item.kind === 'model'),
      knowledge: capabilityCatalog.filter((item: AgentCapabilityItem) => item.kind === 'knowledge'),
      workflow: capabilityCatalog.filter((item: AgentCapabilityItem) => item.kind === 'workflow'),
      skill: capabilityCatalog.filter((item: AgentCapabilityItem) => item.kind === 'skill'),
      tool: capabilityCatalog.filter((item: AgentCapabilityItem) => item.kind === 'tool'),
    }),
    [capabilityCatalog],
  )
  const capabilityByRef = useMemo(
    () => new Map(capabilityCatalog.map((item: AgentCapabilityItem) => [item.ref, item])),
    [capabilityCatalog],
  )

  const parseVersionSpecBindings = (spec: Record<string, unknown>) => {
    const bindingsSpec = (spec.bindings as Record<string, unknown> | undefined) || {}
    const readRefs = (value: unknown) => (Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [])

    return {
      modelRef: typeof bindingsSpec.model_ref === 'string' ? bindingsSpec.model_ref : '',
      knowledgeRefs: readRefs(bindingsSpec.knowledge_refs),
      toolRefs: readRefs(bindingsSpec.tool_refs),
      workflowRefs: readRefs(bindingsSpec.workflow_refs),
      skillRefs: readRefs(bindingsSpec.skill_refs),
    }
  }

  useEffect(() => {
    if (!agent) {
      return
    }

    setProfileForm({
      name: agent.name || '',
      description: agent.description || '',
      visibility: agent.visibility || 'private',
      status: agent.status || 'active',
    })
  }, [agent])

  useEffect(() => {
    if (!latestVersion) {
      return
    }

    const spec = latestVersion.spec_json || {}
    const specBindings = parseVersionSpecBindings(spec)
    const params = (spec.params as Record<string, unknown> | undefined) || {}
    const limits = (spec.limits as Record<string, unknown> | undefined) || {}

    setDraftForm({
      systemPrompt: typeof spec.system_prompt === 'string' ? spec.system_prompt : '',
      modelRef: specBindings.modelRef,
      temperature:
        typeof params.temperature === 'number' ? String(params.temperature) : '0.2',
      maxIterations:
        typeof limits.max_iterations === 'number' ? String(limits.max_iterations) : '8',
      knowledgeRefs: specBindings.knowledgeRefs,
      toolRefs: specBindings.toolRefs,
      workflowRefs: specBindings.workflowRefs,
      skillRefs: specBindings.skillRefs,
    })
  }, [latestVersion])

  useEffect(() => {
    if (modelOptions.length === 0) {
      return
    }

    setDraftForm((current) => ({
      ...current,
      modelRef: current.modelRef || modelOptions[0].modelName,
    }))
  }, [modelOptions])

  const handleSaveProfile = async () => {
    if (!agentId) {
      return
    }
    if (!profileForm.name.trim()) {
      toast.error(t('agent.detail.toast.nameRequired'))
      return
    }

    try {
      setSavingProfile(true)
      await updateAgent(agentId, {
        name: profileForm.name.trim(),
        description: profileForm.description.trim() || undefined,
        visibility: profileForm.visibility,
        status: profileForm.status,
      })
      await refetchAgent()
      toast.success(t('agent.detail.toast.profileUpdated'))
    } catch (error) {
      toast.error(t('agent.detail.toast.profileUpdateFailed'))
      console.error('Failed to update agent:', error)
    } finally {
      setSavingProfile(false)
    }
  }

  const handleCreateVersion = async () => {
    if (!agentId) {
      return
    }
    if (!draftForm.modelRef) {
      toast.error(t('agent.detail.toast.modelRequired'))
      return
    }

    try {
      setCreatingVersion(true)
      await createAgentVersion(agentId, {
        system_prompt: draftForm.systemPrompt.trim() || undefined,
        bindings: {
          model_ref: draftForm.modelRef,
          knowledge_refs: draftForm.knowledgeRefs,
          tool_refs: draftForm.toolRefs,
          workflow_refs: draftForm.workflowRefs,
          skill_refs: draftForm.skillRefs,
        },
        temperature: draftForm.temperature ? Number(draftForm.temperature) : undefined,
        max_iterations: draftForm.maxIterations ? Number(draftForm.maxIterations) : undefined,
      })
      await Promise.all([refetchAgent(), refetchVersions(), refetchBindings()])
      toast.success(t('agent.detail.toast.versionCreated'))
    } catch (error) {
      toast.error(t('agent.detail.toast.versionCreateFailed'))
      console.error('Failed to create agent version:', error)
    } finally {
      setCreatingVersion(false)
    }
  }

  const handlePublish = async (versionId: string) => {
    if (!agentId) {
      return
    }

    try {
      setPublishingVersionId(versionId)
      await publishAgentVersion(agentId, { version_id: versionId })
      await Promise.all([refetchAgent(), refetchVersions(), refetchBindings(), refetchReleases()])
      toast.success(t('agent.detail.toast.published'))
    } catch (error) {
      toast.error(t('agent.detail.toast.publishFailed'))
      console.error('Failed to publish agent version:', error)
    } finally {
      setPublishingVersionId(null)
    }
  }

  const toggleKnowledge = (knowledgeId: string) => {
    setDraftForm((current) => ({
      ...current,
      knowledgeRefs: current.knowledgeRefs.includes(knowledgeId)
        ? current.knowledgeRefs.filter((item) => item !== knowledgeId)
        : [...current.knowledgeRefs, knowledgeId],
    }))
  }

  const toggleCapabilityRef = (field: 'toolRefs' | 'workflowRefs' | 'skillRefs', ref: string) => {
    setDraftForm((current) => ({
      ...current,
      [field]: current[field].includes(ref)
        ? current[field].filter((item) => item !== ref)
        : [...current[field], ref],
    }))
  }

  const visibilityOptions = [
    { value: 'private', labelKey: 'agent.detail.visibility.private' },
    { value: 'workspace', labelKey: 'agent.detail.visibility.workspace' },
    { value: 'tenant', labelKey: 'agent.detail.visibility.tenant' },
    { value: 'public', labelKey: 'agent.detail.visibility.public' },
  ] satisfies { value: string; labelKey: TranslationKey }[]

  const statusOptions = [
    { value: 'active', labelKey: 'agent.detail.status.active' },
    { value: 'archived', labelKey: 'agent.detail.status.archived' },
    { value: 'disabled', labelKey: 'agent.detail.status.disabled' },
  ] satisfies { value: string; labelKey: TranslationKey }[]

  const capabilityFields = [
    {
      field: 'toolRefs',
      labelKey: 'agent.detail.assembly.toolBindings',
      emptyKey: 'agent.detail.assembly.emptyToolBindings',
      items: capabilityCatalogGroups.tool,
    },
    {
      field: 'workflowRefs',
      labelKey: 'agent.detail.assembly.workflowBindings',
      emptyKey: 'agent.detail.assembly.emptyWorkflowBindings',
      items: capabilityCatalogGroups.workflow,
    },
    {
      field: 'skillRefs',
      labelKey: 'agent.detail.assembly.skillBindings',
      emptyKey: 'agent.detail.assembly.emptySkillBindings',
      items: capabilityCatalogGroups.skill,
    },
  ] satisfies {
    field: 'toolRefs' | 'workflowRefs' | 'skillRefs'
    labelKey: TranslationKey
    emptyKey: TranslationKey
    items: AgentCapabilityItem[]
  }[]

  const capabilityGroupLabelKeys = {
    model: 'agent.detail.capabilityGroups.model',
    knowledge: 'agent.detail.capabilityGroups.knowledge',
    workflow: 'agent.detail.capabilityGroups.workflow',
    skill: 'agent.detail.capabilityGroups.skill',
    tool: 'agent.detail.capabilityGroups.tool',
  } satisfies Record<string, TranslationKey>
  type CapabilityGroupName = keyof typeof capabilityGroupLabelKeys
  const regressionSummary = regressionReport?.summary_json || {}
  const regressionMetrics = regressionReport?.metrics_json || {}
  const regressionTotal = Number(regressionSummary.total || 0)
  const regressionPassed = Number(regressionSummary.passed || 0)
  const regressionLatency = typeof regressionMetrics.avg_latency_ms === 'number'
    ? `${Math.round(regressionMetrics.avg_latency_ms)} ms avg`
    : '-'
  const regressionCost = typeof regressionMetrics.avg_cost_amount === 'number'
    ? `$${regressionMetrics.avg_cost_amount.toFixed(2)} avg`
    : '-'

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white shadow-xl">
        <CardHeader className="gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="bg-white/10 text-white hover:bg-white/10">
              {t('agent.detail.hero.badge')}
            </Badge>
            {agent?.published_version_id ? (
              <Badge variant="secondary" className="bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/20">
                {t('agent.detail.hero.published')}
              </Badge>
            ) : (
              <Badge variant="secondary" className="bg-amber-500/20 text-amber-100 hover:bg-amber-500/20">
                {t('agent.detail.hero.draftOnly')}
              </Badge>
            )}
          </div>
          <div className="space-y-2">
            <CardTitle className="text-3xl font-semibold tracking-tight">
              {agentLoading ? t('agent.detail.hero.loadingAgent') : agent?.name || agentId}
            </CardTitle>
            <CardDescription className="max-w-2xl text-slate-300">
              {agent?.description || t('agent.detail.hero.description')}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(`/chat/${agentId}`)} className="bg-white text-slate-950 hover:bg-slate-100">
              <Bot className="mr-2 h-4 w-4" />
              {t('agent.detail.hero.openChat')}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/knowledge')}>
              <ScrollText className="mr-2 h-4 w-4" />
              {t('agent.detail.hero.knowledge')}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/models')}>
              <Settings2 className="mr-2 h-4 w-4" />
              {t('agent.detail.hero.models')}
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/observe/runs?subject_id=${agentId}`)}>
              <Clock3 className="mr-2 h-4 w-4" />
              {t('agent.detail.hero.viewRuns')}
            </Button>
            <Button variant="secondary" onClick={() => navigate('/workflow')}>
              <Workflow className="mr-2 h-4 w-4" />
              {t('agent.detail.hero.workflow')}
            </Button>
          </div>
        </CardHeader>
      </Card>

      {agentLoading && !agent && (
        <PageStatus
          variant="loading"
          title={t('agent.detail.statusPage.loadingTitle')}
          description={t('agent.detail.statusPage.loadingDescription')}
        />
      )}

      {!agentLoading && agentLoadFailed && (
        <PageStatus
          variant="error"
          title={t('agent.detail.statusPage.errorTitle')}
          description={agentLoadError instanceof Error ? agentLoadError.message : t('agent.detail.statusPage.errorDescription')}
          actionLabel={t('agent.detail.statusPage.retry')}
          onAction={() => refetchAgent()}
        />
      )}

      {!agentLoading && !agentLoadFailed && !agent && (
        <PageStatus
          variant="empty"
          title={t('agent.detail.statusPage.emptyTitle')}
          description={t('agent.detail.statusPage.emptyDescription')}
          actionLabel={t('agent.detail.statusPage.backToAgents')}
          onAction={() => navigate('/agents')}
        />
      )}

      {!agentLoading && !agentLoadFailed && agent && (
        <>
      <div className="grid gap-4 xl:grid-cols-[0.82fr_1.18fr]">
        <Card>
          <CardHeader>
            <CardTitle>{t('agent.detail.overview.title')}</CardTitle>
            <CardDescription>{t('agent.detail.overview.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="agent-name">{t('agent.detail.overview.name')}</Label>
              <Input
                id="agent-name"
                value={profileForm.name}
                onChange={(event) => setProfileForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="agent-description">{t('agent.detail.overview.agentDescription')}</Label>
              <Textarea
                id="agent-description"
                value={profileForm.description}
                onChange={(event) => setProfileForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t('agent.detail.overview.visibility')}</Label>
                <Select
                  value={profileForm.visibility}
                  onValueChange={(value) => setProfileForm((current) => ({ ...current, visibility: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('agent.detail.overview.selectVisibility')} />
                  </SelectTrigger>
                  <SelectContent>
                    {visibilityOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(option.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>{t('agent.detail.overview.status')}</Label>
                <Select
                  value={profileForm.status}
                  onValueChange={(value) => setProfileForm((current) => ({ ...current, status: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('agent.detail.overview.selectStatus')} />
                  </SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((option) => (
                      <SelectItem key={option.value} value={option.value}>
                        {t(option.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2 rounded-xl border p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('agent.detail.overview.currentVersion')}</span>
                <span className="font-medium">{agent?.current_version_id || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('agent.detail.overview.publishedVersion')}</span>
                <span className="font-medium">{agent?.published_version_id || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">{t('agent.detail.overview.updated')}</span>
                <span className="font-medium">{formatTimestamp(agent?.updated_at)}</span>
              </div>
            </div>
            <Button onClick={handleSaveProfile} disabled={savingProfile || agentLoading}>
              {savingProfile ? t('agent.detail.overview.saving') : t('agent.detail.overview.saveProfile')}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>{t('agent.detail.assembly.title')}</CardTitle>
            <CardDescription>{t('agent.detail.assembly.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="agent-system-prompt">{t('agent.detail.assembly.systemPrompt')}</Label>
              <Textarea
                id="agent-system-prompt"
                value={draftForm.systemPrompt}
                onChange={(event) => setDraftForm((current) => ({ ...current, systemPrompt: event.target.value }))}
                placeholder={t('agent.detail.assembly.systemPromptPlaceholder')}
                className="min-h-32"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>{t('agent.detail.assembly.model')}</Label>
                <Select
                  value={draftForm.modelRef}
                  onValueChange={(value) => setDraftForm((current) => ({ ...current, modelRef: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder={t('agent.detail.assembly.selectModel')} />
                  </SelectTrigger>
                  <SelectContent>
                    {modelOptions.map((model) => (
                      <SelectItem key={model.id} value={model.modelName}>
                        {model.name || model.modelName}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="agent-temperature">{t('agent.detail.assembly.temperature')}</Label>
                <Input
                  id="agent-temperature"
                  type="number"
                  min={0}
                  max={2}
                  step={0.1}
                  value={draftForm.temperature}
                  onChange={(event) => setDraftForm((current) => ({ ...current, temperature: event.target.value }))}
                />
              </div>
            </div>
            <div className="grid gap-2 md:max-w-xs">
              <Label htmlFor="agent-max-iterations">{t('agent.detail.assembly.maxIterations')}</Label>
              <Input
                id="agent-max-iterations"
                type="number"
                min={1}
                max={50}
                value={draftForm.maxIterations}
                onChange={(event) => setDraftForm((current) => ({ ...current, maxIterations: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label>{t('agent.detail.assembly.knowledgeBindings')}</Label>
              <div className="flex flex-wrap gap-2 rounded-xl border p-3">
                {knowledgeOptions.length === 0 && (
                  <div className="text-sm text-muted-foreground">{t('agent.detail.assembly.emptyKnowledgeBindings')}</div>
                )}
                {knowledgeOptions.map((knowledge) => {
                  const selected = draftForm.knowledgeRefs.includes(knowledge.id)
                  return (
                    <Button
                      key={knowledge.id}
                      type="button"
                      variant={selected ? 'default' : 'outline'}
                      size="sm"
                      onClick={() => toggleKnowledge(knowledge.id)}
                    >
                      {knowledge.name}
                    </Button>
                  )
                })}
              </div>
            </div>
            {capabilityFields.map(({ field, labelKey, emptyKey, items }) => (
              <div key={field} className="grid gap-2">
                <Label>{t(labelKey)}</Label>
                <div className="grid gap-2 rounded-xl border p-3 sm:grid-cols-2">
                  {items.length === 0 && (
                    <div className="text-sm text-muted-foreground sm:col-span-2">{t(emptyKey)}</div>
                  )}
                  {items.map((item) => {
                    const selected = draftForm[field].includes(item.ref)
                    const sourceLabel = getCapabilitySourceLabel(item)
                    const pluginSourceLabel = getCapabilityPluginSourceLabel(item)
                    return (
                      <Button
                        key={item.ref}
                        type="button"
                        variant={selected ? 'default' : 'outline'}
                        size="sm"
                        aria-pressed={selected}
                        className={getCapabilityButtonClassName(selected)}
                        onClick={() => toggleCapabilityRef(field, item.ref)}
                      >
                        <span className="flex min-w-0 flex-1 flex-col gap-1">
                          <span className="flex min-w-0 items-center justify-between gap-2">
                            <span className="min-w-0 truncate font-medium">{item.name}</span>
                            <Badge variant={selected ? 'secondary' : 'outline'} className="shrink-0">
                              {sourceLabel}
                            </Badge>
                          </span>
                          <span className={cn('min-w-0 break-all text-xs', selected ? 'text-primary-foreground/80' : 'text-muted-foreground')}>
                            {item.ref}
                          </span>
                          {pluginSourceLabel && (
                            <span className={cn('text-xs font-medium', selected ? 'text-primary-foreground/85' : 'text-foreground/70')}>
                              {pluginSourceLabel}
                            </span>
                          )}
                        </span>
                      </Button>
                    )
                  })}
                </div>
              </div>
            ))}
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleCreateVersion} disabled={creatingVersion || !draftForm.modelRef}>
                <Rocket className="mr-2 h-4 w-4" />
                {creatingVersion ? t('agent.detail.assembly.creatingVersion') : t('agent.detail.assembly.createDraftVersion')}
              </Button>
              <Button variant="outline" onClick={() => refetchVersions()} disabled={versionsLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {t('agent.detail.assembly.refreshVersions')}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <div className="grid gap-4">
          {regressionReport || regressionReportLoading ? (
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <CardTitle>Regression Gate</CardTitle>
                    <CardDescription>Latest replay report for the current release candidate.</CardDescription>
                  </div>
                  {regressionReport ? (
                    <Badge variant={regressionReport.passed ? 'default' : 'destructive'}>
                      {regressionReport.passed ? 'Passed' : 'Failed'}
                    </Badge>
                  ) : null}
                </div>
              </CardHeader>
              <CardContent className="grid gap-3 sm:grid-cols-3">
                {regressionReportLoading && !regressionReport ? (
                  <div className="text-sm text-muted-foreground sm:col-span-3">Loading regression report...</div>
                ) : (
                  <>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Cases</div>
                      <div className="mt-1 text-lg font-semibold">{regressionPassed} / {regressionTotal} cases</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Latency</div>
                      <div className="mt-1 text-lg font-semibold">{regressionLatency}</div>
                    </div>
                    <div className="rounded-lg border p-3">
                      <div className="text-xs text-muted-foreground">Cost</div>
                      <div className="mt-1 text-lg font-semibold">{regressionCost}</div>
                    </div>
                  </>
                )}
              </CardContent>
            </Card>
          ) : null}

        <Card>
          <CardHeader>
            <CardTitle>{t('agent.detail.versions.title')}</CardTitle>
            <CardDescription>{t('agent.detail.versions.description')}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {versionsLoading && <div className="text-sm text-muted-foreground">{t('agent.detail.versions.loading')}</div>}
            {!versionsLoading && versions.length === 0 && (
              <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                {t('agent.detail.versions.empty')}
              </div>
            )}
            {!versionsLoading &&
              versions.map((version: AgentVersion) => {
                const spec = version.spec_json || {}
                const versionBindings = parseVersionSpecBindings(spec)

                return (
                  <Card key={version.id}>
                    <CardHeader className="pb-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <CardTitle className="text-base">v{version.version}</CardTitle>
                          <CardDescription>{formatTimestamp(version.created_at)}</CardDescription>
                        </div>
                        <Badge variant={version.status === 'published' ? 'default' : 'outline'}>{version.status}</Badge>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{versionBindings.modelRef || t('agent.detail.versions.noModel')}</Badge>
                        {versionBindings.knowledgeRefs.map((knowledgeId) => {
                          const knowledge = knowledgeOptions.find((item) => item.id === knowledgeId)
                          return (
                            <Badge key={knowledgeId} variant="secondary">
                              {knowledge?.name || knowledgeId}
                            </Badge>
                          )
                        })}
                        {versionBindings.toolRefs.map((ref) => {
                          const capability = capabilityByRef.get(ref)
                          const pluginSourceLabel = capability ? getCapabilityPluginSourceLabel(capability) : null
                          return (
                            <Badge key={ref} variant="outline" className="max-w-full gap-1 whitespace-normal break-all text-left">
                              <span>{ref}</span>
                              {pluginSourceLabel && <span className="text-muted-foreground">Plugin {pluginSourceLabel}</span>}
                            </Badge>
                          )
                        })}
                        {versionBindings.workflowRefs.map((ref) => <Badge key={ref} variant="outline">{ref}</Badge>)}
                        {versionBindings.skillRefs.map((ref) => <Badge key={ref} variant="outline">{ref}</Badge>)}
                      </div>
                      {typeof spec.system_prompt === 'string' && spec.system_prompt && (
                        <div className="rounded-xl bg-muted p-3 text-sm text-muted-foreground">
                          {spec.system_prompt}
                        </div>
                      )}
                      <div className="flex flex-wrap gap-2">
                        <Button
                          variant={version.status === 'published' ? 'secondary' : 'default'}
                          onClick={() => handlePublish(version.id)}
                          disabled={publishingVersionId === version.id || version.status === 'published'}
                        >
                          {version.status === 'published'
                            ? t('agent.detail.versions.published')
                            : publishingVersionId === version.id
                              ? t('agent.detail.versions.publishing')
                              : t('agent.detail.versions.publish')}
                        </Button>
                        <Button variant="outline" onClick={() => navigate(`/chat/${agentId}`)}>
                          {t('agent.detail.hero.openChat')}
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
          </CardContent>
        </Card>
        </div>

        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>{t('agent.detail.catalog.title')}</CardTitle>
              <CardDescription>{t('agent.detail.catalog.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {capabilityCatalogLoading && <div className="text-sm text-muted-foreground">{t('agent.detail.catalog.loading')}</div>}
              {!capabilityCatalogLoading &&
                (Object.entries(capabilityCatalogGroups) as [CapabilityGroupName, AgentCapabilityItem[]][]).map(([groupName, items]) => (
                  <div key={groupName} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">{t(capabilityGroupLabelKeys[groupName])}</div>
                      <Badge variant="outline">{items.length}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {items.slice(0, 3).map((item) => (
                        <Badge key={item.ref} variant="secondary">
                          {item.name}
                        </Badge>
                      ))}
                      {items.length > 3 && (
                        <Badge variant="outline">{t('agent.detail.catalog.more', { count: items.length - 3 })}</Badge>
                      )}
                      {items.length === 0 && (
                        <div className="text-xs text-muted-foreground">
                          {t('agent.detail.catalog.emptyGroup', { group: t(capabilityGroupLabelKeys[groupName]) })}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agent.detail.bindings.title')}</CardTitle>
              <CardDescription>{t('agent.detail.bindings.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {bindingsLoading && <div className="text-sm text-muted-foreground">{t('agent.detail.bindings.loading')}</div>}
              {!bindingsLoading && bindings.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('agent.detail.bindings.empty')}</div>
              )}
              {!bindingsLoading &&
                (Object.entries(bindingGroups) as [CapabilityGroupName, AgentBinding[]][]).map(([groupName, groupBindings]) => (
                  <div key={groupName} className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      {t(capabilityGroupLabelKeys[groupName])}
                    </div>
                    {groupBindings.length === 0 ? (
                      <div className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
                        {t('agent.detail.bindings.emptyGroup', { group: t(capabilityGroupLabelKeys[groupName]) })}
                      </div>
                    ) : (
                      groupBindings.map((binding) => (
                        <div key={binding.id} className="flex items-center justify-between rounded-lg border px-3 py-2 text-sm">
                          <Badge variant="outline">{binding.binding_type}</Badge>
                          <span className="max-w-[220px] truncate text-right">{binding.target_key || binding.target_id || '-'}</span>
                        </div>
                      ))
                    )}
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agent.detail.releases.title')}</CardTitle>
              <CardDescription>{t('agent.detail.releases.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {releasesLoading && <div className="text-sm text-muted-foreground">{t('agent.detail.releases.loading')}</div>}
              {!releasesLoading && releases.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('agent.detail.releases.empty')}</div>
              )}
              {!releasesLoading &&
                releases.map((release) => (
                  <div key={release.id} className="rounded-lg border px-3 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={release.action === 'rollback' ? 'outline' : 'default'}>
                          {release.action === 'rollback' ? t('agent.detail.releases.rollback') : t('agent.detail.releases.publish')}
                        </Badge>
                        <span className="font-medium">{release.to_version_id}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{formatTimestamp(release.created_at)}</span>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {release.from_version_id
                        ? t('agent.detail.releases.fromTo', { from: release.from_version_id, to: release.to_version_id })
                        : t('agent.detail.releases.to', { to: release.to_version_id })}
                    </div>
                    {release.notes && <div className="mt-2 text-xs text-muted-foreground">{release.notes}</div>}
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t('agent.detail.runs.title')}</CardTitle>
              <CardDescription>{t('agent.detail.runs.description')}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {runsLoading && <div className="text-sm text-muted-foreground">{t('agent.detail.runs.loading')}</div>}
              {!runsLoading && recentRuns.length === 0 && (
                <div className="text-sm text-muted-foreground">{t('agent.detail.runs.empty')}</div>
              )}
              {!runsLoading &&
                recentRuns.map((run: RunResponse) => (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => navigate(`/observe/runs/${run.id}`)}
                    className="w-full rounded-lg border p-3 text-left transition-colors hover:border-primary/40"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">{run.mode}</div>
                      <Badge variant={run.status === 'completed' || run.status === 'succeeded' ? 'default' : 'outline'}>{run.status}</Badge>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{formatTimestamp(run.started_at)}</div>
                    <div className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {run.input_summary || run.output_summary || run.error_message || t('agent.detail.runs.noSummary')}
                    </div>
                  </button>
                ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => navigate('/agents')}>
          {t('agent.detail.statusPage.backToAgents')}
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
        </>
      )}
    </div>
  )
}

export default AgentDetailPage
