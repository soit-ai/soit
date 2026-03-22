import { Activity, ArrowRight, Coins, RefreshCw } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { getRunCostSummary, listRuns } from '@/services/run-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

function ObservabilityPage() {
  const navigate = useNavigate()

  const {
    data: runPage,
    isLoading: runsLoading,
    refetch: refetchRuns,
  } = useQuery({
    queryKey: ['observability', 'runs'],
    queryFn: () => listRuns({ page_size: 20 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: costSummary,
    isLoading: costsLoading,
    refetch: refetchCosts,
  } = useQuery({
    queryKey: ['observability', 'cost-summary'],
    queryFn: () => getRunCostSummary(),
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
            Observability
          </Badge>
          <CardTitle className="text-3xl font-semibold tracking-tight">Watch the runtime, not just the UI.</CardTitle>
          <CardDescription className="max-w-2xl text-zinc-300">
            Track current execution volume, inspect recent runs, and keep cost and failure trends visible while the
            runtime core continues to consolidate.
          </CardDescription>
        </CardHeader>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Prompt Tokens</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Coins className="h-5 w-5 text-amber-500" />
              {costsLoading ? '...' : costSummary?.tokens_prompt ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Completion Tokens</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Coins className="h-5 w-5 text-emerald-500" />
              {costsLoading ? '...' : costSummary?.tokens_completion ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardDescription>Total Runtime ms</CardDescription>
            <CardTitle className="flex items-center gap-2 text-2xl">
              <Activity className="h-5 w-5 text-sky-500" />
              {costsLoading ? '...' : costSummary?.ms_total ?? 0}
            </CardTitle>
          </CardHeader>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <CardTitle>Recent Runs</CardTitle>
            <CardDescription>Latest execution records across chat, agent, workflow, and tool activity.</CardDescription>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() => {
                refetchRuns()
                refetchCosts()
              }}
              disabled={runsLoading || costsLoading}
            >
              <RefreshCw className="mr-2 h-4 w-4" />
              Refresh
            </Button>
            <Button onClick={() => navigate('/observability/runs')}>
              Open Run Explorer
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {runsLoading && <div className="text-sm text-muted-foreground">Loading observability stream...</div>}
          {!runsLoading && !(runPage?.items || []).length && (
            <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
              No runs recorded yet.
            </div>
          )}
          {!runsLoading && (runPage?.items || []).length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Run</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Started</TableHead>
                  <TableHead>Duration</TableHead>
                  <TableHead>Summary</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(runPage?.items || []).map((run) => (
                  <TableRow key={run.id}>
                    <TableCell className="font-medium">{run.id}</TableCell>
                    <TableCell>{run.mode}</TableCell>
                    <TableCell>
                      <Badge variant={run.status === 'failed' ? 'destructive' : run.status === 'succeeded' ? 'default' : 'outline'}>
                        {run.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatTimestamp(run.started_at)}</TableCell>
                    <TableCell>{run.duration_ms ? `${run.duration_ms} ms` : '-'}</TableCell>
                    <TableCell className="max-w-[320px] truncate">{run.output_summary || run.input_summary || '-'}</TableCell>
                    <TableCell className="text-right">
                      <Button variant="ghost" size="icon" onClick={() => navigate(`/observability/runs/${run.id}`)}>
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
    </div>
  )
}

export default ObservabilityPage
