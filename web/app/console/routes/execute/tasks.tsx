import { useMemo, useState } from 'react'

import { NavLink } from 'react-router'

import {
  ConsoleButton,
  DataStateRow,
  FilterChip,
  FilterSearch,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  Workbench,
  WorkbenchPanel,
  type ConsoleStatus,
} from '../../components'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../../components/ui'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { compactNumber, relativeTime } from '../../adapters/palette'
import { useQuery } from '@/hooks/use-query'
import { mockTiles } from '../../mocks/tiles'
import { useTranslation } from '@/i18n'
import { getTaskWorkbench, getTaskWorkbenchItems, type TaskWorkbenchRow } from '@/services/task-service'

type TaskFilter = 'all' | 'queued' | 'processing' | 'awaiting' | 'done' | 'failed'

const PAGE_SIZE = 50

/**
 * The prototype's quick filters expressed as the workbench tab / status pair the
 * server understands. `queued` and `done` have no dedicated tab, so they ride
 * the `all` tab with an exact status filter.
 */
const FILTER_QUERY: Record<TaskFilter, { tab: string; status?: string }> = {
  all: { tab: 'all' },
  queued: { tab: 'all', status: 'queued' },
  processing: { tab: 'running' },
  awaiting: { tab: 'waiting_approval' },
  done: { tab: 'all', status: 'succeeded' },
  failed: { tab: 'failed' },
}

/** Runtime task status → the shared console status vocabulary. */
function taskStatusToConsole(status: string): ConsoleStatus {
  switch (status) {
    case 'queued':
    case 'preparing':
      return 'queued'
    case 'running':
    case 'retrying':
      return 'running'
    case 'waiting_approval':
    case 'waiting_input':
    case 'paused':
      return 'warn'
    case 'succeeded':
      return 'pass'
    case 'failed':
      return 'failed'
    case 'canceled':
    case 'cancelled':
    case 'expired':
      return 'cancelled'
    default:
      return 'info'
  }
}

/** `waiting_approval` → `AWAITING APPROVAL`, matching the prototype's chips. */
function statusLabel(status: string): string {
  return status.replace(/_/g, ' ').toUpperCase()
}

/**
 * The prototype's second line under the task name. The workbench row carries no
 * free-text description, so it reads the runtime context the server does send:
 * the failure reason first (that is what the line is for on a failed task),
 * otherwise owner and agent.
 */
function rowNote(row: TaskWorkbenchRow): string {
  if (row.error_message) return row.error_message
  const context = [row.owner, row.agent_id].filter(Boolean).join(' · ')
  return context || '—'
}

export default function ConsoleTasks() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [filter, setFilter] = useState<TaskFilter>('all')
  const [search, setSearch] = useState('')
  const [pageToken, setPageToken] = useState<string | undefined>(undefined)
  const [prevTokens, setPrevTokens] = useState<string[]>([])

  const resetPaging = () => {
    setPageToken(undefined)
    setPrevTokens([])
  }

  const workbenchQuery = useQuery({
    queryKey: ['console', 'tasks', 'workbench'],
    queryFn: () => getTaskWorkbench({ page_size: PAGE_SIZE }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const keyword = search.trim()
  const itemsParams = useMemo(
    () => ({
      ...FILTER_QUERY[filter],
      keyword: keyword || undefined,
      page_token: pageToken,
      page_size: PAGE_SIZE,
    }),
    [filter, keyword, pageToken],
  )

  const itemsQuery = useQuery({
    queryKey: ['console', 'tasks', 'items', itemsParams],
    queryFn: () => getTaskWorkbenchItems(itemsParams),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const summary = workbenchQuery.data?.summary
  const tabs = workbenchQuery.data?.tabs
  const rows = itemsQuery.data?.items || []
  const total = itemsQuery.data?.total ?? 0
  const nextToken = itemsQuery.data?.next_page_token || null

  const goNext = () => {
    if (!nextToken) return
    setPrevTokens((stack) => [...stack, pageToken || ''])
    setPageToken(nextToken)
  }
  const goPrev = () => {
    if (prevTokens.length === 0) return
    const stack = [...prevTokens]
    const previous = stack.pop() || ''
    setPrevTokens(stack)
    setPageToken(previous || undefined)
  }

  return (
    <Workbench
      title={t('console.tasks.title')}
      description={t('console.tasks.description')}
      actions={
        // There is no POST /tasks: a task is created by the runtime when a run
        // needs one, so the honest affordance is to go start a run rather than
        // offer a create dialog with nothing behind it.
        <ConsoleButton variant="primary" onClick={() => navigate('/chat')}>
          <IconPlus />
          {t('console.tasks.newTask')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          {/* BACKEND-PENDING: prototype figure — the workbench summary reports
              no queue depth or queue age; see mocks/tiles.ts. */}
          <StatTile label={t('console.tasks.tiles.queued')} value={mockTiles.taskQueued.value} sub={<span className="mono dimmer">{mockTiles.taskQueued.sub}</span>} />
          <StatTile label={t('console.tasks.tiles.processing')} value={summary ? compactNumber(summary.running) : '—'} na={!summary} sub={<span className="mono dimmer">{summary ? `${summary.long_running} long-running` : t('console.common.loading')}</span>} />
          <StatTile label={t('console.tasks.tiles.awaiting')} value={summary ? compactNumber(summary.waiting_approval) : '—'} na={!summary} sub={<span className="mono dimmer">{summary ? `${summary.waiting_input} waiting on input` : t('console.common.loading')}</span>} />
          {/* The server counts every open failure; it is not windowed to 24h. */}
          <StatTile label={t('console.tasks.tiles.failed')} value={summary ? compactNumber(summary.failed) : '—'} na={!summary} sub={<span className="mono dimmer">{summary ? `all open · ${summary.today_completed} completed today` : t('console.common.loading')}</span>} />
        </StatTileGrid>
      }
      filters={
        <>
          {(
            [
              ['all', t('console.tasks.filters.all'), tabs?.all],
              // No server counter for queued or done; the chips carry no count.
              ['queued', t('console.tasks.filters.queued'), undefined],
              ['processing', t('console.tasks.filters.processing'), tabs?.running],
              ['awaiting', t('console.tasks.filters.awaiting'), tabs?.waiting_approval],
              ['done', t('console.tasks.filters.done'), undefined],
              ['failed', t('console.tasks.filters.failed'), tabs?.failed],
            ] as const
          ).map(([value, label, count]) => (
            <FilterChip key={value} active={filter === value} count={count} onClick={() => { setFilter(value); resetPaging() }}>
              {label}
            </FilterChip>
          ))}
          <FilterSearch
            value={search}
            onChange={(event) => { setSearch(event.target.value); resetPaging() }}
            placeholder={t('console.tasks.filters.searchPlaceholder')}
          />
        </>
      }
    >
      <WorkbenchPanel>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t('console.tasks.columns.task')}</TableHead>
              <TableHead>{t('console.tasks.columns.type')}</TableHead>
              <TableHead>{t('console.tasks.columns.status')}</TableHead>
              <TableHead>{t('console.tasks.columns.progress')}</TableHead>
              <TableHead className="num">{t('console.tasks.columns.attempt')}</TableHead>
              <TableHead>{t('console.tasks.columns.run')}</TableHead>
              <TableHead className="num">{t('console.tasks.columns.updated')}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <DataStateRow colSpan={7} isPending={itemsQuery.isPending} isError={itemsQuery.isError} />
            ) : (
              rows.map((task) => (
                <TableRow
                  key={task.id}
                  className="rowlink cursor-pointer"
                  onClick={() => navigate(`/execute/tasks/${task.id}`)}
                >
                  <TableCell>
                    <b style={{ fontWeight: 600 }}>{task.display_name}</b>
                    <br />
                    <span className="dimmer" style={{ fontSize: 11 }}>
                      {rowNote(task)}
                    </span>
                  </TableCell>
                  <TableCell className="mono dim">{task.task_type}</TableCell>
                  <TableCell>
                    <StatusChip status={taskStatusToConsole(task.status)} label={statusLabel(task.status)} />
                  </TableCell>
                  {/* The workbench row carries no progress; `progress_json` is
                      only on the task detail, so the list shows no bar. */}
                  <TableCell>
                    <span className="dimmer">—</span>
                  </TableCell>
                  {/* No attempt counter on the task record. */}
                  <TableCell className="num dim">—</TableCell>
                  <TableCell>
                    {task.run_id ? (
                      <a
                        className="runid"
                        href={`/observe/runs/${task.run_id}`}
                        onClick={(event) => {
                          event.preventDefault()
                          event.stopPropagation()
                          navigate(`/observe/runs/${task.run_id}`)
                        }}
                      >
                        {task.run_id}
                      </a>
                    ) : (
                      <span className="dimmer">—</span>
                    )}
                  </TableCell>
                  <TableCell className="num dimmer">{relativeTime(task.updated_at)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
        <Pager
          summary={
            <>
              {t('console.tasks.pageSummary', { count: rows.length, total })}
              <span className="mono" style={{ marginLeft: 14 }}>
                {summary ? `updated ${relativeTime(summary.updated_at)}` : ''}
              </span>
            </>
          }
          onPrev={goPrev}
          onNext={goNext}
          prevDisabled={prevTokens.length === 0}
          nextDisabled={!nextToken}
          prevLabel={t('console.runs.prev')}
          nextLabel={t('console.runs.next')}
        >
          <span className="spacer" />
          <NavLink className="more" to="/govern/approvals">
            {t('console.tasks.awaitingLink', { count: tabs?.waiting_approval ?? 0 })}
          </NavLink>
        </Pager>
      </WorkbenchPanel>
    </Workbench>
  )
}
