import { useEffect, useMemo, useState } from 'react'
import {
  AlertTriangle,
  BarChart3,
  Box,
  Building2,
  Clock3,
  WalletCards,
} from 'lucide-react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import {
  BoxAlert,
  BoxDataTable,
  type BoxDataTableColumn,
  BoxPageHeader,
  BoxShell,
  MetricStrip,
} from '@/components/box'
import { Button } from '@/components/ui/button'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { getModelWorkbenchOverview } from '@/services/provider-service'

import { QuotaProgress, StatusBadge, WorkbenchPanel, type QuotaReminderRow, type ModelOverviewMetric } from './ui/workbench'

function formatNumber(value?: number | null) {
  return typeof value === 'number' ? value.toLocaleString() : '--'
}

function formatCurrency(value?: number | null, currency?: string | null) {
  if (typeof value !== 'number') return '--'
  return `${currency || ''} ${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`.trim()
}

function formatLatency(value?: number | null) {
  return typeof value === 'number' ? `${value.toLocaleString()}ms` : '--'
}

function ModelOverviewPage() {
  const { t } = useTranslation()
  const [chartsReady, setChartsReady] = useState(false)

  useEffect(() => {
    const timeout = window.setTimeout(() => setChartsReady(true), 150)
    return () => window.clearTimeout(timeout)
  }, [])

  const overviewQuery = useQuery({
    queryKey: ['models', 'workbench', 'overview'],
    queryFn: () => getModelWorkbenchOverview(),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const overview = overviewQuery.data
  const summary = overview?.summary

  const metrics = useMemo<ModelOverviewMetric[]>(() => [
    {
      id: 'models',
      label: t('model.overview.metrics.totalModels'),
      value: formatNumber(summary?.total_models),
      delta: `+${formatNumber(summary?.available_models)}`,
      trend: overview?.trend.map((row) => row.tokens) || [],
      icon: Box,
      tone: 'blue',
    },
    {
      id: 'providers',
      label: t('model.overview.metrics.providers'),
      value: formatNumber(summary?.total_providers),
      delta: `+${formatNumber(summary?.online_providers)}`,
      trend: overview?.trend.map((row) => row.calls) || [],
      icon: Building2,
      tone: 'green',
    },
    {
      id: 'calls',
      label: t('model.overview.metrics.monthCalls'),
      value: formatNumber(summary?.month_calls),
      delta: t('model.overview.metrics.fromRuns'),
      trend: overview?.trend.map((row) => row.calls) || [],
      icon: BarChart3,
      tone: 'blue',
    },
    {
      id: 'cost',
      label: t('model.overview.metrics.monthCost'),
      value: formatCurrency(summary?.month_cost_amount, summary?.currency),
      delta: t('model.overview.metrics.fromRuns'),
      trend: overview?.trend.map((row) => row.cost_amount) || [],
      icon: WalletCards,
      tone: 'green',
    },
    {
      id: 'exceptions',
      label: t('model.overview.metrics.exceptions'),
      value: formatNumber(summary?.abnormal_models),
      delta: summary?.abnormal_models ? t('model.overview.metrics.needsAttention') : t('model.overview.metrics.normal'),
      trend: overview?.trend.map((row) => row.avg_latency_ms || 0) || [],
      icon: AlertTriangle,
      tone: summary?.abnormal_models ? 'red' : 'green',
    },
  ], [overview?.trend, summary, t])

  const trendRows = useMemo(() => {
    const rows = overview?.trend || []
    if (rows.length) {
      return rows.map((row) => ({
        date: row.date,
        calls: row.calls,
        tokens: row.tokens,
        latency: row.avg_latency_ms || 0,
        cost: row.cost_amount,
      }))
    }
    return [
      { date: '05-25', tokens: 0, latency: 0 },
      { date: '05-26', tokens: 0, latency: 0 },
      { date: '05-27', tokens: 0, latency: 0 },
      { date: '05-28', tokens: 0, latency: 0 },
      { date: '05-29', tokens: 0, latency: 0 },
      { date: '05-30', tokens: 0, latency: 0 },
      { date: '05-31', tokens: 0, latency: 0 },
    ]
  }, [overview?.trend])

  const providerCostRows = useMemo(() => {
    const rows = overview?.cost_share || []
    const colors = ['#2563eb', '#10b981', '#f97316', '#6366f1', '#8b5cf6']
    return rows.slice(0, 5).map((row, index) => ({
      name: row.label || t('model.overview.unknownProvider'),
      value: row.value,
      color: colors[index] || '#94a3b8',
    }))
  }, [overview?.cost_share, t])

  const topModelRows = useMemo(() => {
    return (overview?.top_models || []).slice(0, 5).map((row, index) => ({
      id: row.id,
      rank: index + 1,
      name: row.display_name || row.model_id || t('model.overview.unknownModel'),
      calls: formatNumber(row.month_calls),
      latency: formatLatency(row.avg_latency_ms),
    }))
  }, [overview?.top_models, t])

  const topProviderRows = useMemo(() => {
    return (overview?.top_providers || []).slice(0, 5).map((row, index) => ({
      id: row.id,
      rank: index + 1,
      name: row.name,
      calls: formatNumber(row.month_calls),
      cost: formatCurrency(row.month_cost_amount, row.currency),
    }))
  }, [overview?.top_providers])

  const quotaRows = useMemo<QuotaReminderRow[]>(() => {
    return (overview?.quota_reminders || []).slice(0, 5).map((row) => ({
      id: row.id,
      label: row.label,
      used: row.quota_used === null || row.quota_used === undefined ? '--' : formatNumber(row.quota_used),
      remaining: row.remaining_quota === null || row.remaining_quota === undefined ? '--' : formatNumber(row.remaining_quota),
      status: row.status,
      percent: row.quota_percent || 0,
    }))
  }, [overview?.quota_reminders])

  const hasError = overviewQuery.isError

  const topModelColumns = useMemo<BoxDataTableColumn<{ id: string; rank: number; name: string; calls: string; latency: string }>[]>(() => [
    { id: 'rank', header: t('model.overview.tables.rank'), render: (row) => row.rank },
    { id: 'name', header: t('model.overview.tables.model'), render: (row) => row.name },
    { id: 'calls', header: t('model.overview.tables.calls'), cellClassName: 'font-semibold text-foreground', render: (row) => row.calls },
    { id: 'latency', header: t('model.overview.tables.latency'), render: (row) => row.latency },
  ], [t])

  const topProviderColumns = useMemo<BoxDataTableColumn<{ id: string; rank: number; name: string; calls: string; cost: string }>[]>(() => [
    { id: 'rank', header: t('model.overview.tables.rank'), render: (row) => row.rank },
    { id: 'name', header: t('model.providers.columns.provider'), render: (row) => row.name },
    { id: 'calls', header: t('model.overview.tables.calls'), cellClassName: 'font-semibold text-foreground', render: (row) => row.calls },
    { id: 'cost', header: t('model.providers.columns.monthCost'), render: (row) => row.cost },
  ], [t])

  const quotaColumns = useMemo<BoxDataTableColumn<QuotaReminderRow>[]>(() => [
    { id: 'label', header: t('model.overview.tables.providerModel'), render: (row) => row.label },
    { id: 'used', header: t('model.overview.tables.quotaUsed'), render: (row) => <QuotaProgress label={row.used} value={row.percent} /> },
    { id: 'remaining', header: t('model.overview.tables.remainingQuota'), render: (row) => row.remaining },
    { id: 'status', header: t('model.overview.tables.status'), render: (row) => <StatusBadge status={row.status} label={t(`model.overview.quotaStatus.${row.status}`)} /> },
  ], [t])

  return (
    <BoxShell>
      <BoxPageHeader
        title={t('model.overview.title')}
        description={t('model.overview.description')}
        action={(
          <Button className="h-11 gap-2 rounded-lg bg-blue-600 px-5 text-white shadow-[0_12px_28px_rgba(37,99,235,0.25)] hover:bg-blue-700">
            <Clock3 className="h-4 w-4" />
            {t('model.overview.actions.month')}
          </Button>
        )}
      />

      {hasError ? (
        <BoxAlert
          severity="warning"
          title={t('model.common.loadFailedTitle')}
          description={t('model.common.loadFailedDescription')}
        />
      ) : null}

      <MetricStrip items={metrics} deltaLabel={t('model.common.deltaLabel')} />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(360px,0.75fr)]">
        <WorkbenchPanel title={t('model.overview.trend.title')}>
          <div className="h-[300px] overflow-x-auto">
            {chartsReady ? (
              <BarChart data={trendRows} width={760} height={300}>
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 12 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="tokens" name={t('model.overview.trend.tokens')} fill="#2563eb" radius={[4, 4, 0, 0]} />
                <Bar dataKey="latency" name={t('model.overview.trend.latency')} fill="#f97316" radius={[4, 4, 0, 0]} />
              </BarChart>
            ) : null}
          </div>
        </WorkbenchPanel>

        <WorkbenchPanel title={t('model.overview.costShare.title')}>
          <div className="h-[300px] overflow-x-auto">
            {chartsReady && providerCostRows.length ? (
              <PieChart width={420} height={300}>
                <Pie data={providerCostRows} dataKey="value" nameKey="name" innerRadius={72} outerRadius={108} paddingAngle={2}>
                  {providerCostRows.map((entry) => <Cell key={entry.name} fill={entry.color} />)}
                </Pie>
                <Tooltip />
                <Legend />
              </PieChart>
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {t('model.overview.costShare.empty')}
              </div>
            )}
          </div>
        </WorkbenchPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-3">
        <WorkbenchPanel title={t('model.overview.tables.hotModels')}>
          <BoxDataTable columns={topModelColumns} rows={topModelRows} emptyMessage={t('model.overview.tables.empty')} />
        </WorkbenchPanel>
        <WorkbenchPanel title={t('model.overview.tables.hotProviders')}>
          <BoxDataTable columns={topProviderColumns} rows={topProviderRows} emptyMessage={t('model.overview.tables.empty')} />
        </WorkbenchPanel>
        <WorkbenchPanel title={t('model.overview.tables.quotaReminder')}>
          <BoxDataTable columns={quotaColumns} rows={quotaRows} emptyMessage={t('model.overview.tables.empty')} />
        </WorkbenchPanel>
      </div>
    </BoxShell>
  )
}

export default ModelOverviewPage
