import {
  listConversations,
  createConversation,
  deleteConversation,
  updateConversation,
} from '@/services/chat-service'
import type { ComponentType, PropsWithChildren } from 'react'
import { type ThreadMessage } from '@assistant-ui/react'
import { MessageConverter } from './message-adapter'
import { resolveStoredChatModel, resolveStoredChatProvider } from './defaults'

// Thread status type.
export type RemoteThreadStatus = 'regular' | 'archived'

// Thread metadata type.
export type RemoteThreadMetadata = {
  readonly remoteId: string
  readonly externalId?: string
  readonly title?: string
  readonly status: RemoteThreadStatus
  readonly createdAt?: number
  readonly updatedAt?: number
}

// Thread list response type.
export type RemoteThreadListResponse = {
  threads: RemoteThreadMetadata[]
  total?: number
  page?: number
  pageSize?: number
}

// Thread initialization response type.
export type RemoteThreadInitializeResponse = {
  remoteId: string
  externalId: string
  title?: string
}

// Adapter interface.
export interface RemoteThreadListAdapter {
  list(): Promise<RemoteThreadListResponse>
  initialize(threadId: string): Promise<RemoteThreadInitializeResponse>
  rename(remoteId: string, newTitle: string): Promise<void>
  archive(remoteId: string): Promise<void>
  unarchive(remoteId: string): Promise<void>
  delete(remoteId: string): Promise<void>
  generateTitle(remoteId: string, messages: readonly ThreadMessage[]): Promise<ReadableStream>
  unstable_Provider?: ComponentType<PropsWithChildren>
}

export const CustomThreadListAdapter = (appId: string): RemoteThreadListAdapter => {
  console.log(`[ThreadAdapter] Initializing adapter for appId: ${appId}`)

  return {
    async list(): Promise<RemoteThreadListResponse> {
      console.log(`[ThreadAdapter] Fetching conversations for appId: ${appId}`)
      try {
        const response = await listConversations({
          page_size: 100,
        })
        console.log(`[ThreadAdapter] Successfully fetched ${response.items.length} conversations`)

        return {
          threads: response.items.map((item) => ({
            appId,
            remoteId: item.id,
            title: item.title || 'New Chat',
            status: 'regular' as RemoteThreadStatus,
            externalId: item.id,
            createdAt: item.created_at ? new Date(item.created_at).getTime() : undefined,
            updatedAt: item.updated_at ? new Date(item.updated_at).getTime() : undefined,
          })),
          total: response.items.length,
          page: 1,
          pageSize: 100,
        }
      } catch (error) {
        console.error('[ThreadAdapter] Failed to fetch conversations:', error)
        return { threads: [] }
      }
    },

    async initialize(threadId: string): Promise<RemoteThreadInitializeResponse> {
      console.log(`[ThreadAdapter] Initializing new conversation with threadId: ${threadId}`)
      try {
        const defaultModelRef = resolveStoredChatModel()
        const provider = resolveStoredChatProvider()
        const newConversation = await createConversation({
          title: 'New Chat',
          default_model_ref: defaultModelRef,
          metadata: {
            provider,
            model_ref: defaultModelRef,
          },
        })
        console.log(`[ThreadAdapter] Successfully created new conversation with id: ${newConversation.id}`)

        return {
          remoteId: newConversation.id,
          externalId: newConversation.id,
          title: newConversation.title || undefined,
        }
      } catch (error) {
        console.error('[ThreadAdapter] Failed to create new conversation:', error)
        const fallbackId = threadId || `thread_${Date.now()}`
        console.log(`[ThreadAdapter] Using fallback id: ${fallbackId}`)
        return {
          remoteId: fallbackId,
          externalId: fallbackId,
          title: 'New Chat',
        }
      }
    },

    // Rename a conversation.
    async rename(remoteId: string, newTitle: string): Promise<void> {
      console.log(`[ThreadAdapter] Renaming conversation ${remoteId} to: ${newTitle}`)
      try {
        await updateConversation(remoteId, {
          title: newTitle,
        })
        console.log(`[ThreadAdapter] Successfully renamed conversation ${remoteId}`)
      } catch (error) {
        console.error(`[ThreadAdapter] Failed to rename conversation ${remoteId}:`, error)
        throw error
      }
    },

    // Delete a conversation.
    async delete(remoteId: string): Promise<void> {
      console.log(`[ThreadAdapter] Deleting conversation: ${remoteId}`)
      try {
        await deleteConversation(remoteId)
        console.log(`[ThreadAdapter] Successfully deleted conversation ${remoteId}`)
      } catch (error) {
        console.error(`[ThreadAdapter] Failed to delete conversation ${remoteId}:`, error)
        throw error
      }
    },

    // Archive a conversation.
    async archive(remoteId: string): Promise<void> {
      console.log(`[ThreadAdapter] Archiving conversation: ${remoteId}`)
      try {
        await updateConversation(remoteId, { status: 'archived' })
      } catch (error) {
        console.error(`[ThreadAdapter] Failed to archive conversation ${remoteId}:`, error)
        throw error
      }
    },

    // Unarchive a conversation.
    async unarchive(remoteId: string): Promise<void> {
      console.log(`[ThreadAdapter] Unarchiving conversation: ${remoteId}`)
      try {
        await updateConversation(remoteId, { status: 'active' })
      } catch (error) {
        console.error(`[ThreadAdapter] Failed to unarchive conversation ${remoteId}:`, error)
        throw error
      }
    },

    // Generate a conversation title.
    async generateTitle(remoteId: string, messages: readonly ThreadMessage[]): Promise<ReadableStream> {
      console.log(`[ThreadAdapter] Generating title for conversation: ${remoteId}`)
      try {
        const firstUser = messages.find((message) => message.role === 'user')
        const content = firstUser?.content?.[0]
        const text = content && content.type === 'text' ? content.text : ''
        const title = text.trim().slice(0, 80) || 'New Chat'
        const encoder = new TextEncoder()
        return new ReadableStream({
          start(controller) {
            controller.enqueue(encoder.encode(title))
            controller.close()
          },
        })
      } catch (error) {
        console.error(`[ThreadAdapter] Failed to generate title for conversation ${remoteId}:`, error)
        throw error
      }
    },
    // The Provider component adds thread-specific adapters.
    // unstable_Provider: ({ children }) => {
    //   console.log('[ThreadAdapter] unstable_Provider')
    //   const _adapters = useRuntimeAdapters()
    //   console.log('[ThreadAdapter] adapters', _adapters)
    //   // This runs in the context of each thread
    //   const threadListItem = useThreadListItem()
    //   console.log('[ThreadAdapter] threadListItem', threadListItem)
    //   const remoteId = threadListItem.remoteId
    //   // Create thread-specific history adapter
    //   const history = useMemo<ThreadHistoryAdapter>(
    //     () => ({
    //       async load() {
    //         console.log('[ThreadAdapter] Loading messages for thread:', remoteId)
    //         if (!remoteId) return { messages: [] }
    //         try {
    //           const response = await getMessages({
    //             app_id: appId,
    //             conversation_id: remoteId,
    //             page_size: 100,
    //           })
    //           const messages = response.messages.map((msg) => ({
    //             message: MessageConverter.toThreadMessage(msg),
    //             parentId: null,
    //           }))
    //           return {
    //             messages,
    //             unstable_resume: false,
    //           }
    //         } catch (error) {
    //           console.error('[ThreadAdapter] Failed to load messages from API', error)
    //           return { messages: [], unstable_resume: false }
    //         }
    //       },
    //       async append(item) {
    //         console.log('[ThreadAdapter] Appending message for thread:', remoteId)
    //         if (!remoteId) {
    //           console.warn('Cannot save message - thread not initialized')
    //           return
    //         }

    //         try {
    //           // Create message via chat completions API.
    //           const _message: ChatMessage = {
    //             role: item.message.role as 'system' | 'user' | 'assistant',
    //             content: item.message.content[0].type === 'text' ? item.message.content[0].text : '',
    //           }

    //           const request: ChatCompletionRequest = {
    //             model: 'deepseek-chat',
    //             messages: [_message],
    //             context: {
    //               config: {
    //                 app_id: appId,
    //                 conversation_id: remoteId,
    //               },
    //             },
    //           }

    //           await createChatCompletion(request)
    //         } catch (error) {
    //           console.error('[ThreadAdapter] Failed to append message', error)
    //           throw error
    //         }
    //       },
    //     }),
    //     [remoteId]
    //   )
    //   console.log('[ThreadAdapter] history', history)
    //   const adapters = useMemo(() => ({ history }), [history])
    //   return <RuntimeAdapterProvider adapters={adapters}>{children}</RuntimeAdapterProvider>
    // },
  }
}
