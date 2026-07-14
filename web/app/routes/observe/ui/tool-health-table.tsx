import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { ToolHealthSummary } from '@/services/observe-service'

type ToolHealthTableProps = {
  tools: ToolHealthSummary[]
}

const statusVariant = (status: ToolHealthSummary['health_status']) => {
  if (status === 'healthy') return 'default'
  if (status === 'warning') return 'secondary'
  if (status === 'critical') return 'destructive'
  return 'outline'
}

const formatRate = (value: number) => `${Math.round(value * 100)}%`

export function ToolHealthTable({ tools }: ToolHealthTableProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Tool Reliability</CardTitle>
      </CardHeader>
      <CardContent>
        {!tools.length ? (
          <div className="text-sm text-muted-foreground">No tool calls recorded yet.</div>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tool</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Calls</TableHead>
                <TableHead>Failed</TableHead>
                <TableHead>Failure Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.tool_ref}>
                  <TableCell className="font-medium">{tool.tool_ref}</TableCell>
                  <TableCell>
                    <Badge variant={statusVariant(tool.health_status)}>{tool.health_status}</Badge>
                  </TableCell>
                  <TableCell>{tool.call_count}</TableCell>
                  <TableCell>{tool.failed_call_count}</TableCell>
                  <TableCell>{formatRate(tool.failure_rate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
