import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  Clock3,
  FileText,
  MoreHorizontal,
  Play,
  Plus,
  RotateCw,
  ShieldCheck,
  TrendingUp,
  Workflow,
} from 'lucide-react'
import { useMemo, useState } from 'react'

import { Avatar, AvatarFallback, AvatarGroup, AvatarGroupCount } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  MetricStrip,
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxPagination,
  BoxShell,
  BoxToolbar,
  type BoxToolbarTab,
} from '@/components/box'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'

type WorkflowStatus = 'running' | 'publishing' | 'abnormal' | 'draft'

interface WorkflowRow {
  id: string
  name: string
  description: string
  icon: typeof Workflow
  iconClassName: string
  status: WorkflowStatus
  agents: string[]
  extraAgents?: number
  todayRuns?: string
  avgLatency?: string
  successRate?: string
  recentException?: string
  owner: string
  lastRun: string
  action: 'play' | 'target' | 'disabled'
}

const metricDefinitions = [
  {
    id: 'running',
    labelKey: 'workflow.workspaceDashboard.metrics.running',
    value: '12',
    delta: '+2',
    trend: [4, 6, 5, 8, 6, 10, 5, 6, 4, 7, 5],
    icon: Play,
    tone: 'green',
  },
  {
    id: 'today',
    labelKey: 'workflow.workspaceDashboard.metrics.today',
    value: '18,420',
    delta: '+15.3%',
    trend: [8, 7, 9, 8, 12, 10, 14, 9, 10, 8],
    icon: TrendingUp,
    tone: 'blue',
  },
  {
    id: 'latency',
    labelKey: 'workflow.workspaceDashboard.metrics.latency',
    value: '1.8s',
    delta: '-0.3s',
    trend: [7, 8, 7, 10, 8, 9, 15, 9, 11, 10],
    icon: Clock3,
    tone: 'amber',
  },
  {
    id: 'success',
    labelKey: 'workflow.workspaceDashboard.metrics.success',
    value: '97.4%',
    delta: '+1.2%',
    trend: [9, 8, 10, 9, 12, 13, 10, 11, 9, 13],
    icon: ShieldCheck,
    tone: 'green',
  },
  {
    id: 'exceptions',
    labelKey: 'workflow.workspaceDashboard.metrics.exceptions',
    value: '3',
    delta: '+1',
    trend: [3, 5, 4, 8, 5, 4, 6, 3, 4, 3],
    icon: AlertTriangle,
    tone: 'red',
  },
] satisfies Array<Omit<React.ComponentProps<typeof MetricStrip>['items'][number], 'label'> & { labelKey: TranslationKey }>

const tabDefinitions = [
  { id: 'all', labelKey: 'workflow.workspaceDashboard.tabs.all', count: 32 },
  { id: 'high', labelKey: 'workflow.workspaceDashboard.tabs.highVolume', count: 8 },
  { id: 'publishing', labelKey: 'workflow.workspaceDashboard.tabs.publishing', count: 4 },
  { id: 'abnormal', labelKey: 'workflow.workspaceDashboard.tabs.incidents', count: 3 },
  { id: 'draft', labelKey: 'workflow.workspaceDashboard.tabs.drafts', count: 5 },
] satisfies Array<Omit<BoxToolbarTab, 'label'> & { labelKey: TranslationKey }>

const workflowRows: WorkflowRow[] = [
  {
    id: 'customer-clue',
    name: 'Customer Lead Cleanup',
    description: 'Clean and normalize multi-channel lead data',
    icon: Workflow,
    iconClassName: 'bg-emerald-500',
    status: 'running',
    agents: ['JD', 'AK'],
    extraAgents: 2,
    todayRuns: '2,548',
    avgLatency: '1.2s',
    successRate: '98.6%',
    owner: 'Jude',
    lastRun: '1 min ago',
    action: 'play',
  },
  {
    id: 'invoice-archive',
    name: 'Invoice Recognition Archive',
    description: 'Recognize, verify, and archive invoices',
    icon: FileText,
    iconClassName: 'bg-violet-500',
    status: 'publishing',
    agents: ['AL'],
    extraAgents: 1,
    todayRuns: '2,187',
    avgLatency: '2.6s',
    successRate: '96.8%',
    owner: 'Alice',
    lastRun: '2 min ago',
    action: 'play',
  },
  {
    id: 'data-sync',
    name: 'Data Sync',
    description: 'Synchronize systems and verify consistency',
    icon: RotateCw,
    iconClassName: 'bg-blue-500',
    status: 'running',
    agents: ['BO', 'CL'],
    extraAgents: 3,
    todayRuns: '3,420',
    avgLatency: '1.5s',
    successRate: '99.1%',
    owner: 'Bob',
    lastRun: '30 sec ago',
    action: 'play',
  },
  {
    id: 'content-review',
    name: 'Content Review',
    description: 'Review text and image compliance flows',
    icon: CheckCircle2,
    iconClassName: 'bg-orange-500',
    status: 'abnormal',
    agents: ['CH', 'AU'],
    extraAgents: 2,
    todayRuns: '921',
    avgLatency: '3.4s',
    successRate: '91.2%',
    recentException: '2 incidents',
    owner: 'Charlie',
    lastRun: 'Just now',
    action: 'play',
  },
  {
    id: 'ticket-routing',
    name: 'Ticket Routing',
    description: 'Route tickets to the best owner',
    icon: Workflow,
    iconClassName: 'bg-cyan-500',
    status: 'publishing',
    agents: ['DV'],
    extraAgents: 1,
    todayRuns: '1,856',
    avgLatency: '1.1s',
    successRate: '97.8%',
    owner: 'David',
    lastRun: '3 min ago',
    action: 'target',
  },
  {
    id: 'contract-check',
    name: 'Contract Risk Check',
    description: 'Detect contract risks and validate clauses',
    icon: ShieldCheck,
    iconClassName: 'bg-amber-500',
    status: 'running',
    agents: ['EV', 'LI'],
    extraAgents: 2,
    todayRuns: '1,243',
    avgLatency: '2.0s',
    successRate: '96.5%',
    owner: 'Eve',
    lastRun: '5 min ago',
    action: 'target',
  },
  {
    id: 'notification',
    name: 'Notification Delivery',
    description: 'Send notifications and collect delivery receipts',
    icon: FileText,
    iconClassName: 'bg-blue-500',
    status: 'draft',
    agents: ['FR', 'NO'],
    extraAgents: 2,
    owner: 'Frank',
    lastRun: '-',
    action: 'disabled',
  },
  {
    id: 'reporting',
    name: 'Report Generation',
    description: 'Aggregate data and generate visual reports',
    icon: BarChart3,
    iconClassName: 'bg-emerald-500',
    status: 'running',
    agents: ['GR'],
    extraAgents: 1,
    todayRuns: '1,122',
    avgLatency: '1.3s',
    successRate: '98.3%',
    owner: 'Grace',
    lastRun: '2 min ago',
    action: 'play',
  },
]

const statusConfig = {
  running: {
    labelKey: 'workflow.workspaceDashboard.status.running',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  publishing: {
    labelKey: 'workflow.workspaceDashboard.status.publishing',
    className: 'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-400/20 dark:bg-blue-400/10 dark:text-blue-200',
  },
  abnormal: {
    labelKey: 'workflow.workspaceDashboard.status.incident',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  draft: {
    labelKey: 'workflow.workspaceDashboard.status.draft',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<WorkflowStatus, { labelKey: TranslationKey; className: string }>

function WorkflowNameCell({ row, name, description }: { row: WorkflowRow; name: string; description: string }) {
  const Icon = row.icon

  return (
    <div className="flex min-w-[230px] items-center gap-3">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-white', row.iconClassName)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{name}</div>
        <div className="mt-0.5 max-w-[280px] truncate text-xs text-muted-foreground">{description}</div>
      </div>
    </div>
  )
}

function StatusBadge({ status, label }: { status: WorkflowStatus; label: string }) {
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{label}</Badge>
}

function AgentAvatars({ agents, extraAgents }: { agents: string[]; extraAgents?: number }) {
  return (
    <AvatarGroup>
      {agents.map((agent, index) => (
        <Avatar key={`${agent}-${index}`} size="sm" className="border border-background bg-muted">
          <AvatarFallback className={cn('text-[10px] font-semibold text-white', index % 2 === 0 ? 'bg-slate-700 dark:bg-slate-500' : 'bg-blue-600 dark:bg-blue-500')}>
            {agent}
          </AvatarFallback>
        </Avatar>
      ))}
      {extraAgents ? <AvatarGroupCount className="size-6 text-xs">+{extraAgents}</AvatarGroupCount> : null}
    </AvatarGroup>
  )
}

function OperationButtons({ action }: { action: WorkflowRow['action'] }) {
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <BarChart3 className="h-3.5 w-3.5" />
      </Button>
      <Button
        variant="outline"
        size="icon-xs"
        disabled={action === 'disabled'}
        className="border-border bg-panel text-foreground shadow-none"
      >
        {action === 'target' ? <CheckCircle2 className="h-3.5 w-3.5" /> : <Play className="h-3.5 w-3.5" />}
      </Button>
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function WorkflowBoxPage() {
  const { t } = useTranslation()
  const [activeTab, setActiveTab] = useState('all')
  const [search, setSearch] = useState('')

  const metrics = useMemo(() => metricDefinitions.map((item) => ({
    ...item,
    label: t(item.labelKey),
  })), [t])

  const tabs = useMemo(() => tabDefinitions.map((item) => ({
    id: item.id,
    label: t(item.labelKey),
    count: item.count,
  })), [t])

  const rows = useMemo(() => {
    const keyword = search.trim().toLowerCase()
    const byTab = workflowRows.filter((row) => {
      if (activeTab === 'all') return true
      if (activeTab === 'high') return Number((row.todayRuns || '0').replace(',', '')) > 2000
      return row.status === activeTab
    })
    if (!keyword) return byTab
    return byTab.filter((row) => [row.name, row.description, row.owner].join(' ').toLowerCase().includes(keyword))
  }, [activeTab, search])

  const columns = useMemo<BoxDataTableColumn<WorkflowRow>[]>(() => [
    {
      id: 'name',
      header: t('workflow.workspaceDashboard.columns.workflow'),
      render: (row) => (
        <WorkflowNameCell
          row={row}
          name={row.name}
          description={row.description}
        />
      ),
    },
    {
      id: 'status',
      header: t('workflow.workspaceDashboard.columns.status'),
      render: (row) => <StatusBadge status={row.status} label={t(statusConfig[row.status].labelKey)} />,
    },
    {
      id: 'agents',
      header: t('workflow.workspaceDashboard.columns.linkedAgent'),
      render: (row) => <AgentAvatars agents={row.agents} extraAgents={row.extraAgents} />,
    },
    {
      id: 'todayRuns',
      header: t('workflow.workspaceDashboard.columns.runsToday'),
      cellClassName: 'font-semibold text-foreground',
      render: (row) => row.todayRuns || '-',
    },
    {
      id: 'avgLatency',
      header: t('workflow.workspaceDashboard.columns.avgLatency'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(row.status === 'abnormal' ? 'text-red-600 dark:text-red-300' : row.avgLatency === '2.6s' || row.avgLatency === '2.0s' ? 'text-orange-600 dark:text-orange-300' : 'text-emerald-600 dark:text-emerald-300')}>
          {row.avgLatency || '-'}
        </span>
      ),
    },
    {
      id: 'successRate',
      header: t('workflow.workspaceDashboard.columns.successRate'),
      cellClassName: 'font-semibold',
      render: (row) => (
        <span className={cn(row.status === 'abnormal' ? 'text-orange-600 dark:text-orange-300' : row.successRate ? 'text-emerald-600 dark:text-emerald-300' : 'text-muted-foreground')}>
          {row.successRate || '-'}
        </span>
      ),
    },
    {
      id: 'recentException',
      header: t('workflow.workspaceDashboard.columns.recentIncident'),
      render: (row) => row.recentException ? (
        <Badge className="rounded-md border-red-200 bg-red-50 text-red-600 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200">{row.recentException}</Badge>
      ) : <span className="text-muted-foreground">-</span>,
    },
    {
      id: 'owner',
      header: t('workflow.workspaceDashboard.columns.owner'),
      render: (row) => row.owner,
    },
    {
      id: 'lastRun',
      header: t('workflow.workspaceDashboard.columns.lastRun'),
      render: (row) => {
        return <span className={row.lastRun === '-' ? 'text-muted-foreground' : 'text-foreground/80'}>{row.lastRun}</span>
      },
    },
    {
      id: 'actions',
      header: t('workflow.workspaceDashboard.columns.actions'),
      render: (row) => <OperationButtons action={row.action} />,
    },
  ], [t])

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('workflow.workspaceDashboard.header.title')}
        description={t('workflow.workspaceDashboard.header.description')}
        action={(
          <Button className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700">
            <Plus className="h-4 w-4" />
            {t('workflow.workspaceDashboard.header.create')}
          </Button>
        )}
      />

      <MetricStrip items={metrics} deltaLabel={t('workflow.workspaceDashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('workflow.workspaceDashboard.toolbar.searchPlaceholder')}
        filterLabel={t('workflow.workspaceDashboard.toolbar.filter')}
        timeLabel={t('workflow.workspaceDashboard.toolbar.allTime')}
        refreshLabel={t('workflow.workspaceDashboard.toolbar.refresh')}
      />

      <BoxDataTable columns={columns} rows={rows} emptyMessage={t('workflow.workspaceDashboard.table.empty')} />

      <BoxPagination
        total={32}
        pageSize={10}
        currentPage={1}
        pages={[1, 2, 3, 4]}
        labels={{
          totalSuffix: t('workflow.workspaceDashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('workflow.workspaceDashboard.pagination.pageSizeSuffix'),
          goTo: t('workflow.workspaceDashboard.pagination.goTo'),
          page: t('workflow.workspaceDashboard.pagination.page'),
        }}
      />
    </BoxShell>
  )
}

export default WorkflowBoxPage
