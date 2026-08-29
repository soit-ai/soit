import { useMemo, useState } from 'react'

import { useParams } from 'react-router'
import { toast } from 'sonner'

import {
  ConsoleButton,
  ConsoleModal,
  DataStateNote,
  IconPlus,
  IconSort,
} from '../components'
import { catColor, relativeTime } from '../adapters/palette'
import { useChat } from '@/hooks/use-chat'
import { useMutation, useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import {
  createThread,
  deleteThread,
  getThread,
  listThreads,
  updateThread,
} from '@/services/thread-service'
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

/**
 * The console shell around the existing chat stack. The thread rail and header
 * are the console's; the conversation is the assistant-ui thread over the AG-UI
 * runtime, mounted as-is so streaming, tool calls, attachments, reasoning and
 * approval interrupts behave exactly as they do everywhere else.
 */
export default function ConsoleChat() {
  const { t } = useTranslation()
  const { agentId, threadId } = useParams<{ agentId?: string; threadId?: string }>()
  const [selectedThread, setSelectedThread] = useState<string | null>(threadId || null)

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

  // The runtime is keyed to the selected thread; `agentId` falls back to the
  // shared default agent, the same value the standalone chat surface uses.
  const chat = useChat({
    agentId: thread?.agent_id || agentId || 'default',
    threadId: activeThreadId || undefined,
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
                        href={`/chat/${row.agent_id || 'agent'}/${row.id}`}
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
            {/* Falling back to the page title made two "Chat" headings on the
                page while a thread loaded; the id identifies the thread. */}
            <h2>{thread?.title || activeThreadId || '—'}</h2>
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

          {/* The conversation itself is the assistant-ui thread over the AG-UI
              runtime: streaming, markdown, tool calls, attachments, reasoning
              and approval interrupts all come from there. Only the shell around
              it — rail, head, modals — is the console's own. */}
          <div className="chatpane-thread">
            {activeThreadId ? (
              <chat.ChatBox
                key={`${agentLabel}:${activeThreadId}`}
                className="p-0 h-full"
                initInputPosition="bottom"
              />
            ) : (
              <DataStateNote
                isPending={threadsQuery.isPending}
                isError={threadsQuery.isError}
                emptyLabel={t('console.chat.noThread')}
              />
            )}
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
