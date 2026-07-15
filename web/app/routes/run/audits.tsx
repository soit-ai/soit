import { useMemo } from 'react'
import { Link, useSearchParams } from 'react-router'
import { ArrowRight, RefreshCw, Search, ShieldCheck } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useQuery } from '@/hooks/use-query'
import { listRunAudits, type RunAuditLogResponse } from '@/services/run-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatTimestamp = (value?: string | null) => {
  if (!value) return '-'
  return formatDateTime(isoToZonedDate(value))
}

const previewPayload = (payload?: Record<string, unknown> | null) => {
  if (!payload || Object.keys(payload).length === 0) return '-'
  const text = JSON.stringify(payload)
  return text.length > 120 ? `${text.slice(0, 120)}...` : text
}

const auditStatus = (audit: RunAuditLogResponse) => {
  const success = audit.response?.success
  if (success === true) return 'allowed'
  if (success === false) return 'denied'
  return 'recorded'
}

function AuditExplorerPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const runId = searchParams.get('run_id') || ''
  const stepId = searchParams.get('step_id') || ''
  const stepType = searchParams.get('step_type') || ''
  const gatewayType = searchParams.get('gateway_type') || ''
  const pageToken = searchParams.get('page_token') || undefined

  const params = useMemo(() => ({
    run_id: runId || undefined,
    step_id: stepId || undefined,
    step_type: stepType || undefined,
    gateway_type: gatewayType || undefined,
    page_token: pageToken,
    page_size: 50,
  }), [gatewayType, pageToken, runId, stepId, stepType])

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['observe', 'audits', params],
    queryFn: () => listRunAudits(params),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const updateParams = (patch: Record<string, string>) => {
    const next = new URLSearchParams(searchParams)
    Object.entries(patch).forEach(([key, value]) => {
      if (value.trim()) next.set(key, value.trim())
      else next.delete(key)
    })
    next.delete('page_token')
    setSearchParams(next)
  }

  const resetFilters = () => {
    setSearchParams(new URLSearchParams())
  }

  const audits = data?.items || []

  return (
    <main className="flex min-w-0 flex-1 flex-col bg-background">
      <div className="mx-auto flex w-full min-w-0 flex-1 flex-col gap-4 px-5 py-5 lg:px-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-blue-600" />
              <h1 className="text-2xl font-semibold tracking-tight">Audit Explorer</h1>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Query governed tool, model, plugin, and policy gateway records across workspace runs.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={() => refetch()} disabled={isLoading}>
              <RefreshCw className="h-4 w-4" />
              Refresh
            </Button>
            <Button asChild>
              <Link to="/observe/runs?include_observe_summary=true">
                Run Explorer
                <ArrowRight className="h-4 w-4" />
              </Link>
            </Button>
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Audit Filters</CardTitle>
            <CardDescription>Use exact identifiers for incident review or leave Run ID blank for workspace-wide records.</CardDescription>
          </CardHeader>
          <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-[1fr_1fr_0.7fr_0.7fr_auto]">
            <Input aria-label="Run ID" placeholder="Run ID" defaultValue={runId} onBlur={(event) => updateParams({ run_id: event.target.value })} />
            <Input aria-label="Step ID" placeholder="Step ID" defaultValue={stepId} onBlur={(event) => updateParams({ step_id: event.target.value })} />
            <Input aria-label="Step Type" placeholder="Step type" defaultValue={stepType} onBlur={(event) => updateParams({ step_type: event.target.value })} />
            <Input aria-label="Gateway Type" placeholder="Gateway type" defaultValue={gatewayType} onBlur={(event) => updateParams({ gateway_type: event.target.value })} />
            <Button variant="outline" type="button" onClick={resetFilters}>
              <Search className="h-4 w-4" />
              Reset
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Audit Records</CardTitle>
            <CardDescription>Gateway status, request preview, and response preview for governed calls.</CardDescription>
          </CardHeader>
          <CardContent>
            {isError ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-sm text-destructive">Audit records could not be loaded.</div>
            ) : isLoading ? (
              <div className="text-sm text-muted-foreground">Loading audit records...</div>
            ) : audits.length === 0 ? (
              <div className="rounded-lg border border-dashed p-8 text-center text-sm text-muted-foreground">No audit records match the current filters.</div>
            ) : (
              <div className="overflow-x-auto">
                <Table className="min-w-[980px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Run</TableHead>
                      <TableHead>Step</TableHead>
                      <TableHead>Gateway</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Time</TableHead>
                      <TableHead>Preview</TableHead>
                      <TableHead>Request</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {audits.map((audit, index) => (
                      <TableRow key={`${audit.run_id}:${audit.step_id}:${index}`}>
                        <TableCell className="font-mono text-xs">{audit.run_id}</TableCell>
                        <TableCell>
                          <div className="text-sm font-medium">{audit.step_id}</div>
                          <div className="text-xs text-muted-foreground">{audit.step_type}</div>
                        </TableCell>
                        <TableCell>{audit.gateway_type || '-'}</TableCell>
                        <TableCell>
                          <Badge variant={auditStatus(audit) === 'denied' ? 'destructive' : auditStatus(audit) === 'allowed' ? 'default' : 'outline'}>
                            {auditStatus(audit)}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">{formatTimestamp(audit.timestamp)}</TableCell>
                        <TableCell className="max-w-[220px] truncate text-xs text-muted-foreground">{audit.preview || '-'}</TableCell>
                        <TableCell className="max-w-[260px] truncate font-mono text-xs text-muted-foreground">{previewPayload(audit.request)}</TableCell>
                        <TableCell className="text-right">
                          <Button asChild variant="outline" size="sm">
                            <Link to={`/observe/runs/${audit.run_id}`}>Open Run</Link>
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </main>
  )
}

export default AuditExplorerPage
