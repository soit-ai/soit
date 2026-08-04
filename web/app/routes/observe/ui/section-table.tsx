import { Link } from 'react-router'
import { BarChart3, Database, LineChart, MoreHorizontal } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { useTranslation } from '@/i18n'
import type { DashboardSection } from '@/services/observe-service'

import {
  asNumber,
  asString,
  formatMs,
  formatPercent,
  statusBadge,
} from './dashboard-utils'

function EmptyState({ section }: { section: DashboardSection }) {
  const { t } = useTranslation()

  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed bg-panel p-8 text-center">
      <Database className="h-8 w-8 text-muted-foreground" />
      <div className="mt-3 text-base font-semibold">{section.empty_state.title}</div>
      <div className="mt-1 max-w-md text-sm text-muted-foreground">{section.empty_state.description}</div>
      <Link to="/observe/runs?include_observe_summary=true" className="mt-4 text-sm font-medium text-blue-600 hover:underline dark:text-blue-300">
        {t('observe.header.openRunExplorer')}
      </Link>
    </div>
  )
}

type SectionTableProps = {
  section: DashboardSection
  onOpenRuns: (row: Record<string, unknown>) => void
  onOpenDetail: (row: Record<string, unknown>) => void
}

export function SectionTable({ section, onOpenRuns, onOpenDetail }: SectionTableProps) {
  const { t } = useTranslation()
  if (!section.rows.length) return <EmptyState section={section} />
  const title = section.id === 'agent_health'
    ? t('observe.table.titles.agent_health')
    : section.id === 'workflow_bottlenecks'
      ? t('observe.table.titles.workflow_bottlenecks')
      : section.id === 'tool_reliability'
        ? t('observe.table.titles.tool_reliability')
        : t('observe.table.titles.knowledge_quality')

  const columns = section.id === 'agent_health'
    ? [
        t('observe.table.columns.agentName'),
        t('observe.table.columns.status'),
        t('observe.table.columns.runCount'),
        t('observe.table.columns.avgLatency'),
        t('observe.table.columns.errorRate'),
        t('observe.table.columns.successRate'),
        t('observe.table.columns.lastError'),
        t('observe.table.columns.owner'),
        t('observe.table.columns.lastRun'),
      ]
    : section.id === 'workflow_bottlenecks'
      ? [
          t('observe.table.columns.workflow'),
          t('observe.table.columns.stage'),
          t('observe.table.columns.currentQueue'),
          t('observe.table.columns.avgWait'),
          t('observe.table.columns.failureRate'),
          t('observe.table.columns.affectedAgents'),
          t('observe.table.columns.owner'),
        ]
      : section.id === 'tool_reliability'
        ? [
            t('observe.table.columns.toolName'),
            t('observe.table.columns.type'),
            t('observe.table.columns.callCount'),
            t('observe.table.columns.successRate'),
            t('observe.table.columns.avgDuration'),
            t('observe.table.columns.failureReason'),
            t('observe.table.columns.relatedAgents'),
            t('observe.table.columns.owner'),
          ]
        : [
            t('observe.table.columns.knowledgeBase'),
            t('observe.table.columns.relatedAgents'),
            t('observe.table.columns.hitRate'),
            t('observe.table.columns.missingAnswerRate'),
            t('observe.table.columns.expiredChunks'),
            t('observe.table.columns.lastUpdated'),
            t('observe.table.columns.status'),
            t('observe.table.columns.owner'),
          ]

  const renderCells = (row: Record<string, unknown>) => {
    if (section.id === 'agent_health') {
      return [asString(row.name), <Badge key="status" variant={statusBadge(asString(row.status))}>{asString(row.status)}</Badge>, asString(row.run_count), formatMs(row.avg_latency_ms), formatPercent(row.failed_run_count && row.run_count ? asNumber(row.failed_run_count) / asNumber(row.run_count) : 0), formatPercent(row.success_rate), asString(row.last_error), asString(row.owner), asString(row.last_run_at)]
    }
    if (section.id === 'workflow_bottlenecks') {
      return [asString(row.name), asString(row.stage), asString(row.current_queue), formatMs(row.avg_wait_ms), formatPercent(row.failure_rate), Array.isArray(row.affected_agents) ? row.affected_agents.join(', ') : '-', asString(row.owner)]
    }
    if (section.id === 'tool_reliability') {
      return [asString(row.name), asString(row.type), asString(row.call_count), formatPercent(row.success_rate), formatMs(row.avg_latency_ms), Object.keys((row.failure_reason || {}) as Record<string, unknown>).join(', ') || '-', Array.isArray(row.related_agents) ? row.related_agents.join(', ') : '-', asString(row.owner)]
    }
    return [asString(row.name), Array.isArray(row.related_agents) ? row.related_agents.join(', ') : '-', formatPercent(row.hit_rate), formatPercent(row.missing_answer_rate), asString(row.expired_chunks), asString(row.last_updated), <Badge key="status" variant={statusBadge(asString(row.status))}>{asString(row.status)}</Badge>, asString(row.owner)]
  }

  return (
    <div className="overflow-hidden rounded-lg border border-border/80 bg-panel/95">
      <div className="border-b px-4 py-3 text-[15px] font-semibold">{title}</div>
      <div className="overflow-x-auto">
        <Table className="min-w-[1040px]">
          <TableHeader>
            <TableRow className="h-9 bg-muted/60">
              {columns.map((column) => <TableHead key={column} className="h-9 px-3 text-xs font-semibold">{column}</TableHead>)}
              <TableHead className="h-9 w-[132px] px-3 text-right text-xs font-semibold">{t('observe.table.columns.actions')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {section.rows.map((row) => (
              <TableRow key={row.id} className="h-11">
                {renderCells(row).map((cell, index) => <TableCell key={`${row.id}-${index}`} className="px-3 py-2 text-[13px]">{cell}</TableCell>)}
                <TableCell className="px-3 py-2 text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="outline" size="icon-sm" aria-label={t('observe.table.rowActions.viewRuns')} onClick={() => onOpenRuns(row)}><BarChart3 className="h-4 w-4" /></Button>
                    <Button variant="outline" size="icon-sm" aria-label={t('observe.table.rowActions.viewDetail')} onClick={() => onOpenDetail(row)}><LineChart className="h-4 w-4" /></Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="icon-sm" aria-label={t('observe.table.rowActions.more')}><MoreHorizontal className="h-4 w-4" /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => onOpenRuns(row)}>{t('observe.table.rowActions.viewRuns')}</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigator.clipboard?.writeText(row.id)}>{t('observe.table.rowActions.copyId')}</DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
