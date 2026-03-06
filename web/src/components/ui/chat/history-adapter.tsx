import {
  type ThreadMessage,
  type ThreadHistoryAdapter,
  type ExportedMessageRepository,
  type ExportedMessageRepositoryItem,
} from '@assistant-ui/react'
import { listMessages, createChatCompletion, type ChatMessage, type ChatCompletionRequest, type Message } from '@/services/chat-service'
import { useChatStore } from '@/stores/chat'
import { MessageConverter } from './message-adapter'
import { resolveStoredChatModel } from './defaults'

class HistoryAdapterError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message)
    this.name = 'HistoryAdapterError'
  }
}

export type HistoryAdapter = ThreadHistoryAdapter

export class CustomHistoryAdapter implements HistoryAdapter {
  private logger = {
    info: (message: string, ...args: unknown[]) => console.log(`[HistoryAdapter] ${message}`, ...args),
    error: (message: string, error: unknown) => console.error(`[HistoryAdapter] ${message}`, error),
    warn: (message: string, ...args: unknown[]) => console.warn(`[HistoryAdapter] ${message}`, ...args),
  }

  constructor(private readonly appId: string) {}

  async load(): Promise<ExportedMessageRepository & { unstable_resume?: boolean }> {
    const currentRemoteId = useChatStore.getState().getConversationId(this.appId)
    this.logger.info('Loading history for thread:', currentRemoteId)
    if (!currentRemoteId) {
      this.logger.info('No thread ID, returning empty messages')
      return { messages: [], unstable_resume: false }
    }

    try {
      const allMessages: Message[] = []
      let pageToken: string | undefined = undefined
      const maxPages = 10
      const pageSize = 100

      for (let page = 0; page < maxPages; page += 1) {
        const response = await listMessages({
          conversation_id: currentRemoteId,
          page_size: pageSize,
          page_token: pageToken,
        })
        allMessages.push(...response.items)
        pageToken = response.next_page_token || undefined
        if (!pageToken) {
          break
        }
      }

      const sortedMessages = [...allMessages].sort((a, b) => {
        const aTime = new Date(a.created_at).getTime()
        const bTime = new Date(b.created_at).getTime()
        return aTime - bTime
      })

      const converted = sortedMessages.map((msg) => ({
        message: MessageConverter.toThreadMessage(msg),
        parentId: null,
      }))

      this.logger.info(`Loaded ${converted.length} messages for thread:`, currentRemoteId)
      return { messages: converted, unstable_resume: false }
    } catch (error) {
      this.logger.error('Failed to load messages from API', error)
      return { messages: [], unstable_resume: false }
    }
  }

  private resolveMessageText(message: ThreadMessage): string {
    const textPart = message.content.find((part) => part.type === 'text')
    if (textPart && textPart.type === 'text') {
      return textPart.text
    }
    try {
      return JSON.stringify(message.content)
    } catch (error) {
      return ''
    }
  }

  async append(item: ExportedMessageRepositoryItem): Promise<void> {
    const currentRemoteId = useChatStore.getState().getConversationId(this.appId)
    this.logger.info('Appending message for thread:', currentRemoteId)
    if (!currentRemoteId) {
      this.logger.warn('Cannot append message: no current thread ID')
      return
    }

    try {
      const resolvedModel = resolveStoredChatModel()
      const message: ChatMessage = {
        role: item.message.role as 'system' | 'user' | 'assistant',
        content: this.resolveMessageText(item.message),
      }

      const request: ChatCompletionRequest = {
        model: resolvedModel,
        conversation_id: currentRemoteId,
        messages: [message],
      }

      await createChatCompletion(request)
    } catch (error) {
      this.logger.error('Failed to append message', error)
      throw new HistoryAdapterError('Failed to append message', error)
    }
  }
}
