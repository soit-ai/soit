import { Plus, RefreshCw, Search, Workflow as WorkflowIcon } from 'lucide-react'
import { useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { createWorkflow, listWorkflows, type Workflow } from '@/services/workflow-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function WorkflowBoxPage() {
  const navigate = useNavigate()
  const [search, setSearch] = useState('')
  const [newWorkflowName, setNewWorkflowName] = useState('')
  const [creating, setCreating] = useState(false)

  const {
    data: workflowPage,
    isLoading,
    refetch,
  } = useQuery({
    queryKey: ['workflow', 'list'],
    queryFn: () => listWorkflows({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const workflows = useMemo(() => {
    const items = workflowPage?.items || []
    if (!search.trim()) {
      return items
    }
    const keyword = search.trim().toLowerCase()
    return items.filter((workflow: Workflow) => {
      const haystack = [workflow.name, workflow.description || '', JSON.stringify(workflow.metadata_json || {})]
        .join(' ')
        .toLowerCase()
      return haystack.includes(keyword)
    })
  }, [search, workflowPage?.items])

  const handleCreate = async () => {
    const name = newWorkflowName.trim()
    if (!name) {
      return
    }
    try {
      setCreating(true)
      const workflow = await createWorkflow({
        name,
        description: 'Workflow builder entry created during agent-centered refactor.',
      })
      setNewWorkflowName('')
      await refetch()
      navigate(`/workflow/${workflow.id}/build`)
    } catch (error) {
      toast.error('Failed to create workflow')
      console.error('Failed to create workflow:', error)
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-sky-950 via-cyan-900 to-teal-800 text-white shadow-xl">
        <CardHeader>
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            Workflows
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">
            Workflows are becoming the agent orchestration surface.
          </CardTitle>
          <CardDescription className="max-w-2xl text-cyan-100/80">
            Build multi-step execution graphs, keep versions visible, and route into the new runtime model.
          </CardDescription>
        </CardHeader>
      </Card>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Workflow Registry</CardTitle>
            <CardDescription>Build, publish, and monitor workflow graphs from the agent-centered orchestration surface.</CardDescription>
          </div>
          <div className="flex flex-wrap gap-2">
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Search workflows"
                className="w-[260px] pl-9"
              />
            </div>
            <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-col gap-2 rounded-xl border border-dashed p-4 lg:flex-row">
            <Input
              value={newWorkflowName}
              onChange={(event) => setNewWorkflowName(event.target.value)}
              placeholder="New workflow name"
              className="lg:max-w-sm"
            />
            <Button onClick={handleCreate} disabled={creating || !newWorkflowName.trim()}>
              <Plus className="mr-2 h-4 w-4" />
              Create Workflow
            </Button>
          </div>

          {isLoading && <div className="text-sm text-muted-foreground">Loading workflows...</div>}
          {!isLoading && workflows.length === 0 && (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No workflows found.
            </div>
          )}

          {!isLoading && workflows.length > 0 && (
            <div className="grid gap-4 xl:grid-cols-2">
              {workflows.map((workflow: Workflow) => (
                <Card key={workflow.id} className="transition-colors hover:border-primary/40">
                  <CardHeader className="gap-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="space-y-1">
                        <CardTitle className="flex items-center gap-2 text-xl">
                          <WorkflowIcon className="h-5 w-5" />
                          {workflow.name}
                        </CardTitle>
                        <CardDescription>{workflow.description || 'No description yet.'}</CardDescription>
                      </div>
                      <Badge variant="outline">{workflow.current_version_id ? 'Versioned' : 'Draft'}</Badge>
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="grid gap-2 text-sm text-muted-foreground sm:grid-cols-2">
                      <div>Current version: {workflow.current_version_id || '-'}</div>
                      <div>Updated: {formatTimestamp(workflow.updated_at)}</div>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button onClick={() => navigate(`/workflow/${workflow.id}/build`)}>
                        Open Builder
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/workflow/${workflow.id}/publish`)}>
                        Publish
                      </Button>
                      <Button variant="outline" onClick={() => navigate(`/workflow/${workflow.id}/monitor`)}>
                        Monitor
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default WorkflowBoxPage
