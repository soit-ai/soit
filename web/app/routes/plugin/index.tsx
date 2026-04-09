import { useMemo } from 'react'
import { Clock3, Database, Puzzle, Shapes } from 'lucide-react'

import { NavLayout } from '@/components/layout/nav-layout'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useNavigate } from '@/hooks/use-navigate'
import { useQuery } from '@/hooks/use-query'
import { useCapabilityGovernanceUsage } from '@/hooks/use-capability-governance-usage'
import {
  formatCapabilityMetadataValue,
  getCapabilityMetadataEntries,
  listCapabilityRegistry,
  type CapabilityRegistryItem,
} from '@/services/capability-service'
import { formatDateTime, isoToZonedDate } from '@/utils/date-time'

const formatSourceLabel = (item: CapabilityRegistryItem) => {
  const segments = [item.source_kind]
  if (item.source_id) {
    segments.push(item.source_id)
  }
  if (item.source_version) {
    segments.push(`v${item.source_version}`)
  }
  return segments.join(' · ')
}

const summarizeSourceKinds = (items: CapabilityRegistryItem[]) => {
  return items.reduce<Record<string, number>>((acc, item) => {
    acc[item.source_kind] = (acc[item.source_kind] || 0) + 1
    return acc
  }, {})
}

const formatTimestamp = (value?: string | null) => {
  if (!value) {
    return '-'
  }
  return formatDateTime(isoToZonedDate(value))
}

export default function PluginPage() {
  const navigate = useNavigate()
  const { data, isLoading } = useQuery({
    queryKey: ['capabilities', 'plugin'],
    queryFn: () => listCapabilityRegistry({ source_kind: 'plugin', page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const capabilityItems = data?.items || []
  const sourceKinds = useMemo(() => summarizeSourceKinds(capabilityItems), [capabilityItems])
  const metadataFieldCount = useMemo(
    () => capabilityItems.reduce((count, item) => count + Object.keys(item.metadata_json || {}).length, 0),
    [capabilityItems]
  )
  const { boundAgents, recentRuns, isLoading: usageLoading } = useCapabilityGovernanceUsage(
    capabilityItems.map((item) => item.ref)
  )

  return (
    <NavLayout fixed className="bg-muted/20">
      <div className="flex flex-1 flex-col gap-6 p-6">
        <Card className="border-none bg-gradient-to-br from-amber-950 via-stone-900 to-stone-800 text-white shadow-xl">
          <CardHeader className="gap-4">
            <Badge variant="secondary" className="w-fit bg-white/10 text-white hover:bg-white/10">
              Capability Governance
            </Badge>
            <div className="space-y-2">
              <CardTitle className="flex items-center gap-3 text-3xl font-semibold tracking-tight">
                <Puzzle className="h-7 w-7" />
                Plugins
              </CardTitle>
              <CardDescription className="max-w-2xl text-stone-300">
                Inspect runtime capabilities sourced from plugins, their source metadata, and the registry entries available for
                governance.
              </CardDescription>
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-3">
              <Card className="border-white/10 bg-white/5 text-white">
                <CardHeader className="pb-2">
                  <CardDescription className="text-stone-300">Plugin-sourced capabilities</CardDescription>
                  <CardTitle className="text-2xl">{capabilityItems.length}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="border-white/10 bg-white/5 text-white">
                <CardHeader className="pb-2">
                  <CardDescription className="text-stone-300">Source kinds</CardDescription>
                  <CardTitle className="text-2xl">{Object.keys(sourceKinds).length}</CardTitle>
                </CardHeader>
              </Card>
              <Card className="border-white/10 bg-white/5 text-white">
                <CardHeader className="pb-2">
                  <CardDescription className="text-stone-300">Metadata fields</CardDescription>
                  <CardTitle className="text-2xl">{metadataFieldCount}</CardTitle>
                </CardHeader>
              </Card>
            </div>
          </CardContent>
        </Card>

        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Database className="h-4 w-4" />
                Source Mix
              </CardTitle>
              <CardDescription>Where the plugin-sourced capabilities originate from.</CardDescription>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.keys(sourceKinds).length === 0 && (
                <span className="text-sm text-muted-foreground">
                  {isLoading ? 'Loading registry...' : 'No plugin-sourced capabilities yet.'}
                </span>
              )}
              {Object.entries(sourceKinds).map(([sourceKind, count]) => (
                <Badge key={sourceKind} variant="outline">
                  {sourceKind} · {count}
                </Badge>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Shapes className="h-4 w-4" />
                Source Metadata
              </CardTitle>
              <CardDescription>Registry provenance for plugin-sourced capabilities.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3 text-sm text-muted-foreground">
              {capabilityItems.slice(0, 3).map((item) => (
                <div key={item.ref} className="space-y-1 rounded-lg border p-3">
                  <div className="font-medium text-foreground">{item.name}</div>
                  <div>{formatSourceLabel(item)}</div>
                  <div className="flex flex-wrap gap-2">
                    {getCapabilityMetadataEntries(item).map((entry) => (
                      <Badge key={`${item.ref}-${entry.key}`} variant="secondary">
                        {entry.key}: {formatCapabilityMetadataValue(entry.value)}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
              {capabilityItems.length === 0 && (
                <div>{isLoading ? 'Loading provenance...' : 'No source metadata is available yet.'}</div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Clock3 className="h-4 w-4" />
                Governance Notes
              </CardTitle>
              <CardDescription>Operational signals are shown when the registry exposes them.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-2 text-sm text-muted-foreground">
              <div>Capability refs are stable anchors for runtime bindings.</div>
              <div>Source IDs and versions are shown when they are present.</div>
              <div>Metadata JSON is rendered directly so governance data stays intact.</div>
            </CardContent>
          </Card>
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Bound By Agents</CardTitle>
              <CardDescription>Agents currently binding plugin-sourced runtime capabilities.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {boundAgents.length === 0 && (
                <div className="text-sm text-muted-foreground">
                  {usageLoading ? 'Loading bindings...' : 'No agents are currently bound to plugin-sourced capabilities.'}
                </div>
              )}
              {boundAgents.map((agent) => (
                <div key={agent.agentId} className="rounded-lg border p-3">
                  <div className="font-medium">{agent.agentName}</div>
                  <div className="mt-1 text-xs text-muted-foreground">{agent.agentId}</div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {agent.capabilityRefs.map((ref) => (
                      <Badge key={`${agent.agentId}-${ref}`} variant="outline">
                        {ref}
                      </Badge>
                    ))}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Recent Runtime Usage</CardTitle>
              <CardDescription>Latest runs emitted by agents currently bound to plugin-sourced capabilities.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentRuns.length === 0 && (
                <div className="text-sm text-muted-foreground">
                  {usageLoading ? 'Loading runtime usage...' : 'No recent runtime usage found for bound agents.'}
                </div>
              )}
              {recentRuns.map((run) => (
                <div key={run.id} className="rounded-lg border p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{run.mode}</div>
                      <div className="mt-1 text-xs text-muted-foreground">{run.subject_id || run.id}</div>
                    </div>
                    <Badge variant="outline">{run.status}</Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">Started: {formatTimestamp(run.started_at)}</div>
                  <div className="mt-3 flex justify-end">
                    <Button variant="ghost" size="sm" onClick={() => navigate(`/observability/runs/${run.id}`)}>
                      Open Run
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Puzzle className="h-4 w-4" />
              Plugin-Sourced Capabilities
            </CardTitle>
            <CardDescription>Runtime capability entries projected from plugin installation and publication surfaces.</CardDescription>
          </CardHeader>
          <CardContent>
            {capabilityItems.length === 0 && (
              <div className="rounded-xl border border-dashed p-8 text-center text-sm text-muted-foreground">
                {isLoading ? 'Loading plugin capabilities...' : 'No plugin-sourced capabilities found in the registry.'}
              </div>
            )}
            {capabilityItems.length > 0 && (
              <div className="grid gap-4 xl:grid-cols-2">
                {capabilityItems.map((item) => (
                  <Card key={item.ref} className="transition-colors hover:border-primary/40">
                    <CardHeader className="gap-3">
                      <div className="flex items-start justify-between gap-3">
                        <div className="space-y-1">
                          <CardTitle className="flex items-center gap-2 text-xl">
                            <Puzzle className="h-5 w-5" />
                            {item.name}
                          </CardTitle>
                          <CardDescription className="break-all text-xs text-muted-foreground">
                            {item.ref}
                          </CardDescription>
                        </div>
                        <Badge variant="outline">{item.kind}</Badge>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <Badge variant="secondary">{item.source_kind}</Badge>
                        {item.source_version && <Badge variant="outline">v{item.source_version}</Badge>}
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="text-sm text-muted-foreground">{formatSourceLabel(item)}</div>
                      {item.source_id && <div className="text-sm text-muted-foreground">Source ID: {item.source_id}</div>}
                      <div className="flex flex-wrap gap-2">
                        {getCapabilityMetadataEntries(item).map((entry) => (
                          <Badge key={`${item.ref}-${entry.key}`} variant="outline">
                            {entry.key}: {entry.value}
                          </Badge>
                        ))}
                      </div>
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
