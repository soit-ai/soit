import {
  AlertTriangle,
  CheckCircle2,
  Database,
  FileCog,
  MoreHorizontal,
  PackageCheck,
  PackagePlus,
  Play,
  Plug,
  RefreshCw,
  ShieldCheck,
  SquareArrowOutUpRight,
  Upload,
} from 'lucide-react'
import type { ComponentProps, DragEvent } from 'react'
import { useEffect, useMemo, useState } from 'react'
import { toast } from 'sonner'

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
  MetricStrip,
} from '@/components/box'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { useCapabilityGovernanceUsage } from '@/hooks/use-capability-governance-usage'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import {
  installPlugin,
  listPluginCapabilities,
  listPlugins,
  reloadPluginRuntime,
  setPluginEnabled,
  uninstallPlugin,
  upgradePluginPackage,
  uploadPluginPackage,
  type Plugin,
  type PluginCapability,
} from '@/services/plugin-service'

type PluginWorkbenchType = 'plugin' | 'skill' | 'mcp' | 'tool' | 'workflow_node' | 'mixed'
type PluginSourceBucket = 'official' | 'community' | 'private'
type PluginRisk = 'low' | 'medium' | 'high' | 'none'
type PluginStatus = 'running' | 'enabled' | 'available' | 'disabled'

interface PluginWorkbenchRow {
  id: string
  rowKind: 'capability' | 'plugin'
  name: string
  ref: string
  type: PluginWorkbenchType
  version?: string | null
  publisher?: string | null
  status: PluginStatus
  source: PluginSourceBucket
  risk: PluginRisk
  description?: string | null
  tags: string[]
  permissions: string[]
  dependencies: string[]
  compatibleWith: string[]
  todayCalls: number
  boundAgentNames: string[]
  rawPlugin?: Plugin
  rawCapability?: PluginCapability
}

type PluginMetricDefinition = Omit<ComponentProps<typeof MetricStrip>['items'][number], 'label' | 'value'> & {
  labelKey: TranslationKey
  value: string
}

const PAGE_SIZE = 10

const typeLabelKeys = {
  plugin: 'plugin.workspaceDashboard.types.plugin',
  skill: 'plugin.workspaceDashboard.types.skill',
  mcp: 'plugin.workspaceDashboard.types.mcp',
  tool: 'plugin.workspaceDashboard.types.tool',
  workflow_node: 'plugin.workspaceDashboard.types.workflowNode',
  mixed: 'plugin.workspaceDashboard.types.mixed',
} satisfies Record<PluginWorkbenchType, TranslationKey>

const sourceLabelKeys = {
  official: 'plugin.workspaceDashboard.sources.official',
  community: 'plugin.workspaceDashboard.sources.community',
  private: 'plugin.workspaceDashboard.sources.private',
} satisfies Record<PluginSourceBucket, TranslationKey>

const riskLabelKeys = {
  low: 'plugin.workspaceDashboard.risk.low',
  medium: 'plugin.workspaceDashboard.risk.medium',
  high: 'plugin.workspaceDashboard.risk.high',
  none: 'plugin.workspaceDashboard.risk.none',
} satisfies Record<PluginRisk, TranslationKey>

const statusLabelKeys = {
  running: 'plugin.workspaceDashboard.status.running',
  enabled: 'plugin.workspaceDashboard.status.enabled',
  available: 'plugin.workspaceDashboard.status.available',
  disabled: 'plugin.workspaceDashboard.status.disabled',
} satisfies Record<PluginStatus, TranslationKey>

const statusClassName = {
  running: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  enabled: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  available: 'border-border bg-muted text-muted-foreground',
  disabled: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200',
} satisfies Record<PluginStatus, string>

const riskClassName = {
  low: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  medium: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200',
  high: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  none: 'border-border bg-muted text-muted-foreground',
} satisfies Record<PluginRisk, string>

function formatNumber(value: number) {
  return value.toLocaleString()
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.map((item) => String(item)).filter(Boolean)
}

function readMetadataString(metadata: Record<string, unknown> | null | undefined, keys: string[]) {
  for (const key of keys) {
    const value = metadata?.[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return null
}

function resolveType(plugin?: Plugin, capability?: PluginCapability): PluginWorkbenchType {
  const raw = capability?.artifact_kind || capability?.kind || plugin?.plugin_type || 'plugin'
  if (raw === 'mcp_server' || raw === 'mcp') return 'mcp'
  if (raw === 'skill') return 'skill'
  if (raw === 'tool') return 'tool'
  if (raw === 'workflow_node') return 'workflow_node'
  if (raw === 'mixed') return 'mixed'
  return 'plugin'
}

function resolveStatus(plugin?: Plugin): PluginStatus {
  if (!plugin) return 'available'
  if (plugin.installed && plugin.enabled) return 'running'
  if (plugin.installed && plugin.enabled === false) return 'disabled'
  if (plugin.installed) return 'enabled'
  return 'available'
}

function resolveSource(plugin?: Plugin): PluginSourceBucket {
  const metadata = plugin?.metadata_json
  const source = readMetadataString(metadata, ['source', 'source_bucket', 'sourceKind'])?.toLowerCase()
  if (source === 'private' || source === 'internal') return 'private'
  if (source === 'community') return 'community'
  if (source === 'official') return 'official'
  const publisher = plugin?.publisher?.toLowerCase() || ''
  if (publisher.includes('official') || publisher.includes('soit')) return 'official'
  return plugin?.publish_status === 'private' ? 'private' : 'community'
}

function resolveRisk(plugin?: Plugin, capability?: PluginCapability): PluginRisk {
  const risk = (
    readMetadataString(capability?.metadata_json, ['risk', 'risk_level']) ||
    readMetadataString(plugin?.metadata_json, ['risk', 'risk_level']) ||
    ''
  ).toLowerCase()
  if (risk === 'high') return 'high'
  if (risk === 'medium' || risk === 'middle') return 'medium'
  if (risk === 'low') return 'low'
  return 'none'
}

function resolveTags(plugin?: Plugin, capability?: PluginCapability) {
  return Array.from(new Set([
    ...asStringArray(capability?.metadata_json?.tags),
    ...asStringArray(plugin?.metadata_json?.tags),
  ]))
}

function resolvePermissions(plugin?: Plugin, capability?: PluginCapability) {
  return Array.from(new Set([
    ...asStringArray(capability?.metadata_json?.permissions),
    ...asStringArray(plugin?.metadata_json?.permissions),
    ...asStringArray(plugin?.manifest_json?.permissions),
  ]))
}

function resolveDependencies(plugin?: Plugin, capability?: PluginCapability) {
  return Array.from(new Set([
    ...asStringArray(capability?.metadata_json?.dependencies),
    ...asStringArray(plugin?.metadata_json?.dependencies),
    ...asStringArray(plugin?.manifest_json?.dependencies),
  ]))
}

function resolveCompatibleWith(plugin?: Plugin, capability?: PluginCapability) {
  const values = [
    ...asStringArray(capability?.metadata_json?.compatible_with),
    ...asStringArray(plugin?.metadata_json?.compatible_with),
    ...resolveTags(plugin, capability),
  ]
  return Array.from(new Set(values)).slice(0, 4)
}

function resolveDescription(plugin?: Plugin, capability?: PluginCapability) {
  const metadataDescription = readMetadataString(capability?.metadata_json, ['description', 'summary'])
  return metadataDescription || plugin?.description || null
}

function buildRows(
  plugins: Plugin[],
  capabilities: PluginCapability[],
  boundAgentMap: Map<string, string[]>,
  runCountMap: Map<string, number>,
): PluginWorkbenchRow[] {
  const pluginMap = new Map(plugins.map((plugin) => [plugin.id, plugin]))
  if (capabilities.length > 0) {
    const capabilityRows = capabilities.map((capability) => {
      const plugin = pluginMap.get(capability.plugin_id || capability.source_id || '')
      const type = resolveType(plugin, capability)
      return {
        id: capability.ref,
        rowKind: 'capability' as const,
        name: plugin?.name || capability.name,
        ref: capability.ref,
        type,
        version: capability.source_version || plugin?.version,
        publisher: plugin?.publisher,
        status: resolveStatus(plugin),
        source: resolveSource(plugin),
        risk: resolveRisk(plugin, capability),
        description: resolveDescription(plugin, capability),
        tags: resolveTags(plugin, capability),
        permissions: resolvePermissions(plugin, capability),
        dependencies: resolveDependencies(plugin, capability),
        compatibleWith: resolveCompatibleWith(plugin, capability),
        todayCalls: runCountMap.get(capability.ref) || 0,
        boundAgentNames: boundAgentMap.get(capability.ref) || [],
        rawPlugin: plugin,
        rawCapability: capability,
      }
    })
    const representedPluginIds = new Set(capabilities.map((capability) => capability.plugin_id || capability.source_id).filter(Boolean))
    const pluginOnlyRows = plugins
      .filter((plugin) => !representedPluginIds.has(plugin.id))
      .map((plugin) => {
        const type = resolveType(plugin)
        return {
          id: plugin.id,
          rowKind: 'plugin' as const,
          name: plugin.name,
          ref: plugin.id,
          type,
          version: plugin.version,
          publisher: plugin.publisher,
          status: resolveStatus(plugin),
          source: resolveSource(plugin),
          risk: resolveRisk(plugin),
          description: plugin.description,
          tags: resolveTags(plugin),
          permissions: resolvePermissions(plugin),
          dependencies: resolveDependencies(plugin),
          compatibleWith: resolveCompatibleWith(plugin),
          todayCalls: 0,
          boundAgentNames: [],
          rawPlugin: plugin,
        }
      })
    return [...pluginOnlyRows, ...capabilityRows]
  }

  return plugins.map((plugin) => {
    const type = resolveType(plugin)
    return {
      id: plugin.id,
      rowKind: 'plugin',
      name: plugin.name,
      ref: plugin.id,
      type,
      version: plugin.version,
      publisher: plugin.publisher,
      status: resolveStatus(plugin),
      source: resolveSource(plugin),
      risk: resolveRisk(plugin),
      description: plugin.description,
      tags: resolveTags(plugin),
      permissions: resolvePermissions(plugin),
      dependencies: resolveDependencies(plugin),
      compatibleWith: resolveCompatibleWith(plugin),
      todayCalls: 0,
      boundAgentNames: [],
      rawPlugin: plugin,
    }
  })
}

function buildMetricItems(rows: PluginWorkbenchRow[], plugins: Plugin[], recentRunCount: number): PluginMetricDefinition[] {
  const connectedCapabilities = rows.length
  const runningPlugins = plugins.filter((plugin) => plugin.installed && plugin.enabled).length
  const pendingRisks = rows.filter((row) => row.risk === 'high' || row.status === 'disabled').length
  const healthyCount = rows.filter((row) => row.risk !== 'high' && row.status !== 'disabled').length
  const healthRate = rows.length ? `${Number(((healthyCount / rows.length) * 100).toFixed(1))}%` : '-'

  return [
    {
      id: 'connected',
      labelKey: 'plugin.workspaceDashboard.metrics.connected',
      value: formatNumber(connectedCapabilities),
      trend: [5, 7, 6, 8, 10, 9, 12, 11, 13, 12],
      icon: PackageCheck,
      tone: 'blue',
    },
    {
      id: 'running',
      labelKey: 'plugin.workspaceDashboard.metrics.running',
      value: formatNumber(runningPlugins),
      trend: [3, 4, 4, 5, 6, 6, 7, 6, 8, 8],
      icon: Play,
      tone: 'green',
    },
    {
      id: 'today',
      labelKey: 'plugin.workspaceDashboard.metrics.todayCalls',
      value: formatNumber(recentRunCount),
      trend: [7, 9, 8, 11, 10, 12, 15, 13, 16, 14],
      icon: Database,
      tone: 'blue',
    },
    {
      id: 'risks',
      labelKey: 'plugin.workspaceDashboard.metrics.pendingRisks',
      value: formatNumber(pendingRisks),
      trend: [2, 1, 2, 3, 2, 2, 1, 2, 1, 1],
      icon: AlertTriangle,
      tone: pendingRisks > 0 ? 'red' : 'green',
    },
    {
      id: 'health',
      labelKey: 'plugin.workspaceDashboard.metrics.healthRate',
      value: healthRate,
      trend: [8, 8, 9, 9, 10, 9, 10, 11, 10, 12],
      icon: ShieldCheck,
      tone: 'green',
    },
  ]
}

function PluginNameCell({ row, typeLabel }: { row: PluginWorkbenchRow; typeLabel: string }) {
  const Icon = row.type === 'mcp' ? Plug : row.type === 'skill' ? FileCog : PackageCheck
  const colorClassName =
    row.risk === 'high'
      ? 'bg-slate-950 dark:bg-slate-700'
      : row.type === 'skill'
        ? 'bg-violet-600'
        : row.type === 'mcp'
          ? 'bg-slate-900'
          : 'bg-blue-600'

  return (
    <div className="flex min-w-[250px] items-center gap-3">
      <div className={cn('flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-white', colorClassName)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.name}</div>
        <div className="mt-0.5 flex min-w-0 items-center gap-2 text-xs text-muted-foreground">
          <span className="truncate">{row.ref}</span>
          <span className="shrink-0">· {typeLabel}</span>
        </div>
      </div>
    </div>
  )
}

function AgentAvatars({ names }: { names: string[] }) {
  if (!names.length) return <span className="text-muted-foreground">-</span>
  return (
    <AvatarGroup>
      {names.slice(0, 5).map((name, index) => (
        <Avatar key={`${name}-${index}`} size="sm" className="border border-background bg-muted">
          <AvatarFallback className={cn('text-[10px] font-semibold text-white', index % 2 === 0 ? 'bg-slate-700 dark:bg-slate-500' : 'bg-blue-600 dark:bg-blue-500')}>
            {name.slice(0, 2).toUpperCase()}
          </AvatarFallback>
        </Avatar>
      ))}
      {names.length > 5 ? <AvatarGroupCount className="size-6 text-xs">+{names.length - 5}</AvatarGroupCount> : null}
    </AvatarGroup>
  )
}

function DisabledAction({ label, tooltip }: { label: string; tooltip: string }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span>
          <Button variant="outline" size="sm" disabled>
            {label}
          </Button>
        </span>
      </TooltipTrigger>
      <TooltipContent>{tooltip}</TooltipContent>
    </Tooltip>
  )
}

function isSameVersionConflict(error: unknown) {
  const responseData = (error as { response?: { data?: { details?: { reason?: string } } } })?.response?.data
  return responseData?.details?.reason === 'same_version_exists'
}

function UploadPackageDialog({
  open,
  onOpenChange,
  title,
  description,
  fileLabel,
  dropTitle,
  dropDescription,
  selectedFileLabel,
  cancelLabel,
  submitLabel,
  uploading,
  onSubmit,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: string
  description: string
  fileLabel: string
  dropTitle: string
  dropDescription: string
  selectedFileLabel: (name: string) => string
  cancelLabel: string
  submitLabel: string
  uploading: boolean
  onSubmit: (file: File) => void
}) {
  const [file, setFile] = useState<File | null>(null)

  useEffect(() => {
    if (!open) {
      setFile(null)
    }
  }, [open])

  const handleDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault()
    const droppedFile = event.dataTransfer.files?.[0]
    if (droppedFile) {
      setFile(droppedFile)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <label
          htmlFor="plugin-package-file"
          onDragOver={(event) => event.preventDefault()}
          onDrop={handleDrop}
          className="flex min-h-40 cursor-pointer flex-col items-center justify-center rounded-lg border border-dashed border-border bg-muted/40 px-6 py-8 text-center transition-colors hover:border-primary/60 hover:bg-primary/5"
        >
          <Upload className="mb-3 h-8 w-8 text-muted-foreground" />
          <span className="text-sm font-semibold text-foreground">{dropTitle}</span>
          <span className="mt-1 text-xs text-muted-foreground">{dropDescription}</span>
          <input
            id="plugin-package-file"
            aria-label={fileLabel}
            type="file"
            accept=".zip,application/zip"
            className="sr-only"
            onChange={(event) => setFile(event.target.files?.[0] || null)}
          />
        </label>

        {file ? (
          <div className="rounded-md border border-border bg-panel px-3 py-2 text-sm text-foreground">
            {selectedFileLabel(file.name)}
          </div>
        ) : null}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={uploading}>
            {cancelLabel}
          </Button>
          <Button type="button" onClick={() => file && onSubmit(file)} disabled={!file || uploading}>
            {submitLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function DetailList({ title, values, empty }: { title: string; values: string[]; empty: string }) {
  return (
    <div className="space-y-2 border-t border-border pt-4">
      <div className="text-sm font-semibold text-foreground">{title}</div>
      {values.length ? (
        <ul className="space-y-2 text-sm text-muted-foreground">
          {values.map((value) => (
            <li key={value} className="flex items-start gap-2">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
              <span>{value}</span>
            </li>
          ))}
        </ul>
      ) : (
        <div className="text-sm text-muted-foreground">{empty}</div>
      )}
    </div>
  )
}

function PluginDetailPanel({
  row,
  typeLabel,
  sourceLabel,
  riskLabel,
  labels,
  onInstall,
  onUninstall,
  onToggleEnabled,
  onUpdatePackage,
  busy,
}: {
  row?: PluginWorkbenchRow
  typeLabel: string
  sourceLabel: string
  riskLabel: string
  labels: {
    detailTitle: string
    description: string
    permissions: string
    dependencies: string
    compatibleWith: string
    relatedAgents: string
    recentCalls: string
    empty: string
    configure: string
    upload: string
    docs: string
    install: string
    uninstall: string
    enable: string
    disable: string
    updatePackage: string
    unavailableAction: string
    noItems: string
  }
  onInstall: (row: PluginWorkbenchRow) => void
  onUninstall: (row: PluginWorkbenchRow) => void
  onToggleEnabled: (row: PluginWorkbenchRow, enabled: boolean) => void
  onUpdatePackage: (row: PluginWorkbenchRow) => void
  busy: boolean
}) {
  if (!row) {
    return (
      <div className="rounded-lg border border-border bg-panel p-5 text-sm text-muted-foreground shadow-sm">
        {labels.empty}
      </div>
    )
  }

  const plugin = row.rawPlugin

  return (
    <div className="p-5 pt-0">
      <div className="flex items-start justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-slate-950 text-white dark:bg-slate-700">
            <Plug className="h-5 w-5" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-lg font-semibold text-foreground">{row.name}</div>
            <div className="mt-1 text-xs text-muted-foreground">
              {typeLabel} · v{row.version || '-'} · {sourceLabel}
            </div>
          </div>
        </div>
        <Badge className={cn('rounded-md border px-2 py-1 text-xs', riskClassName[row.risk])}>{riskLabel}</Badge>
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {row.tags.map((tag) => (
          <Badge key={tag} variant="secondary" className="rounded-md">
            {tag}
          </Badge>
        ))}
      </div>

      <div className="mt-5 space-y-2">
        <div className="text-sm font-semibold text-foreground">{labels.description}</div>
        <p className="text-sm leading-6 text-muted-foreground">{row.description || labels.noItems}</p>
      </div>

      <DetailList title={labels.permissions} values={row.permissions} empty={labels.noItems} />
      <DetailList title={labels.dependencies} values={row.dependencies} empty={labels.noItems} />
      <DetailList title={labels.compatibleWith} values={row.compatibleWith} empty={labels.noItems} />

      <div className="mt-4 border-t border-border pt-4">
        <div className="mb-3 flex items-center justify-between gap-3">
          <div className="text-sm font-semibold text-foreground">{labels.relatedAgents}</div>
          <Badge variant="outline">{row.boundAgentNames.length}</Badge>
        </div>
        <div className="flex items-center gap-3">
          <AgentAvatars names={row.boundAgentNames} />
          <span className="text-sm text-muted-foreground">{row.boundAgentNames.join(', ') || labels.noItems}</span>
        </div>
      </div>

      <div className="mt-4 border-t border-border pt-4">
        <div className="text-sm font-semibold text-foreground">{labels.recentCalls}</div>
        <div className="mt-2 text-3xl font-semibold text-foreground">{formatNumber(row.todayCalls)}</div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {plugin?.installed ? (
          <>
            <DisabledAction label={labels.configure} tooltip={labels.unavailableAction} />
            <Button variant="outline" size="sm" disabled={busy} onClick={() => onUpdatePackage(row)}>
              {labels.updatePackage}
            </Button>
            <Button variant={plugin.enabled ? 'destructive' : 'default'} size="sm" disabled={busy} onClick={() => onToggleEnabled(row, !plugin.enabled)}>
              {plugin.enabled ? labels.disable : labels.enable}
            </Button>
            <Button variant="outline" size="sm" disabled={busy} onClick={() => onUninstall(row)}>
              {labels.uninstall}
            </Button>
          </>
        ) : (
          <>
            <Button size="sm" disabled={busy || !plugin} onClick={() => onInstall(row)}>
              {labels.install}
            </Button>
            <DisabledAction label={labels.upload} tooltip={labels.unavailableAction} />
            <DisabledAction label={labels.docs} tooltip={labels.unavailableAction} />
          </>
        )}
      </div>
    </div>
  )
}

export default function PluginBoxPage() {
  const { t } = useTranslation()
  const [activeType, setActiveType] = useState('all')
  const [activeSource, setActiveSource] = useState('all')
  const [search, setSearch] = useState('')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detailOpen, setDetailOpen] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [localPluginState, setLocalPluginState] = useState<Record<string, Partial<Plugin>>>({})
  const [packageDialogOpen, setPackageDialogOpen] = useState(false)
  const [packageDialogPlugin, setPackageDialogPlugin] = useState<Plugin | null>(null)
  const [pendingReinstallFile, setPendingReinstallFile] = useState<File | null>(null)
  const [reinstallConfirmOpen, setReinstallConfirmOpen] = useState(false)
  const [uninstallTarget, setUninstallTarget] = useState<PluginWorkbenchRow | null>(null)

  const {
    data: pluginPage,
    isLoading: pluginsLoading,
    isError: isPluginsError,
    error: pluginsError,
    refetch: refetchPlugins,
  } = useQuery({
    queryKey: ['plugins', 'workbench', 'plugins'],
    queryFn: () => listPlugins({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const {
    data: capabilityPage,
    isLoading: capabilitiesLoading,
    isError: isCapabilitiesError,
    error: capabilitiesError,
    refetch: refetchCapabilities,
  } = useQuery({
    queryKey: ['plugins', 'workbench', 'capabilities'],
    queryFn: () => listPluginCapabilities({ page_size: 100 }),
    options: {
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  const basePlugins = pluginPage?.items || []
  const plugins = useMemo(() => {
    const baseIds = new Set(basePlugins.map((plugin) => plugin.id))
    const merged = basePlugins.map((plugin) => ({ ...plugin, ...(localPluginState[plugin.id] || {}) }))
    const localOnly = Object.entries(localPluginState)
      .filter(([pluginId, plugin]) => !baseIds.has(pluginId) && plugin.id && plugin.name && plugin.version)
      .map(([, plugin]) => plugin as Plugin)
    return [...localOnly, ...merged]
  }, [basePlugins, localPluginState])
  const capabilities = capabilityPage?.items || []
  const capabilityRefs = useMemo(() => capabilities.map((capability) => capability.ref), [capabilities])
  const { boundAgents, recentRuns, isLoading: usageLoading } = useCapabilityGovernanceUsage(capabilityRefs)

  const boundAgentMap = useMemo(() => {
    const values = new Map<string, string[]>()
    boundAgents.forEach((agent) => {
      agent.capabilityRefs.forEach((ref) => {
        values.set(ref, [...(values.get(ref) || []), agent.agentName])
      })
    })
    return values
  }, [boundAgents])

  const runCountMap = useMemo(() => {
    const values = new Map<string, number>()
    boundAgents.forEach((agent) => {
      agent.capabilityRefs.forEach((ref) => {
        const count = recentRuns.filter((run) => run.subject_id === agent.agentId).length
        values.set(ref, (values.get(ref) || 0) + count)
      })
    })
    return values
  }, [boundAgents, recentRuns])

  const rows = useMemo(
    () => buildRows(plugins, capabilities, boundAgentMap, runCountMap),
    [plugins, capabilities, boundAgentMap, runCountMap],
  )

  const tabs = useMemo<BoxToolbarTab[]>(() => [
    { id: 'all', label: t('plugin.workspaceDashboard.tabs.all'), count: rows.length },
    { id: 'plugin', label: t('plugin.workspaceDashboard.tabs.plugins'), count: rows.filter((row) => row.type === 'plugin').length },
    { id: 'skill', label: t('plugin.workspaceDashboard.tabs.skill'), count: rows.filter((row) => row.type === 'skill').length },
    { id: 'mcp', label: t('plugin.workspaceDashboard.tabs.mcp'), count: rows.filter((row) => row.type === 'mcp').length },
  ], [rows, t])

  const sourceTabs = useMemo<BoxToolbarTab[]>(() => [
    { id: 'all', label: t('plugin.workspaceDashboard.sources.all'), count: rows.length },
    { id: 'official', label: t('plugin.workspaceDashboard.sources.official'), count: rows.filter((row) => row.source === 'official').length },
    { id: 'community', label: t('plugin.workspaceDashboard.sources.community'), count: rows.filter((row) => row.source === 'community').length },
    { id: 'private', label: t('plugin.workspaceDashboard.sources.private'), count: rows.filter((row) => row.source === 'private').length },
  ], [rows, t])

  const filteredRows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    return rows.filter((row) => {
      const matchesType = activeType === 'all' || row.type === activeType
      const matchesSource = activeSource === 'all' || row.source === activeSource
      const matchesSearch = !keyword || [
        row.name,
        row.ref,
        row.publisher,
        row.description,
        ...row.tags,
      ].some((value) => value?.toLowerCase().includes(keyword))
      return matchesType && matchesSource && matchesSearch
    })
  }, [rows, activeType, activeSource, search])

  useEffect(() => {
    setCurrentPage(1)
  }, [activeType, activeSource, search])

  useEffect(() => {
    if (!selectedId && filteredRows.length) {
      setSelectedId(filteredRows[0].id)
    }
    if (selectedId && filteredRows.length && !filteredRows.some((row) => row.id === selectedId)) {
      setSelectedId(filteredRows[0].id)
    }
  }, [filteredRows, selectedId])

  const totalPages = Math.max(1, Math.ceil(filteredRows.length / PAGE_SIZE))
  const safeCurrentPage = Math.min(currentPage, totalPages)
  const pagedRows = filteredRows.slice((safeCurrentPage - 1) * PAGE_SIZE, safeCurrentPage * PAGE_SIZE)
  const selectedRow = rows.find((row) => row.id === selectedId) || filteredRows[0]
  const metrics = useMemo(
    () => buildMetricItems(rows, plugins, recentRuns.length).map((item) => ({ ...item, label: t(item.labelKey) })),
    [rows, plugins, recentRuns.length, t],
  )
  const pendingRiskRow = rows.find((row) => row.risk === 'high' || row.status === 'disabled')

  const refreshAll = () => {
    void refetchPlugins()
    void refetchCapabilities()
  }

  const openDetails = (row: PluginWorkbenchRow) => {
    setSelectedId(row.id)
    setDetailOpen(true)
  }

  const mergePluginState = (plugin: Plugin) => {
    setLocalPluginState((state) => ({ ...state, [plugin.id]: plugin }))
  }

  const openPackageDialog = (plugin?: Plugin | null) => {
    setPackageDialogPlugin(plugin || null)
    setPackageDialogOpen(true)
  }

  const packageActionLabel = (action: 'created' | 'upgraded' | 'reinstalled') => {
    if (action === 'created') return t('plugin.workspaceDashboard.packageDialog.toast.created')
    if (action === 'reinstalled') return t('plugin.workspaceDashboard.packageDialog.toast.reinstalled')
    return t('plugin.workspaceDashboard.packageDialog.toast.upgraded')
  }

  const handlePackageSubmit = async (file: File) => {
    try {
      setActionLoading(packageDialogPlugin ? `upgrade:${packageDialogPlugin.id}` : 'package-upload')
      if (packageDialogPlugin) {
        const result = await upgradePluginPackage(packageDialogPlugin.id, file)
        mergePluginState(result.plugin)
        toast.success(t('plugin.workspaceDashboard.packageDialog.toast.upgraded'))
      } else {
        const result = await uploadPluginPackage(file, 'auto')
        mergePluginState(result.plugin)
        toast.success(packageActionLabel(result.action))
      }
      setPackageDialogOpen(false)
      setPackageDialogPlugin(null)
      refreshAll()
    } catch (error) {
      if (!packageDialogPlugin && isSameVersionConflict(error)) {
        setPendingReinstallFile(file)
        setReinstallConfirmOpen(true)
      } else {
        toast.error(t('plugin.workspaceDashboard.packageDialog.toast.failed'))
        console.error('Failed to upload plugin package:', error)
      }
    } finally {
      setActionLoading(null)
    }
  }

  const handleConfirmReinstall = async () => {
    if (!pendingReinstallFile) return
    try {
      setActionLoading('package-reinstall')
      const result = await uploadPluginPackage(pendingReinstallFile, 'reinstall')
      mergePluginState(result.plugin)
      toast.success(t('plugin.workspaceDashboard.packageDialog.toast.reinstalled'))
      setPackageDialogOpen(false)
      setPackageDialogPlugin(null)
      setPendingReinstallFile(null)
      setReinstallConfirmOpen(false)
      refreshAll()
    } catch (error) {
      toast.error(t('plugin.workspaceDashboard.packageDialog.toast.failed'))
      console.error('Failed to reinstall plugin package:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleReloadRuntime = async () => {
    try {
      setActionLoading('runtime')
      const result = await reloadPluginRuntime()
      toast.success(t('plugin.marketplacePage.toast.reloadSuccess', { count: result.loaded_count }))
      refreshAll()
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.reloadError'))
      console.error('Failed to reload plugin runtime:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleInstall = async (row: PluginWorkbenchRow) => {
    const plugin = row.rawPlugin
    if (!plugin) return
    try {
      setActionLoading(row.id)
      await installPlugin(plugin.id, {})
      setLocalPluginState((state) => ({ ...state, [plugin.id]: { installed: true, enabled: true } }))
      toast.success(t('plugin.marketplacePage.toast.installSuccess'))
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.installError'))
      console.error('Failed to install plugin:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleUninstall = async (row: PluginWorkbenchRow) => {
    setUninstallTarget(row)
  }

  const executeUninstall = async () => {
    const row = uninstallTarget
    if (!row) return
    const plugin = row.rawPlugin
    if (!plugin) return
    try {
      setActionLoading(row.id)
      await uninstallPlugin(plugin.id)
      setLocalPluginState((state) => ({ ...state, [plugin.id]: { installed: false, enabled: false } }))
      toast.success(t('plugin.marketplacePage.toast.uninstallSuccess'))
      setUninstallTarget(null)
    } catch (error) {
      toast.error(t('plugin.marketplacePage.toast.uninstallError'))
      console.error('Failed to uninstall plugin:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const handleToggleEnabled = async (row: PluginWorkbenchRow, enabled: boolean) => {
    const plugin = row.rawPlugin
    if (!plugin) return
    try {
      setActionLoading(row.id)
      await setPluginEnabled(plugin.id, enabled)
      setLocalPluginState((state) => ({ ...state, [plugin.id]: { installed: true, enabled } }))
      toast.success(enabled ? t('plugin.marketplacePage.toast.enableSuccess') : t('plugin.marketplacePage.toast.disableSuccess'))
    } catch (error) {
      toast.error(enabled ? t('plugin.marketplacePage.toast.enableError') : t('plugin.marketplacePage.toast.disableError'))
      console.error('Failed to toggle plugin enabled:', error)
    } finally {
      setActionLoading(null)
    }
  }

  const columns = useMemo<BoxDataTableColumn<PluginWorkbenchRow>[]>(() => [
    {
      id: 'name',
      header: t('plugin.workspaceDashboard.columns.name'),
      render: (row) => <PluginNameCell row={row} typeLabel={t(typeLabelKeys[row.type])} />,
    },
    {
      id: 'type',
      header: t('plugin.workspaceDashboard.columns.type'),
      render: (row) => <Badge variant="secondary" className="rounded-md">{t(typeLabelKeys[row.type])}</Badge>,
    },
    {
      id: 'version',
      header: t('plugin.workspaceDashboard.columns.version'),
      render: (row) => <span>{row.version ? `v${row.version}` : '-'}</span>,
    },
    {
      id: 'status',
      header: t('plugin.workspaceDashboard.columns.status'),
      render: (row) => <Badge className={cn('rounded-md border px-2 py-1', statusClassName[row.status])}>{t(statusLabelKeys[row.status])}</Badge>,
    },
    {
      id: 'source',
      header: t('plugin.workspaceDashboard.columns.source'),
      render: (row) => <span>{t(sourceLabelKeys[row.source])}</span>,
    },
    {
      id: 'compatibility',
      header: t('plugin.workspaceDashboard.columns.compatibility'),
      render: (row) => (
        <div className="flex min-w-[160px] flex-wrap gap-1">
          {row.compatibleWith.slice(0, 3).map((item) => (
            <Badge key={item} variant="outline" className="rounded-md text-[11px]">{item}</Badge>
          ))}
          {!row.compatibleWith.length ? <span className="text-muted-foreground">-</span> : null}
        </div>
      ),
    },
    {
      id: 'calls',
      header: t('plugin.workspaceDashboard.columns.todayCalls'),
      cellClassName: 'font-semibold text-foreground',
      render: (row) => formatNumber(row.todayCalls),
    },
    {
      id: 'risk',
      header: t('plugin.workspaceDashboard.columns.risk'),
      render: (row) => <Badge className={cn('rounded-md border px-2 py-1', riskClassName[row.risk])}>{t(riskLabelKeys[row.risk])}</Badge>,
    },
    {
      id: 'actions',
      header: t('plugin.workspaceDashboard.columns.actions'),
      render: (row) => {
        const plugin = row.rawPlugin
        const busy = actionLoading === row.id
        return (
          <div className="flex items-center gap-2" onClick={(event) => event.stopPropagation()}>
            {plugin?.installed ? (
              <Button variant="outline" size="sm" disabled={busy} onClick={() => handleToggleEnabled(row, !plugin.enabled)}>
                {plugin.enabled ? t('plugin.workspaceDashboard.actions.disable') : t('plugin.workspaceDashboard.actions.enable')}
              </Button>
            ) : (
              <Button size="sm" disabled={busy || !plugin} onClick={() => handleInstall(row)}>
                {t('plugin.workspaceDashboard.actions.install')}
              </Button>
            )}
            <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
              <MoreHorizontal className="h-3.5 w-3.5" />
            </Button>
          </div>
        )
      },
    },
  ], [actionLoading, t])

  const errorMessage = isPluginsError || isCapabilitiesError
    ? pluginsError instanceof Error
      ? pluginsError.message
      : capabilitiesError instanceof Error
        ? capabilitiesError.message
        : undefined
    : undefined

  return (
    <TooltipProvider>
      <BoxShell>
        <BoxPageHeader
          title={t('plugin.workspaceDashboard.header.title')}
          description={t('plugin.workspaceDashboard.header.description')}
          action={(
            <>
              <Button variant="outline" className="h-11 gap-2 rounded-lg border-border bg-panel px-4 text-foreground shadow-sm" onClick={handleReloadRuntime} disabled={actionLoading === 'runtime'}>
                <RefreshCw className={cn('h-4 w-4', actionLoading === 'runtime' && 'animate-spin')} />
                {t('plugin.workspaceDashboard.header.sync')}
              </Button>
              <Button variant="outline" className="h-11 gap-2 rounded-lg border-border bg-panel px-4 text-foreground shadow-sm" onClick={() => openPackageDialog()}>
                <Upload className="h-4 w-4" />
                {t('plugin.workspaceDashboard.header.upload')}
              </Button>
              <Button className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700" disabled>
                <PackagePlus className="h-4 w-4" />
                {t('plugin.workspaceDashboard.header.connect')}
              </Button>
            </>
          )}
        />

        {errorMessage ? (
          <BoxAlert
            severity="warning"
            title={t('plugin.workspaceDashboard.alert.fetchFailed')}
            description={errorMessage}
            action={<Button variant="outline" size="sm" onClick={refreshAll}>{t('plugin.workspaceDashboard.toolbar.refresh')}</Button>}
          />
        ) : pendingRiskRow ? (
          <BoxAlert
            severity={pendingRiskRow.risk === 'high' ? 'critical' : 'warning'}
            badge={t(riskLabelKeys[pendingRiskRow.risk])}
            title={t('plugin.workspaceDashboard.alert.title')}
            description={t('plugin.workspaceDashboard.alert.description', { name: pendingRiskRow.name })}
            action={<Button variant="ghost" size="sm" onClick={() => openDetails(pendingRiskRow)}>{t('plugin.workspaceDashboard.alert.action')} <SquareArrowOutUpRight className="h-4 w-4" /></Button>}
          />
        ) : null}

        <MetricStrip items={metrics} deltaLabel={t('plugin.workspaceDashboard.metrics.deltaLabel')} />

        <div className="flex max-w-full flex-wrap items-center gap-1 rounded-lg border border-border bg-panel p-1 shadow-sm">
          {sourceTabs.map((tab) => {
            const selected = activeSource === tab.id
            return (
              <button
                key={tab.id}
                type="button"
                onClick={() => setActiveSource(tab.id)}
                className={cn(
                  'flex h-9 items-center gap-2 rounded-md px-4 text-sm font-medium text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground',
                  selected && 'bg-primary/10 text-primary shadow-[inset_0_0_0_1px_rgba(37,99,235,0.18)]',
                )}
              >
                <span>{tab.label}</span>
                <span className={cn('rounded-full px-2 py-0.5 text-xs', selected ? 'bg-background text-primary' : 'bg-muted text-muted-foreground')}>{tab.count}</span>
              </button>
            )
          })}
        </div>

        <BoxToolbar
          tabs={tabs}
          activeTab={activeType}
          onTabChange={setActiveType}
          searchValue={search}
          onSearchChange={setSearch}
          searchPlaceholder={t('plugin.workspaceDashboard.toolbar.searchPlaceholder')}
          filterLabel={t('plugin.workspaceDashboard.toolbar.filter')}
          timeLabel={t('plugin.workspaceDashboard.toolbar.sort')}
          refreshLabel={t('plugin.workspaceDashboard.toolbar.refresh')}
          onRefresh={refreshAll}
        />

        <div className="min-w-0 space-y-4">
          <BoxDataTable
            columns={columns}
            rows={pagedRows}
            emptyMessage={pluginsLoading || capabilitiesLoading || usageLoading ? t('plugin.workspaceDashboard.table.loading') : t('plugin.workspaceDashboard.table.empty')}
            onRowClick={openDetails}
            getRowClassName={(row) => row.id === selectedRow?.id ? 'bg-primary/5 shadow-[inset_3px_0_0_rgb(37,99,235)]' : undefined}
          />
          <BoxPagination
            total={filteredRows.length}
            pageSize={PAGE_SIZE}
            currentPage={safeCurrentPage}
            pages={Array.from({ length: Math.min(5, totalPages) }, (_, index) => index + 1)}
            hasPrevious={safeCurrentPage > 1}
            hasNext={safeCurrentPage < totalPages}
            onPrevious={() => setCurrentPage((page) => Math.max(1, page - 1))}
            onNext={() => setCurrentPage((page) => Math.min(totalPages, page + 1))}
            onPageChange={setCurrentPage}
            labels={{
              totalSuffix: t('plugin.workspaceDashboard.pagination.totalSuffix'),
              pageSizeSuffix: t('plugin.workspaceDashboard.pagination.pageSizeSuffix'),
              goTo: t('plugin.workspaceDashboard.pagination.goTo'),
              page: t('plugin.workspaceDashboard.pagination.page'),
            }}
          />
        </div>

        <Sheet open={detailOpen && Boolean(selectedRow)} onOpenChange={setDetailOpen}>
          <SheetContent side="right" className="w-[min(520px,92vw)] gap-0 overflow-y-auto bg-panel p-0 sm:max-w-none">
            {selectedRow ? (
              <>
                <SheetHeader className="sr-only">
                  <SheetTitle>{selectedRow.name}</SheetTitle>
                  <SheetDescription>{t('plugin.workspaceDashboard.detail.title')}</SheetDescription>
                </SheetHeader>
                <PluginDetailPanel
                  row={selectedRow}
                  typeLabel={t(typeLabelKeys[selectedRow.type])}
                  sourceLabel={t(sourceLabelKeys[selectedRow.source])}
                  riskLabel={t(riskLabelKeys[selectedRow.risk])}
                  labels={{
                    detailTitle: t('plugin.workspaceDashboard.detail.title'),
                    description: t('plugin.workspaceDashboard.detail.description'),
                    permissions: t('plugin.workspaceDashboard.detail.permissions'),
                    dependencies: t('plugin.workspaceDashboard.detail.dependencies'),
                    compatibleWith: t('plugin.workspaceDashboard.detail.compatibleWith'),
                    relatedAgents: t('plugin.workspaceDashboard.detail.relatedAgents'),
                    recentCalls: t('plugin.workspaceDashboard.detail.recentCalls'),
                    empty: t('plugin.workspaceDashboard.detail.empty'),
                    configure: t('plugin.workspaceDashboard.actions.configure'),
                    upload: t('plugin.workspaceDashboard.actions.upload'),
                    docs: t('plugin.workspaceDashboard.actions.docs'),
                    install: t('plugin.workspaceDashboard.actions.install'),
                    uninstall: t('plugin.workspaceDashboard.actions.uninstall'),
                    enable: t('plugin.workspaceDashboard.actions.enable'),
                    disable: t('plugin.workspaceDashboard.actions.disable'),
                    updatePackage: t('plugin.workspaceDashboard.actions.updatePackage'),
                    unavailableAction: t('plugin.workspaceDashboard.actions.unavailable'),
                    noItems: t('plugin.workspaceDashboard.detail.noItems'),
                  }}
                  onInstall={handleInstall}
                  onUninstall={handleUninstall}
                  onToggleEnabled={handleToggleEnabled}
                  onUpdatePackage={(row) => row.rawPlugin && openPackageDialog(row.rawPlugin)}
                  busy={actionLoading === selectedRow.id}
                />
              </>
            ) : null}
          </SheetContent>
        </Sheet>

        <UploadPackageDialog
          open={packageDialogOpen}
          onOpenChange={(open) => {
            setPackageDialogOpen(open)
            if (!open) {
              setPackageDialogPlugin(null)
            }
          }}
          title={packageDialogPlugin ? t('plugin.workspaceDashboard.packageDialog.updateTitle') : t('plugin.workspaceDashboard.packageDialog.uploadTitle')}
          description={packageDialogPlugin ? t('plugin.workspaceDashboard.packageDialog.updateDescription') : t('plugin.workspaceDashboard.packageDialog.uploadDescription')}
          fileLabel={t('plugin.workspaceDashboard.packageDialog.fileLabel')}
          dropTitle={t('plugin.workspaceDashboard.packageDialog.dropTitle')}
          dropDescription={t('plugin.workspaceDashboard.packageDialog.dropDescription')}
          selectedFileLabel={(name) => t('plugin.workspaceDashboard.packageDialog.selectedFile', { name })}
          cancelLabel={t('plugin.workspaceDashboard.packageDialog.cancel')}
          submitLabel={t('plugin.workspaceDashboard.packageDialog.submit')}
          uploading={actionLoading === 'package-upload' || actionLoading === 'package-reinstall' || (packageDialogPlugin ? actionLoading === `upgrade:${packageDialogPlugin.id}` : false)}
          onSubmit={handlePackageSubmit}
        />

        <AlertDialog open={reinstallConfirmOpen} onOpenChange={setReinstallConfirmOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('plugin.workspaceDashboard.reinstallConfirm.title')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('plugin.workspaceDashboard.reinstallConfirm.description')}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={actionLoading === 'package-reinstall'}>
                {t('plugin.workspaceDashboard.reinstallConfirm.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction onClick={handleConfirmReinstall} disabled={actionLoading === 'package-reinstall'}>
                {t('plugin.workspaceDashboard.reinstallConfirm.confirm')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        <AlertDialog open={Boolean(uninstallTarget)} onOpenChange={(open) => !open && setUninstallTarget(null)}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{t('plugin.workspaceDashboard.uninstallConfirm.title')}</AlertDialogTitle>
              <AlertDialogDescription>
                {t('plugin.workspaceDashboard.uninstallConfirm.description', { name: uninstallTarget?.name || '' })}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel disabled={Boolean(uninstallTarget && actionLoading === uninstallTarget.id)}>
                {t('plugin.workspaceDashboard.uninstallConfirm.cancel')}
              </AlertDialogCancel>
              <AlertDialogAction
                variant="destructive"
                onClick={executeUninstall}
                disabled={Boolean(uninstallTarget && actionLoading === uninstallTarget.id)}
              >
                {t('plugin.workspaceDashboard.uninstallConfirm.confirm')}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
      </BoxShell>
    </TooltipProvider>
  )
}
