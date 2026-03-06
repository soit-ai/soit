import { forwardRef, useCallback, useEffect, useMemo, useState } from 'react'
import type { AssistantClient } from '@assistant-ui/react'
import { ChatBox, type ChatBoxProps } from '@/components/ui/chat/chat-box'
import { Thread, type ThreadProps } from '@/components/ui/chat/thread'

interface UseChatOptions {
  appId?: string
  conversationId?: string
  modelName?: string
  historyReloadKey?: number | string
}

type HookChatBoxProps = ThreadProps & {
  conversationId?: string
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
    appId = 'default',
    conversationId: initialConversationId,
    modelName: initialModelName,
    historyReloadKey: initialHistoryReloadKey = 0,
  } = options

  const [conversationId, setConversationId] = useState(initialConversationId || '')
  const [modelName, setModelName] = useState(initialModelName || '')
  const [historyReloadKey, setHistoryReloadKey] = useState<number | string>(
    initialHistoryReloadKey
  )

  useEffect(() => {
    setConversationId(initialConversationId || '')
  }, [initialConversationId])

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
    (): Omit<ChatBoxProps, keyof ThreadProps> & Pick<ChatBoxProps, 'appId'> => ({
      appId,
      conversationId: conversationId || undefined,
      modelName: modelName || undefined,
      historyReloadKey,
    }),
    [appId, conversationId, modelName, historyReloadKey]
  )

  const HookChatBox = useMemo(
    () =>
      forwardRef<AssistantClient, HookChatBoxProps>(
        (
          {
            conversationId: propConversationId,
            modelName: propModelName,
            historyReloadKey: propHistoryReloadKey,
            ...threadProps
          },
          ref
        ) => {
          return (
            <ChatBox
              ref={ref}
              appId={appId}
              conversationId={(propConversationId ?? conversationId) || undefined}
              modelName={(propModelName ?? modelName) || undefined}
              historyReloadKey={propHistoryReloadKey ?? historyReloadKey}
              {...threadProps}
            />
          )
        }
      ),
    [appId, conversationId, modelName, historyReloadKey]
  )

  HookChatBox.displayName = 'HookChatBox'

  return {
    appId,
    conversationId,
    modelName,
    historyReloadKey,
    setConversationId,
    setModelName,
    setHistoryReloadKey,
    refreshHistory,
    chatBoxProps,
    ChatBox: HookChatBox,
    ChatUI: HookChatBox,
    ThreadBox,
  }
}
