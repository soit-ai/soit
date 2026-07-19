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
import type { DashboardSection } from '@/services/observe-service'

import {
  asNumber,
  asString,
  formatMs,
  formatPercent,
  statusBadge,
} from './dashboard-utils'

function EmptyState({ section }: { section: DashboardSection }) {
  return (
    <div className="flex min-h-[220px] flex-col items-center justify-center rounded-lg border border-dashed bg-panel p-8 text-center">
      <Database className="h-8 w-8 text-muted-foreground" />
      <div className="mt-3 text-base font-semibold">{section.empty_state.title}</div>
      <div className="mt-1 max-w-md text-sm text-muted-foreground">{section.empty_state.description}</div>
      <Link to="/observe/runs?include_observe_summary=true" className="mt-4 text-sm font-medium text-blue-600 hover:underline dark:text-blue-300">
        打开 Run Explorer
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
  if (!section.rows.length) return <EmptyState section={section} />
  const title = section.id === 'agent_health'
    ? 'Agent 健康明细'
    : section.id === 'workflow_bottlenecks'
      ? '瓶颈明细'
      : section.id === 'tool_reliability'
        ? '工具明细'
        : '知识质量明细'

  const columns = section.id === 'agent_health'
    ? ['Agent 名称', '状态', '运行数', '平均延迟', '错误率', '成功率', '最近异常', '负责人', '最近运行']
    : section.id === 'workflow_bottlenecks'
      ? ['工作流', '阶段', '当前队列', '平均等待', '失败率', '影响 Agent', '负责人']
      : section.id === 'tool_reliability'
        ? ['工具名称', '类型', '调用次数', '成功率', '平均耗时', '失败原因', '关联 Agent', '负责人']
        : ['知识库', '关联 Agent', '命中率', '无答案率', '过期片段', '最近更新', '状态', '负责人']

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
              <TableHead className="h-9 w-[132px] px-3 text-right text-xs font-semibold">操作</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {section.rows.map((row) => (
              <TableRow key={row.id} className="h-11">
                {renderCells(row).map((cell, index) => <TableCell key={`${row.id}-${index}`} className="px-3 py-2 text-[13px]">{cell}</TableCell>)}
                <TableCell className="px-3 py-2 text-right">
                  <div className="flex justify-end gap-1">
                    <Button variant="outline" size="icon-sm" aria-label="查看运行" onClick={() => onOpenRuns(row)}><BarChart3 className="h-4 w-4" /></Button>
                    <Button variant="outline" size="icon-sm" aria-label="查看详情" onClick={() => onOpenDetail(row)}><LineChart className="h-4 w-4" /></Button>
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="outline" size="icon-sm" aria-label="更多操作"><MoreHorizontal className="h-4 w-4" /></Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem onClick={() => onOpenRuns(row)}>查看运行</DropdownMenuItem>
                        <DropdownMenuItem onClick={() => navigator.clipboard?.writeText(row.id)}>复制 ID</DropdownMenuItem>
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
