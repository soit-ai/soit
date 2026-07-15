'use client'

import { ContentType } from '@/utils/request'
import { globalMitt } from '@/hooks/use-mitt'
import { type ChatModelAdapter } from '@assistant-ui/react'
import { createThread, getThread } from '@/services/thread-service'
import { cancelResponse, createResponse, createStreamResponse, type ResponseRead } from '@/services/responses-service'
import { cancelAgentExecution, streamAgentExecution } from '@/services/agent-service'
import { toast } from 'sonner'
import { DEFAULT_CHAT_PROVIDER, resolveRuntimeChatModel, resolveStoredChatProvider } from './defaults'

const THINK_OPEN_TAG = '<think>'
const THINK_CLOSE_TAG = '</think>'
const STREAM_EMIT_INTERVAL_MS = 40
const CHAT_RETRY_ATTEMPTS = 3
const CHAT_RETRY_BASE_DELAY_MS = 250

type AssistantContentPart =
  | { type: 'reasoning'; text: string; duration?: number }
  | { type: 'text'; text: string; duration?: number }
  | { type: 'tool-call'; toolCallId: string; toolName: string; args?: unknown; argsText?: string; result?: unknown }

type ResponseStreamEvent =
  | { type: 'response.created'; responseId?: string; runId?: string; threadId?: string }
  | { type: 'response.output_text.delta'; delta: string }
  | { type: 'response.output_text.done'; text: string }
  | { type: 'response.succeeded'; responseId?: string; runId?: string; model?: string; finishReason?: string; usage?: Record<string, unknown> }
  | { type: 'response.failed'; error: string }
  | { type: 'tool.call.requested' | 'tool.call.started' | 'tool.call.completed' | 'tool.call.failed'; toolCallId: string; toolName: string; argumentsText: string; resultText: string }

type AgentStreamEvent =
  | { type: 'agent.run.started'; runId?: string }
  | { type: 'agent.response.succeeded'; output: string }
  | { type: 'agent.run.succeeded'; runId?: string; status?: string }
  | { type: 'agent.run.failed'; runId?: string; threadId?: string; taskId?: string; responseId?: string; errorCode?: string; errorMessage?: string }
  | { type: 'agent.run.canceled'; runId?: string; threadId?: string; taskId?: string; responseId?: string }
  | { type: 'agent.tool.started'; toolCallId: string; toolName: string }
  | { type: 'agent.tool.succeeded'; toolCallId: string; toolName: string; resultText: string }
  | { type: 'agent.result'; output: string; runId?: string; threadId?: string; responseId?: string; model?: string; finishReason?: string; tokensPrompt?: number; tokensCompletion?: number; toolCalls?: number; budgetExceeded?: boolean; budgetReason?: string; costTotal?: number; citations?: Array<Record<string, unknown>> }
  | { type: 'agent.error'; error: string }

const safeJsonParse = <T = unknown>(value: string): T | null => {
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

const toJsonText = (value: unknown): string => {
  if (typeof value === 'string') return value
  if (value === null || value === undefined) return ''
  try {
    return JSON.stringify(value)
  } catch {
    return String(value)
  }
}

async function* parseResponseSSEStream(stream: AsyncGenerator<{ event: string; data: string }, void, unknown>): AsyncGenerator<ResponseStreamEvent, void, unknown> {
  for await (const part of stream) {
    if (!part) continue
    if (typeof part.data === 'string' && part.data.trim() === '[DONE]') return
    const payload = safeJsonParse<Record<string, unknown>>(part.data) || {}
    if (part.event === 'response.created') {
      yield {
        type: 'response.created',
        responseId: typeof payload.response_id === 'string' ? payload.response_id : undefined,
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        threadId: typeof payload.thread_id === 'string' ? payload.thread_id : undefined,
      }
      continue
    }
    if (part.event === 'response.output_text.delta') {
      yield { type: 'response.output_text.delta', delta: typeof payload.delta === 'string' ? payload.delta : '' }
      continue
    }
    if (part.event === 'response.output_text.done') {
      yield { type: 'response.output_text.done', text: typeof payload.text === 'string' ? payload.text : '' }
      continue
    }
    if (part.event === 'response.succeeded') {
      yield {
        type: 'response.succeeded',
        responseId: typeof payload.response_id === 'string' ? payload.response_id : undefined,
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        model: typeof payload.model === 'string' ? payload.model : undefined,
        finishReason: typeof payload.finish_reason === 'string' ? payload.finish_reason : undefined,
        usage: payload.usage && typeof payload.usage === 'object' ? (payload.usage as Record<string, unknown>) : undefined,
      }
      continue
    }
    if (part.event === 'response.failed') {
      const errorPayload = payload.error && typeof payload.error === 'object' ? (payload.error as Record<string, unknown>) : {}
      yield {
        type: 'response.failed',
        error:
          (typeof payload.error_message === 'string' && payload.error_message) ||
          (typeof errorPayload.message === 'string' && errorPayload.message) ||
          'Response failed',
      }
      continue
    }
    if (part.event.startsWith('tool.call.')) {
      yield {
        type: part.event as 'tool.call.requested' | 'tool.call.started' | 'tool.call.completed' | 'tool.call.failed',
        toolCallId:
          (typeof payload.tool_call_id === 'string' && payload.tool_call_id) ||
          (typeof payload.step_id === 'string' && payload.step_id) ||
          '',
        toolName: typeof payload.tool_name === 'string' ? payload.tool_name : 'tool',
        argumentsText: toJsonText(payload.arguments),
        resultText: toJsonText(payload.result || payload.error),
      }
    }
  }
}

async function* parseAgentSSEStream(stream: AsyncGenerator<{ event: string; data: string }, void, unknown>): AsyncGenerator<AgentStreamEvent, void, unknown> {
  for await (const part of stream) {
    if (!part) continue
    if (typeof part.data === 'string' && part.data.trim() === '[DONE]') return
    const payload = safeJsonParse<Record<string, unknown>>(part.data) || {}
    if (part.event === 'agent.run.started') {
      yield { type: 'agent.run.started', runId: typeof payload.run_id === 'string' ? payload.run_id : undefined }
      continue
    }
    if (part.event === 'agent.response.succeeded') {
      yield { type: 'agent.response.succeeded', output: typeof payload.output === 'string' ? payload.output : '' }
      continue
    }
    if (part.event === 'agent.run.succeeded') {
      yield {
        type: 'agent.run.succeeded',
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        status: typeof payload.status === 'string' ? payload.status : undefined,
      }
      continue
    }
    if (part.event === 'agent.run.failed') {
      yield {
        type: 'agent.run.failed',
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        threadId: typeof payload.thread_id === 'string' ? payload.thread_id : undefined,
        taskId: typeof payload.task_id === 'string' ? payload.task_id : undefined,
        responseId: typeof payload.response_id === 'string' ? payload.response_id : undefined,
        errorCode: typeof payload.error_code === 'string' ? payload.error_code : undefined,
        errorMessage: typeof payload.error_message === 'string' ? payload.error_message : undefined,
      }
      continue
    }
    if (part.event === 'agent.tool.started') {
      yield {
        type: 'agent.tool.started',
        toolCallId: (typeof payload.tool_call_id === 'string' && payload.tool_call_id) || `tool-${Date.now()}`,
        toolName: typeof payload.tool_ref === 'string' ? payload.tool_ref : 'tool',
      }
      continue
    }
    if (part.event === 'agent.tool.succeeded') {
      yield {
        type: 'agent.tool.succeeded',
        toolCallId: (typeof payload.tool_call_id === 'string' && payload.tool_call_id) || (typeof payload.tool_ref === 'string' ? payload.tool_ref : `tool-${Date.now()}`),
        toolName: typeof payload.tool_ref === 'string' ? payload.tool_ref : 'tool',
        resultText: toJsonText(payload),
      }
      continue
    }
    if (part.event === 'agent.result') {
      yield {
        type: 'agent.result',
        output: typeof payload.output === 'string' ? payload.output : '',
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        threadId: typeof payload.thread_id === 'string' ? payload.thread_id : undefined,
        responseId: typeof payload.response_id === 'string' ? payload.response_id : undefined,
        model: typeof payload.model === 'string' ? payload.model : undefined,
        finishReason: typeof payload.finish_reason === 'string' ? payload.finish_reason : undefined,
        tokensPrompt: typeof payload.tokens_prompt === 'number' ? payload.tokens_prompt : undefined,
        tokensCompletion: typeof payload.tokens_completion === 'number' ? payload.tokens_completion : undefined,
        toolCalls: typeof payload.tool_calls === 'number' ? payload.tool_calls : undefined,
        budgetExceeded: typeof payload.budget_exceeded === 'boolean' ? payload.budget_exceeded : undefined,
        budgetReason: typeof payload.budget_reason === 'string' ? payload.budget_reason : undefined,
        costTotal: typeof payload.cost_total === 'number' ? payload.cost_total : undefined,
        citations: Array.isArray(payload.citations) ? payload.citations as Array<Record<string, unknown>> : undefined,
      }
      continue
    }
    if (part.event === 'agent.error') {
      yield { type: 'agent.error', error: typeof payload.error === 'string' ? payload.error : 'Agent execution failed' }
      continue
    }
    if (part.event === 'agent.run.canceled') {
      yield {
        type: 'agent.run.canceled',
        runId: typeof payload.run_id === 'string' ? payload.run_id : undefined,
        threadId: typeof payload.thread_id === 'string' ? payload.thread_id : undefined,
        taskId: typeof payload.task_id === 'string' ? payload.task_id : undefined,
        responseId: typeof payload.response_id === 'string' ? payload.response_id : undefined,
      }
      continue
    }
  }
}

const normalizeThinkTags = (content: string): string => content.replace(/\\u003c/gi, '<').replace(/\\u003e/gi, '>')

const splitReasoningContent = (content: string): { reasoning: string; text: string } => {
  const normalized = normalizeThinkTags(content || '')
  if (!normalized.includes(THINK_OPEN_TAG)) return { reasoning: '', text: normalized }
  let reasoning = ''
  let text = ''
  let remaining = normalized
  let inReasoning = false
  while (remaining.length > 0) {
    if (inReasoning) {
      const closeIdx = remaining.indexOf(THINK_CLOSE_TAG)
      if (closeIdx < 0) {
        reasoning += remaining
        break
      }
      reasoning += remaining.slice(0, closeIdx)
      remaining = remaining.slice(closeIdx + THINK_CLOSE_TAG.length)
      inReasoning = false
      continue
    }
    const openIdx = remaining.indexOf(THINK_OPEN_TAG)
    if (openIdx < 0) {
      text += remaining
      break
    }
    if (openIdx > 0) text += remaining.slice(0, openIdx)
    remaining = remaining.slice(openIdx + THINK_OPEN_TAG.length)
    inReasoning = true
  }
  const normalizedReasoning = reasoning.trim()
  return { reasoning: normalizedReasoning, text: normalizedReasoning ? text.replace(/^\s+/, '') : text }
}

const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') return value
  if (typeof value === 'number') return value === 1
  if (typeof value === 'string') return ['1', 'true', 'on', 'yes', 'enabled'].includes(value.trim().toLowerCase())
  return false
}

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

const getRetryDelay = (attempt: number): number => CHAT_RETRY_BASE_DELAY_MS * Math.pow(2, attempt)

const normalizeAttachment = (attachment: any) => ({
  id: attachment?.id,
  name: attachment?.name || attachment?.file?.name || 'Attachment',
  type: attachment?.type || 'file',
  size: attachment?.size || attachment?.file?.size,
  url: attachment?.url,
  content: attachment?.content,
})

const buildAssistantContent = (
  reasoning: string,
  text: string,
  reasoningDuration: number,
  duration: number,
  toolCalls: Array<{ toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }> = []
): AssistantContentPart[] => {
  const content: AssistantContentPart[] = []
  if (reasoning) content.push({ type: 'reasoning', text: reasoning, duration: reasoningDuration })
  if (text || !content.length) content.push({ type: 'text', text, duration })
  for (const tc of toolCalls) {
    content.push({ type: 'tool-call', toolCallId: tc.toolCallId, toolName: tc.toolName, args: tc.args, argsText: tc.argsText, result: tc.result })
  }
  return content
}

const resolveResponseOutputText = (response: ResponseRead): string => {
  if (typeof response.output_json?.text === 'string') return response.output_json.text as string
  const items = response.output_json?.items
  if (!Array.isArray(items)) return ''
  for (const item of items) {
    const content = item && typeof item === 'object' ? (item as Record<string, unknown>).content : null
    if (!Array.isArray(content)) continue
    for (const part of content) {
      const text = part && typeof part === 'object' ? (part as Record<string, unknown>).text : null
      if (typeof text === 'string') return text
    }
  }
  return ''
}

export const ChatAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal, context, runConfig }) {
    void runConfig
    messages = messages.filter((message) => message.role !== 'assistant' || !message.content.some((content) => content.type === 'reasoning'))
    const rawContext = context as { config?: Record<string, any> } | undefined
    const config = (rawContext?.config || {}) as Record<string, any>
    const deepThinking = toBoolean(config.deepThinking ?? localStorage.getItem('chat_deep_thinking'))
    const model = resolveRuntimeChatModel(config.modelName, deepThinking)
    const provider = (typeof config.provider === 'string' && config.provider) || resolveStoredChatProvider() || DEFAULT_CHAT_PROVIDER
    const reasoningEffort = deepThinking ? config.reasoningEffort || 'high' : undefined
    const authorization = (config.authorization as string) || ''
    const stream = config.stream !== undefined ? Boolean(config.stream) : true
    const agentId = config.agentId || 'default'
    let activeThreadId = config.thread_id || ''
    let createdThreadId = ''
    const workspaceId = localStorage.getItem('workspace_id') || ''

    const emitThreadCreated = (threadId: string) => {
      if (!threadId) return
      globalMitt.emit('chat_thread_created', { agentId, threadId })
    }

    const resolveMessageText = (message: any): string => message?.content?.find((content: any) => content.type === 'text')?.text || ''
    const resolveMessageAttachments = (message: any) => Array.isArray(message?.attachments) ? message.attachments.map(normalizeAttachment) : []
    const resolveServerMessageId = (message: any): string | undefined => {
      const custom = (message?.metadata?.custom || {}) as Record<string, any>
      const byMetadata = custom.server_message_id || custom.message_id
      if (typeof byMetadata === 'string' && byMetadata) return byMetadata
      if (typeof message?.id === 'string' && message.id.startsWith('id_')) return message.id
      return undefined
    }
    const toPayloadMessage = (message: any) => ({
      role: message.role,
      content: resolveMessageText(message),
      metadata: {
        attachments: resolveMessageAttachments(message),
        agent_id: agentId !== 'default' ? agentId : undefined,
        provider,
        model_ref: model || undefined,
        deep_thinking: deepThinking || undefined,
        reasoning_effort: reasoningEffort,
      },
    })

    const buildCompletionPayload = () => {
      const normalizedMessages = [...messages]
      if (!normalizedMessages.length) return { payloadMessages: [] as Array<Record<string, any>>, parentMessageId: undefined as string | undefined }
      const lastMessage = normalizedMessages[normalizedMessages.length - 1]
      const payloadMessages = lastMessage?.role === 'user' ? [toPayloadMessage(lastMessage)] : ([] as Array<Record<string, any>>)
      let parentMessageId: string | undefined
      const parentSearchStart = lastMessage?.role === 'user' ? normalizedMessages.length - 2 : normalizedMessages.length - 1
      for (let i = parentSearchStart; i >= 0; i -= 1) {
        const candidate = resolveServerMessageId(normalizedMessages[i])
        if (candidate) {
          parentMessageId = candidate
          break
        }
      }
      return { payloadMessages, parentMessageId }
    }

    const ensureThread = async (): Promise<string> => {
      if (activeThreadId) return activeThreadId
      const createdThread = await createThread({
        agent_id: agentId !== 'default' ? agentId : undefined,
        default_model_ref: model || undefined,
        metadata_json: {
          agent_id: agentId !== 'default' ? agentId : undefined,
          provider,
          model_ref: model || undefined,
          deep_thinking: deepThinking || undefined,
          reasoning_effort: reasoningEffort,
          source: 'chat.responses',
        },
      })
      activeThreadId = createdThread.id
      createdThreadId = activeThreadId
      return activeThreadId
    }

    const emitCreatedThreadIfNeeded = () => {
      if (!createdThreadId) return
      emitThreadCreated(createdThreadId)
      createdThreadId = ''
    }

    const resolveLatestMessage = async (runId?: string, threadId?: string) => {
      if (!threadId) return null
      const threadDetail = await getThread(threadId)
      const assistantMessages = (threadDetail?.messages || []).filter((item) => item.role === 'assistant' && (!runId || item.run_id === runId))
      return assistantMessages[assistantMessages.length - 1] || null
    }

    const { payloadMessages, parentMessageId } = buildCompletionPayload()

    try {
      if (agentId !== 'default') {
        const agentMessages = payloadMessages
          .filter((message) => typeof message.content === 'string' && message.content.trim())
          .map((message) => ({
            role: message.role as 'system' | 'user' | 'assistant' | 'tool',
            content: String(message.content),
            metadata: (message.metadata as Record<string, unknown> | undefined) || undefined,
          }))
        if (!agentMessages.length) return

        let activeRunId = ''
        let activeResponseId = ''
        let output = ''
        let duration = 0
        let finalMeta: Record<string, unknown> | null = null
        const startTime = Date.now()
        const toolCalls: Array<{ toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }> = []
        let cancelSent = false

        const upsertAgentToolCall = (toolCallId: string, toolName: string, resultText?: string) => {
          const existing = toolCalls.find((item) => item.toolCallId === toolCallId)
          if (existing) {
            existing.toolName = toolName || existing.toolName
            if (resultText) {
              try { existing.result = JSON.parse(resultText) } catch { existing.result = resultText }
            }
            return
          }
          const nextToolCall: { toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown } = { toolCallId, toolName, args: {}, argsText: '{}', result: undefined }
          if (resultText) {
            try { nextToolCall.result = JSON.parse(resultText) } catch { nextToolCall.result = resultText }
          }
          toolCalls.push(nextToolCall)
        }

        for (let attempt = 0; attempt < CHAT_RETRY_ATTEMPTS; attempt += 1) {
          try {
            const streamResult = streamAgentExecution(agentId, {
              input: agentMessages[agentMessages.length - 1]?.content || '',
              thread_id: activeThreadId || undefined,
              request_id: crypto.randomUUID(),
            }, {
              signal: abortSignal,
              headers: { 'Content-Type': ContentType.json, authorization, ...(workspaceId ? { 'X-Workspace-Id': workspaceId } : {}) },
            })

            for await (const ev of parseAgentSSEStream(streamResult)) {
              duration = (Date.now() - startTime) / 1000
              if (ev.type === 'agent.run.started') {
                if (ev.runId) activeRunId = ev.runId
                continue
              }
              if (ev.type === 'agent.tool.started') {
                upsertAgentToolCall(ev.toolCallId, ev.toolName)
                yield { content: buildAssistantContent('', output, 0, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId, response_id: activeResponseId, thread_id: activeThreadId || null } } }
                continue
              }
              if (ev.type === 'agent.tool.succeeded') {
                upsertAgentToolCall(ev.toolCallId, ev.toolName, ev.resultText)
                yield { content: buildAssistantContent('', output, 0, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId, response_id: activeResponseId, thread_id: activeThreadId || null } } }
                continue
              }
              if (ev.type === 'agent.response.succeeded') {
                output = ev.output || output
                continue
              }
              if (ev.type === 'agent.run.failed') {
                if (ev.runId) activeRunId = ev.runId
                if (ev.responseId) activeResponseId = ev.responseId
                if (ev.threadId) {
                  activeThreadId = ev.threadId
                  emitThreadCreated(activeThreadId)
                }
                finalMeta = {
                  run_id: activeRunId,
                  response_id: activeResponseId,
                  thread_id: activeThreadId || null,
                  task_id: ev.taskId,
                  finish_reason: ev.errorCode,
                  error_code: ev.errorCode,
                  error_message: ev.errorMessage,
                }
                globalMitt.emit('refresh_chat_sidebar')
                globalMitt.emit('chat_completion_finished', { agentId, threadId: activeThreadId || null, ...(finalMeta as Record<string, unknown>) })
                continue
              }
              if (ev.type === 'agent.run.canceled') {
                if (ev.runId) activeRunId = ev.runId
                if (ev.responseId) activeResponseId = ev.responseId
                if (ev.threadId) activeThreadId = ev.threadId
                finalMeta = {
                  run_id: activeRunId,
                  response_id: activeResponseId,
                  thread_id: activeThreadId || null,
                  task_id: ev.taskId,
                  finish_reason: 'canceled',
                }
                continue
              }
              if (ev.type === 'agent.result') {
                output = ev.output || output
                if (ev.runId) activeRunId = ev.runId
                if (ev.responseId) activeResponseId = ev.responseId
                if (ev.threadId) {
                  activeThreadId = ev.threadId
                  emitThreadCreated(activeThreadId)
                }
                finalMeta = {
                  run_id: activeRunId,
                  response_id: activeResponseId,
                  thread_id: activeThreadId || null,
                  model: ev.model,
                  finish_reason: ev.finishReason,
                  tokens_prompt: ev.tokensPrompt,
                  tokens_completion: ev.tokensCompletion,
                  tool_calls: ev.toolCalls,
                  budget_exceeded: ev.budgetExceeded,
                  budget_reason: ev.budgetReason,
                  cost_total: ev.costTotal,
                  citations: ev.citations,
                }
                globalMitt.emit('refresh_chat_sidebar')
                globalMitt.emit('chat_completion_finished', { agentId, threadId: activeThreadId || null, ...(finalMeta as Record<string, unknown>) })
                continue
              }
              if (ev.type === 'agent.error') {
                throw new Error(ev.error)
              }
            }
            break
          } catch (streamError) {
            if (abortSignal?.aborted && activeRunId && !cancelSent) {
              cancelSent = true
              try {
                await cancelAgentExecution(agentId, activeRunId)
              } catch (cancelError) {
                console.error('Failed to cancel agent execution:', cancelError)
              }
            }
            const hasStartedResponse = Boolean(activeRunId || activeResponseId || output || toolCalls.length)
            const shouldRetry = !abortSignal?.aborted && !hasStartedResponse && attempt < CHAT_RETRY_ATTEMPTS - 1
            if (!shouldRetry) {
              throw streamError
            }
            await sleep(getRetryDelay(attempt))
          }
        }

        if (finalMeta || output || toolCalls.length) {
          yield {
            content: buildAssistantContent('', output, 0, duration, toolCalls) as any,
            metadata: { custom: { ...(finalMeta || {}), thread_id: activeThreadId || null } },
          }
        }
        return
      }

      activeThreadId = await ensureThread()
      const requestPayload = {
        model,
        provider,
        thread_id: activeThreadId,
        agent_id: agentId !== 'default' ? agentId : undefined,
        input: { messages: payloadMessages },
        stream,
        metadata: {
          agent_id: agentId !== 'default' ? agentId : undefined,
          provider,
          model_ref: model || undefined,
          deep_thinking: deepThinking || undefined,
          reasoning_effort: reasoningEffort,
          parent_message_id: parentMessageId,
          source: 'chat.responses',
        },
      }

      if (stream) {
        let activeRunId = ''
        let activeResponseId = ''
        let cancelSent = false
        let completionMeta: Record<string, any> | null = null
        let reasoning = ''
        let text = ''
        let duration = 0
        let reasoningDuration = 0
        let rawResponse = ''
        const startTime = Date.now()
        let reasoningStartAt: number | null = null
        let latestRunId = ''
        let lastEmitAt = 0
        let lastEmittedReasoning = ''
        let lastEmittedText = ''
        const toolCalls: Array<{ toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }> = []
        const cancelActiveResponse = async () => {
          if (cancelSent || !activeResponseId) {
            return
          }
          cancelSent = true
          try {
            await cancelResponse(activeResponseId)
          } catch (cancelError) {
            console.error('Failed to cancel response:', cancelError)
          }
        }

        if (abortSignal) {
          abortSignal.addEventListener(
            'abort',
            () => {
              void cancelActiveResponse()
            },
            { once: true }
          )
        }

        const appendDelta = (rawDelta: string) => {
          const normalizedDelta = normalizeThinkTags(rawDelta || '')
          if (!normalizedDelta) return
          rawResponse += normalizedDelta
          if (reasoningStartAt === null && rawResponse.includes(THINK_OPEN_TAG)) reasoningStartAt = Date.now()
          const parsed = splitReasoningContent(rawResponse)
          reasoning = parsed.reasoning
          text = parsed.text
          if (reasoningStartAt !== null && (reasoning || rawResponse.includes(THINK_CLOSE_TAG))) reasoningDuration = (Date.now() - reasoningStartAt) / 1000
        }

        const upsertToolCall = (toolCallId: string, toolName: string, argumentsText: string, resultText?: string) => {
          let args: unknown = {}
          try { args = argumentsText ? JSON.parse(argumentsText) : {} } catch { args = argumentsText }
          const existing = toolCalls.find((item) => item.toolCallId === toolCallId)
          if (existing) {
            existing.toolName = toolName || existing.toolName
            existing.argsText = argumentsText || existing.argsText
            existing.args = args
            if (resultText) { try { existing.result = JSON.parse(resultText) } catch { existing.result = resultText } }
            return
          }
          const nextToolCall = { toolCallId, toolName, args, argsText: argumentsText || '{}' } as { toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }
          if (resultText) { try { nextToolCall.result = JSON.parse(resultText) } catch { nextToolCall.result = resultText } }
          toolCalls.push(nextToolCall)
        }

        for (let attempt = 0; attempt < CHAT_RETRY_ATTEMPTS; attempt += 1) {
          try {
            const streamResult = createStreamResponse(requestPayload, {
              signal: abortSignal,
              headers: { 'Content-Type': ContentType.json, authorization, ...(workspaceId ? { 'X-Workspace-Id': workspaceId } : {}) },
            })

            for await (const ev of parseResponseSSEStream(streamResult)) {
              if (ev.type === 'response.created') {
                if (ev.threadId) activeThreadId = ev.threadId
                if (ev.responseId) activeResponseId = ev.responseId
                if (ev.runId) activeRunId = ev.runId
                if (abortSignal?.aborted) {
                  void cancelActiveResponse()
                }
                continue
              }
              if (ev.type === 'response.output_text.delta') {
                latestRunId = activeRunId || latestRunId
                appendDelta(ev.delta)
                if (reasoning === '\n\n') { reasoning = ''; reasoningDuration = 0 }
                duration = (Date.now() - startTime) / 1000
                if ((!reasoning && !text && !toolCalls.length) || (reasoning === lastEmittedReasoning && text === lastEmittedText)) continue
                const now = Date.now()
                if (now - lastEmitAt < STREAM_EMIT_INTERVAL_MS) continue
                yield { content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId || '', response_id: activeResponseId || '', thread_id: activeThreadId || null } } }
                lastEmitAt = now
                lastEmittedReasoning = reasoning
                lastEmittedText = text
                continue
              }
              if (ev.type === 'response.output_text.done') {
                if (ev.text) {
                  rawResponse = ev.text
                  const parsed = splitReasoningContent(ev.text)
                  reasoning = parsed.reasoning
                  text = parsed.text
                }
                continue
              }
              if (
                (ev.type === 'tool.call.requested' ||
                  ev.type === 'tool.call.started' ||
                  ev.type === 'tool.call.completed' ||
                  ev.type === 'tool.call.failed') &&
                ev.toolCallId
              ) {
                upsertToolCall(ev.toolCallId, ev.toolName, ev.argumentsText, ev.resultText)
                duration = (Date.now() - startTime) / 1000
                yield { content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId || '', response_id: activeResponseId || '', thread_id: activeThreadId || null } } }
                lastEmittedReasoning = reasoning
                lastEmittedText = text
                continue
              }
              if (ev.type === 'response.succeeded') {
                if (ev.responseId) activeResponseId = ev.responseId
                if (ev.runId) activeRunId = ev.runId
                completionMeta = {
                  run_id: ev.runId || activeRunId,
                  response_id: ev.responseId || activeResponseId,
                  model: ev.model || model,
                  finish_reason: ev.finishReason,
                  tokens_prompt: typeof ev.usage?.prompt_tokens === 'number' ? ev.usage.prompt_tokens : undefined,
                  tokens_completion: typeof ev.usage?.completion_tokens === 'number' ? ev.usage.completion_tokens : undefined,
                }
                emitCreatedThreadIfNeeded()
                globalMitt.emit('refresh_chat_sidebar')
                globalMitt.emit('chat_completion_finished', { agentId, threadId: activeThreadId || null, ...completionMeta })
                continue
              }
              if (ev.type === 'response.failed') throw new Error(ev.error)
            }
            break
          } catch (streamError) {
            const hasStartedResponse = Boolean(activeResponseId || activeRunId || rawResponse || text || toolCalls.length)
            const shouldRetry = !abortSignal?.aborted && !hasStartedResponse && attempt < CHAT_RETRY_ATTEMPTS - 1
            if (!shouldRetry) {
              throw streamError
            }
            await sleep(getRetryDelay(attempt))
          }
        }

        if (!completionMeta) {
          try {
            const recovered = await resolveLatestMessage(activeRunId || undefined, activeThreadId)
            if (recovered?.content) {
              const recoveredMeta = ('metadata_json' in recovered ? recovered.metadata_json : {}) || {}
              const recoveredContent = splitReasoningContent(recovered.content)
              yield {
                content: buildAssistantContent(recoveredContent.reasoning, recoveredContent.text, reasoningDuration, duration, toolCalls) as any,
                metadata: { custom: { server_message_id: recovered.id, run_id: ('run_id' in recovered ? recovered.run_id : undefined) || activeRunId || '', response_id: (typeof recoveredMeta.response_id === 'string' && recoveredMeta.response_id) || activeResponseId || '', thread_id: activeThreadId || null, tokens_prompt: 'tokens_prompt' in recovered ? recovered.tokens_prompt : undefined, tokens_completion: 'tokens_completion' in recovered ? recovered.tokens_completion : undefined, finish_reason: 'finish_reason' in recovered ? recovered.finish_reason : undefined, ...(recoveredMeta as Record<string, unknown>) } },
              }
            } else if (text || toolCalls.length) {
              yield { content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId || '', response_id: activeResponseId || '', thread_id: activeThreadId || null, interrupted: true } } }
            }
          } catch {
            if (text || toolCalls.length) yield { content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any, metadata: { custom: { run_id: activeRunId || '', response_id: activeResponseId || '', thread_id: activeThreadId || null, interrupted: true } } }
          }
        }

        if (completionMeta && (reasoning || text || toolCalls.length)) {
          const needFinalEmit = reasoning !== lastEmittedReasoning || text !== lastEmittedText
          yield {
            content: needFinalEmit ? (buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any) : (buildAssistantContent(lastEmittedReasoning, lastEmittedText, reasoningDuration, duration, toolCalls) as any),
            metadata: { custom: { ...(completionMeta as Record<string, unknown>), thread_id: activeThreadId || null } },
          }
        }
      } else {
        let response: ResponseRead | null = null
        for (let attempt = 0; attempt < CHAT_RETRY_ATTEMPTS; attempt += 1) {
          try {
            response = await createResponse(requestPayload)
            break
          } catch (requestError) {
            const shouldRetry = !abortSignal?.aborted && attempt < CHAT_RETRY_ATTEMPTS - 1
            if (!shouldRetry) {
              throw requestError
            }
            await sleep(getRetryDelay(attempt))
          }
        }
        if (!response) {
          throw new Error('Chat request failed')
        }
        const recovered = await resolveLatestMessage(response.run_id || undefined, activeThreadId)
        emitCreatedThreadIfNeeded()
        globalMitt.emit('refresh_chat_sidebar')
        globalMitt.emit('chat_completion_finished', { agentId, threadId: activeThreadId || null, run_id: response.run_id || '', response_id: response.id })
        if (recovered?.content) {
          const parsedMessage = splitReasoningContent(recovered.content)
          const messageMeta = ('metadata_json' in recovered ? recovered.metadata_json : {}) || {}
          yield {
            content: buildAssistantContent(parsedMessage.reasoning, parsedMessage.text, 0, 0) as any,
            metadata: { custom: { server_message_id: recovered.id, run_id: ('run_id' in recovered ? recovered.run_id : undefined) || response.run_id || '', response_id: (typeof messageMeta.response_id === 'string' && messageMeta.response_id) || response.id, thread_id: activeThreadId || null, tokens_prompt: ('tokens_prompt' in recovered ? recovered.tokens_prompt : undefined) || response.usage_json?.prompt_tokens, tokens_completion: ('tokens_completion' in recovered ? recovered.tokens_completion : undefined) || response.usage_json?.completion_tokens, finish_reason: ('finish_reason' in recovered ? recovered.finish_reason : undefined) || response.output_json?.finish_reason, ...(messageMeta as Record<string, unknown>) } },
          }
        } else {
          const parsedResponse = splitReasoningContent(resolveResponseOutputText(response))
          yield {
            content: buildAssistantContent(parsedResponse.reasoning, parsedResponse.text, 0, 0) as any,
            metadata: { custom: { run_id: response.run_id || '', response_id: response.id, thread_id: activeThreadId || null, tokens_prompt: typeof response.usage_json?.prompt_tokens === 'number' ? response.usage_json.prompt_tokens : undefined, tokens_completion: typeof response.usage_json?.completion_tokens === 'number' ? response.usage_json.completion_tokens : undefined, finish_reason: typeof response.output_json?.finish_reason === 'string' ? response.output_json.finish_reason : undefined } },
          }
        }
      }
    } catch (error: any) {
      const aborted = abortSignal?.aborted || error?.name === 'AbortError'
      if (aborted) {
        toast.info('Generation cancelled')
        return
      }
      console.error('*run error', error)
      toast.error(error?.message || 'Chat request failed')
      yield { content: [{ type: 'text', text: `An error occurred. ${error?.message || ''} . Please try again later.` }], metadata: { custom: { id: '' } } }
    }
  },
}
