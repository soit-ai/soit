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
import { createAgent, listAgents, type Agent } from '@/services/agent-service'

const quickActions = [
  {
    title: 'Chat',
    description: 'Run an agent in a threaded conversation surface.',
    href: '/chat',
    icon: Bot,
  },
  {
    title: 'Workflow',
    description: 'Design orchestration graphs and attach them as capabilities.',
    href: '/workflow',
    icon: Workflow,
  },
  {
    title: 'Knowledge',
    description: 'Manage retrieval sources and memory context.',
    href: '/knowledge',
    icon: ScrollText,
  },
  {
    title: 'Runs',
    description: 'Inspect recent execution history, failures, and latency.',
    href: '/runs',
    icon: Activity,
  },
]

function AgentsPage() {
  const navigate = useNavigate()
  const [draftName, setDraftName] = useState('')
  const [draftDescription, setDraftDescription] = useState('')
  const [search, setSearch] = useState('')

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
      toast.success(`Created ${agent.name}`)
      navigate(`/agents/${agent.id}`)
    },
    onError: (error: any) => {
      toast.error(error?.message || 'Failed to create agent')
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
              Agent Center
            </Badge>
            <div className="space-y-2">
              <CardTitle className="text-3xl font-semibold tracking-tight">
                Agent is now the primary workspace object.
              </CardTitle>
              <CardDescription className="max-w-2xl text-slate-300">
                Create an agent, attach workflow and knowledge capabilities, then run it through chat and task
                execution surfaces.
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
              <div className="mb-3 text-sm font-medium">Create Agent</div>
              <div className="space-y-3">
                <Input
                  value={draftName}
                  onChange={(event) => setDraftName(event.target.value)}
                  placeholder="Agent name"
                  className="border-white/10 bg-white text-slate-950"
                />
                <Input
                  value={draftDescription}
                  onChange={(event) => setDraftDescription(event.target.value)}
                  placeholder="Short description"
                  className="border-white/10 bg-white text-slate-950"
                />
                <Button
                  className="w-full bg-white text-slate-950 hover:bg-slate-100"
                  disabled={createMutation.isPending || !draftName.trim()}
                  onClick={() => createMutation.mutate(undefined)}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Create
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle>Agents</CardTitle>
              <CardDescription>Published and draft agents in the current workspace.</CardDescription>
            </div>
            <div className="flex gap-2">
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search agents"
                className="w-[240px]"
              />
              <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                Refresh
              </Button>
            </div>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <PageStatus
              variant="loading"
              title="Loading agents"
              description="Fetching the current workspace agent inventory."
            />
          )}
          {!isLoading && isError && (
            <PageStatus
              variant="error"
              title="Failed to load agents"
              description={error instanceof Error ? error.message : 'The agent list could not be loaded right now.'}
              actionLabel="Retry"
              onAction={() => refetch()}
            />
          )}
          {!isLoading && !isError && agents.length === 0 && (
            <PageStatus
              variant="empty"
              title="No agents yet"
              description="Create one above and start the Agent-centered flow."
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
                          <CardDescription>{agent.description || 'No description yet.'}</CardDescription>
                        </div>
                        <Badge variant={agent.published_version_id ? 'default' : 'outline'}>
                          {agent.published_version_id ? 'Published' : 'Draft'}
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
                        Open Chat
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/agents/${agent.id}`)}>
                        Details
                      </Button>
                      <Button variant="outline" onClick={() => navigate('/workflow')}>
                        Bind Workflow
                      </Button>
                      <Button variant="ghost" onClick={() => navigate('/knowledge')}>
                        Knowledge
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
