'use client'

import { sse, post, ContentType } from '@/utils/request'
import type { SseEvent } from '@/utils/request'
import { globalMitt } from '@/hooks/use-mitt'
import { useChatStore } from '@/stores/chat'
import { type ChatModelAdapter } from '@assistant-ui/react'
import { listMessages } from '@/services/chat-service'
import { toast } from 'sonner'
import {
  DEFAULT_CHAT_PROVIDER,
  resolveRuntimeChatModel,
  resolveStoredChatProvider,
} from './defaults'

const THINK_OPEN_TAG = '<think>'
const THINK_CLOSE_TAG = '</think>'
const STREAM_EMIT_INTERVAL_MS = 40

// Typed SSE events from server (align with MyRuntimeProvider-style event handling)
type SSEStreamEvent =
  | { type: 'start'; conversation_id?: string; run_id?: string }
  | { type: 'delta'; run_id?: string; delta: string }
  | { type: 'text'; content: string }
  | { type: 'tool_call'; id: string; name: string; arguments: string }
  | { type: 'tool_result'; id: string; result: string }
  | { type: 'complete'; run_id?: string; message_id?: string; model?: string; tokens_prompt?: number; tokens_completion?: number; finish_reason?: string; metadata?: Record<string, unknown> }
  | { type: 'error'; error: string }

const safeJsonParse = <T = unknown>(value: string): T | null => {
  try {
    return JSON.parse(value) as T
  } catch {
    return null
  }
}

/** Parse raw SSE stream into typed events for clear switch-based handling */
async function* parseChatSSEStream(
  stream: AsyncGenerator<SseEvent, void, unknown>
): AsyncGenerator<SSEStreamEvent, void, unknown> {
  for await (const part of stream) {
    if (!part) continue
    const event = part.event
    const data = part.data

    // Server sends [DONE] to signal end of stream (align with MyRuntimeProvider)
    if (typeof data === 'string' && data.trim() === '[DONE]') {
      return
    }

    if (event === 'error') {
      const parsed = safeJsonParse<{ error?: string }>(data)
      yield { type: 'error', error: parsed?.error || 'Streaming error' }
      return
    }

    if (event === 'start') {
      const parsed = safeJsonParse<{ conversation_id?: string; run_id?: string }>(data)
      if (parsed) {
        yield { type: 'start', conversation_id: parsed.conversation_id, run_id: parsed.run_id }
      }
      continue
    }

    if (event === 'complete') {
      const parsed = safeJsonParse<{
        run_id?: string
        message_id?: string
        model?: string
        tokens_prompt?: number
        tokens_completion?: number
        finish_reason?: string
        metadata?: Record<string, unknown>
      }>(data)
      if (parsed) {
        yield {
          type: 'complete',
          run_id: parsed.run_id,
          message_id: parsed.message_id,
          model: parsed.model,
          tokens_prompt: parsed.tokens_prompt,
          tokens_completion: parsed.tokens_completion,
          finish_reason: parsed.finish_reason,
          metadata: parsed.metadata,
        }
      }
      continue
    }

    if (event === 'delta') {
      const parsed = safeJsonParse<{ run_id?: string; delta?: string }>(data)
      if (parsed && typeof parsed.delta === 'string') {
        yield { type: 'delta', run_id: parsed.run_id, delta: parsed.delta }
      }
      continue
    }

    if (event === 'text') {
      const parsed = safeJsonParse<{ content?: string; run_id?: string }>(data)
      if (parsed && typeof parsed.content === 'string') {
        yield { type: 'text', content: parsed.content }
      }
      continue
    }

    if (event === 'tool_call') {
      const parsed = safeJsonParse<{ id?: string; name?: string; arguments?: string; run_id?: string }>(data)
      if (parsed && typeof parsed.id === 'string' && typeof parsed.name === 'string') {
        yield {
          type: 'tool_call',
          id: parsed.id,
          name: parsed.name,
          arguments: typeof parsed.arguments === 'string' ? parsed.arguments : '{}',
        }
      }
      continue
    }

    if (event === 'tool_result') {
      const parsed = safeJsonParse<{ id?: string; result?: string; run_id?: string }>(data)
      if (parsed && typeof parsed.id === 'string') {
        yield {
          type: 'tool_result',
          id: parsed.id,
          result: typeof parsed.result === 'string' ? parsed.result : '',
        }
      }
    }
  }
}

const normalizeThinkTags = (content: string): string => {
  return content
    .replace(/\\u003c/gi, '<')
    .replace(/\\u003e/gi, '>')
}

const splitReasoningContent = (
  content: string
): { reasoning: string; text: string } => {
  const normalized = normalizeThinkTags(content || '')
  if (!normalized.includes(THINK_OPEN_TAG)) {
    return {
      reasoning: '',
      text: normalized,
    }
  }

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
    if (openIdx > 0) {
      text += remaining.slice(0, openIdx)
    }
    remaining = remaining.slice(openIdx + THINK_OPEN_TAG.length)
    inReasoning = true
  }

  const normalizedReasoning = reasoning.trim()
  const normalizedText =
    normalizedReasoning.length > 0 ? text.replace(/^\s+/, '') : text
  return {
    reasoning: normalizedReasoning,
    text: normalizedText,
  }
}

const toBoolean = (value: unknown): boolean => {
  if (typeof value === 'boolean') {
    return value
  }
  if (typeof value === 'number') {
    return value === 1
  }
  if (typeof value === 'string') {
    const normalized = value.trim().toLowerCase()
    return ['1', 'true', 'on', 'yes', 'enabled'].includes(normalized)
  }
  return false
}

// Assistant content part: reasoning, text, or tool-call (align with assistant-ui / MyRuntimeProvider)
type AssistantContentPart =
  | { type: 'reasoning'; text: string; duration?: number }
  | { type: 'text'; text: string; duration?: number }
  | { type: 'tool-call'; toolCallId: string; toolName: string; args?: unknown; argsText?: string; result?: unknown }

const buildAssistantContent = (
  reasoning: string,
  text: string,
  reasoningDuration: number,
  duration: number,
  toolCalls: Array<{ toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }> = []
): AssistantContentPart[] => {
  const content: AssistantContentPart[] = []
  if (reasoning) {
    content.push({ type: 'reasoning', text: reasoning, duration: reasoningDuration })
  }
  if (text || !content.length) {
    content.push({ type: 'text', text, duration })
  }
  for (const tc of toolCalls) {
    content.push({
      type: 'tool-call',
      toolCallId: tc.toolCallId,
      toolName: tc.toolName,
      args: tc.args,
      argsText: tc.argsText,
      result: tc.result,
    })
  }
  return content
}

export const ChatAdapter: ChatModelAdapter = {
  // async run({ messages, abortSignal, context, runConfig }) {
  //   console.log('context', context, runConfig)
  //   let baseUrl: string = context?.config?.baseUrl || ''
  //   let model: string = context?.config?.modelName || ''
  //   // @ts-ignore
  //   let authorization: string = (context?.config?.authorization as string) || ''
  //   try {
  //     let _messages: any = messages || []
  //     const result = await post(
  //       baseUrl,
  //       { messages: _messages, context, model, stream: false },
  //       {
  //         signal: abortSignal,
  //         headers: {
  //           'Content-Type': ContentType.json,
  //           authorization: authorization,
  //         },
  //       }
  //     )

  //     console.log('result', result)
  //     if (!result.status || result.status !== 200) {
  //       const data = await result.data
  //       return {
  //         content: [
  //           {
  //             type: 'text',
  //             text: data?.error || 'An error occurred. Please try again later.',
  //           },
  //         ],
  //       }
  //     }
  //     const data = result?.data
  //     return {
  //       content: [
  //         {
  //           type: 'text',
  //           text: data?.choices?.[0]?.message?.content || '',
  //         },
  //       ],
  //     }
  //   } catch (error) {
  //     return {
  //       content: [
  //         {
  //           type: 'text',
  //           text: 'An error occurred. Please try again later.',
  //         },
  //       ],
  //     }
  //   }
  // },
  async *run({ messages, abortSignal, context, runConfig }) {
    void runConfig
    // remove reasoning
    messages = messages.filter((message) => {
      return message.role !== 'assistant' || !message.content.some((content) => content.type === 'reasoning')
    })
    const config = (context?.config || {}) as Record<string, any>
    let baseUrl: string = config.baseUrl || ''
    let streamBaseUrl: string = config.streamBaseUrl || ''
    const deepThinking = toBoolean(
      config.deepThinking ?? localStorage.getItem('chat_deep_thinking')
    )
    let model: string = resolveRuntimeChatModel(config.modelName, deepThinking)
    const resolvedProvider =
      (typeof config.provider === 'string' && config.provider) ||
      resolveStoredChatProvider() ||
      DEFAULT_CHAT_PROVIDER
    const reasoningEffort =
      deepThinking ? config.reasoningEffort || 'high' : undefined
    // @ts-ignore
    let authorization: string = (context?.config?.authorization as string) || ''
    // @ts-ignore
    let stream: boolean = context?.config?.stream !== undefined ? (context?.config?.stream as boolean) : true
    const appId = config.appId || 'default'
    const conversationStore = useChatStore.getState()
    const storedConversationId = conversationStore.getConversationId(appId)
    const conversationId = storedConversationId || config.conversation_id || ''
    const workspaceId = localStorage.getItem('workspace_id') || ''
    const updateConversationContext = (nextConversationId: string, emitEvent: boolean) => {
      if (!nextConversationId) {
        return
      }
      const currentId = conversationStore.getConversationId(appId)
      if (currentId !== nextConversationId) {
        conversationStore.setConversationId(appId, nextConversationId)
        if (emitEvent) {
          globalMitt.emit('chat_conversation_created', {
            appId,
            conversationId: nextConversationId,
          })
        }
      }
    }
    const resolveMessageText = (message: any): string => {
      return message?.content?.find((content: any) => content.type === 'text')?.text || ''
    }
    const resolveMessageAttachments = (message: any) => {
      if (!Array.isArray(message?.attachments)) {
        return []
      }
      return message.attachments.map((attachment: any) => ({
        id: attachment.id,
        name: attachment.name,
        type: attachment.type,
        size: attachment.size,
        url: attachment.url,
      }))
    }
    const resolveServerMessageId = (message: any): string | undefined => {
      const custom = (message?.metadata?.custom || {}) as Record<string, any>
      const byMetadata = custom.server_message_id || custom.message_id
      if (typeof byMetadata === 'string' && byMetadata) {
        return byMetadata
      }
      if (typeof message?.id === 'string' && message.id.startsWith('id_')) {
        return message.id
      }
      return undefined
    }
    const toPayloadMessage = (message: any) => {
      return {
        role: message.role,
        content: resolveMessageText(message),
        metadata: {
          attachments: resolveMessageAttachments(message),
          provider: resolvedProvider || DEFAULT_CHAT_PROVIDER,
          model_ref: model || undefined,
          deep_thinking: deepThinking || undefined,
          reasoning_effort: reasoningEffort,
        },
      }
    }
    const buildCompletionPayload = () => {
      const normalizedMessages = [...messages]
      if (!normalizedMessages.length) {
        return {
          payloadMessages: [] as Array<Record<string, any>>,
          parentMessageId: undefined as string | undefined,
        }
      }

      const lastMessage = normalizedMessages[normalizedMessages.length - 1]
      const payloadMessages =
        lastMessage?.role === 'user' ? [toPayloadMessage(lastMessage)] : ([] as Array<Record<string, any>>)

      let parentMessageId: string | undefined
      const parentSearchStart = lastMessage?.role === 'user' ? normalizedMessages.length - 2 : normalizedMessages.length - 1
      for (let i = parentSearchStart; i >= 0; i -= 1) {
        const candidate = resolveServerMessageId(normalizedMessages[i])
        if (candidate) {
          parentMessageId = candidate
          break
        }
      }

      return {
        payloadMessages,
        parentMessageId,
      }
    }
    const resolveLatestMessage = async (runId?: string) => {
      const resolvedConversationId = conversationStore.getConversationId(appId) || conversationId
      if (!resolvedConversationId) {
        return null
      }
      let pageToken: string | undefined = undefined
      let lastMessage: any = null
      for (let page = 0; page < 5; page += 1) {
        const response = await listMessages({
          conversation_id: resolvedConversationId,
          page_size: 100,
          page_token: pageToken,
        })
        const items = response?.items || []
        items.forEach((item: any) => {
          if (item.role === 'assistant') {
            if (!runId || item.run_id === runId) {
              lastMessage = item
            }
          }
        })
        pageToken = response?.next_page_token || undefined
        if (!pageToken) {
          break
        }
      }
      return lastMessage
    }
    const { payloadMessages, parentMessageId } = buildCompletionPayload()
    const debugPayload = {
      appId,
      conversationId,
      parentMessageId: parentMessageId || null,
      model,
      stream,
      deepThinking,
      reasoningEffort: reasoningEffort || null,
      provider: resolvedProvider || DEFAULT_CHAT_PROVIDER,
      messageCount: payloadMessages.length,
    }
    console.debug('[chat-adapter] request', debugPayload)
    try {
      if (stream) {
        const url = streamBaseUrl || baseUrl
        let activeRunId = ''
        let completionMeta: Record<string, any> | null = null
        const streamResult = await sse(
          url,
          {
            messages: payloadMessages,
            conversation_id: conversationId,
            parent_message_id: parentMessageId,
            model,
            stream: true,
            metadata: {
              provider: resolvedProvider || DEFAULT_CHAT_PROVIDER,
              model_ref: model || undefined,
              deep_thinking: deepThinking || undefined,
              reasoning_effort: reasoningEffort,
            },
          },
          {
            signal: abortSignal,
            headers: {
              'Content-Type': ContentType.json,
              authorization: authorization,
              ...(workspaceId ? { 'X-Workspace-Id': workspaceId } : {}),
            },
          }
        )
        let reasoning = ''
        let text = ''
        let duration = 0
        let reasoningDuration = 0
        let rawResponse = ''
        let startTime = Date.now()
        let reasoningStartAt: number | null = null
        let latestRunId = ''
        let lastEmitAt = 0
        let lastEmittedReasoning = ''
        let lastEmittedText = ''
        const toolCalls: Array<{ toolCallId: string; toolName: string; args: unknown; argsText: string; result?: unknown }> = []

        const appendDelta = (rawDelta: string) => {
          const normalizedDelta = normalizeThinkTags(rawDelta || '')
          if (!normalizedDelta) {
            return
          }
          rawResponse += normalizedDelta
          if (reasoningStartAt === null && rawResponse.includes(THINK_OPEN_TAG)) {
            reasoningStartAt = Date.now()
          }
          const parsed = splitReasoningContent(rawResponse)
          reasoning = parsed.reasoning
          text = parsed.text
          if (reasoningStartAt !== null && (reasoning || rawResponse.includes(THINK_CLOSE_TAG))) {
            reasoningDuration = (Date.now() - reasoningStartAt) / 1000
          }
        }

        const typedStream = parseChatSSEStream(streamResult)
        for await (const ev of typedStream) {
          switch (ev.type) {
            case 'error':
              throw new Error(ev.error)
            case 'start':
              if (ev.conversation_id) {
                updateConversationContext(ev.conversation_id, false)
              }
              if (ev.run_id) {
                activeRunId = ev.run_id
              }
              break
            case 'complete': {
              console.debug('[chat-adapter] stream complete', {
                appId,
                conversationId: conversationStore.getConversationId(appId) || conversationId || null,
                runId: ev.run_id || activeRunId || null,
                modelRequested: model,
                modelUsed: ev.model || null,
              })
              if (ev.run_id) {
                activeRunId = ev.run_id
              }
              const resolvedConversationId = conversationStore.getConversationId(appId) || conversationId
              if (resolvedConversationId) {
                globalMitt.emit('chat_conversation_created', {
                  appId,
                  conversationId: resolvedConversationId,
                })
              }
              completionMeta = {
                run_id: ev.run_id || activeRunId,
                message_id: ev.message_id,
                server_message_id: ev.message_id,
                model: ev.model,
                tokens_prompt: ev.tokens_prompt,
                tokens_completion: ev.tokens_completion,
                finish_reason: ev.finish_reason,
              }
              if (ev.metadata) {
                completionMeta = { ...completionMeta, ...ev.metadata }
              }
              globalMitt.emit('refresh_chat_sidebar')
              globalMitt.emit('chat_completion_finished', {
                appId,
                conversationId: conversationStore.getConversationId(appId) || conversationId,
                ...completionMeta,
              })
              break
            }
            case 'delta': {
              const runId = ev.run_id || activeRunId
              latestRunId = runId || latestRunId
              appendDelta(ev.delta)
              if (reasoning === '\n\n') {
                reasoning = ''
                reasoningDuration = 0
              }
              duration = (Date.now() - startTime) / 1000
              if (!reasoning && !text && !toolCalls.length) break
              if (reasoning === lastEmittedReasoning && text === lastEmittedText) break
              const now = Date.now()
              if (now - lastEmitAt < STREAM_EMIT_INTERVAL_MS) break
              const content = buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls)
              yield {
                content: content as any,
                metadata: { custom: { run_id: runId || '' } },
              }
              lastEmitAt = now
              lastEmittedReasoning = reasoning
              lastEmittedText = text
              break
            }
            case 'text': {
              const runId = activeRunId
              latestRunId = runId || latestRunId
              text += ev.content
              duration = (Date.now() - startTime) / 1000
              if (!reasoning && !text && !toolCalls.length) break
              const now = Date.now()
              if (now - lastEmitAt < STREAM_EMIT_INTERVAL_MS && reasoning === lastEmittedReasoning && text === lastEmittedText) break
              const content = buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls)
              yield {
                content: content as any,
                metadata: { custom: { run_id: runId || '' } },
              }
              lastEmitAt = now
              lastEmittedReasoning = reasoning
              lastEmittedText = text
              break
            }
            case 'tool_call': {
              const runId = activeRunId
              latestRunId = runId || latestRunId
              let args: unknown = {}
              try {
                args = JSON.parse(ev.arguments)
              } catch {
                args = ev.arguments
              }
              toolCalls.push({
                toolCallId: ev.id,
                toolName: ev.name,
                args,
                argsText: ev.arguments,
              })
              duration = (Date.now() - startTime) / 1000
              const content = buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls)
              yield {
                content: content as any,
                metadata: { custom: { run_id: runId || '' } },
              }
              lastEmittedReasoning = reasoning
              lastEmittedText = text
              break
            }
            case 'tool_result': {
              const runId = activeRunId
              latestRunId = runId || latestRunId
              const tc = toolCalls.find((t) => t.toolCallId === ev.id)
              if (tc) {
                try {
                  tc.result = JSON.parse(ev.result)
                } catch {
                  tc.result = ev.result
                }
              }
              duration = (Date.now() - startTime) / 1000
              const content = buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls)
              yield {
                content: content as any,
                metadata: { custom: { run_id: runId || '' } },
              }
              lastEmittedReasoning = reasoning
              lastEmittedText = text
              break
            }
          }
        }
        if (!completionMeta) {
          try {
            const recovered = await resolveLatestMessage(activeRunId || undefined)
            if (recovered?.content) {
              const recoveredMeta = recovered.metadata_json || {}
              const recoveredContent = splitReasoningContent(recovered.content)
              yield {
                content: buildAssistantContent(
                  recoveredContent.reasoning,
                  recoveredContent.text,
                  reasoningDuration,
                  duration,
                  toolCalls
                ) as any,
                metadata: {
                  custom: {
                    server_message_id: recovered.id,
                    run_id: recovered.run_id || activeRunId || '',
                    tokens_prompt: recovered.tokens_prompt,
                    tokens_completion: recovered.tokens_completion,
                    finish_reason: recovered.finish_reason,
                    ...recoveredMeta,
                  },
                },
              }
            } else if (text || toolCalls.length) {
              yield {
                content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any,
                metadata: {
                  custom: {
                    run_id: activeRunId || '',
                    interrupted: true,
                  },
                },
              }
            }
          } catch (error) {
            if (text || toolCalls.length) {
              yield {
                content: buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any,
                metadata: {
                  custom: {
                    run_id: activeRunId || '',
                    interrupted: true,
                  },
                },
              }
            }
          }
        }
        if (completionMeta && (reasoning || text || toolCalls.length)) {
          const needFinalEmit =
            reasoning !== lastEmittedReasoning || text !== lastEmittedText
          const customMeta = Object.assign({}, completionMeta, { run_id: completionMeta.run_id || latestRunId })
          yield {
            content: needFinalEmit
              ? (buildAssistantContent(reasoning, text, reasoningDuration, duration, toolCalls) as any)
              : (buildAssistantContent(
                  lastEmittedReasoning,
                  lastEmittedText,
                  reasoningDuration,
                  duration,
                  toolCalls
                ) as any),
            metadata: {
              custom: customMeta,
            },
          }
        }
      } else {
        const url = baseUrl
        const result = await post(
          url,
          {
            messages: payloadMessages,
            conversation_id: conversationId,
            parent_message_id: parentMessageId,
            model,
            stream: false,
            metadata: {
              provider: resolvedProvider || DEFAULT_CHAT_PROVIDER,
              model_ref: model || undefined,
              deep_thinking: deepThinking || undefined,
              reasoning_effort: reasoningEffort,
            },
          },
          {
            signal: abortSignal,
            headers: {
              'Content-Type': ContentType.json,
              authorization: authorization,
              ...(workspaceId ? { 'X-Workspace-Id': workspaceId } : {}),
            },
          }
        )
        const data: any = result
        console.debug('[chat-adapter] completion', {
          appId,
          conversationId: data?.conversation_id || conversationId || null,
          runId: data?.run_id || null,
          modelRequested: model,
          modelUsed: data?.model || data?.message?.model_ref || null,
        })
        if (data?.conversation_id) {
          updateConversationContext(data.conversation_id, true)
          globalMitt.emit('refresh_chat_sidebar')
        }

        const parsedMessage = splitReasoningContent(data?.message?.content || '')
        const messageMeta = data?.message?.metadata_json || {}
        yield {
          content: buildAssistantContent(parsedMessage.reasoning, parsedMessage.text, 0, 0) as any,
          metadata: {
            custom: {
              server_message_id: data?.message?.id,
              run_id: data?.run_id || '',
              tokens_prompt: data?.tokens_prompt ?? messageMeta.tokens_prompt,
              tokens_completion: data?.tokens_completion ?? messageMeta.tokens_completion,
              finish_reason: data?.finish_reason ?? messageMeta.finish_reason,
              ...messageMeta,
            },
          },
        }
      }
    } catch (error: any) {
      console.error('*run error', error)
      toast.error(error?.message || 'Chat request failed')
      yield {
        content: [
          {
            type: 'text',
            text: `An error occurred. ${error?.message || ''} . Please try again later.`,
          },
        ],
        metadata: {
          custom: {
            id: '',
          },
        },
      }
    }
  },
}
