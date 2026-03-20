import { forwardRef, useCallback, useEffect, useMemo, useState } from 'react'
import type { AssistantClient } from '@assistant-ui/react'
import { ChatBox, type ChatBoxProps } from '@/components/ui/chat/chat-box'
import { Thread, type ThreadProps } from '@/components/ui/chat/thread'

interface UseChatOptions {
  agentId?: string
  threadId?: string
  modelName?: string
  historyReloadKey?: number | string
}

type HookChatBoxProps = ThreadProps & {
  threadId?: string
  modelName?: string
  historyReloadKey?: number | string
}

export const ThreadBox = Thread

export const ChatUI = forwardRef<AssistantClient, ChatBoxProps>((props, ref) => {
  return <ChatBox ref={ref} {...props} />
})

ChatUI.displayName = 'ChatUI'

export const useChat = (options: UseChatOptions = {}) => {
  const {
    agentId = 'default',
    threadId: initialThreadId,
    modelName: initialModelName,
    historyReloadKey: initialHistoryReloadKey = 0,
  } = options

  const [threadId, setThreadId] = useState(initialThreadId || '')
  const [modelName, setModelName] = useState(initialModelName || '')
  const [historyReloadKey, setHistoryReloadKey] = useState<number | string>(
    initialHistoryReloadKey
  )

  useEffect(() => {
    setThreadId(initialThreadId || '')
  }, [initialThreadId])

  useEffect(() => {
    setModelName(initialModelName || '')
  }, [initialModelName])

  useEffect(() => {
    setHistoryReloadKey(initialHistoryReloadKey)
  }, [initialHistoryReloadKey])

  const refreshHistory = useCallback(() => {
    setHistoryReloadKey((prev) =>
      typeof prev === 'number' ? prev + 1 : Date.now()
    )
  }, [])

  const chatBoxProps = useMemo(
    (): Omit<ChatBoxProps, keyof ThreadProps> & Pick<ChatBoxProps, 'agentId'> => ({
      agentId,
      threadId: threadId || undefined,
      modelName: modelName || undefined,
      historyReloadKey,
    }),
    [agentId, threadId, modelName, historyReloadKey]
  )

  const HookChatBox = useMemo(
    () =>
      forwardRef<AssistantClient, HookChatBoxProps>(
        (
          {
            threadId: propThreadId,
            modelName: propModelName,
            historyReloadKey: propHistoryReloadKey,
            ...threadProps
          },
          ref
        ) => {
          return (
            <ChatBox
              ref={ref}
              agentId={agentId}
              threadId={(propThreadId ?? threadId) || undefined}
              modelName={(propModelName ?? modelName) || undefined}
              historyReloadKey={propHistoryReloadKey ?? historyReloadKey}
              {...threadProps}
            />
          )
        }
      ),
    [agentId, threadId, modelName, historyReloadKey]
  )

  HookChatBox.displayName = 'HookChatBox'

  return {
    agentId,
    threadId,
    modelName,
    historyReloadKey,
    setThreadId,
    setModelName,
    setHistoryReloadKey,
    refreshHistory,
    chatBoxProps,
    ChatBox: HookChatBox,
    ChatUI: HookChatBox,
    ThreadBox,
  }
}
