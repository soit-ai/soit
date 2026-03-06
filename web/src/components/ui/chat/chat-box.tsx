import {
  AssistantRuntimeProvider,
  useAui,
  type AssistantClient,
  type ExportedMessageRepository,
  type ExportedMessageRepositoryItem,
  type ModelContext,
} from '@assistant-ui/react'
import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef } from 'react'
import { DevToolsModal } from '@assistant-ui/react-devtools'
import { Thread, type ThreadProps } from '@/components/ui/chat/thread'
import { localRuntime } from '@/components/ui/chat/local-runtime'
import { MessageConverter } from '@/components/ui/chat/message-adapter'
import { useQuery } from '@/hooks/use-query'
import { listMessages, type Message } from '@/services/chat-service'
import { API_BASE_URL } from '@/utils/request'
import { useChatStore } from '@/stores/chat'
import {
  DEFAULT_CHAT_PROVIDER,
  isDeepThinkingEnabled,
  resolveRuntimeChatModel,
  resolveStoredChatProvider,
} from '@/components/ui/chat/defaults'

export type ChatBoxProps = ThreadProps & {
  appId: string
  conversationId?: string
  modelName?: string
  historyReloadKey?: number | string
}

const ModelContextBridge = ({ getModelContext }: { getModelContext: () => ModelContext }) => {
  const aui = useAui()

  useEffect(() => {
    return aui.modelContext().register({
      getModelContext,
    })
  }, [aui, getModelContext])

  return null
}

const AuiBridge = forwardRef<AssistantClient>((_, ref) => {
  const aui = useAui()

  useImperativeHandle(ref, () => aui, [aui])

  return null
})

AuiBridge.displayName = 'AuiBridge'

const fetchConversationMessages = async (
  conversationId: string
): Promise<ExportedMessageRepository> => {
  if (!conversationId) {
    return { messages: [], headId: null }
  }

  const allItems: Message[] = []
  let pageToken: string | undefined
  const maxPages = 10

  for (let page = 0; page < maxPages; page += 1) {
    const response = await listMessages({
      conversation_id: conversationId,
      page_size: 100,
      page_token: pageToken,
    })
    allItems.push(...(response.items || []))
    pageToken = response.next_page_token || undefined
    if (!pageToken) {
      break
    }
  }

  const sortedItems = [...allItems].sort((a, b) => {
    const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
    const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
    return aTime - bTime
  })

  const dedupedItems: Message[] = []
  const seen = new Set<string>()
  for (const item of sortedItems) {
    if (!item.id || seen.has(item.id)) {
      continue
    }
    seen.add(item.id)
    dedupedItems.push(item)
  }

  const messageIdSet = new Set(dedupedItems.map((message) => message.id))
  const hasExplicitParent = dedupedItems.some((message) => Boolean(message.parent_id))

  const mappedMessages: ExportedMessageRepositoryItem[] = []
  let previousMessageId: string | null = null
  for (const message of dedupedItems) {
    const threadMessage = MessageConverter.toThreadMessage(message)
    const mappedParentId =
      hasExplicitParent && message.parent_id && messageIdSet.has(message.parent_id)
        ? message.parent_id
        : previousMessageId
    mappedMessages.push({
      message: threadMessage,
      parentId: mappedParentId ?? null,
    })
    previousMessageId = threadMessage.id
  }

  const headId =
    dedupedItems.length > 0 ? dedupedItems[dedupedItems.length - 1]?.id ?? null : null

  return {
    headId,
    messages: mappedMessages,
  }
}

const ThreadSyncEffect = ({
  appId,
  conversationId,
  historyReloadKey,
}: {
  appId: string
  conversationId?: string
  historyReloadKey?: number | string
}) => {
  const aui = useAui()
  const importedAtRef = useRef<number>(0)

  useEffect(() => {
    useChatStore.getState().setConversationId(appId, conversationId || '')
    if (!conversationId) {
      importedAtRef.current = 0
      aui.thread().import({ messages: [] })
    }
  }, [appId, conversationId, aui])

  const { data: repository, dataUpdatedAt, error } = useQuery<ExportedMessageRepository>({
    queryKey: ['chat-messages', conversationId || '', historyReloadKey || 0],
    queryFn: () => fetchConversationMessages(conversationId || ''),
    options: {
      enabled: Boolean(conversationId),
      staleTime: Number.POSITIVE_INFINITY,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  useEffect(() => {
    if (!conversationId || !dataUpdatedAt) {
      return
    }
    if (importedAtRef.current === dataUpdatedAt) {
      return
    }
    // Always reset before importing persisted history to avoid accidental branch merges.
    aui.thread().import({ messages: [] })
    aui.thread().import(repository ?? { messages: [], headId: null })
    importedAtRef.current = dataUpdatedAt
  }, [aui, conversationId, dataUpdatedAt, repository])

  useEffect(() => {
    if (error) {
      console.error('Failed to load conversation messages:', error)
    }
  }, [error])

  return null
}

export const ChatBox = forwardRef<AssistantClient, ChatBoxProps>(
  ({ appId, conversationId, modelName, historyReloadKey, ...threadProps }, ref) => {
    const runtime = localRuntime({ appId })
    const activeConversationId = conversationId || ''

    const getModelContext = useCallback((): ModelContext => {
      const deepThinkingEnabled = isDeepThinkingEnabled()
      const resolvedModelName = resolveRuntimeChatModel(modelName, deepThinkingEnabled)
      return {
        config: {
          appId,
          modelName: resolvedModelName,
          provider: resolveStoredChatProvider() || DEFAULT_CHAT_PROVIDER,
          apiKey: import.meta.env.VITE_ASSISTANT_API_KEY || 'demo-key',
          baseUrl: '/chat/completions',
          streamBaseUrl: `${API_BASE_URL}/chat/stream`,
          authorization:
            import.meta.env.VITE_ASSISTANT_HEADER_AUTH ||
            'Bearer ' + (localStorage.getItem('token') || 'demo-token'),
          stream: true,
          deepThinking: deepThinkingEnabled,
          reasoningEffort: deepThinkingEnabled ? 'high' : undefined,
          conversation_id: activeConversationId,
        },
      }
    }, [activeConversationId, appId, modelName])

    return (
      <AssistantRuntimeProvider runtime={runtime}>
        <DevToolsModal />
        <ModelContextBridge getModelContext={getModelContext} />
        <AuiBridge ref={ref} />
        <ThreadSyncEffect
          appId={appId}
          conversationId={conversationId}
          historyReloadKey={historyReloadKey}
        />
        <Thread {...threadProps} />
      </AssistantRuntimeProvider>
    )
  }
)

ChatBox.displayName = 'ChatBox'
