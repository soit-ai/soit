import { HttpAgent, type AgentSubscriber, type RunAgentInput } from '@ag-ui/client'
import {
  type Attachment,
  type AttachmentAdapter,
  type CompleteAttachment,
  type PendingAttachment,
  WebSpeechSynthesisAdapter,
} from '@assistant-ui/react'
import { useAgUiRuntime } from '@assistant-ui/react-ag-ui'
import { useEffect, useMemo, useRef } from 'react'
import { toast } from 'sonner'

import { globalMitt } from '@/hooks/use-mitt'
import {
  attachmentContentUrl,
  uploadAttachment,
} from '@/services/attachment-service'
import { cancelResponse } from '@/services/responses-service'
import { createRunFeedback } from '@/services/observe-service'
import { createThread } from '@/services/thread-service'
import { API_BASE_URL, buildAuthHeaders } from '@/utils/request'

const REQUEST_ATTEMPTS = 3
const REQUEST_RETRY_BASE_DELAY_MS = 250
const STREAM_RECONNECT_ATTEMPTS = 5

class GovernedAttachmentAdapter implements AttachmentAdapter {
  accept = [
    'image/*',
    'text/*',
    'application/json',
    'application/pdf',
    'application/rtf',
    'application/msword',
    'application/vnd.ms-excel',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/xml',
    'application/zip',
  ].join(',')

  async add({ file }: { file: File }): Promise<PendingAttachment> {
    return {
      id: globalThis.crypto?.randomUUID?.() || file.name,
      type: file.type.startsWith('image/') ? 'image' : 'document',
      name: file.name,
      contentType: file.type || 'application/octet-stream',
      file,
      status: { type: 'requires-action', reason: 'composer-send' },
    }
  }

  async send(attachment: PendingAttachment): Promise<CompleteAttachment> {
    const uploaded = await uploadAttachment(attachment.file)
    const mimeType = uploaded.content_type
    const contentUrl = attachmentContentUrl(uploaded.id)
    const isImage = mimeType.startsWith('image/')
    return {
      ...attachment,
      id: uploaded.id,
      type: isImage ? 'image' : 'document',
      name: uploaded.filename,
      contentType: mimeType,
      status: { type: 'complete' },
      content: isImage
        ? [{ type: 'image', image: contentUrl, filename: uploaded.filename }]
        : [{ type: 'file', data: contentUrl, mimeType, filename: uploaded.filename }],
    }
  }

  async remove(_attachment: Attachment): Promise<void> {
    return undefined
  }
}

type SoitResources = {
  interactionId?: string
  responseId?: string
  executionRunId?: string
  taskId?: string
  threadId?: string
  agentId?: string
}

type UseSoitAgUiRuntimeOptions = {
  agentId: string
  threadId?: string
  modelRef: string
}

const delay = (duration: number) => new Promise((resolve) => setTimeout(resolve, duration))

const isRetryableResponse = (response: Response): boolean => {
  return response.status === 408 || response.status === 429 || response.status >= 500
}

const replaceRunThread = (
  requestInit: RequestInit,
  threadId: string,
  parentInteractionId?: string
): RequestInit => {
  if (typeof requestInit.body !== 'string') {
    return requestInit
  }
  const input = JSON.parse(requestInit.body) as RunAgentInput
  input.threadId = threadId
  if (input.resume?.length && !input.parentRunId && parentInteractionId) {
    input.parentRunId = parentInteractionId
  }
  const attachmentIds = new Set<string>()
  const collectAttachmentIds = (value: unknown): void => {
    if (typeof value === 'string') {
      const matches = value.matchAll(/\/attachments\/([^/?#]+)\/content(?:[?#]|$)/g)
      for (const match of matches) {
        if (match[1]) attachmentIds.add(decodeURIComponent(match[1]))
      }
      return
    }
    if (Array.isArray(value)) {
      value.forEach(collectAttachmentIds)
      return
    }
    if (value && typeof value === 'object') {
      Object.values(value).forEach(collectAttachmentIds)
    }
  }
  input.messages.forEach(collectAttachmentIds)
  const forwardedProps = (input.forwardedProps || {}) as Record<string, unknown>
  const soit = (
    forwardedProps.soit && typeof forwardedProps.soit === 'object'
      ? forwardedProps.soit
      : {}
  ) as Record<string, unknown>
  input.forwardedProps = {
    ...forwardedProps,
    soit: {
      ...soit,
      attachmentIds: [...attachmentIds],
    },
  }
  return { ...requestInit, body: JSON.stringify(input) }
}

type StreamCursor = {
  responseId: string
  lastEventId: string
  terminal: boolean
  buffer: string
}

const inspectSseChunk = (cursor: StreamCursor, chunk: string): string => {
  cursor.buffer += chunk.replaceAll('\r\n', '\n')
  const frames = cursor.buffer.split('\n\n')
  cursor.buffer = frames.pop() || ''
  for (const frame of frames) {
    let eventId = ''
    for (const line of frame.split('\n')) {
      if (line.startsWith('id:')) {
        eventId = line.slice(3).trim()
        continue
      }
      if (!line.startsWith('data:')) {
        continue
      }
      const value = line.slice(5).trim()
      if (!value || value === '[DONE]') {
        continue
      }
      try {
        const event = JSON.parse(value) as { type?: string }
        if (event.type === 'RUN_FINISHED' || event.type === 'RUN_ERROR') {
          cursor.terminal = true
        }
      } catch {
        // The AG-UI parser will report malformed event payloads to the runtime.
      }
    }
    if (eventId) {
      cursor.lastEventId = eventId
      cursor.responseId = eventId.slice(0, eventId.lastIndexOf(':'))
    }
  }
  return frames.length ? `${frames.join('\n\n')}\n\n` : ''
}

const withAgUiReconnect = (
  initialResponse: Response,
  originalUrl: string,
  originalInit: RequestInit,
  headers: HeadersInit
): Response => {
  if (!initialResponse.body || !initialResponse.ok) {
    return initialResponse
  }

  let decoder = new TextDecoder()
  const encoder = new TextEncoder()
  const cursor: StreamCursor = {
    responseId: '',
    lastEventId: '',
    terminal: false,
    buffer: '',
  }
  const signal = originalInit.signal
  const stream = new ReadableStream<Uint8Array>({
    async start(controller) {
      let response = initialResponse
      let reconnectAttempts = 0
      try {
        while (true) {
          const reader = response.body?.getReader()
          if (!reader) {
            throw new Error('AG-UI response has no readable body')
          }
          let readFailed = false
          try {
            while (true) {
              const { done, value } = await reader.read()
              if (done) {
                break
              }
              const completeFrames = inspectSseChunk(
                cursor,
                decoder.decode(value, { stream: true })
              )
              if (completeFrames) {
                controller.enqueue(encoder.encode(completeFrames))
              }
            }
          } catch (error) {
            if (signal?.aborted) {
              controller.close()
              return
            }
            readFailed = true
          } finally {
            reader.releaseLock()
          }

          if (cursor.terminal || signal?.aborted) {
            controller.close()
            return
          }
          cursor.buffer = ''
          decoder = new TextDecoder()
          while (true) {
            if (reconnectAttempts >= STREAM_RECONNECT_ATTEMPTS) {
              throw new Error(
                readFailed
                  ? 'AG-UI stream reconnect attempts were exhausted'
                  : 'AG-UI stream ended before a terminal event'
              )
            }
            reconnectAttempts += 1
            await delay(
              REQUEST_RETRY_BASE_DELAY_MS * 2 ** Math.min(reconnectAttempts - 1, 3)
            )
            const reconnectHeaders = new Headers(headers)
            let reconnectUrl = originalUrl
            let reconnectInit: RequestInit = { ...originalInit, headers: reconnectHeaders }
            if (cursor.responseId) {
              reconnectUrl = `${API_BASE_URL}/responses/${cursor.responseId}/stream`
              if (cursor.lastEventId) {
                reconnectHeaders.set('Last-Event-ID', cursor.lastEventId)
              }
              reconnectInit = {
                method: 'GET',
                headers: reconnectHeaders,
                signal,
              }
            }
            let candidate: Response
            try {
              candidate = await fetch(reconnectUrl, reconnectInit)
            } catch (error) {
              if (signal?.aborted) {
                controller.close()
                return
              }
              if (reconnectAttempts >= STREAM_RECONNECT_ATTEMPTS) {
                throw error
              }
              continue
            }
            if (!candidate.ok) {
              if (
                !isRetryableResponse(candidate) ||
                reconnectAttempts >= STREAM_RECONNECT_ATTEMPTS
              ) {
                throw new Error(`AG-UI reconnect failed with HTTP ${candidate.status}`)
              }
              await candidate.body?.cancel()
              continue
            }
            response = candidate
            break
          }
        }
      } catch (error) {
        controller.error(error)
      }
    },
  })

  return new Response(stream, {
    status: initialResponse.status,
    statusText: initialResponse.statusText,
    headers: initialResponse.headers,
  })
}

export const useSoitAgUiRuntime = ({
  agentId,
  threadId,
  modelRef,
}: UseSoitAgUiRuntimeOptions) => {
  const selectionRef = useRef({ agentId, threadId: threadId || '', modelRef })
  const resourcesRef = useRef<SoitResources>({})
  const pendingThreadRef = useRef('')

  selectionRef.current = { agentId, threadId: threadId || '', modelRef }

  const agent = useMemo(() => {
    let instance: HttpAgent
    const pendingThreadId = `pending-${globalThis.crypto?.randomUUID?.() || Date.now()}`

    const transport = async (url: string, requestInit: RequestInit): Promise<Response> => {
      let activeThreadId = selectionRef.current.threadId || pendingThreadRef.current
      if (!activeThreadId) {
        const activeAgentId = selectionRef.current.agentId
        const created = await createThread({
          agent_id: activeAgentId !== 'default' ? activeAgentId : undefined,
          default_model_ref: selectionRef.current.modelRef || undefined,
          source: 'web',
          metadata_json: {
            source: 'chat.ag-ui',
            protocol: 'ag-ui',
          },
        })
        activeThreadId = created.id
        pendingThreadRef.current = activeThreadId
        instance.threadId = activeThreadId
      }

      const nextInit = replaceRunThread(
        requestInit,
        activeThreadId,
        resourcesRef.current.interactionId
      )
      const requestHeaders = new Headers(nextInit.headers)
      requestHeaders.set('Accept', 'text/event-stream')
      requestHeaders.set('Content-Type', 'application/json')
      const headers = buildAuthHeaders(Object.fromEntries(requestHeaders.entries()))

      let lastResponse: Response | null = null
      let lastError: unknown = null
      for (let attempt = 0; attempt < REQUEST_ATTEMPTS; attempt += 1) {
        try {
          const response = await fetch(url, { ...nextInit, headers })
          lastResponse = response
          if (!isRetryableResponse(response) || attempt === REQUEST_ATTEMPTS - 1) {
            return withAgUiReconnect(response, url, nextInit, headers)
          }
          await response.body?.cancel()
        } catch (error) {
          if (nextInit.signal?.aborted || attempt === REQUEST_ATTEMPTS - 1) {
            throw error
          }
          lastError = error
        }
        await delay(REQUEST_RETRY_BASE_DELAY_MS * 2 ** attempt)
      }
      if (!lastResponse) {
        throw lastError || new Error('AG-UI request did not produce a response')
      }
      return lastResponse
    }

    instance = new HttpAgent({
      agentId: agentId !== 'default' ? agentId : undefined,
      threadId: threadId || pendingThreadId,
      url: `${API_BASE_URL}/responses`,
      fetch: transport,
    })
    return instance
  }, [agentId, threadId])

  useEffect(() => {
    const finish = () => {
      const resources = resourcesRef.current
      const resolvedThreadId = resources.threadId || pendingThreadRef.current || threadId || ''
      const createdThreadId = pendingThreadRef.current
      pendingThreadRef.current = ''
      globalThis.setTimeout(() => {
        if (createdThreadId) {
          globalMitt.emit('chat_thread_created', { agentId, threadId: createdThreadId })
        }
        globalMitt.emit('refresh_chat_sidebar')
        globalMitt.emit('chat_completion_finished', {
          agentId,
          threadId: resolvedThreadId || null,
          run_id: resources.executionRunId || '',
          response_id: resources.responseId || '',
          task_id: resources.taskId,
          interaction_id: resources.interactionId,
        })
      }, 0)
    }

    const subscriber: AgentSubscriber = {
      onCustomEvent: ({ event }) => {
        if (event.name !== 'soit.resources' || !event.value || typeof event.value !== 'object') {
          return
        }
        resourcesRef.current = event.value as SoitResources
      },
      onRunFinishedEvent: (params) => {
        if (params.outcome === 'interrupt') {
          return
        }
        finish()
      },
      onRunFailed: finish,
    }
    return agent.subscribe(subscriber).unsubscribe
  }, [agent, agentId, threadId])

  const adapters = useMemo(
    () => ({
      attachments: new GovernedAttachmentAdapter(),
      feedback: {
        submit: ({ message, type }: { message: any; type: 'positive' | 'negative' }) => {
          const metadata = (message.metadata?.custom || {}) as Record<string, any>
          void createRunFeedback({
            run_id: metadata.run_id || metadata.runId || null,
            task_id: metadata.task_id || metadata.taskId || null,
            thread_id: resourcesRef.current.threadId || selectionRef.current.threadId || null,
            agent_id: resourcesRef.current.agentId || (
              selectionRef.current.agentId !== 'default' ? selectionRef.current.agentId : null
            ),
            rating: type === 'positive' ? 5 : 1,
            category: 'chat_response',
            metadata_json: {
              message_id: message.id,
              response_id: metadata.response_id || metadata.responseId || null,
              interaction_id: resourcesRef.current.interactionId || null,
              feedback_type: type,
            },
          }).catch((error) => {
            toast.error(error instanceof Error ? error.message : 'Feedback submission failed')
          })
        },
      },
      speech: new WebSpeechSynthesisAdapter(),
    }),
    []
  )

  return useAgUiRuntime({
    agent,
    adapters,
    showThinking: true,
    onCancel: () => {
      const responseId = resourcesRef.current.responseId
      if (responseId) {
        void cancelResponse(responseId).catch((error) => {
          console.error('Failed to cancel response:', error)
        })
      }
    },
    onError: (error) => {
      toast.error(error.message || 'Chat request failed')
    },
  })
}
