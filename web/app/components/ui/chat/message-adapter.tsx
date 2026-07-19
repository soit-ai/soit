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
  role: NormalizedRole
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

const normalizeRole = (role: unknown): NormalizedRole => {
  if (role === 'system' || role === 'user' || role === 'assistant' || role === 'tool') {
    return role
  }
  throw new MessageAdapterError(`Unsupported canonical message role: ${String(role)}`)
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

const normalizeReasoningText = (value: unknown): string => {
  if (typeof value === 'string') {
    return value.trim()
  }
  if (!Array.isArray(value)) {
    return ''
  }
  return value
    .map((item) => {
      if (typeof item === 'string') {
        return item.trim()
      }
      if (item && typeof item === 'object') {
        const content = (item as Record<string, unknown>).content
        return typeof content === 'string' ? content.trim() : ''
      }
      return ''
    })
    .filter(Boolean)
    .join('\n\n')
}

const normalizeAttachments = (attachments: unknown): any[] => {
  if (!Array.isArray(attachments)) {
    return []
  }
  return attachments
    .filter((attachment): attachment is Record<string, any> => !!attachment && typeof attachment === 'object')
    .map((attachment) => ({
      ...attachment,
      type: attachment.type || 'file',
      name: attachment.name || attachment.filename || 'Attachment',
      source: 'message',
    }))
}

const stringifyToolArgs = (args: unknown): string => {
  if (typeof args === 'string') {
    return args
  }
  try {
    return JSON.stringify(args ?? {})
  }
  catch {
    return '{}'
  }
}

const normalizeToolCalls = (toolCalls: unknown): ThreadAssistantMessagePart[] => {
  if (!Array.isArray(toolCalls)) {
    return []
  }
  return toolCalls
    .filter((toolCall): toolCall is Record<string, any> => !!toolCall && typeof toolCall === 'object')
    .map((toolCall, index) => {
      const toolCallId = toolCall.tool_call_id || toolCall.toolCallId || toolCall.id || `tool-${index + 1}`
      const toolName = toolCall.tool_name || toolCall.toolName || toolCall.name || 'tool'
      const args = toolCall.arguments_json ?? toolCall.arguments ?? toolCall.args ?? {}
      const result = toolCall.result_json ?? toolCall.result
      const status = toolCall.status === 'failed'
        ? { type: 'incomplete', reason: 'error', error: toolCall.error || toolCall.error_message || 'Tool call failed' }
        : { type: 'complete', reason: 'stop' }
      return {
        type: 'tool-call',
        toolCallId: String(toolCallId),
        toolName: String(toolName),
        args,
        argsText: stringifyToolArgs(args),
        result,
        status,
      } as any
    })
}

const normalizeMessageStatus = (
  status: unknown,
  errorMessage?: unknown
): MessageStatus => {
  const normalizedStatus = String(status || 'completed').trim().toLowerCase()
  if (normalizedStatus === 'failed' || normalizedStatus === 'error') {
    return {
      type: 'incomplete',
      reason: 'error',
      error: String(errorMessage || 'Agent execution failed'),
    }
  }
  if (normalizedStatus === 'canceled' || normalizedStatus === 'cancelled') {
    return { type: 'incomplete', reason: 'cancelled' }
  }
  if (
    normalizedStatus === 'running'
    || normalizedStatus === 'pending'
    || normalizedStatus === 'streaming'
  ) {
    return { type: 'running' }
  }
  if (normalizedStatus === 'waiting_approval' || normalizedStatus === 'interrupted') {
    return { type: 'requires-action', reason: 'interrupt' }
  }
  return { type: 'complete', reason: 'stop' }
}

export const MessageConverter = {
  toThreadMessage(message: ChatLedgerMessage): ThreadMessage {
    const metadata = message.metadata_json || {}
    const normalizedRole = normalizeRole(message.role)
    const customMetadata = {
      server_message_id: message.id,
      parent_id: message.parent_id ?? null,
      source_role: message.role,
      response_id: message.response_id ?? undefined,
      task_id: message.task_id ?? undefined,
      branch_id: metadata.branch_id ?? undefined,
      message_status: message.status ?? undefined,
      sequence_no: message.sequence_no ?? undefined,
      run_id: message.run_id ?? undefined,
      model_ref: message.model_ref ?? undefined,
      tokens_prompt: message.tokens_prompt ?? undefined,
      tokens_completion: message.tokens_completion ?? undefined,
      finish_reason: message.finish_reason ?? undefined,
      budget_exceeded: metadata.budget_exceeded ?? undefined,
      budget_reason: metadata.budget_reason ?? undefined,
      cost_total: metadata.cost_total ?? undefined,
      citations: message.citations_json ?? undefined,
      artifacts: metadata.artifacts ?? undefined,
      attachments: message.attachments_json ?? undefined,
      tool_calls: message.tool_calls_json ?? undefined,
      summary: message.summary ?? undefined,
      rag_query: metadata.rag_query ?? undefined,
      rag_knowledge: metadata.rag_knowledge ?? undefined,
      error_code: message.error_code ?? undefined,
      error_message: message.error_message ?? undefined,
      interrupted: metadata.interrupted ?? undefined,
      reasoning: metadata.reasoning ?? metadata.reasoning_summary ?? undefined,
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
          attachments: normalizeAttachments(customMetadata.attachments) as any,
        } as ThreadUserMessage

      case 'assistant': {
        const parsedContent = splitReasoningContent(message.content || '')
        const reasoning =
          normalizeReasoningText(customMetadata.reasoning) || parsedContent.reasoning
        const assistantContent: ThreadAssistantMessagePart[] = []
        if (reasoning) {
          assistantContent.push({ type: 'reasoning', text: reasoning } as any)
        }
        assistantContent.push({ type: 'text', text: parsedContent.answer } as any)
        assistantContent.push(...normalizeToolCalls(customMetadata.tool_calls))
        return {
          ...baseProps,
          role: 'assistant',
          content: assistantContent as readonly ThreadAssistantMessagePart[],
          status: normalizeMessageStatus(
            customMetadata.message_status,
            customMetadata.error_message
          ),
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
          status: normalizeMessageStatus(
            customMetadata.message_status,
            customMetadata.error_message
          ),
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
