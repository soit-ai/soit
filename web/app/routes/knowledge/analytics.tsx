import { useParams } from 'react-router'
import { ArrowLeft, ArrowRight, BarChart3, Coins, Link2 } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import {
  getKnowledgeBase,
  getKnowledgeRunCostByMode,
  getKnowledgeRunCostSummary,
  listKnowledgeUsages,
  listKnowledgeRuns,
} from '@/services/knowledge-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function KnowledgeAnalyticsPage() {
  const { knowledgeId = '' } = useParams()
  const navigate = useNavigate()

  const { data: knowledge } = useQuery({
    queryKey: ['knowledge', knowledgeId],
    queryFn: () => getKnowledgeBase(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: costSummary } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'cost-summary'],
    queryFn: () => getKnowledgeRunCostSummary(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: costByMode = [] } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'cost-by-mode'],
    queryFn: () => getKnowledgeRunCostByMode(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: runPage } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'runs'],
    queryFn: () => listKnowledgeRuns(knowledgeId, { page_size: 20 }),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const { data: usages = [] } = useQuery({
    queryKey: ['knowledge', knowledgeId, 'usages'],
    queryFn: () => listKnowledgeUsages(knowledgeId),
    options: {
      enabled: Boolean(knowledgeId),
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex items-center justify-between gap-3">
        <Button variant="ghost" onClick={() => navigate(`/knowledge/${knowledgeId}`)}>
          <ArrowLeft className="mr-2 h-4 w-4" />
          Back to Knowledge
        </Button>
        {knowledge && <Badge variant="outline">{knowledge.status}</Badge>}
      </div>

      <Card className="border-none bg-gradient-to-br from-amber-100 via-orange-50 to-white shadow-sm">
        <CardHeader>
          <Badge variant="secondary" className="w-fit">
            Analytics
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">{knowledge?.name || 'Knowledge analytics'}</CardTitle>
          <CardDescription>
            Inspect runtime cost, linked agents and workflows, and recent execution activity.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Prompt Tokens</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Coins className="h-5 w-5 text-amber-500" />
              {costSummary?.tokens_prompt ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completion Tokens</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Coins className="h-5 w-5 text-emerald-500" />
              {costSummary?.tokens_completion ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Runtime ms</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <BarChart3 className="h-5 w-5 text-sky-500" />
              {costSummary?.ms_total ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent Runs</CardTitle>
            <CardDescription>Latest runtime activity associated with this knowledge base.</CardDescription>
          </CardHeader>
          <CardContent>
            {!(runPage?.items || []).length && (
              <div className="text-sm text-muted-foreground">No runs recorded yet.</div>
            )}
            {(runPage?.items || []).length > 0 && (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Mode</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {(runPage?.items || []).map((run) => (
                    <TableRow key={run.id}>
                      <TableCell className="font-medium">{run.id}</TableCell>
                      <TableCell>{run.mode}</TableCell>
                      <TableCell>
                        <Badge variant="outline">{run.status}</Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="icon" onClick={() => navigate(`/observe/runs/${run.id}`)}>
                          <ArrowRight className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Bound Usages</CardTitle>
            <CardDescription>Agents and workflows currently referencing this knowledge base.</CardDescription>
          </CardHeader>
          <CardContent>
            {usages.length === 0 && (
              <div className="text-sm text-muted-foreground">No usages linked yet.</div>
            )}
            {usages.length > 0 && (
              <div className="space-y-3">
                {usages.map((item) => (
                  <div key={item.resource_version_id} className="rounded-lg border p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <div className="flex items-center gap-2 font-medium">
                          <Link2 className="h-4 w-4 text-muted-foreground" />
                          {item.resource_name}
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {item.resource_kind} · v{item.resource_version}
                        </div>
                      </div>
                      <Badge variant="outline">{item.resource_status}</Badge>
                    </div>
                    <div className="mt-2 text-xs text-muted-foreground">
                      Last run: {formatTimestamp(item.last_run_at)} · Run count: {item.run_count}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cost By Mode</CardTitle>
        </CardHeader>
        <CardContent>
          {costByMode.length === 0 && <div className="text-sm text-muted-foreground">No cost data available.</div>}
          {costByMode.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Mode</TableHead>
                  <TableHead>Prompt Tokens</TableHead>
                  <TableHead>Completion Tokens</TableHead>
                  <TableHead>Total Runtime ms</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {costByMode.map((item) => (
                  <TableRow key={item.mode}>
                    <TableCell>{item.mode}</TableCell>
                    <TableCell>{item.tokens_prompt}</TableCell>
                    <TableCell>{item.tokens_completion}</TableCell>
                    <TableCell>{item.ms_total}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default KnowledgeAnalyticsPage
