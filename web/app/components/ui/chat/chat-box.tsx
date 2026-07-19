import {
  AssistantRuntimeProvider,
  useAui,
  type AssistantClient,
  type ExportedMessageRepository,
  type ExportedMessageRepositoryItem,
  type ModelContext,
} from '@assistant-ui/react'
import {
  Suspense,
  forwardRef,
  lazy,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { Thread, type ThreadProps } from '@/components/ui/chat/thread'
import { useSoitAgUiRuntime } from '@/components/ui/chat/agui-runtime'
import { MessageConverter, type ChatLedgerMessage } from '@/components/ui/chat/message-adapter'
import { useQuery } from '@/hooks/use-query'
import { getThread, type ThreadMessage as RuntimeThreadMessage } from '@/services/thread-service'
import {
  DEFAULT_CHAT_PROVIDER,
  resolveRuntimeChatModel,
  resolveStoredChatProvider,
  isDeepThinkingEnabled,
  isCodeInterpreterEnabled,
  isWebSearchEnabled,
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
      model_ref: message.model_ref,
      tokens_prompt: message.tokens_prompt,
      tokens_completion: message.tokens_completion,
      finish_reason: message.finish_reason,
      run_id: message.run_id || undefined,
      response_id: message.response_id,
      task_id: message.task_id,
      status: message.status,
      sequence_no: message.sequence_no,
      summary: message.summary,
      citations_json: message.citations_json,
      attachments_json: message.attachments_json,
      tool_calls_json: message.tool_calls_json,
      error_code: message.error_code,
      error_message: message.error_message,
      created_by: message.created_by || undefined,
      metadata_json: {
        ...message.metadata_json,
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
  onReady,
}: {
  agentId: string
  threadId?: string
  historyReloadKey?: number | string
  onReady: () => void
}) => {
  const aui = useAui()
  const importedAtRef = useRef<number>(0)

  useEffect(() => {
    if (!threadId) {
      importedAtRef.current = 0
      aui.thread().import({ messages: [] })
      onReady()
    }
  }, [agentId, threadId, aui, onReady])

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
    onReady()
  }, [aui, threadId, dataUpdatedAt, repository, onReady])

  useEffect(() => {
    if (error) {
      console.error('Failed to load thread messages:', error)
      onReady()
    }
  }, [error, onReady])

  return null
}

export const ChatBox = forwardRef<AssistantClient, ChatBoxProps>(
  ({ agentId, threadId, modelName, historyReloadKey, ...threadProps }, ref) => {
    const syncIdentity = `${agentId}:${threadId || 'new'}`
    const [readyIdentity, setReadyIdentity] = useState('')
    const handleHistoryReady = useCallback(() => {
      setReadyIdentity(syncIdentity)
    }, [syncIdentity])
    const resolvedModelName = resolveRuntimeChatModel(modelName, isDeepThinkingEnabled())
    const runtime = useSoitAgUiRuntime({
      agentId,
      threadId,
      modelRef: resolvedModelName,
    })

    const getModelContext = useCallback((): ModelContext => {
      const deepThinkingEnabled = isDeepThinkingEnabled()
      const requestModelName = resolveRuntimeChatModel(modelName, deepThinkingEnabled)
      return {
        config: {
          soit: {
            mode: agentId !== 'default' ? 'agent' : 'direct',
            agentId: agentId !== 'default' ? agentId : undefined,
            modelRef: agentId === 'default' ? requestModelName : undefined,
            requestId: globalThis.crypto?.randomUUID?.(),
            deepThinking: deepThinkingEnabled,
            reasoningEffort: deepThinkingEnabled ? 'high' : undefined,
            provider: resolveStoredChatProvider() || DEFAULT_CHAT_PROVIDER,
            webSearch: agentId === 'default' ? isWebSearchEnabled() : undefined,
            codeInterpreter: agentId === 'default' ? isCodeInterpreterEnabled() : undefined,
          },
        } as any,
      }
    }, [agentId, modelName])

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
          onReady={handleHistoryReady}
        />
        {readyIdentity === syncIdentity ? (
          <Thread {...threadProps} />
        ) : (
          <div className="h-full w-full" aria-busy="true" />
        )}
      </AssistantRuntimeProvider>
    )
  }
)

ChatBox.displayName = 'ChatBox'
