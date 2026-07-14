import { useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Bell,
  Bot,
  Braces,
  Clock3,
  Database,
  FileText,
  MessageCircle,
  MoreHorizontal,
  Network,
  Plus,
  ShieldCheck,
  Store,
  TrendingUp,
} from 'lucide-react'
import { toast } from 'sonner'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  MetricStrip,
  type MetricStripItem,
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
} from '@/components/box'
import { useNavigate } from '@/hooks/use-navigate'
import { useMutation } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'
import { createAgent } from '@/services/agent-service'

type AgentStatus = 'running' | 'configuring' | 'abnormal' | 'unconfigured'
type AbilityTone = 'blue' | 'emerald' | 'orange' | 'red' | 'violet'
type AgentAction = 'chat' | 'disabled'

interface AgentAbility {
  id: string
  label: string
  icon: typeof FileText
  tone: AbilityTone
}

interface AgentRow {
  id: string
  name: string
  description: string
  icon: typeof Bot
  iconClassName: string
  status: AgentStatus
  abilities: AgentAbility[]
  todayCalls?: string
  avgLatency?: string
  successRate?: string
  recentException?: string
  owner: string
  lastRun: string
  action: AgentAction
}

type MetricDefinition = Omit<MetricStripItem, 'label'> & {
  labelKey: TranslationKey
}

const metrics = [
  {
    id: 'running',
    labelKey: 'agent.dashboard.metrics.running',
    value: '16',
    delta: '+2',
    trend: [5, 8, 8, 10, 6, 7, 5, 7, 6, 5],
    icon: Bot,
    tone: 'green',
  },
  {
    id: 'today',
    labelKey: 'agent.dashboard.metrics.todayCalls',
    value: '8,750',
    delta: '+12.4%',
    trend: [5, 6, 8, 7, 9, 13, 10, 9, 9, 8],
    icon: TrendingUp,
    tone: 'blue',
  },
  {
    id: 'latency',
    labelKey: 'agent.dashboard.metrics.avgLatency',
    value: '245ms',
    delta: '+18ms',
    trend: [7, 7, 8, 7, 10, 9, 13, 10, 8, 8],
    icon: Clock3,
    tone: 'amber',
  },
  {
    id: 'success',
    labelKey: 'agent.dashboard.metrics.successRate',
    value: '98.6%',
    delta: '+0.6%',
    trend: [8, 11, 11, 10, 12, 10, 10, 11, 9, 12],
    icon: ShieldCheck,
    tone: 'green',
  },
  {
    id: 'exceptions',
    labelKey: 'agent.dashboard.metrics.pendingExceptions',
    value: '1',
    delta: '-1',
    trend: [3, 5, 4, 4, 3, 3, 3, 2, 3, 3],
    icon: AlertTriangle,
    tone: 'red',
  },
] satisfies MetricDefinition[]

const tabs = [
  { id: 'all', labelKey: 'agent.dashboard.tabs.all', count: 24 },
  { id: 'high', labelKey: 'agent.dashboard.tabs.highCalls', count: 5 },
  { id: 'low-success', labelKey: 'agent.dashboard.tabs.lowSuccess', count: 3 },
  { id: 'long-latency', labelKey: 'agent.dashboard.tabs.longLatency', count: 2 },
  { id: 'unconfigured', labelKey: 'agent.dashboard.tabs.unconfigured', count: 2 },
] satisfies { id: string; labelKey: TranslationKey; count: number }[]

const agentRows: AgentRow[] = [
  {
    id: 'customer-service',
    name: 'Customer Support Agent',
    description: 'Customer-facing Q&A and ticket assistance.',
    icon: MessageCircle,
    iconClassName: 'bg-blue-500',
    status: 'running',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'knowledge', label: 'Knowledge', icon: Database, tone: 'emerald' },
      { id: 'tools', label: 'Tools', icon: Network, tone: 'emerald' },
    ],
    todayCalls: '2,548',
    avgLatency: '186ms',
    successRate: '99.2%',
    owner: 'Jude',
    lastRun: 'Just now',
    action: 'chat',
  },
  {
    id: 'bi-analysis',
    name: 'BI Analysis Agent',
    description: 'Turns natural language into analysis and charts.',
    icon: BarChart3,
    iconClassName: 'bg-emerald-500',
    status: 'running',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'knowledge', label: 'Knowledge', icon: Database, tone: 'emerald' },
      { id: 'analytics', label: 'Analytics', icon: BarChart3, tone: 'orange' },
    ],
    todayCalls: '1,987',
    avgLatency: '212ms',
    successRate: '98.7%',
    owner: 'Alice',
    lastRun: '1 minute ago',
    action: 'chat',
  },
  {
    id: 'document-summary',
    name: 'Document Summary Agent',
    description: 'Summarizes long documents and extracts key facts.',
    icon: FileText,
    iconClassName: 'bg-violet-500',
    status: 'configuring',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'knowledge', label: 'Knowledge', icon: Database, tone: 'emerald' },
      { id: 'tools', label: 'Tools', icon: Network, tone: 'emerald' },
    ],
    todayCalls: '942',
    avgLatency: '320ms',
    successRate: '97.1%',
    owner: 'Bob',
    lastRun: '3 minutes ago',
    action: 'chat',
  },
  {
    id: 'code-assistant',
    name: 'Code Assistant Agent',
    description: 'Understands, generates, and fixes code.',
    icon: Braces,
    iconClassName: 'bg-emerald-500',
    status: 'running',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'analytics', label: 'Analytics', icon: BarChart3, tone: 'orange' },
      { id: 'tools', label: 'Tools', icon: Network, tone: 'emerald' },
    ],
    todayCalls: '1,623',
    avgLatency: '198ms',
    successRate: '98.9%',
    owner: 'Charlie',
    lastRun: '2 minutes ago',
    action: 'chat',
  },
  {
    id: 'exception-detection',
    name: 'Exception Detection Agent',
    description: 'Detects log anomalies and analyzes alerts.',
    icon: Bell,
    iconClassName: 'bg-red-500',
    status: 'abnormal',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'alerts', label: 'Alerts', icon: Bell, tone: 'red' },
      { id: 'flow', label: 'Flow', icon: Network, tone: 'violet' },
    ],
    todayCalls: '321',
    avgLatency: '1,452ms',
    successRate: '89.3%',
    recentException: '3',
    owner: 'David',
    lastRun: 'Just now',
    action: 'chat',
  },
  {
    id: 'hr-assistant',
    name: 'HR Assistant Agent',
    description: 'Guides employee policy and process questions.',
    icon: Bot,
    iconClassName: 'bg-sky-500',
    status: 'running',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
      { id: 'knowledge', label: 'Knowledge', icon: Database, tone: 'emerald' },
      { id: 'tools', label: 'Tools', icon: Network, tone: 'emerald' },
    ],
    todayCalls: '785',
    avgLatency: '168ms',
    successRate: '99.6%',
    owner: 'Eve',
    lastRun: '5 minutes ago',
    action: 'chat',
  },
  {
    id: 'content-review',
    name: 'Content Review Agent',
    description: 'Reviews text and images for compliance.',
    icon: Store,
    iconClassName: 'bg-orange-500',
    status: 'unconfigured',
    abilities: [
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'red' },
      { id: 'analytics', label: 'Analytics', icon: BarChart3, tone: 'orange' },
    ],
    owner: 'Frank',
    lastRun: '-',
    action: 'disabled',
  },
  {
    id: 'data-sync',
    name: 'Data Sync Agent',
    description: 'Connects external data sources and provides query service.',
    icon: Database,
    iconClassName: 'bg-blue-500',
    status: 'running',
    abilities: [
      { id: 'knowledge', label: 'Knowledge', icon: Database, tone: 'emerald' },
      { id: 'flow', label: 'Flow', icon: Network, tone: 'violet' },
      { id: 'docs', label: 'Documents', icon: FileText, tone: 'blue' },
    ],
    todayCalls: '544',
    avgLatency: '210ms',
    successRate: '98.3%',
    recentException: '1',
    owner: 'Grace',
    lastRun: '1 minute ago',
    action: 'chat',
  },
]

const statusConfig = {
  running: {
    labelKey: 'agent.dashboard.status.running',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  configuring: {
    labelKey: 'agent.dashboard.status.configuring',
    className: 'border-orange-200 bg-orange-50 text-orange-700 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200',
  },
  abnormal: {
    labelKey: 'agent.dashboard.status.abnormal',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  unconfigured: {
    labelKey: 'agent.dashboard.status.unconfigured',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<AgentStatus, { labelKey: TranslationKey; className: string }>

const abilityToneClassNameMap = {
  blue: 'border-blue-200 bg-blue-50 text-blue-600 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  emerald: 'border-emerald-200 bg-emerald-50 text-emerald-600 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  orange: 'border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200',
  red: 'border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  violet: 'border-violet-200 bg-violet-50 text-violet-600 dark:border-violet-400/20 dark:bg-violet-400/10 dark:text-violet-200',
} satisfies Record<AbilityTone, string>

function AgentNameCell({ row }: { row: AgentRow }) {
  const Icon = row.icon

  return (
    <div className="flex min-w-[245px] items-center gap-3">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white', row.iconClassName)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{row.name}</div>
        <div className="mt-0.5 max-w-[300px] truncate text-xs text-muted-foreground">{row.description}</div>
      </div>
    </div>
  )
}

function StatusBadge({ status }: { status: AgentStatus }) {
  const { t } = useTranslation()
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{t(config.labelKey)}</Badge>
}

function AbilityIcons({ abilities }: { abilities: AgentAbility[] }) {
  return (
    <div className="flex min-w-[110px] items-center gap-2">
      {abilities.map((ability) => {
        const Icon = ability.icon
        return (
          <span
            key={ability.id}
            title={ability.label}
            className={cn(
              'flex h-7 w-7 items-center justify-center rounded-md border',
              abilityToneClassNameMap[ability.tone],
            )}
          >
            <Icon className="h-3.5 w-3.5" />
          </span>
        )
      })}
    </div>
  )
}

function RecentException({ value }: { value?: string }) {
  const { t } = useTranslation()
  if (!value) return <span className="text-muted-foreground">-</span>

  const variantClassName =
    value === '3'
      ? 'border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200'
      : 'border-orange-200 bg-orange-50 text-orange-600 dark:border-orange-400/20 dark:bg-orange-400/10 dark:text-orange-200'

  return (
    <Badge className={cn('rounded-md border px-2 py-1', variantClassName)}>
      {t('agent.dashboard.table.exceptionCount', { count: value })}
    </Badge>
  )
}

function OperationButtons({ action }: { action: AgentAction }) {
  const { t } = useTranslation()

  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="icon-xs"
        disabled={action === 'disabled'}
        aria-label={t('agent.dashboard.table.chatAction')}
        title={t('agent.dashboard.table.chatAction')}
        className="border-border bg-panel text-foreground shadow-none"
      >
        <MessageCircle className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        aria-label={t('agent.dashboard.table.reportAction')}
        title={t('agent.dashboard.table.reportAction')}
        className="border-border bg-panel text-foreground shadow-none"
      >
        <BarChart3 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        aria-label={t('agent.dashboard.table.moreAction')}
        title={t('agent.dashboard.table.moreAction')}
        className="border-border bg-panel text-foreground shadow-none"
      >
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function AgentBoxPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [draftName, setDraftName] = useState('')
  const [draftDescription, setDraftDescription] = useState('')

  const createMutation = useMutation({
    mutationKey: ['agents', 'create'],
    mutationFn: () =>
      createAgent({
        name: draftName.trim(),
        description: draftDescription.trim() || undefined,
        visibility: 'private',
      }),
    onSuccess: (agent) => {
      setDraftName('')
      setDraftDescription('')
      setDialogOpen(false)
      toast.success(t('agent.workspace.created', { name: agent.name }))
      navigate(`/agents/${agent.id}`)
    },
    onError: (error: any) => {
      toast.error(error?.message || t('agent.workspace.createFailed'))
    },
  })

  const toolbarTabs = useMemo<BoxToolbarTab[]>(
    () => tabs.map((tab) => ({ id: tab.id, label: t(tab.labelKey), count: tab.count })),
    [t],
  )

  const rows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    const byTab = agentRows.filter((row) => {
      if (activeTab === 'all') return true
      if (activeTab === 'high') return Number((row.todayCalls || '0').replace(',', '')) >= 1600
      if (activeTab === 'low-success') return Number((row.successRate || '100').replace('%', '')) < 98
      if (activeTab === 'long-latency') {
        const latency = row.avgLatency?.replace(',', '').replace('ms', '') || '0'
        return Number(latency) >= 300
      }
      return row.status === activeTab
    })

    if (!keyword) return byTab
    return byTab.filter((row) =>
      [row.name, row.description, row.owner].join(' ').toLowerCase().includes(keyword),
    )
  }, [activeTab, search])

  const columns = useMemo<BoxDataTableColumn<AgentRow>[]>(() => [
    {
      id: 'name',
      header: t('agent.dashboard.table.name'),
      render: (row) => <AgentNameCell row={row} />,
    },
    {
      id: 'status',
      header: t('agent.dashboard.table.status'),
      render: (row) => <StatusBadge status={row.status} />,
    },
    {
      id: 'abilities',
      header: t('agent.dashboard.table.abilities'),
      render: (row) => <AbilityIcons abilities={row.abilities} />,
    },
    {
      id: 'todayCalls',
      header: t('agent.dashboard.table.todayCalls'),
      cellClassName: 'font-semibold text-foreground',
      render: (row) => row.todayCalls || '-',
    },
    {
      id: 'avgLatency',
      header: t('agent.dashboard.table.avgLatency'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(
          row.status === 'abnormal'
            ? 'text-red-600 dark:text-red-300'
            : row.avgLatency === '320ms'
              ? 'text-orange-600 dark:text-orange-300'
              : row.avgLatency
                ? 'text-emerald-600 dark:text-emerald-300'
                : 'text-muted-foreground',
        )}
        >
          {row.avgLatency || '-'}
        </span>
      ),
    },
    {
      id: 'successRate',
      header: t('agent.dashboard.table.successRate'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(
          row.status === 'abnormal'
            ? 'text-red-600 dark:text-red-300'
            : row.successRate === '97.1%'
              ? 'text-orange-600 dark:text-orange-300'
              : row.successRate
                ? 'text-emerald-600 dark:text-emerald-300'
                : 'text-muted-foreground',
        )}
        >
          {row.successRate || '-'}
        </span>
      ),
    },
    {
      id: 'recentException',
      header: t('agent.dashboard.table.recentException'),
      render: (row) => row.status === 'unconfigured'
        ? <Badge className="rounded-md border border-border bg-muted px-2 py-1 text-muted-foreground">{t('agent.dashboard.status.unconfigured')}</Badge>
        : <RecentException value={row.recentException} />,
    },
    {
      id: 'owner',
      header: t('agent.dashboard.table.owner'),
      render: (row) => row.owner,
    },
    {
      id: 'lastRun',
      header: t('agent.dashboard.table.lastRun'),
      render: (row) => (
        <span className={row.lastRun === '-' ? 'text-muted-foreground' : 'text-foreground/80'}>
          {row.lastRun}
        </span>
      ),
    },
    {
      id: 'actions',
      header: t('agent.dashboard.table.actions'),
      render: (row) => <OperationButtons action={row.action} />,
    },
  ], [t])

  const metricItems = useMemo(
    () => metrics.map(({ labelKey, ...metric }) => ({ ...metric, label: t(labelKey) })),
    [t],
  )

  const canCreate = draftName.trim().length > 0 && !createMutation.isPending

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('agent.dashboard.title')}
        description={t('agent.dashboard.description')}
        action={(
          <Button
            type="button"
            className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700"
            onClick={() => setDialogOpen(true)}
          >
            <Plus className="h-4 w-4" />
            {t('agent.dashboard.create.action')}
          </Button>
        )}
      />

      <MetricStrip items={metricItems} deltaLabel={t('agent.dashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={toolbarTabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('agent.dashboard.toolbar.searchPlaceholder')}
        filterLabel={t('agent.dashboard.toolbar.filter')}
        timeLabel={t('agent.dashboard.toolbar.time')}
        refreshLabel={t('agent.dashboard.toolbar.refresh')}
      />

      <BoxDataTable
        columns={columns}
        rows={rows}
        emptyMessage={t('agent.dashboard.table.empty')}
      />

      <BoxPagination
        total={24}
        pageSize={10}
        currentPage={1}
        pages={[1, 2, 3]}
        labels={{
          totalSuffix: t('agent.dashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('agent.dashboard.pagination.pageSizeSuffix'),
          goTo: t('agent.dashboard.pagination.goTo'),
          page: t('agent.dashboard.pagination.page'),
        }}
      />

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('agent.dashboard.create.title')}</DialogTitle>
            <DialogDescription>{t('agent.dashboard.create.description')}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <Input
              value={draftName}
              onChange={(event) => setDraftName(event.target.value)}
              placeholder={t('agent.workspace.namePlaceholder')}
              autoFocus
            />
            <Input
              value={draftDescription}
              onChange={(event) => setDraftDescription(event.target.value)}
              placeholder={t('agent.workspace.descriptionPlaceholder')}
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
              {t('agent.dashboard.create.cancel')}
            </Button>
            <Button
              type="button"
              disabled={!canCreate}
              onClick={() => createMutation.mutate(undefined)}
            >
              <Plus className="h-4 w-4" />
              {createMutation.isPending ? t('agent.dashboard.create.submitting') : t('agent.dashboard.create.submit')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </BoxShell>
  )
}

export default AgentBoxPage
