import { useState } from 'react'

import {
  ConsoleButton,
  IconPlus,
  IconSend,
  IconSort,
  StatusChip,
  type ConsoleStatus,
} from '../components'
import { useConsoleNavigate } from '../shell/use-console-navigate'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

interface MockThread {
  id: string
  cap: 'today' | 'yesterday'
  title: string
  time: string
  note: string
}

interface MockEvidence {
  run_id: string
  status: ConsoleStatus
  label: string
  parts: string[]
}

interface MockMessage {
  id: string
  who: 'user' | 'agent'
  name: string
  time: string
  body: React.ReactNode
  typing?: boolean
  evidence?: MockEvidence
}

// BACKEND-PENDING: chat threads and governed-run replies come from the chat service.
const MOCK_THREADS: MockThread[] = [
  { id: 'thread_8f2c', cap: 'today', title: 'checkout-api 502s', time: '13:47Z', note: 'tailing error logs from the restarted pods…' },
  { id: 'thread_8e01', cap: 'today', title: 'staging deploy window', time: '11:20Z', note: 'window confirmed 14:00–15:00Z, freeze after' },
  { id: 'thread_8d4b', cap: 'today', title: 'quota report for finance', time: '09:02Z', note: 'exported usage by team as run artifact' },
  { id: 'thread_7c92', cap: 'yesterday', title: 'vault rotation runbook', time: '18:44Z', note: 'SLACK_BOT_TOKEN rotated · 3 agents re-bound' },
  { id: 'thread_7b10', cap: 'yesterday', title: 'gpu-01 disk pressure', time: '15:02Z', note: 'cleared 42 GB of stale model shards' },
]

const MOCK_MESSAGES: MockMessage[] = [
  {
    id: 'm1',
    who: 'user',
    name: 'Jude',
    time: '13:45:12Z',
    body: <p>restart the checkout-api deployment in staging, it&apos;s serving 502s</p>,
  },
  {
    id: 'm2',
    who: 'agent',
    name: 'ops-copilot',
    time: '13:45:40Z',
    body: (
      <p>
        Restarted <span className="mono">deployment/checkout-api</span> in{' '}
        <span className="mono">ns/staging</span> and watched the rollout: all 12 replicas are back to
        ready. 502 rate dropped to zero within ~30s of the new pods passing readiness.
      </p>
    ),
    evidence: { run_id: 'run_01J9KD7Z2M', status: 'pass', label: 'PASS', parts: ['2/2 gates', '7 steps', '8.9s', '$0.038'] },
  },
  {
    id: 'm3',
    who: 'user',
    name: 'Jude',
    time: '13:46:05Z',
    body: <p>great — can you also purge the CDN cache for the storefront?</p>,
  },
  {
    id: 'm4',
    who: 'agent',
    name: 'ops-copilot',
    time: '13:46:18Z',
    body: (
      <p>
        I can&apos;t do that: <span className="mono">cdn.purge</span> isn&apos;t inside my tool grants,
        so the policy gate stopped the call before it executed. Nothing was sent to the CDN provider.
        An owner can extend grant <span className="mono">g_44</span> if this should be in scope.
      </p>
    ),
    evidence: { run_id: 'run_01J9KD8B4X', status: 'blocked', label: 'BLOCKED', parts: ['gate tool-permission', '1.1s', '$0.003'] },
  },
  {
    id: 'm5',
    who: 'user',
    name: 'Jude',
    time: '13:47:02Z',
    body: <p>ok, tail the last 50 error-level logs from the new pods instead</p>,
  },
  {
    id: 'm6',
    who: 'agent',
    name: 'ops-copilot',
    time: '13:47:10Z',
    body: (
      <p>
        Pulling logs from the 12 fresh pods, filtering to <span className="mono">level=error</span>{' '}
        since the rollout completed
        <span className="caret" />
      </p>
    ),
    evidence: { run_id: 'run_01J9KD9QRS', status: 'running', label: 'RUNNING', parts: ['step 3/5 · k8s.logs', '3.4s'] },
  },
]

export default function ConsoleChat() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [activeThread, setActiveThread] = useState('thread_8f2c')

  const caps: Array<['today' | 'yesterday', string]> = [
    ['today', t('console.chat.today')],
    ['yesterday', t('console.chat.yesterday')],
  ]

  return (
    <>
      <div className="page-head">
        <h1>{t('console.chat.title')}</h1>
        <span className="chip">
          <i style={{ background: 'var(--primary)' }} />
          {t('console.chat.governed')}
        </span>
        <span className="spacer" />
        <ConsoleButton variant="primary">
          <IconPlus />
          {t('console.chat.newThread')}
        </ConsoleButton>
      </div>

      <div className="chatgrid">
        <div className="panel threads">
          <div className="panel-head" style={{ gap: 8 }}>
            <span className="idm" style={{ '--c': 'var(--cat-purple)' } as React.CSSProperties}>
              <i />
              <b style={{ fontWeight: 600 }}>ops-copilot</b>
            </span>
            <IconSort style={{ color: 'var(--faint)', marginLeft: 'auto' }} />
          </div>
          <div className="thread-list">
            {caps.map(([cap, label]) => (
              <div key={cap}>
                <div className="thread-cap">{label}</div>
                {MOCK_THREADS.filter((thread) => thread.cap === cap).map((thread) => (
                  <a
                    key={thread.id}
                    className={cn('thread', activeThread === thread.id && 'on')}
                    href={`/v2/chat/ops-copilot/${thread.id}`}
                    onClick={(event) => {
                      event.preventDefault()
                      setActiveThread(thread.id)
                    }}
                  >
                    <b>
                      {thread.title} <time>{thread.time}</time>
                    </b>
                    <small>{thread.note}</small>
                  </a>
                ))}
              </div>
            ))}
          </div>
        </div>

        <div className="panel chatpane">
          <div className="chat-head">
            <h2>checkout-api 502s</h2>
            <span className="chip">
              <i style={{ background: 'var(--cat-purple)' }} />
              ops-copilot
            </span>
            <span className="mono dimmer" style={{ fontSize: 10.5 }}>
              thread_8f2c
            </span>
            <span className="spacer" style={{ flex: 1 }} />
            <span className="mono dimmer" style={{ fontSize: 10.5 }}>
              policy bundle v2026.08.27-2
            </span>
          </div>

          <div className="msgs">
            {MOCK_MESSAGES.map((message) => (
              <div key={message.id} className="msg">
                {message.who === 'user' ? (
                  <span className="who avatar">JD</span>
                ) : (
                  <span
                    className="who aavatar"
                    style={{ '--c': 'var(--cat-purple)', width: 26, height: 26 } as React.CSSProperties}
                  />
                )}
                <div>
                  <div className="msg-h">
                    <b>{message.name}</b>
                    <time>{message.time}</time>
                  </div>
                  <div className="msg-b">{message.body}</div>
                  {message.evidence && (
                    <a
                      className="evd"
                      href={`/v2/observe/runs/${message.evidence.run_id}`}
                      onClick={(event) => {
                        event.preventDefault()
                        navigate(`/v2/observe/runs/${message.evidence!.run_id}`)
                      }}
                    >
                      <span className="runid">{message.evidence.run_id}</span>
                      <StatusChip status={message.evidence.status} label={message.evidence.label} />
                      {message.evidence.parts.map((part) => (
                        <span key={part} style={{ display: 'contents' }}>
                          <span className="sep">·</span>
                          <span>{part}</span>
                        </span>
                      ))}
                      {message.evidence.status !== 'running' && (
                        <span style={{ marginLeft: 'auto', color: 'var(--primary-subtle-foreground)' }}>
                          {t('console.chat.openEvidence')}
                        </span>
                      )}
                    </a>
                  )}
                </div>
              </div>
            ))}
          </div>

          <div className="composer">
            <div className="composer-box">
              <input placeholder={t('console.chat.composerPlaceholder')} />
              <span className="chip">claude-sonnet-5</span>
              <ConsoleButton variant="primary" style={{ height: 28 }}>
                <IconSend />
                {t('console.chat.send')}
              </ConsoleButton>
            </div>
            <div className="composer-note">
              <span>{t('console.chat.note1')}</span>
              <span>{t('console.chat.note2')}</span>
              <span style={{ marginLeft: 'auto' }}>{t('console.chat.note3')}</span>
            </div>
          </div>
        </div>
      </div>
    </>
  )
}
