import { useMemo, useState } from 'react'
import { Activity, ArrowRight, Bot, Plus, RefreshCw, ScrollText, Workflow } from 'lucide-react'
import { toast } from 'sonner'

import { NavLayout } from '@/components/layout/nav-layout'
import { PageStatus } from '@/components/common/page-status'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useNavigate } from '@/hooks/use-navigate'
import { useTranslation } from '@/i18n'
import { createAgent, listAgents, type Agent } from '@/services/agent-service'

function AgentsPage() {
  const navigate = useNavigate()
  const { t } = useTranslation()
  const [draftName, setDraftName] = useState('')
  const [draftDescription, setDraftDescription] = useState('')
  const [search, setSearch] = useState('')

  const quickActions = [
    {
      title: t('agent.workspace.quickActions.chat.title'),
      description: t('agent.workspace.quickActions.chat.description'),
      href: '/chat',
      icon: Bot,
    },
    {
      title: t('agent.workspace.quickActions.workflow.title'),
      description: t('agent.workspace.quickActions.workflow.description'),
      href: '/workflow',
      icon: Workflow,
    },
    {
      title: t('agent.workspace.quickActions.knowledge.title'),
      description: t('agent.workspace.quickActions.knowledge.description'),
      href: '/knowledge',
      icon: ScrollText,
    },
    {
      title: t('agent.workspace.quickActions.runs.title'),
      description: t('agent.workspace.quickActions.runs.description'),
      href: '/runs',
      icon: Activity,
    },
  ]

  const {
    data: agentPage,
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ['agents', 'list'],
    queryFn: () => listAgents({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const createMutation = useMutation({
    mutationKey: ['agents', 'create'],
    mutationFn: () =>
      createAgent({
        name: draftName.trim(),
        description: draftDescription.trim() || undefined,
        visibility: 'private',
      }),
    onSuccess: (agent) => {
      setDraftName('')
      setDraftDescription('')
      refetch()
      toast.success(t('agent.workspace.created', { name: agent.name }))
      navigate(`/agents/${agent.id}`)
    },
    onError: (error: any) => {
      toast.error(error?.message || t('agent.workspace.createFailed'))
    },
  })

  const agents = useMemo(() => {
    const items = agentPage?.items || []
    if (!search.trim()) {
      return items
    }
    const keyword = search.trim().toLowerCase()
    return items.filter((agent: Agent) => {
      const haystack = [agent.name, agent.description || '', ...(agent.tags || [])]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
  }, [agentPage?.items, search])

  return (
    <NavLayout fixed className="bg-muted/20">
      <div className="flex flex-1 flex-col gap-6 p-6">
        <Card className="border-none bg-gradient-to-br from-slate-950 via-slate-900 to-slate-800 text-white shadow-xl">
          <CardHeader className="gap-4">
            <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
              {t('agent.workspace.badge')}
            </Badge>
            <div className="space-y-2">
              <CardTitle className="text-3xl font-semibold tracking-tight">
                {t('agent.workspace.title')}
              </CardTitle>
              <CardDescription className="max-w-2xl text-slate-300">
                {t('agent.workspace.description')}
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
            <div className="grid gap-3 sm:grid-cols-2">
              {quickActions.map((item) => (
                <button
                  key={item.title}
                  type="button"
                  onClick={() => navigate(item.href)}
                  className="rounded-2xl border border-white/10 bg-white/5 p-4 text-left transition-colors hover:bg-white/10"
                >
                  <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-white/10">
                    <item.icon className="h-5 w-5" />
                  </div>
                  <div className="text-sm font-medium">{item.title}</div>
                  <div className="mt-1 text-sm text-slate-300">{item.description}</div>
                </button>
              ))}
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/5 p-4">
              <div className="mb-3 text-sm font-medium">{t('agent.workspace.createTitle')}</div>
              <div className="space-y-3">
                <Input
                  value={draftName}
                  onChange={(event) => setDraftName(event.target.value)}
                  placeholder={t('agent.workspace.namePlaceholder')}
                  className="border-white/10 bg-white text-slate-950"
                />
                <Input
                  value={draftDescription}
                  onChange={(event) => setDraftDescription(event.target.value)}
                  placeholder={t('agent.workspace.descriptionPlaceholder')}
                  className="border-white/10 bg-white text-slate-950"
                />
                <Button
                  className="w-full bg-white text-slate-950 hover:bg-slate-100"
                  disabled={createMutation.isPending || !draftName.trim()}
                  onClick={() => createMutation.mutate(undefined)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  {t('agent.workspace.createAction')}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>{t('agent.workspace.listTitle')}</CardTitle>
              <CardDescription>{t('agent.workspace.listDescription')}</CardDescription>
            </div>
            <div className="flex gap-2">
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder={t('agent.workspace.searchPlaceholder')}
                className="w-[240px]"
              />
              <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {t('agent.workspace.refresh')}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading && (
              <PageStatus
                variant="loading"
                title={t('agent.workspace.loadingTitle')}
                description={t('agent.workspace.loadingDescription')}
              />
            )}
            {!isLoading && isError && (
              <PageStatus
                variant="error"
                title={t('agent.workspace.errorTitle')}
                description={error instanceof Error ? error.message : t('agent.workspace.errorDescription')}
                actionLabel={t('agent.workspace.retry')}
                onAction={() => refetch()}
              />
            )}
            {!isLoading && !isError && agents.length === 0 && (
              <PageStatus
                variant="empty"
                title={t('agent.workspace.emptyTitle')}
                description={t('agent.workspace.emptyDescription')}
              />
            )}
            {!isLoading && !isError && agents.length > 0 && (
              <div className="grid gap-4 xl:grid-cols-2">
                {agents.map((agent: Agent) => (
                  <Card key={agent.id} className="transition-colors hover:border-primary/40">
                    <CardHeader className="gap-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <CardTitle className="text-xl">{agent.name}</CardTitle>
                          <CardDescription>{agent.description || t('agent.workspace.noDescription')}</CardDescription>
                        </div>
                        <Badge variant={agent.published_version_id ? 'default' : 'outline'}>
                          {agent.published_version_id ? t('agent.workspace.published') : t('agent.workspace.draft')}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="outline">{agent.visibility}</Badge>
                        <Badge variant="outline">{agent.status}</Badge>
                        {(agent.tags || []).map((tag) => (
                          <Badge key={tag} variant="secondary">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                    </CardHeader>
                    <CardContent className="flex flex-wrap items-center gap-2">
                      <Button onClick={() => navigate(`/chat/${agent.id}`)}>
                        {t('agent.workspace.openChat')}
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/agents/${agent.id}`)}>
                        {t('agent.workspace.details')}
                      </Button>
                      <Button variant="outline" onClick={() => navigate('/workflow')}>
                        {t('agent.workspace.bindWorkflow')}
                      </Button>
                      <Button variant="ghost" onClick={() => navigate('/knowledge')}>
                        {t('agent.workspace.quickActions.knowledge.title')}
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => navigate(`/chat/${agent.id}`)}>
                        <ArrowRight className="h-4 w-4" />
                      </Button>
                    </CardContent>
                  </Card>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </NavLayout>
  )
}

export default AgentsPage
