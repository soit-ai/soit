import {
  AlertTriangle,
  Check,
  Clock3,
  ExternalLink,
  FileText,
  ListChecks,
  MoreHorizontal,
  Plus,
  SquareStack,
} from 'lucide-react'
import { useMemo, useState } from 'react'

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

type KnowledgeStatus = 'ready' | 'indexing' | 'error' | 'unconfigured'

interface KnowledgeBoxRow {
  id: string
  name: string
  description: string
  marker: string
  markerClassName: string
  status: KnowledgeStatus
  contentSource: string
  documents: string
  chunks: string
  todayCalls?: string
  hitRate?: string
  lastSync: string
  owner: string
}

const metricDefinitions = [
  {
    id: 'total',
    labelKey: 'knowledge.workspaceDashboard.metrics.total',
    value: '32',
    delta: '+2',
    trend: [8, 9, 10, 9, 11, 12, 12, 13, 14, 13],
    icon: SquareStack,
    tone: 'blue',
  },
  {
    id: 'ready',
    labelKey: 'knowledge.workspaceDashboard.metrics.ready',
    value: '27',
    delta: '84.4%',
    trend: [7, 8, 8, 9, 10, 9, 11, 10, 12, 12],
    icon: Check,
    tone: 'green',
  },
  {
    id: 'ingested',
    labelKey: 'knowledge.workspaceDashboard.metrics.ingested',
    value: '1,284',
    delta: '+18.6%',
    trend: [5, 7, 8, 7, 10, 12, 9, 14, 13, 16],
    icon: FileText,
    tone: 'cyan',
  },
  {
    id: 'latency',
    labelKey: 'knowledge.workspaceDashboard.metrics.latency',
    value: '2m 18s',
    delta: '-24s',
    trend: [14, 12, 13, 10, 9, 11, 8, 7, 8, 6],
    icon: Clock3,
    tone: 'amber',
  },
  {
    id: 'exceptions',
    labelKey: 'knowledge.workspaceDashboard.metrics.exceptions',
    value: '4',
    delta: '+1',
    trend: [3, 4, 3, 6, 4, 5, 7, 5, 4, 4],
    icon: AlertTriangle,
    tone: 'red',
  },
] satisfies Array<Omit<React.ComponentProps<typeof MetricStrip>['items'][number], 'label'> & { labelKey: TranslationKey }>

const tabDefinitions = [
  { id: 'all', labelKey: 'knowledge.workspaceDashboard.tabs.all', count: 32 },
  { id: 'high', labelKey: 'knowledge.workspaceDashboard.tabs.highVolume', count: 8 },
  { id: 'low-hit', labelKey: 'knowledge.workspaceDashboard.tabs.lowHit', count: 3 },
  { id: 'slow', labelKey: 'knowledge.workspaceDashboard.tabs.slow', count: 4 },
  { id: 'unconfigured', labelKey: 'knowledge.workspaceDashboard.tabs.unconfigured', count: 2 },
] satisfies Array<Omit<BoxToolbarTab, 'label'> & { labelKey: TranslationKey }>

const knowledgeRows: KnowledgeBoxRow[] = [
  {
    id: 'support-policy',
    name: 'Support Policy Knowledge Base',
    description: 'After-sales, returns, exchanges, and benefits guidance',
    marker: 'S',
    markerClassName: 'bg-blue-600',
    status: 'ready',
    contentSource: 'Notion / PDF',
    documents: '1,248',
    chunks: '48k',
    todayCalls: '2,548',
    hitRate: '98.6%',
    lastSync: 'Just now',
    owner: 'Jude',
  },
  {
    id: 'bi-metric',
    name: 'BI Metric Definition Library',
    description: 'Business metrics, report definitions, and SQL examples',
    marker: 'B',
    markerClassName: 'bg-emerald-500',
    status: 'ready',
    contentSource: 'Dataset / API',
    documents: '860',
    chunks: '31k',
    todayCalls: '1,987',
    hitRate: '97.9%',
    lastSync: '1 min ago',
    owner: 'Alice',
  },
  {
    id: 'delivery-docs',
    name: 'Delivery Project Documents',
    description: 'Project plans, meeting notes, and risk items',
    marker: 'D',
    markerClassName: 'bg-violet-500',
    status: 'indexing',
    contentSource: 'Doc / Link',
    documents: '426',
    chunks: '18k',
    todayCalls: '942',
    hitRate: '93.1%',
    lastSync: '3 min ago',
    owner: 'Bob',
  },
  {
    id: 'finance-policy',
    name: 'Finance Policy Library',
    description: 'Approval rules, reimbursement policy, and contract templates',
    marker: 'F',
    markerClassName: 'bg-red-500',
    status: 'error',
    contentSource: 'PDF / OCR',
    documents: '321',
    chunks: '12k',
    todayCalls: '321',
    hitRate: '81.2%',
    lastSync: 'Just now',
    owner: 'David',
  },
  {
    id: 'hr-manual',
    name: 'HR Employee Handbook',
    description: 'Onboarding, compensation, benefits, and attendance policy',
    marker: 'H',
    markerClassName: 'bg-cyan-500',
    status: 'ready',
    contentSource: 'Wiki / Doc',
    documents: '785',
    chunks: '22k',
    todayCalls: '785',
    hitRate: '99.1%',
    lastSync: '5 min ago',
    owner: 'Eve',
  },
  {
    id: 'content-rules',
    name: 'Content Review Rules',
    description: 'Text, image, and content compliance rules',
    marker: 'C',
    markerClassName: 'bg-orange-500',
    status: 'unconfigured',
    contentSource: 'Manual',
    documents: '-',
    chunks: '-',
    lastSync: '-',
    owner: 'Frank',
  },
]

const statusConfig = {
  ready: {
    labelKey: 'knowledge.workspaceDashboard.status.ready',
    className: 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200',
  },
  indexing: {
    labelKey: 'knowledge.workspaceDashboard.status.indexing',
    className: 'border-amber-200 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-200',
  },
  error: {
    labelKey: 'knowledge.workspaceDashboard.status.error',
    className: 'border-red-200 bg-red-50 text-red-700 dark:border-red-400/20 dark:bg-red-400/10 dark:text-red-200',
  },
  unconfigured: {
    labelKey: 'knowledge.workspaceDashboard.status.unconfigured',
    className: 'border-border bg-muted text-muted-foreground',
  },
} satisfies Record<KnowledgeStatus, { labelKey: TranslationKey; className: string }>

function KnowledgeNameCell({ row, name, description }: { row: KnowledgeBoxRow; name: string; description: string }) {
  return (
    <div className="flex min-w-[270px] items-center gap-3">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-sm font-semibold text-white', row.markerClassName)}>
        {row.marker}
      </div>
      <div className="min-w-0">
        <div className="truncate font-semibold text-foreground">{name}</div>
        <div className="mt-0.5 max-w-[310px] truncate text-xs text-muted-foreground">{description}</div>
      </div>
    </div>
  )
}

function StatusBadge({ status, label }: { status: KnowledgeStatus; label: string }) {
  const config = statusConfig[status]
  return <Badge className={cn('rounded-md border px-2 py-1', config.className)}>{label}</Badge>
}

function HitRate({ row }: { row: KnowledgeBoxRow }) {
  if (!row.hitRate) return <span className="text-muted-foreground">-</span>
  const value = Number(row.hitRate.replace('%', ''))
  const className = value < 90
    ? 'text-red-600 dark:text-red-300'
    : value < 95
      ? 'text-orange-600 dark:text-orange-300'
      : 'text-emerald-600 dark:text-emerald-300'

  return <span className={cn('font-semibold', className)}>{row.hitRate}</span>
}

function OperationButtons() {
  return (
    <div className="flex items-center gap-2">
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <ListChecks className="h-3.5 w-3.5" />
      </Button>
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <ExternalLink className="h-3.5 w-3.5" />
      </Button>
      <Button variant="outline" size="icon-xs" className="border-border bg-panel text-foreground shadow-none">
        <MoreHorizontal className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

function KnowledgeBoxPage() {
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
    const byTab = knowledgeRows.filter((row) => {
      if (activeTab === 'all') return true
      if (activeTab === 'high') return Number((row.todayCalls || '0').replace(',', '')) > 1500
      if (activeTab === 'low-hit') return row.hitRate ? Number(row.hitRate.replace('%', '')) < 95 : false
      if (activeTab === 'slow') return row.status === 'indexing' || row.status === 'error'
      return row.status === activeTab
    })

    if (!keyword) return byTab
    return byTab.filter((row) => [row.name, row.description, row.contentSource, row.owner].join(' ').toLowerCase().includes(keyword))
  }, [activeTab, search])

  const columns = useMemo<BoxDataTableColumn<KnowledgeBoxRow>[]>(() => [
    {
      id: 'name',
      header: t('knowledge.workspaceDashboard.columns.knowledge'),
      render: (row) => (
        <KnowledgeNameCell
          row={row}
          name={row.name}
          description={row.description}
        />
      ),
    },
    {
      id: 'status',
      header: t('knowledge.workspaceDashboard.columns.status'),
      render: (row) => <StatusBadge status={row.status} label={t(statusConfig[row.status].labelKey)} />,
    },
    {
      id: 'source',
      header: t('knowledge.workspaceDashboard.columns.source'),
      render: (row) => row.contentSource,
    },
    {
      id: 'documents',
      header: t('knowledge.workspaceDashboard.columns.documentsChunks'),
      cellClassName: 'font-medium text-foreground',
      render: (row) => `${row.documents} / ${row.chunks}`,
    },
    {
      id: 'todayCalls',
      header: t('knowledge.workspaceDashboard.columns.callsToday'),
      cellClassName: 'font-medium text-foreground',
      render: (row) => row.todayCalls || '-',
    },
    {
      id: 'hitRate',
      header: t('knowledge.workspaceDashboard.columns.hitRate'),
      render: (row) => <HitRate row={row} />,
    },
    {
      id: 'lastSync',
      header: t('knowledge.workspaceDashboard.columns.lastSync'),
      render: (row) => {
        return <span className={row.lastSync === '-' ? 'text-muted-foreground' : 'text-foreground/80'}>{row.lastSync}</span>
      },
    },
    {
      id: 'owner',
      header: t('knowledge.workspaceDashboard.columns.owner'),
      render: (row) => row.owner,
    },
    {
      id: 'actions',
      header: t('knowledge.workspaceDashboard.columns.actions'),
      render: () => <OperationButtons />,
    },
  ], [t])

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('knowledge.workspaceDashboard.header.title')}
        description={t('knowledge.workspaceDashboard.header.description')}
        action={(
          <Button className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700 dark:bg-blue-500 dark:hover:bg-blue-400">
            <Plus className="h-4 w-4" />
            {t('knowledge.workspaceDashboard.header.create')}
          </Button>
        )}
      />

      <MetricStrip items={metrics} deltaLabel={t('knowledge.workspaceDashboard.metrics.deltaLabel')} />

      <BoxToolbar
        tabs={tabs}
        activeTab={activeTab}
        onTabChange={setActiveTab}
        searchValue={search}
        onSearchChange={setSearch}
        searchPlaceholder={t('knowledge.workspaceDashboard.toolbar.searchPlaceholder')}
        filterLabel={t('knowledge.workspaceDashboard.toolbar.filter')}
        timeLabel={t('knowledge.workspaceDashboard.toolbar.allTime')}
        refreshLabel={t('knowledge.workspaceDashboard.toolbar.refresh')}
      />

      <BoxDataTable columns={columns} rows={rows} emptyMessage={t('knowledge.workspaceDashboard.table.empty')} />

      <BoxPagination
        total={32}
        pageSize={10}
        currentPage={1}
        pages={[1, 2, 3]}
        labels={{
          totalSuffix: t('knowledge.workspaceDashboard.pagination.totalSuffix'),
          pageSizeSuffix: t('knowledge.workspaceDashboard.pagination.pageSizeSuffix'),
          goTo: t('knowledge.workspaceDashboard.pagination.goTo'),
          page: t('knowledge.workspaceDashboard.pagination.page'),
        }}
      />
    </BoxShell>
  )
}

export default KnowledgeBoxPage
