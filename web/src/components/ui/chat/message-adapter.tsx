import {
  type ThreadMessage,
  type TextMessagePart,
  type ThreadUserMessagePart,
  type ThreadAssistantMessagePart,
  type ThreadSystemMessage,
  type ThreadUserMessage,
  type ThreadAssistantMessage,
  type MessageStatus,
} from '@assistant-ui/react'

export interface ChatLedgerMessage {
  id: string
  parent_id?: string | null
  role: 'system' | 'user' | 'assistant' | string
  content: string
  response_id?: string | null
  task_id?: string | null
  status?: string | null
  sequence_no?: number | null
  model_ref?: string | null
  tokens_prompt?: number | null
  tokens_completion?: number | null
  finish_reason?: string | null
  run_id?: string | null
  summary?: string | null
  citations_json?: Array<Record<string, any>> | null
  attachments_json?: Array<Record<string, any>> | null
  tool_calls_json?: Array<Record<string, any>> | null
  error_code?: string | null
  error_message?: string | null
  created_by?: string | null
  metadata_json?: Record<string, any>
  created_at: string
}

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
  toThreadMessage(message: ChatLedgerMessage): ThreadMessage {
    const metadata = message.metadata_json || {}
    const normalizedRole = normalizeRole(message.role, metadata)
    const customMetadata = {
      server_message_id: message.id,
      parent_id: message.parent_id ?? null,
      source_role: message.role,
      response_id: message.response_id ?? metadata.response_id ?? undefined,
      task_id: message.task_id ?? metadata.task_id ?? undefined,
      message_status: message.status ?? metadata.status ?? undefined,
      sequence_no: message.sequence_no ?? metadata.sequence_no ?? undefined,
      run_id: message.run_id ?? metadata.run_id ?? undefined,
      model_ref: message.model_ref ?? metadata.model ?? undefined,
      tokens_prompt: message.tokens_prompt ?? metadata.tokens_prompt ?? undefined,
      tokens_completion: message.tokens_completion ?? metadata.tokens_completion ?? undefined,
      finish_reason: message.finish_reason ?? metadata.finish_reason ?? undefined,
      citations: message.citations_json ?? metadata.citations ?? undefined,
      attachments: message.attachments_json ?? metadata.attachments ?? undefined,
      tool_calls: message.tool_calls_json ?? metadata.tool_calls ?? undefined,
      summary: message.summary ?? metadata.summary ?? undefined,
      rag_query: metadata.rag_query ?? undefined,
      rag_knowledge: metadata.rag_knowledge ?? undefined,
      error_code: message.error_code ?? metadata.error_code ?? undefined,
      error_message: message.error_message ?? metadata.error_message ?? undefined,
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
          content: [{ type: 'text', text: message.content }] as readonly [TextMessagePart],
        } as ThreadSystemMessage

      case 'user':
        return {
          ...baseProps,
          role: 'user',
          content: [{ type: 'text', text: message.content }] as readonly ThreadUserMessagePart[],
          attachments: [],
        } as ThreadUserMessage

      case 'assistant': {
        const { reasoning, answer } = splitReasoningContent(message.content || '')
        const assistantContent: ThreadAssistantMessagePart[] = []
        if (reasoning) {
          assistantContent.push({ type: 'reasoning', text: reasoning } as any)
        }
        if (answer || !assistantContent.length) {
          assistantContent.push({ type: 'text', text: answer } as any)
        }
        return {
          ...baseProps,
          role: 'assistant',
          content: assistantContent as readonly ThreadAssistantMessagePart[],
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
          content: [{ type: 'text', text: message.content }] as readonly ThreadAssistantMessagePart[],
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

  toApiMessage(message: ThreadMessage, threadId: string): ChatLedgerMessage {
    const textPart = message.content?.find((part: any) => part?.type === 'text') as
      | { text?: string }
      | undefined
    const content = textPart?.text || ''

    return {
      id: message.id,
      role: message.role as 'system' | 'user' | 'assistant',
      content,
      created_at: message.createdAt instanceof Date ? message.createdAt.toISOString() : new Date().toISOString(),
      parent_id: null,
      metadata_json: {
        thread_id: threadId,
      },
    }
  },
}
