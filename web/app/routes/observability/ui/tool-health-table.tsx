import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import type { ToolHealthSummary } from '@/services/observability-service'

type ToolHealthTableProps = {
  tools: ToolHealthSummary[]
}

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
                <TableHead>Calls</TableHead>
                <TableHead>Failed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tools.map((tool) => (
                <TableRow key={tool.tool_ref}>
                  <TableCell className="font-medium">{tool.tool_ref}</TableCell>
                  <TableCell>{tool.call_count}</TableCell>
                  <TableCell>{tool.failed_call_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  )
}
