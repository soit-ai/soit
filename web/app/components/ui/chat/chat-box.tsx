import {
  AssistantRuntimeProvider,
  useAui,
  type AssistantClient,
  type ExportedMessageRepository,
  type ExportedMessageRepositoryItem,
  type ModelContext,
} from '@assistant-ui/react'
import { Suspense, forwardRef, lazy, useCallback, useEffect, useImperativeHandle, useRef } from 'react'
import { Thread, type ThreadProps } from '@/components/ui/chat/thread'
import { localRuntime } from '@/components/ui/chat/local-runtime'
import { MessageConverter, type ChatLedgerMessage } from '@/components/ui/chat/message-adapter'
import { useQuery } from '@/hooks/use-query'
import { getThread, type ThreadMessage as RuntimeThreadMessage } from '@/services/thread-service'
import { API_BASE_URL } from '@/utils/request'
import {
  DEFAULT_CHAT_PROVIDER,
  resolveRuntimeChatModel,
  resolveStoredChatProvider,
  isDeepThinkingEnabled,
} from '@/components/ui/chat/defaults'

const ChatDevTools = import.meta.env.DEV
  ? lazy(async () => {
    const module = await import('@assistant-ui/react-devtools')
    return { default: module.DevToolsModal }
  })
  : null

export type ChatBoxProps = ThreadProps & {
  agentId: string
  threadId?: string
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

const fetchThreadMessages = async (
  threadId: string
): Promise<ExportedMessageRepository> => {
  if (!threadId) {
    return { messages: [], headId: null }
  }

  const detail = await getThread(threadId)

  const sortedItems = [...(detail.messages || [])].sort((a, b) => {
    if (typeof a.sequence_no === 'number' && typeof b.sequence_no === 'number' && a.sequence_no !== b.sequence_no) {
      return a.sequence_no - b.sequence_no
    }
    const aTime = a.created_at ? new Date(a.created_at).getTime() : 0
    const bTime = b.created_at ? new Date(b.created_at).getTime() : 0
    return aTime - bTime
  })

  const dedupedItems: RuntimeThreadMessage[] = []
  const seen = new Set<string>()
  for (const item of sortedItems) {
    if (!item.id || seen.has(item.id)) {
      continue
    }
    seen.add(item.id)
    dedupedItems.push(item)
  }

  const mappedMessages: ExportedMessageRepositoryItem[] = dedupedItems.map((message) => {
    const normalizedMessage: ChatLedgerMessage = {
      id: message.id,
      parent_id: message.parent_message_id || undefined,
      role: message.role,
      content: message.content,
      model_ref:
        message.model_ref ||
        (typeof message.metadata_json?.model_ref === 'string' ? message.metadata_json.model_ref : undefined),
      tokens_prompt:
        typeof message.tokens_prompt === 'number'
          ? message.tokens_prompt
          : typeof message.metadata_json?.tokens_prompt === 'number'
            ? message.metadata_json.tokens_prompt
            : undefined,
      tokens_completion:
        typeof message.tokens_completion === 'number'
          ? message.tokens_completion
          : typeof message.metadata_json?.tokens_completion === 'number'
            ? message.metadata_json.tokens_completion
            : undefined,
      finish_reason:
        message.finish_reason ||
        (typeof message.metadata_json?.finish_reason === 'string' ? message.metadata_json.finish_reason : undefined),
      run_id: message.run_id || undefined,
      created_by: message.created_by || undefined,
      metadata_json: {
        ...message.metadata_json,
        citations: Array.isArray(message.citations_json) ? message.citations_json : message.metadata_json?.citations,
        attachments: Array.isArray(message.attachments_json) ? message.attachments_json : message.metadata_json?.attachments,
        tool_calls: Array.isArray(message.tool_calls_json) ? message.tool_calls_json : message.metadata_json?.tool_calls,
        response_id: message.response_id || message.metadata_json?.response_id,
        task_id: message.task_id || message.metadata_json?.task_id,
        status: message.status || message.metadata_json?.status,
        sequence_no: message.sequence_no,
      },
      created_at: message.created_at,
    }
    return {
      message: MessageConverter.toThreadMessage(normalizedMessage),
      parentId: normalizedMessage.parent_id || null,
    }
  })

  const headId =
    mappedMessages.length > 0 ? mappedMessages[mappedMessages.length - 1]?.message.id ?? null : null

  return {
    headId,
    messages: mappedMessages,
  }
}

const ThreadSyncEffect = ({
  agentId,
  threadId,
  historyReloadKey,
}: {
  agentId: string
  threadId?: string
  historyReloadKey?: number | string
}) => {
  const aui = useAui()
  const importedAtRef = useRef<number>(0)

  useEffect(() => {
    if (!threadId) {
      importedAtRef.current = 0
      aui.thread().import({ messages: [] })
    }
  }, [agentId, threadId, aui])

  const { data: repository, dataUpdatedAt, error } = useQuery<ExportedMessageRepository>({
    queryKey: ['chat-messages', threadId || '', historyReloadKey || 0],
    queryFn: () => fetchThreadMessages(threadId || ''),
    options: {
      enabled: Boolean(threadId),
      staleTime: Number.POSITIVE_INFINITY,
      retry: false,
      refetchOnWindowFocus: false,
    },
  })

  useEffect(() => {
    if (!threadId || !dataUpdatedAt) {
      return
    }
    if (importedAtRef.current === dataUpdatedAt) {
      return
    }
    // Always reset before importing persisted history to avoid accidental branch merges.
    aui.thread().import({ messages: [] })
    aui.thread().import(repository ?? { messages: [], headId: null })
    importedAtRef.current = dataUpdatedAt
  }, [aui, threadId, dataUpdatedAt, repository])

  useEffect(() => {
    if (error) {
      console.error('Failed to load thread messages:', error)
    }
  }, [error])

  return null
}

export const ChatBox = forwardRef<AssistantClient, ChatBoxProps>(
  ({ agentId, threadId, modelName, historyReloadKey, ...threadProps }, ref) => {
    const runtime = localRuntime({ agentId })

    const getModelContext = useCallback((): ModelContext => {
      const deepThinkingEnabled = isDeepThinkingEnabled()
      const resolvedModelName = resolveRuntimeChatModel(modelName, deepThinkingEnabled)
      return {
        config: {
          agentId,
          modelName: resolvedModelName,
          provider: resolveStoredChatProvider() || DEFAULT_CHAT_PROVIDER,
          apiKey: import.meta.env.VITE_ASSISTANT_API_KEY || 'demo-key',
          baseUrl: '/responses',
          streamBaseUrl: `${API_BASE_URL}/responses`,
          authorization:
            import.meta.env.VITE_ASSISTANT_HEADER_AUTH ||
            'Bearer ' + (localStorage.getItem('token') || 'demo-token'),
          stream: true,
          deepThinking: deepThinkingEnabled,
          reasoningEffort: deepThinkingEnabled ? 'high' : undefined,
          thread_id: threadId,
        } as any,
      }
    }, [agentId, modelName, threadId])

    return (
      <AssistantRuntimeProvider runtime={runtime}>
        {ChatDevTools ? (
          <Suspense fallback={null}>
            <ChatDevTools />
          </Suspense>
        ) : null}
        <ModelContextBridge getModelContext={getModelContext} />
        <AuiBridge ref={ref} />
        <ThreadSyncEffect
          agentId={agentId}
          threadId={threadId}
          historyReloadKey={historyReloadKey}
        />
        <Thread {...threadProps} />
      </AssistantRuntimeProvider>
    )
  }
)

ChatBox.displayName = 'ChatBox'
