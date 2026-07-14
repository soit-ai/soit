import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useNavigate } from '@/hooks/use-navigate'
import type { AgentSummary } from '@/services/observe-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

type AgentHealthTableProps = {
  agents: AgentSummary[]
}

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

export function AgentHealthTable({ agents }: AgentHealthTableProps) {
  const navigate = useNavigate()

  return (
    <Card>
      <CardHeader>
        <CardTitle>Agent Health</CardTitle>
      </CardHeader>
      <CardContent>
        {!agents.length ? (
          <div className="text-sm text-muted-foreground">No agent-level runtime activity yet.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Agent</TableHead>
                <TableHead>Runs</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Last Run</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {agents.map((agent) => (
                <TableRow
                  key={agent.agent_id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/observe/runs?subject_id=${agent.agent_id}`)}
                >
                  <TableCell className="font-medium">{agent.agent_id}</TableCell>
                  <TableCell>{agent.run_count}</TableCell>
                  <TableCell>{agent.failed_run_count}</TableCell>
                  <TableCell>{formatTimestamp(agent.last_run_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
