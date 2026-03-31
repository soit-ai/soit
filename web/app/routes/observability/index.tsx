import { Activity, ArrowRight, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { getObservabilityDashboard } from '@/services/observability-service'

import { AgentHealthTable } from './ui/agent-health-table'
import { ToolHealthTable } from './ui/tool-health-table'
import { WorkspaceSummaryCards } from './ui/workspace-summary'

function ObservabilityPage() {
  const navigate = useNavigate()
  const { data: dashboard, isLoading, refetch } = useQuery({
    queryKey: ['observability', 'dashboard'],
    queryFn: () => getObservabilityDashboard(),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <Card className="border-none bg-gradient-to-br from-zinc-950 via-zinc-900 to-zinc-800 text-white shadow-xl">
        <CardHeader className="gap-3">
          <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
            Workspace Console
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">Observe the workspace before drilling into runs.</CardTitle>
          <CardDescription className="max-w-2xl text-zinc-300">
            Workspace health, agent summaries, workflow bottlenecks, knowledge quality, and tool reliability all roll up here first.
          </CardDescription>
        </CardHeader>
      </Card>

      <WorkspaceSummaryCards summary={dashboard?.workspace_summary} />

      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
        <Button onClick={() => navigate('/observability/runs')}>
          Open Run Explorer
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>
      </div>

      <Tabs defaultValue="agents">
        <TabsList variant="line">
          <TabsTrigger value="agents">Agent Health</TabsTrigger>
          <TabsTrigger value="workflows">Workflow Bottlenecks</TabsTrigger>
          <TabsTrigger value="tools">Tool Reliability</TabsTrigger>
          <TabsTrigger value="knowledge">Knowledge Quality</TabsTrigger>
        </TabsList>

        <TabsContent value="agents">
          <AgentHealthTable agents={dashboard?.agent_summaries || []} />
        </TabsContent>

        <TabsContent value="workflows">
          <Card>
            <CardHeader>
              <CardTitle>Workflow Bottlenecks</CardTitle>
            </CardHeader>
            <CardContent>
              {!dashboard?.workflow_bottlenecks?.length ? (
                <div className="text-sm text-muted-foreground">No workflow bottlenecks recorded yet.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Node</TableHead>
                      <TableHead>Steps</TableHead>
                      <TableHead>Failed</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard.workflow_bottlenecks.map((item) => (
                      <TableRow key={item.node_id}>
                        <TableCell className="font-medium">{item.node_id}</TableCell>
                        <TableCell>{item.step_count}</TableCell>
                        <TableCell>{item.failed_step_count}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tools">
          <ToolHealthTable tools={dashboard?.tool_health || []} />
        </TabsContent>

        <TabsContent value="knowledge">
          <div className="grid gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Knowledge Quality</CardTitle>
              </CardHeader>
              <CardContent>
                {!dashboard?.knowledge_quality?.length ? (
                  <div className="text-sm text-muted-foreground">No retrieval quality events recorded yet.</div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Signal</TableHead>
                        <TableHead>Events</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dashboard.knowledge_quality.map((item) => (
                        <TableRow key={item.step_type}>
                          <TableCell className="font-medium">{item.step_type}</TableCell>
                          <TableCell>{item.event_count}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Model Cost</CardTitle>
              </CardHeader>
              <CardContent>
                {!dashboard?.model_costs?.length ? (
                  <div className="text-sm text-muted-foreground">No model cost data recorded yet.</div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Model</TableHead>
                        <TableHead>Cost</TableHead>
                        <TableHead>Tokens</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {dashboard.model_costs.map((item) => (
                        <TableRow key={item.model_ref}>
                          <TableCell className="font-medium">{item.model_ref}</TableCell>
                          <TableCell>{item.total_cost_usd.toFixed(2)}</TableCell>
                          <TableCell>{item.total_tokens}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5 text-sky-500" />
            Approval Summary
          </CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border p-4">
            <div className="text-sm text-muted-foreground">Pending</div>
            <div className="mt-2 text-2xl font-semibold">{dashboard?.approvals_summary.pending ?? '...'}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="text-sm text-muted-foreground">Approved</div>
            <div className="mt-2 text-2xl font-semibold">{dashboard?.approvals_summary.approved ?? '...'}</div>
          </div>
          <div className="rounded-lg border p-4">
            <div className="text-sm text-muted-foreground">Rejected</div>
            <div className="mt-2 text-2xl font-semibold">{dashboard?.approvals_summary.rejected ?? '...'}</div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

export default ObservabilityPage
