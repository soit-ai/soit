import {
  type ThreadMessage,
  type TextContentPart,
  type ThreadUserContentPart,
  type ThreadAssistantContentPart,
  type ThreadSystemMessage,
  type ThreadUserMessage,
  type ThreadAssistantMessage,
  type MessageStatus,
} from '@assistant-ui/react'
import { type Message } from '@/services/chat-service'

type ExportedMessageRepositoryItem = {
  message: ThreadMessage
  parentId: string | null
}

type ExportedMessageRepository = {
  headId?: string | null
  messages: ExportedMessageRepositoryItem[]
}

type NormalizedRole = 'system' | 'user' | 'assistant' | 'tool'

class MessageAdapterError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message)
    this.name = 'MessageAdapterError'
  }
}

const roleMap: Record<string, NormalizedRole> = {
  system: 'system',
  sys: 'system',
  user: 'user',
  human: 'user',
  assistant: 'assistant',
  ai: 'assistant',
  bot: 'assistant',
  model: 'assistant',
  tool: 'tool',
  function: 'tool',
}

const normalizeRole = (role: unknown, metadata?: Record<string, any> | null): NormalizedRole => {
  const roleKey = String(role || '')
    .trim()
    .toLowerCase()
  if (roleKey && roleMap[roleKey]) {
    return roleMap[roleKey]
  }

  const metadataCandidates = [
    metadata?.role,
    metadata?.sender,
    metadata?.message_role,
    metadata?.type,
  ]
  for (const candidate of metadataCandidates) {
    const candidateKey = String(candidate || '')
      .trim()
      .toLowerCase()
    if (candidateKey && roleMap[candidateKey]) {
      return roleMap[candidateKey]
    }
  }

  return 'assistant'
}

const normalizeThinkTags = (content: string): string => {
  return content
    .replace(/\\u003c/gi, '<')
    .replace(/\\u003e/gi, '>')
}

const splitReasoningContent = (
  content: string
): { reasoning: string; answer: string } => {
  const normalized = normalizeThinkTags(content || '')
  if (!normalized.includes('<think>')) {
    return { reasoning: '', answer: normalized }
  }

  let reasoning = ''
  let answer = ''
  let remaining = normalized
  let inReasoning = false

  while (remaining.length > 0) {
    if (inReasoning) {
      const closeIdx = remaining.indexOf('</think>')
      if (closeIdx < 0) {
        reasoning += remaining
        break
      }
      reasoning += remaining.slice(0, closeIdx)
      remaining = remaining.slice(closeIdx + '</think>'.length)
      inReasoning = false
      continue
    }

    const openIdx = remaining.indexOf('<think>')
    if (openIdx < 0) {
      answer += remaining
      break
    }
    if (openIdx > 0) {
      answer += remaining.slice(0, openIdx)
    }
    remaining = remaining.slice(openIdx + '<think>'.length)
    inReasoning = true
  }

  const normalizedReasoning = reasoning.trim()
  const normalizedAnswer =
    normalizedReasoning.length > 0 ? answer.replace(/^\s+/, '') : answer
  return {
    reasoning: normalizedReasoning,
    answer: normalizedAnswer,
  }
}

export const MessageConverter = {
  toThreadMessage(message: Message): ThreadMessage {
    const metadata = message.metadata_json || {}
    const normalizedRole = normalizeRole(message.role, metadata)
    const customMetadata = {
      server_message_id: message.id,
      parent_id: message.parent_id ?? null,
      source_role: message.role,
      run_id: message.run_id ?? metadata.run_id ?? undefined,
      model_ref: message.model_ref ?? metadata.model ?? undefined,
      tokens_prompt: message.tokens_prompt ?? metadata.tokens_prompt ?? undefined,
      tokens_completion: message.tokens_completion ?? metadata.tokens_completion ?? undefined,
      finish_reason: message.finish_reason ?? metadata.finish_reason ?? undefined,
      citations: metadata.citations ?? undefined,
      rag_query: metadata.rag_query ?? undefined,
      rag_datasets: metadata.rag_datasets ?? undefined,
      interrupted: metadata.interrupted ?? undefined,
    }
    const baseProps = {
      id: message.id,
      createdAt: message.created_at ? new Date(message.created_at) : new Date(),
      metadata: {
        custom: customMetadata,
        },
    }

    switch (normalizedRole) {
      case 'system':
        return {
          ...baseProps,
          role: 'system',
          content: [{ type: 'text', text: message.content }] as readonly [TextContentPart],
        } as ThreadSystemMessage

      case 'user':
        return {
          ...baseProps,
          role: 'user',
          content: [{ type: 'text', text: message.content }] as readonly ThreadUserContentPart[],
          attachments: [],
        } as ThreadUserMessage

      case 'assistant': {
        const { reasoning, answer } = splitReasoningContent(message.content || '')
        const assistantContent: ThreadAssistantContentPart[] = []
        if (reasoning) {
          assistantContent.push({ type: 'reasoning', text: reasoning } as any)
        }
        if (answer || !assistantContent.length) {
          assistantContent.push({ type: 'text', text: answer } as any)
        }
        return {
          ...baseProps,
          role: 'assistant',
          content: assistantContent as readonly ThreadAssistantContentPart[],
          status: { type: 'complete', reason: 'stop' } as MessageStatus,
          metadata: {
            unstable_state: null,
            unstable_annotations: [],
            unstable_data: [],
            steps: [],
            custom: customMetadata,
          },
        } as ThreadAssistantMessage
      }

      case 'tool':
        return {
          ...baseProps,
          role: 'assistant',
          content: [{ type: 'text', text: message.content }] as readonly ThreadAssistantContentPart[],
          status: { type: 'complete', reason: 'stop' } as MessageStatus,
          metadata: {
            unstable_state: null,
            unstable_annotations: [],
            unstable_data: [],
            steps: [],
            custom: { role: 'tool', ...customMetadata },
          },
        } as ThreadAssistantMessage

      default:
        throw new MessageAdapterError(`No support message role: ${normalizedRole}`)
    }
  },

  toApiMessage(message: ThreadMessage, conversationId: string): Message {
    const textPart = message.content?.find((part: any) => part?.type === 'text') as
      | { text?: string }
      | undefined
    const content = textPart?.text || ''

    return {
      id: message.id,
      role: message.role as 'system' | 'user' | 'assistant',
      content,
      created_at: message.createdAt instanceof Date ? message.createdAt.toISOString() : new Date().toISOString(),
      conversation_id: conversationId,
    }
  },
}
