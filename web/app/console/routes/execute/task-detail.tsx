import {
  Backlink,
  ConsoleButton,
  DataStateNote,
  KeyValueList,
  StatusChip,
  TaskProgress,
  WorkbenchPanel,
  type ConsoleStatus,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { NavLink, useParams } from 'react-router'
import { toast } from 'sonner'
import { requestErrorMessage } from '@/utils/request'
import {
  cancelTask,
  getTask,
  resumeTask,
  retryTask,
  type Task,
  type TaskControlResponse,
  type TaskEvent,
} from '@/services/task-service'

type EventTone = 'plain' | 'brand' | 'ok' | 'warn'

const TONE_CLASS: Record<EventTone, string | undefined> = {
  plain: undefined,
  brand: 'brand',
  ok: 'ok',
  warn: 'warn',
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
 * The task record has no display-name column; the server derives one from the
 * input payload for list rows, and the detail page applies the same rule so a
 * task reads with the same name on both pages.
 */
function taskTitle(task: Task): string {
  const input = task.input_json || {}
  for (const key of ['title', 'demo_title', 'name']) {
    const value = input[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return task.task_type
}

/** Prototype event stamp: 12:02:11.004Z. */
function formatStamp(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 23)}Z`
}

function formatDuration(ms: number): string {
  if (ms < 0) return '—'
  const seconds = Math.floor(ms / 1000)
  if (seconds < 60) return `${seconds}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}m`
}

function elapsedOf(task: Task): string {
  if (!task.started_at) return '—'
  const start = new Date(task.started_at).getTime()
  const end = task.finished_at ? new Date(task.finished_at).getTime() : Date.now()
  if (Number.isNaN(start) || Number.isNaN(end)) return '—'
  return formatDuration(end - start)
}

function payloadString(event: TaskEvent, key: string): string | undefined {
  const value = (event.payload_json || {})[key]
  return typeof value === 'string' && value ? value : undefined
}

function eventTone(event: TaskEvent): EventTone {
  const status = payloadString(event, 'status')
  if (status === 'succeeded') return 'ok'
  if (status && ['failed', 'canceled', 'cancelled', 'expired', 'paused', 'retrying', 'waiting_approval', 'waiting_input'].includes(status)) {
    return 'warn'
  }
  if (status && ['running', 'preparing'].includes(status)) return 'brand'
  return 'plain'
}

export default function ConsoleTaskDetail() {
  const { t } = useTranslation()
  const { id } = useParams<{ id: string }>()
  const navigate = useConsoleNavigate()

  const detailQuery = useQuery({
    queryKey: ['console', 'task-detail', id],
    queryFn: () => getTask(id as string),
    options: { enabled: Boolean(id), retry: false, refetchOnWindowFocus: false },
  })

  const refetchDetail = () => {
    void detailQuery.refetch()
  }

  const resumeMutation = useMutation<TaskControlResponse, unknown, void>({
    mutationKey: ['console', 'task-detail', id, 'resume'],
    mutationFn: () => resumeTask(id as string),
    onSuccess: refetchDetail,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to resume task'))
    },
  })
  const retryMutation = useMutation<TaskControlResponse, unknown, void>({
    mutationKey: ['console', 'task-detail', id, 'retry'],
    mutationFn: () => retryTask(id as string),
    onSuccess: refetchDetail,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to retry task'))
    },
  })
  const cancelMutation = useMutation<TaskControlResponse, unknown, void>({
    mutationKey: ['console', 'task-detail', id, 'cancel'],
    mutationFn: () => cancelTask(id as string),
    onSuccess: refetchDetail,
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to cancel task'))
    },
  })

  if (!detailQuery.data) {
    return (
      <>
        <Backlink to="/v2/execute/tasks">{t('console.taskDetail.back')}</Backlink>
        <div className="rd-head">
          <h1 style={{ fontFamily: 'var(--font-sans)' }}>{id}</h1>
        </div>
        <div className="panel">
          <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
        </div>
      </>
    )
  }

  const { task, events, checkpoints, available_actions: actions } = detailQuery.data

  const percent = typeof task.progress_json?.percent === 'number' ? task.progress_json.percent : null

  const meta: Array<{ key: string; value: string; to?: string }> = [
    { key: 'Type', value: task.task_type },
    {
      key: 'Agent',
      value: task.agent_id || '—',
      to: task.agent_id ? `/v2/build/agents/${task.agent_id}` : undefined,
    },
    { key: 'Thread', value: task.thread_id || '—' },
    {
      key: 'Run',
      value: task.run_id || '—',
      to: task.run_id ? `/v2/observe/runs/${task.run_id}` : undefined,
    },
    { key: 'Owner', value: task.created_by || '—' },
    { key: 'Started', value: formatStamp(task.started_at) },
    { key: 'Elapsed', value: elapsedOf(task) },
  ]

  // The task's declared input is the only configuration the runtime persists;
  // nested objects are omitted because the rail renders single-line values.
  const configuration = Object.entries(task.input_json || {})
    .filter(([, value]) => value === null || ['string', 'number', 'boolean'].includes(typeof value))
    .slice(0, 12)
    .map(([key, value]) => ({ key, value: value === null ? '—' : String(value) }))

  const linkedRuns = task.run_id ? [{ key: 'Run', value: task.run_id }] : []

  const controlPending =
    resumeMutation.isPending || retryMutation.isPending || cancelMutation.isPending

  return (
    <>
      <Backlink to="/v2/execute/tasks">{t('console.taskDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{taskTitle(task)}</h1>
        <StatusChip status={taskStatusToConsole(task.status)} label={statusLabel(task.status)} />
        {/* `progress_json.percent` is the only progress the runtime records. */}
        <TaskProgress pct={percent ?? 0} label={percent != null ? `${percent}%` : '—'} />
        <span className="spacer" />
        {actions.includes('resume') && (
          <ConsoleButton disabled={controlPending} onClick={() => resumeMutation.mutate()}>
            {t('console.taskDetail.resumeTask')}
          </ConsoleButton>
        )}
        {actions.includes('retry') && (
          <ConsoleButton disabled={controlPending} onClick={() => retryMutation.mutate()}>
            {t('console.taskDetail.retryTask')}
          </ConsoleButton>
        )}
        {actions.includes('cancel') && (
          <ConsoleButton
            style={{ color: 'var(--danger-foreground)' }}
            disabled={controlPending}
            onClick={() => cancelMutation.mutate()}
          >
            {t('console.taskDetail.cancel')}
          </ConsoleButton>
        )}
      </div>

      <div className="rd-meta">
        {meta.map((item) => (
          <span key={item.key}>
            {item.key}
            <b>
              {item.to ? (
                <a
                  className="runid"
                  href={item.to}
                  onClick={(event) => {
                    event.preventDefault()
                    navigate(item.to as string)
                  }}
                >
                  {item.value}
                </a>
              ) : (
                item.value
              )}
            </b>
          </span>
        ))}
      </div>

      <div className="rdgrid">
        <div className="stack">
          <WorkbenchPanel title={t('console.taskDetail.events')} hint={t('console.taskDetail.eventsHint')}>
            {events.length === 0 ? (
              <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
            ) : (
              <ul className="events">
                {events.map((event) => {
                  const status = payloadString(event, 'status')
                  const errorCode = payloadString(event, 'error_code')
                  const runId = payloadString(event, 'run_id')
                  return (
                    <li key={event.id}>
                      <span className={cn('eico', TONE_CLASS[eventTone(event)])} />
                      {event.event_type}
                      {[status, errorCode].filter(Boolean).map((token) => (
                        <span key={token} className="mono dim">
                          {' '}
                          {token}
                        </span>
                      ))}
                      {runId && (
                        <>
                          {' '}
                          <a
                            className="runid"
                            href={`/v2/observe/runs/${runId}`}
                            onClick={(clickEvent) => {
                              clickEvent.preventDefault()
                              navigate(`/v2/observe/runs/${runId}`)
                            }}
                          >
                            {runId}
                          </a>
                        </>
                      )}
                      <time>{formatStamp(event.created_at)}</time>
                    </li>
                  )
                })}
              </ul>
            )}
          </WorkbenchPanel>

          <WorkbenchPanel
            title={t('console.taskDetail.checkpoints')}
            hint={t('console.taskDetail.checkpointsHint')}
          >
            {checkpoints.length === 0 ? (
              <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>{t('console.taskDetail.columns.checkpoint')}</th>
                    <th className="num">{t('console.taskDetail.columns.afterStep')}</th>
                    <th className="num">{t('console.taskDetail.columns.stateSize')}</th>
                    <th className="num">{t('console.taskDetail.columns.created')}</th>
                    <th className="num" />
                  </tr>
                </thead>
                <tbody>
                  {checkpoints.map((checkpoint) => (
                    <tr key={checkpoint.id}>
                      <td className="mono">{checkpoint.id}</td>
                      <td className="num dim">{checkpoint.checkpoint_no}</td>
                      {/* Checkpoints record no serialized state size. */}
                      <td className="num dim">—</td>
                      <td className="num dimmer">{formatStamp(checkpoint.created_at)}</td>
                      <td className="num">
                        {/* Resume is a task-level control; the runtime has no
                            per-checkpoint resume endpoint. */}
                        {actions.includes('resume') && (
                          <ConsoleButton
                            size="sm"
                            disabled={controlPending}
                            onClick={() => resumeMutation.mutate()}
                          >
                            {t('console.taskDetail.resume')}
                          </ConsoleButton>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </WorkbenchPanel>
        </div>

        <div className="rail">
          <WorkbenchPanel
            title={t('console.taskDetail.pendingApproval')}
            actions={
              <NavLink className="more" to="/v2/govern/approvals">
                {t('console.taskDetail.allApprovals')}
              </NavLink>
            }
          >
            {/* BACKEND-PENDING: approvals are held on tool calls, not on the
                task, and no service exposes the pending request or a decision
                endpoint — so no approval text and no Approve/Reject controls. */}
            <DataStateNote />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.taskDetail.configuration')}>
            {configuration.length === 0 ? (
              <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
            ) : (
              <KeyValueList items={configuration} />
            )}
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.taskDetail.linkedRuns')}>
            {linkedRuns.length === 0 ? (
              <DataStateNote isPending={detailQuery.isPending} isError={detailQuery.isError} />
            ) : (
              <ul className="kv">
                {linkedRuns.map((item) => (
                  <li key={item.key}>
                    <span className="k">{item.key}</span>
                    <span className="v link">
                      <a
                        className="runid"
                        href={`/v2/observe/runs/${item.value}`}
                        onClick={(event) => {
                          event.preventDefault()
                          navigate(`/v2/observe/runs/${item.value}`)
                        }}
                      >
                        {item.value}
                      </a>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </WorkbenchPanel>
        </div>
      </div>
    </>
  )
}
