import {
  Backlink,
  ConsoleButton,
  KeyValueList,
  StatusChip,
  TaskProgress,
  WorkbenchPanel,
} from '../../components'
import { useConsoleNavigate } from '../../shell/use-console-navigate'
import { mockTaskDetail } from '../../mocks/execute'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { NavLink } from 'react-router'

const TONE_CLASS: Record<string, string | undefined> = {
  plain: undefined,
  brand: 'brand',
  ok: 'ok',
  warn: 'warn',
  live: 'live',
}

// BACKEND-PENDING: task-service detail (events, checkpoints, handling) is
// fully available server-side; this fixture mirrors the prototype sample.
export default function ConsoleTaskDetail() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const task = mockTaskDetail

  return (
    <>
      <Backlink to="/v2/execute/tasks">{t('console.taskDetail.back')}</Backlink>

      <div className="rd-head">
        <h1 style={{ fontFamily: 'var(--font-sans)' }}>{task.name}</h1>
        <StatusChip status={task.status} label={task.status_label} />
        <TaskProgress pct={task.pct} label={task.progress_label} />
        <span className="spacer" />
        <ConsoleButton>{t('console.taskDetail.pause')}</ConsoleButton>
        <ConsoleButton>{t('console.taskDetail.retryStep')}</ConsoleButton>
        <ConsoleButton style={{ color: 'var(--danger-foreground)' }}>
          {t('console.taskDetail.cancel')}
        </ConsoleButton>
      </div>

      <div className="rd-meta">
        {task.meta.map((item) => (
          <span key={item.key}>
            {item.key}
            <b>
              {'to' in item && item.to ? (
                <a
                  className="runid"
                  href={item.to as string}
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
            <ul className="events">
              {task.events.map((event, index) => (
                <li key={index}>
                  <span className={cn('eico', TONE_CLASS[event.tone])}>
                    {event.tone === 'live' ? <i /> : null}
                  </span>
                  {event.tone === 'live' ? (
                    <span className="dim">{event.text}</span>
                  ) : (
                    <>
                      {event.text}
                      {event.mono?.map((token) => (
                        <span key={token} className="mono dim">
                          {' '}
                          {token}
                        </span>
                      ))}
                      {event.run_id && (
                        <>
                          {' '}
                          <a
                            className="runid"
                            href={`/v2/observe/runs/${event.run_id}`}
                            onClick={(clickEvent) => {
                              clickEvent.preventDefault()
                              navigate(`/v2/observe/runs/${event.run_id}`)
                            }}
                          >
                            {event.run_id}
                          </a>
                        </>
                      )}
                    </>
                  )}
                  <time>{event.at}</time>
                </li>
              ))}
            </ul>
          </WorkbenchPanel>

          <WorkbenchPanel
            title={t('console.taskDetail.checkpoints')}
            hint={t('console.taskDetail.checkpointsHint')}
          >
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
                {task.checkpoints.map((checkpoint) => (
                  <tr key={checkpoint.id}>
                    <td className="mono">{checkpoint.id}</td>
                    <td className="num dim">{checkpoint.after}</td>
                    <td className="num dim">{checkpoint.size}</td>
                    <td className="num dimmer">{checkpoint.created}</td>
                    <td className="num">
                      <ConsoleButton size="sm">{t('console.taskDetail.resume')}</ConsoleButton>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
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
            <div className="appr">
              <p>{task.approval.text}</p>
              <small>{task.approval.detail}</small>
              <div className="appr-actions">
                <ConsoleButton variant="primary">{t('console.taskDetail.approve')}</ConsoleButton>
                <ConsoleButton>{t('console.taskDetail.reject')}</ConsoleButton>
              </div>
            </div>
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.taskDetail.configuration')}>
            <KeyValueList items={task.configuration} />
          </WorkbenchPanel>

          <WorkbenchPanel title={t('console.taskDetail.linkedRuns')}>
            <ul className="kv">
              {task.linked_runs.map((item) => (
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
          </WorkbenchPanel>
        </div>
      </div>
    </>
  )
}
