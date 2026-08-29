import { useMemo, useState } from 'react'

import { useParams } from 'react-router'
import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  DataStateNote,
  IconPlus,
  IconSend,
  IconSort,
  StatusChip,
  runStatusToConsole,
} from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { catColor, relativeTime } from '../adapters/palette'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { createResponse } from '@/services/responses-service'
import {
  createThread,
  deleteThread,
  getThread,
  listThreads,
  updateThread,
  type ThreadMessage,
} from '@/services/thread-service'
import { listRuns } from '@/services/run-service'
import { requestErrorMessage } from '@/utils/request'

const PAGE_SIZE = 50

function clockTime(iso?: string | null): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  return `${date.toISOString().slice(11, 19)}Z`
}

/** Threads group into Today / Yesterday / Earlier by last activity. */
function bucketOf(iso?: string | null): 'today' | 'yesterday' | 'earlier' {
  if (!iso) return 'earlier'
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return 'earlier'
  const today = new Date()
  const sameDay = (a: Date, b: Date) => a.toISOString().slice(0, 10) === b.toISOString().slice(0, 10)
  if (sameDay(then, today)) return 'today'
  const yesterday = new Date(today.getTime() - 86_400_000)
  if (sameDay(then, yesterday)) return 'yesterday'
  return 'earlier'
}

function initials(name?: string | null): string {
  if (!name) return '··'
  const parts = name.trim().split(/[\s@._-]+/).filter(Boolean)
  if (parts.length === 0) return '··'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[0][0] + parts[1][0]).toUpperCase()
}

/**
 * The console shell around the existing chat data model. Threads and their
 * message ledger come from thread-service; each assistant turn links to the run
 * it executed as, which is the evidence chip the prototype shows.
 */
export default function ConsoleChat() {
  const { t } = useTranslation()
  const { agentId, threadId } = useParams<{ agentId?: string; threadId?: string }>()
  const navigate = useConsoleNavigate()
  const [selectedThread, setSelectedThread] = useState<string | null>(threadId || null)
  const [draft, setDraft] = useState('')

  const threadsQuery = useQuery({
    queryKey: ['console', 'chat', 'threads', agentId],
    queryFn: () => listThreads({ page_size: PAGE_SIZE, agent_id: agentId }),
    options: { retry: false, refetchOnWindowFocus: false },
  })

  const threads = threadsQuery.data?.items || []
  const activeThreadId = selectedThread || threads[0]?.id || ''

  const threadQuery = useQuery({
    queryKey: ['console', 'chat', 'thread', activeThreadId],
    queryFn: () => getThread(activeThreadId),
    options: { enabled: Boolean(activeThreadId), retry: false, refetchOnWindowFocus: false },
  })

  const thread = threadQuery.data?.thread
  const messages = useMemo(
    () => (threadQuery.data?.messages || []).filter((message) => message.role !== 'system'),
    [threadQuery.data],
  )

  // Assistant turns carry a run_id; fetch those runs so each reply can show the
  // real verdict, step count and duration rather than a decorative chip.
  const runIds = useMemo(
    () =>
      Array.from(
        new Set(messages.map((message) => message.run_id).filter((id): id is string => Boolean(id))),
      ),
    [messages],
  )
  const runsQuery = useQuery({
    queryKey: ['console', 'chat', 'runs', activeThreadId, runIds.join(',')],
    queryFn: () => listRuns({ page_size: PAGE_SIZE, include_observe_summary: true }),
    options: {
      enabled: runIds.length > 0,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })
  const runById = useMemo(() => {
    const map = new Map<string, NonNullable<typeof runsQuery.data>['items'][number]>()
    ;(runsQuery.data?.items || []).forEach((run) => map.set(run.id, run))
    return map
  }, [runsQuery.data])

  const sendMutation = useMutation({
    mutationKey: ['console', 'chat', 'send', activeThreadId],
    mutationFn: () =>
      createResponse({
        thread_id: activeThreadId,
        agent_id: thread?.agent_id || agentId || undefined,
        input: [{ role: 'user', content: draft.trim() }],
      }),
    onSuccess: () => {
      setDraft('')
      void threadQuery.refetch()
      void threadsQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to send the message'))
    },
  })

  const [composeOpen, setComposeOpen] = useState(false)
  const [newThread, setNewThread] = useState({ title: '', agent: '' })
  const [renaming, setRenaming] = useState(false)
  const [renameValue, setRenameValue] = useState('')
  const [deletingThread, setDeletingThread] = useState(false)

  const createThreadMutation = useMutation({
    mutationKey: ['console', 'chat', 'create-thread'],
    mutationFn: () =>
      createThread({
        title: newThread.title.trim() || undefined,
        agent_id: newThread.agent.trim() || agentId || undefined,
      }),
    onSuccess: (created) => {
      setComposeOpen(false)
      setNewThread({ title: '', agent: '' })
      setSelectedThread(created.id)
      void threadsQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to create the thread'))
    },
  })

  const renameMutation = useMutation({
    mutationKey: ['console', 'chat', 'rename-thread'],
    mutationFn: () => updateThread(activeThreadId, { title: renameValue.trim() }),
    onSuccess: () => {
      setRenaming(false)
      void threadsQuery.refetch()
      void threadQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to rename the thread'))
    },
  })

  const deleteThreadMutation = useMutation({
    mutationKey: ['console', 'chat', 'delete-thread'],
    mutationFn: () => deleteThread(activeThreadId),
    onSuccess: () => {
      setDeletingThread(false)
      setSelectedThread(null)
      void threadsQuery.refetch()
    },
    onError: (error) => {
      toast.error(requestErrorMessage(error, 'Failed to delete the thread'))
    },
  })

  const buckets: Array<['today' | 'yesterday' | 'earlier', string]> = [
    ['today', t('console.chat.today')],
    ['yesterday', t('console.chat.yesterday')],
    ['earlier', t('console.common.all')],
  ]

  const agentLabel = thread?.agent_id || agentId || '—'

  const evidenceFor = (message: ThreadMessage) => {
    if (!message.run_id) return null
    const run = runById.get(message.run_id)
    const parts: string[] = []
    if (run?.observe_summary) {
      parts.push(`${run.observe_summary.step_count} steps`)
      if (run.observe_summary.audit_count) parts.push(`${run.observe_summary.audit_count} audits`)
    }
    if (run?.duration_ms != null) parts.push(`${(run.duration_ms / 1000).toFixed(1)}s`)
    return {
      run_id: message.run_id,
      status: runStatusToConsole(run?.status || 'unknown'),
      label: (run?.status || 'run').toUpperCase(),
      parts,
      terminal: run?.status !== 'running',
    }
  }

  return (
    <>
      <div className="page-head">
        <h1>{t('console.chat.title')}</h1>
        <span className="chip">
          <i style={{ background: 'var(--primary)' }} />
          {t('console.chat.governed')}
        </span>
        <span className="spacer" />
        <ConsoleButton variant="primary" onClick={() => setComposeOpen(true)}>
          <IconPlus />
          {t('console.chat.newThread')}
        </ConsoleButton>
      </div>

      <div className="chatgrid">
        <div className="panel threads">
          <div className="panel-head" style={{ gap: 8 }}>
            <span className="idm" style={{ '--c': catColor(agentLabel) } as React.CSSProperties}>
              <i />
              <b style={{ fontWeight: 600 }}>{agentLabel}</b>
            </span>
            <IconSort style={{ color: 'var(--faint)', marginLeft: 'auto' }} />
          </div>
          <div className="thread-list">
            {threads.length === 0 ? (
              <DataStateNote
                isPending={threadsQuery.isPending}
                isError={threadsQuery.isError}
              />
            ) : (
              buckets.map(([bucket, label]) => {
                const inBucket = threads.filter(
                  (row) => bucketOf(row.last_message_at || row.updated_at) === bucket,
                )
                if (inBucket.length === 0) return null
                return (
                  <div key={bucket}>
                    <div className="thread-cap">{label}</div>
                    {inBucket.map((row) => (
                      <a
                        key={row.id}
                        className={cn('thread', activeThreadId === row.id && 'on')}
                        href={`/v2/chat/${row.agent_id || 'agent'}/${row.id}`}
                        onClick={(event) => {
                          event.preventDefault()
                          setSelectedThread(row.id)
                        }}
                      >
                        <b>
                          {row.title || row.id}{' '}
                          <time>{clockTime(row.last_message_at || row.updated_at)}</time>
                        </b>
                        <small>{row.summary || `${row.message_count} messages`}</small>
                      </a>
                    ))}
                  </div>
                )
              })
            )}
          </div>
        </div>

        <div className="panel chatpane">
          <div className="chat-head">
            <h2>{thread?.title || t('console.chat.title')}</h2>
            <span className="chip">
              <i style={{ background: catColor(agentLabel) }} />
              {agentLabel}
            </span>
            <span className="mono dimmer" style={{ fontSize: 10.5 }}>
              {thread?.id || '—'}
            </span>
            <span className="spacer" style={{ flex: 1 }} />
            <span className="mono dimmer" style={{ fontSize: 10.5 }}>
              {thread?.default_model_ref || '—'}
            </span>
            {thread && (
              <>
                <ConsoleButton
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    setRenameValue(thread.title || '')
                    setRenaming(true)
                  }}
                >
                  {t('console.chat.rename')}
                </ConsoleButton>
                <ConsoleButton
                  variant="ghost"
                  size="sm"
                  style={{ color: 'var(--danger-foreground)' }}
                  onClick={() => setDeletingThread(true)}
                >
                  {t('console.chat.deleteAction')}
                </ConsoleButton>
              </>
            )}
          </div>

          <div className="msgs">
            {messages.length === 0 ? (
              <DataStateNote
                isPending={Boolean(activeThreadId) && threadQuery.isPending}
                isError={threadQuery.isError}
              />
            ) : (
              messages.map((message) => {
                const evidence = evidenceFor(message)
                const isUser = message.role === 'user'
                return (
                  <div key={message.id} className="msg">
                    {isUser ? (
                      <span className="who avatar">{initials(message.created_by)}</span>
                    ) : (
                      <span
                        className="who aavatar"
                        style={
                          {
                            '--c': catColor(agentLabel),
                            width: 26,
                            height: 26,
                          } as React.CSSProperties
                        }
                      />
                    )}
                    <div>
                      <div className="msg-h">
                        <b>{isUser ? message.created_by || 'you' : agentLabel}</b>
                        <time>{clockTime(message.created_at)}</time>
                      </div>
                      <div className="msg-b">
                        <p>{message.content}</p>
                      </div>
                      {evidence && (
                        <a
                          className="evd"
                          href={`/v2/observe/runs/${evidence.run_id}`}
                          onClick={(event) => {
                            event.preventDefault()
                            navigate(`/v2/observe/runs/${evidence.run_id}`)
                          }}
                        >
                          <span className="runid">{evidence.run_id}</span>
                          <StatusChip status={evidence.status} label={evidence.label} />
                          {evidence.parts.map((part) => (
                            <span key={part} style={{ display: 'contents' }}>
                              <span className="sep">·</span>
                              <span>{part}</span>
                            </span>
                          ))}
                          {evidence.terminal && (
                            <span
                              style={{ marginLeft: 'auto', color: 'var(--primary-subtle-foreground)' }}
                            >
                              {t('console.chat.openEvidence')}
                            </span>
                          )}
                        </a>
                      )}
                    </div>
                  </div>
                )
              })
            )}
          </div>

          {/* Turns post to the Responses API and the ledger is refetched when the
              run completes. Token-by-token streaming, tool calls and approval
              interrupts live in the AG-UI runtime under components/ui/chat; this
              shell should adopt that runtime rather than duplicate it. */}
          <div className="composer">
            <div className="composer-box">
              <input
                placeholder={t('console.chat.composerPlaceholder')}
                value={draft}
                disabled={!activeThreadId || sendMutation.isPending}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && draft.trim()) {
                    event.preventDefault()
                    sendMutation.mutate(undefined)
                  }
                }}
              />
              <span className="chip">{thread?.default_model_ref || '—'}</span>
              <ConsoleButton
                variant="primary"
                style={{ height: 28 }}
                disabled={!draft.trim() || !activeThreadId || sendMutation.isPending}
                onClick={() => sendMutation.mutate(undefined)}
              >
                <IconSend />
                {t('console.chat.send')}
              </ConsoleButton>
            </div>
            <div className="composer-note">
              <span>{t('console.chat.note1')}</span>
              <span>
                {thread?.last_message_at
                  ? `last activity ${relativeTime(thread.last_message_at)}`
                  : '—'}
              </span>
              <span style={{ marginLeft: 'auto' }}>{t('console.chat.note3')}</span>
            </div>
          </div>
        </div>
      </div>

      <ConsoleModal
        open={composeOpen}
        onOpenChange={setComposeOpen}
        title={t('console.chat.newTitle')}
        note={t('console.chat.newNote')}
        confirmLabel={t('console.common.create')}
        busy={createThreadMutation.isPending}
        onConfirm={() => createThreadMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.chat.threadName')}</label>
          <input
            className="input"
            value={newThread.title}
            onChange={(event) =>
              setNewThread((state) => ({ ...state, title: event.target.value }))
            }
          />
        </div>
        <div className="mrow">
          <label>{t('console.chat.threadAgent')}</label>
          <input
            className="input"
            placeholder={agentLabel}
            value={newThread.agent}
            onChange={(event) =>
              setNewThread((state) => ({ ...state, agent: event.target.value }))
            }
            style={{ fontFamily: 'var(--font-mono)', fontSize: 11.5 }}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={renaming}
        onOpenChange={setRenaming}
        title={t('console.chat.renameTitle')}
        confirmLabel={t('console.common.save')}
        confirmDisabled={!renameValue.trim()}
        busy={renameMutation.isPending}
        onConfirm={() => renameMutation.mutate(undefined)}
      >
        <div className="mrow">
          <label>{t('console.chat.threadName')}</label>
          <input
            className="input"
            value={renameValue}
            onChange={(event) => setRenameValue(event.target.value)}
          />
        </div>
      </ConsoleModal>

      <ConsoleModal
        open={deletingThread}
        onOpenChange={setDeletingThread}
        title={t('console.chat.deleteTitle')}
        confirmLabel={t('console.chat.deleteAction')}
        destructive
        busy={deleteThreadMutation.isPending}
        onConfirm={() => deleteThreadMutation.mutate(undefined)}
      >
        <div style={{ padding: '12px 16px', fontSize: 12.5, lineHeight: 1.6 }} className="dim">
          {t('console.chat.deleteConfirm')}
        </div>
      </ConsoleModal>
    </>
  )
}
