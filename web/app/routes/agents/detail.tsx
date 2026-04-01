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
import { listCapabilityRegistry, type CapabilityRegistryItem } from '@/services/capability-service'
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

function AgentDetailPage() {
  const navigate = useNavigate()
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
    queryKey: ['agents', agentId, 'bindings', agent?.current_version_id || 'all'],
    queryFn: () => listAgentBindings(agentId, agent?.current_version_id ? { version_id: agent.current_version_id } : undefined),
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

  const { data: modelConfigs = [] } = useQuery<ModelLibraryItem[]>({
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
    queryFn: () => listCapabilityRegistry({ page_size: 200 }),
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
      plugin: bindings.filter((item) => item.binding_type === 'plugin'),
      tool: bindings.filter((item) => item.binding_type === 'tool'),
    }),
    [bindings],
  )
  const capabilityCatalogGroups = useMemo(
    () => ({
      model: capabilityCatalog.filter((item: CapabilityRegistryItem) => item.kind === 'model'),
      knowledge: capabilityCatalog.filter((item: CapabilityRegistryItem) => item.kind === 'knowledge'),
      workflow: capabilityCatalog.filter((item: CapabilityRegistryItem) => item.kind === 'workflow'),
      skill: capabilityCatalog.filter((item: CapabilityRegistryItem) => item.kind === 'skill'),
      tool: capabilityCatalog.filter((item: CapabilityRegistryItem) => item.kind === 'tool'),
    }),
    [capabilityCatalog],
  )

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
    if (latestVersion) {
      const spec = latestVersion.spec_json || {}
      const modelSpec = (spec.model as Record<string, unknown> | undefined) || {}
      const modelParams = (modelSpec.params as Record<string, unknown> | undefined) || {}
      const ragSpec = (spec.rag as Record<string, unknown> | undefined) || {}
      const limits = (spec.limits as Record<string, unknown> | undefined) || {}

      setDraftForm({
        systemPrompt: typeof spec.system_prompt === 'string' ? spec.system_prompt : '',
        modelRef: typeof modelSpec.ref_key === 'string' ? modelSpec.ref_key : modelOptions[0]?.modelName || '',
        temperature:
          typeof modelParams.temperature === 'number' ? String(modelParams.temperature) : '0.2',
        maxIterations:
          typeof limits.max_iterations === 'number' ? String(limits.max_iterations) : '8',
        knowledgeRefs: Array.isArray(ragSpec.knowledges)
          ? ragSpec.knowledges.filter((item): item is string => typeof item === 'string')
          : [],
      })
      return
    }

    if (modelOptions.length > 0) {
      setDraftForm((current) => ({
        ...current,
        modelRef: current.modelRef || modelOptions[0].modelName,
      }))
    }
  }, [latestVersion, modelOptions])

  const handleSaveProfile = async () => {
    if (!agentId) {
      return
    }
    if (!profileForm.name.trim()) {
      toast.error('Agent name is required.')
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
      toast.success('Agent profile updated.')
    } catch (error) {
      toast.error('Failed to update agent profile.')
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
      toast.error('Select a model before creating a version.')
      return
    }

    try {
      setCreatingVersion(true)
      await createAgentVersion(agentId, {
        system_prompt: draftForm.systemPrompt.trim() || undefined,
        model_ref: draftForm.modelRef,
        knowledge_refs: draftForm.knowledgeRefs,
        temperature: draftForm.temperature ? Number(draftForm.temperature) : undefined,
        max_iterations: draftForm.maxIterations ? Number(draftForm.maxIterations) : undefined,
      })
      await Promise.all([refetchAgent(), refetchVersions(), refetchBindings()])
      toast.success('Draft version created.')
    } catch (error) {
      toast.error('Failed to create draft version.')
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
      toast.success('Agent published.')
    } catch (error) {
      toast.error('Failed to publish agent.')
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

  const renderReleaseAction = (release: AgentRelease) => {
    if (release.action === 'rollback') {
      return 'Rollback'
    }
    return 'Publish'
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white shadow-xl">
        <CardHeader className="gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="bg-white/10 text-white hover:bg-white/10">
              Agent Detail
            </Badge>
            {agent?.published_version_id ? (
              <Badge variant="secondary" className="bg-emerald-500/20 text-emerald-100 hover:bg-emerald-500/20">
                Published
              </Badge>
            ) : (
              <Badge variant="secondary" className="bg-amber-500/20 text-amber-100 hover:bg-amber-500/20">
                Draft Only
              </Badge>
            )}
          </div>
          <div className="space-y-2">
            <CardTitle className="text-3xl font-semibold tracking-tight">
              {agentLoading ? 'Loading agent...' : agent?.name || agentId}
            </CardTitle>
            <CardDescription className="max-w-2xl text-slate-300">
              {agent?.description || 'Configure runtime bindings, publish a version, then move into chat or runs.'}
            </CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => navigate(`/chat/${agentId}`)} className="bg-white text-slate-950 hover:bg-slate-100">
              <Bot className="mr-2 h-4 w-4" />
              Open Chat
            </Button>
            <Button variant="secondary" onClick={() => navigate('/knowledge')}>
              <ScrollText className="mr-2 h-4 w-4" />
              Knowledge
            </Button>
            <Button variant="secondary" onClick={() => navigate('/models')}>
              <Settings2 className="mr-2 h-4 w-4" />
              Models
            </Button>
            <Button variant="secondary" onClick={() => navigate(`/observability/runs?subject_id=${agentId}`)}>
              <Clock3 className="mr-2 h-4 w-4" />
              View Runs
            </Button>
            <Button variant="secondary" onClick={() => navigate('/workflow')}>
              <Workflow className="mr-2 h-4 w-4" />
              Workflow
            </Button>
          </div>
        </CardHeader>
      </Card>

      {agentLoading && !agent && (
        <PageStatus
          variant="loading"
          title="Loading agent"
          description="Fetching the agent shell, versions, bindings, and recent runs."
        />
      )}

      {!agentLoading && agentLoadFailed && (
        <PageStatus
          variant="error"
          title="Failed to load agent"
          description={agentLoadError instanceof Error ? agentLoadError.message : 'The agent could not be loaded right now.'}
          actionLabel="Retry"
          onAction={() => refetchAgent()}
        />
      )}

      {!agentLoading && !agentLoadFailed && !agent && (
        <PageStatus
          variant="empty"
          title="Agent not found"
          description="The requested agent is unavailable or no longer exists in this workspace."
          actionLabel="Back to Agents"
          onAction={() => navigate('/agents')}
        />
      )}

      {!agentLoading && !agentLoadFailed && agent && (
        <>
      <div className="grid gap-4 xl:grid-cols-[0.82fr_1.18fr]">
        <Card>
          <CardHeader>
            <CardTitle>Overview</CardTitle>
            <CardDescription>Edit the agent shell before managing runtime assembly and releases.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="agent-name">Name</Label>
              <Input
                id="agent-name"
                value={profileForm.name}
                onChange={(event) => setProfileForm((current) => ({ ...current, name: event.target.value }))}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="agent-description">Description</Label>
              <Textarea
                id="agent-description"
                value={profileForm.description}
                onChange={(event) => setProfileForm((current) => ({ ...current, description: event.target.value }))}
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Visibility</Label>
                <Select
                  value={profileForm.visibility}
                  onValueChange={(value) => setProfileForm((current) => ({ ...current, visibility: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select visibility" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="private">Private</SelectItem>
                    <SelectItem value="workspace">Workspace</SelectItem>
                    <SelectItem value="tenant">Tenant</SelectItem>
                    <SelectItem value="public">Public</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label>Status</Label>
                <Select
                  value={profileForm.status}
                  onValueChange={(value) => setProfileForm((current) => ({ ...current, status: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="archived">Archived</SelectItem>
                    <SelectItem value="disabled">Disabled</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="grid gap-2 rounded-xl border p-4 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Current Version</span>
                <span className="font-medium">{agent?.current_version_id || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Published Version</span>
                <span className="font-medium">{agent?.published_version_id || '-'}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Updated</span>
                <span className="font-medium">{formatTimestamp(agent?.updated_at)}</span>
              </div>
            </div>
            <Button onClick={handleSaveProfile} disabled={savingProfile || agentLoading}>
              {savingProfile ? 'Saving...' : 'Save Profile'}
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Assembly Draft</CardTitle>
            <CardDescription>Create a new immutable version with assembly-ready model and knowledge bindings.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="agent-system-prompt">System Prompt</Label>
              <Textarea
                id="agent-system-prompt"
                value={draftForm.systemPrompt}
                onChange={(event) => setDraftForm((current) => ({ ...current, systemPrompt: event.target.value }))}
                placeholder="You are a precise support copilot that uses workspace knowledge when available."
                className="min-h-32"
              />
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div className="grid gap-2">
                <Label>Model</Label>
                <Select
                  value={draftForm.modelRef}
                  onValueChange={(value) => setDraftForm((current) => ({ ...current, modelRef: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select model" />
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
                <Label htmlFor="agent-temperature">Temperature</Label>
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
              <Label htmlFor="agent-max-iterations">Max Iterations</Label>
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
              <Label>Knowledge Bindings</Label>
              <div className="flex flex-wrap gap-2 rounded-xl border p-3">
                {knowledgeOptions.length === 0 && (
                  <div className="text-sm text-muted-foreground">No knowledge bases available yet.</div>
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
            <div className="flex flex-wrap gap-2">
              <Button onClick={handleCreateVersion} disabled={creatingVersion || !draftForm.modelRef}>
                <Rocket className="mr-2 h-4 w-4" />
                {creatingVersion ? 'Creating Version...' : 'Create Draft Version'}
              </Button>
              <Button variant="outline" onClick={() => refetchVersions()} disabled={versionsLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh Versions
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.08fr_0.92fr]">
        <Card>
          <CardHeader>
            <CardTitle>Versions</CardTitle>
            <CardDescription>Publish a version before using the agent as a stable runtime entry.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {versionsLoading && <div className="text-sm text-muted-foreground">Loading versions...</div>}
            {!versionsLoading && versions.length === 0 && (
              <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                No versions found for this agent.
              </div>
            )}
            {!versionsLoading &&
              versions.map((version: AgentVersion) => {
                const spec = version.spec_json || {}
                const modelSpec = (spec.model as Record<string, unknown> | undefined) || {}
                const ragSpec = (spec.rag as Record<string, unknown> | undefined) || {}
                const knowledgeRefs = Array.isArray(ragSpec.knowledges)
                  ? ragSpec.knowledges.filter((item): item is string => typeof item === 'string')
                  : []

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
                        <Badge variant="outline">{typeof modelSpec.ref_key === 'string' ? modelSpec.ref_key : 'No model'}</Badge>
                        {knowledgeRefs.map((knowledgeId) => {
                          const knowledge = knowledgeOptions.find((item) => item.id === knowledgeId)
                          return (
                            <Badge key={knowledgeId} variant="secondary">
                              {knowledge?.name || knowledgeId}
                            </Badge>
                          )
                        })}
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
                            ? 'Published'
                            : publishingVersionId === version.id
                              ? 'Publishing...'
                              : 'Publish'}
                        </Button>
                        <Button variant="outline" onClick={() => navigate(`/chat/${agentId}`)}>
                          Open Chat
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
          </CardContent>
        </Card>

        <div className="grid gap-4">
          <Card>
            <CardHeader>
              <CardTitle>Assembly Catalog</CardTitle>
              <CardDescription>Runtime capabilities currently available in this workspace for future agent bindings.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {capabilityCatalogLoading && <div className="text-sm text-muted-foreground">Loading capability catalog...</div>}
              {!capabilityCatalogLoading &&
                Object.entries(capabilityCatalogGroups).map(([groupName, items]) => (
                  <div key={groupName} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium capitalize">{groupName}</div>
                      <Badge variant="outline">{items.length}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {items.slice(0, 3).map((item) => (
                        <Badge key={item.ref} variant="secondary">
                          {item.name}
                        </Badge>
                      ))}
                      {items.length > 3 && <Badge variant="outline">+{items.length - 3} more</Badge>}
                      {items.length === 0 && (
                        <div className="text-xs text-muted-foreground">No {groupName} capabilities registered.</div>
                      )}
                    </div>
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Bindings</CardTitle>
              <CardDescription>Bindings are grouped from the current version snapshot so assembly stays readable.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {bindingsLoading && <div className="text-sm text-muted-foreground">Loading bindings...</div>}
              {!bindingsLoading && bindings.length === 0 && (
                <div className="text-sm text-muted-foreground">No bindings yet. Create a draft version first.</div>
              )}
              {!bindingsLoading &&
                Object.entries(bindingGroups).map(([groupName, groupBindings]) => (
                  <div key={groupName} className="space-y-2">
                    <div className="text-xs font-medium uppercase tracking-[0.18em] text-muted-foreground">
                      {groupName}
                    </div>
                    {groupBindings.length === 0 ? (
                      <div className="rounded-lg border border-dashed px-3 py-2 text-sm text-muted-foreground">
                        No {groupName} bindings yet.
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
              <CardTitle>Releases</CardTitle>
              <CardDescription>Formal publish and rollback ledger exposed by the backend release API.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {releasesLoading && <div className="text-sm text-muted-foreground">Loading release history...</div>}
              {!releasesLoading && releases.length === 0 && (
                <div className="text-sm text-muted-foreground">No releases yet. Publish a version to create live history.</div>
              )}
              {!releasesLoading &&
                releases.map((release) => (
                  <div key={release.id} className="rounded-lg border px-3 py-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Badge variant={release.action === 'rollback' ? 'outline' : 'default'}>{renderReleaseAction(release)}</Badge>
                        <span className="font-medium">{release.to_version_id}</span>
                      </div>
                      <span className="text-xs text-muted-foreground">{formatTimestamp(release.created_at)}</span>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      {release.from_version_id ? `from ${release.from_version_id} -> ${release.to_version_id}` : `to ${release.to_version_id}`}
                    </div>
                    {release.notes && <div className="mt-2 text-xs text-muted-foreground">{release.notes}</div>}
                  </div>
                ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Runs</CardTitle>
              <CardDescription>Recent execution history for this agent.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {runsLoading && <div className="text-sm text-muted-foreground">Loading runs...</div>}
              {!runsLoading && recentRuns.length === 0 && (
                <div className="text-sm text-muted-foreground">No runs yet. Publish the agent and start a chat.</div>
              )}
              {!runsLoading &&
                recentRuns.map((run: RunResponse) => (
                  <button
                    key={run.id}
                    type="button"
                    onClick={() => navigate(`/observability/runs/${run.id}`)}
                    className="w-full rounded-lg border p-3 text-left transition-colors hover:border-primary/40"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium">{run.mode}</div>
                      <Badge variant={run.status === 'completed' ? 'default' : 'outline'}>{run.status}</Badge>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{formatTimestamp(run.started_at)}</div>
                    <div className="mt-2 line-clamp-2 text-sm text-muted-foreground">
                      {run.input_summary || run.output_summary || run.error_message || 'No summary available.'}
                    </div>
                  </button>
                ))}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="flex justify-end">
        <Button variant="ghost" onClick={() => navigate('/agents')}>
          Back to Agents
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>
        </>
      )}
    </div>
  )
}

export default AgentDetailPage
