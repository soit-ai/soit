import { useState } from 'react'

import { NavLink } from 'react-router'

import {
  ConsoleButton,
  FilterChip,
  FilterSearch,
  IconPlus,
  Pager,
  StatTile,
  StatTileGrid,
  StatusChip,
  TaskProgress,
  Workbench,
  WorkbenchPanel,
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
import { mockTaskCounts, mockTaskPagerNote, mockTaskTiles, mockTasks } from '../../mocks/execute'
import { useTranslation } from '@/i18n'

type TaskFilter = 'all' | 'queued' | 'processing' | 'awaiting' | 'done' | 'failed'

const FILTER_MATCH: Record<TaskFilter, (label: string) => boolean> = {
  all: () => true,
  queued: (label) => label === 'QUEUED',
  processing: (label) => label === 'PROCESSING',
  awaiting: (label) => label === 'AWAITING APPROVAL',
  done: (label) => label === 'DONE',
  failed: (label) => label === 'FAILED',
}

// BACKEND-PENDING: task-service list replaces the fixtures.
export default function ConsoleTasks() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [filter, setFilter] = useState<TaskFilter>('all')
  const [search, setSearch] = useState('')

  const rows = mockTasks.filter((task) => {
    if (!FILTER_MATCH[filter](task.status_label)) return false
    const query = search.trim().toLowerCase()
    if (!query) return true
    return [task.name, task.type, task.note].some((value) => value.toLowerCase().includes(query))
  })

  return (
    <Workbench
      title={t('console.tasks.title')}
      description={t('console.tasks.description')}
      actions={
        <ConsoleButton variant="primary">
          <IconPlus />
          {t('console.tasks.newTask')}
        </ConsoleButton>
      }
      tiles={
        <StatTileGrid>
          <StatTile label={t('console.tasks.tiles.queued')} value={mockTaskTiles.queued.value} sub={<span className="mono dimmer">{mockTaskTiles.queued.sub}</span>} />
          <StatTile label={t('console.tasks.tiles.processing')} value={mockTaskTiles.processing.value} sub={<span className="mono dimmer">{mockTaskTiles.processing.sub}</span>} />
          <StatTile label={t('console.tasks.tiles.awaiting')} value={mockTaskTiles.awaiting.value} sub={<span className="mono dimmer">{mockTaskTiles.awaiting.sub}</span>} />
          <StatTile label={t('console.tasks.tiles.failed')} value={mockTaskTiles.failed.value} sub={<span className="mono dimmer">{mockTaskTiles.failed.sub}</span>} />
        </StatTileGrid>
      }
      filters={
        <>
          {(
            [
              ['all', t('console.tasks.filters.all'), mockTaskCounts.all],
              ['queued', t('console.tasks.filters.queued'), mockTaskCounts.queued],
              ['processing', t('console.tasks.filters.processing'), mockTaskCounts.processing],
              ['awaiting', t('console.tasks.filters.awaiting'), mockTaskCounts.awaiting],
              ['done', t('console.tasks.filters.done'), mockTaskCounts.done],
              ['failed', t('console.tasks.filters.failed'), mockTaskCounts.failed],
            ] as const
          ).map(([value, label, count]) => (
            <FilterChip key={value} active={filter === value} count={count} onClick={() => setFilter(value)}>
              {label}
            </FilterChip>
          ))}
          <FilterSearch
            value={search}
            onChange={(event) => setSearch(event.target.value)}
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
            {rows.map((task) => (
              <TableRow
                key={task.id}
                className="rowlink cursor-pointer"
                onClick={() => navigate(`/v2/execute/tasks/${task.id}`)}
              >
                <TableCell>
                  <b style={{ fontWeight: 600 }}>{task.name}</b>
                  <br />
                  <span className="dimmer" style={{ fontSize: 11 }}>
                    {task.note}
                  </span>
                </TableCell>
                <TableCell className="mono dim">{task.type}</TableCell>
                <TableCell>
                  <StatusChip status={task.status} label={task.status_label} />
                </TableCell>
                <TableCell>
                  <TaskProgress pct={task.pct} label={task.progress_label} />
                </TableCell>
                <TableCell className="num dim">{task.attempt}</TableCell>
                <TableCell>
                  {task.run_id ? (
                    <a
                      className="runid"
                      href={`/v2/observe/runs/${task.run_id}`}
                      onClick={(event) => {
                        event.preventDefault()
                        event.stopPropagation()
                        navigate(`/v2/observe/runs/${task.run_id}`)
                      }}
                    >
                      {task.run_id}
                    </a>
                  ) : (
                    <span className="dimmer">—</span>
                  )}
                </TableCell>
                <TableCell className="num dimmer">{task.updated}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
        <Pager
          summary={
            <>
              {t('console.tasks.pageSummary', { count: rows.length, total: mockTaskCounts.all })}
              <span className="mono" style={{ marginLeft: 14 }}>
                {mockTaskPagerNote}
              </span>
            </>
          }
          onPrev={() => {}}
          onNext={() => {}}
          prevDisabled
          nextDisabled
          prevLabel={t('console.runs.prev')}
          nextLabel={t('console.runs.next')}
        >
          <span className="spacer" />
          <NavLink className="more" to="/v2/govern/approvals">
            {t('console.tasks.awaitingLink', { count: mockTaskCounts.awaiting })}
          </NavLink>
        </Pager>
      </WorkbenchPanel>
    </Workbench>
  )
}
