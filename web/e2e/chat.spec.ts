import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('chat_default_model', 'gpt-4o')
  localStorage.setItem('chat_default_provider', 'openai')
}

const mockModels = [
  {
    id: 'model-1',
    provider_id: 'provider-openai',
    provider_slug: 'openai-main',
    provider_name: 'openai',
    provider_kind: 'openai',
    model_id: 'gpt-4o',
    display_name: 'GPT-4o',
    description: 'Mock model',
    model_type: 'llm',
    status: 'available',
    context_window: 128000,
    max_output_tokens: 4096,
    lifecycle_status: 'active',
    sync_status: 'synced',
    source: 'manual',
    month_calls: 0,
    today_calls: 0,
    month_tokens: 0,
    month_cost_amount: 0,
    currency: 'USD',
    avg_latency_ms: null,
    recent_exception_count: 0,
    last_run_at: null,
    last_synced_at: '2026-02-06T00:00:00.000Z',
    updated_at: '2026-02-06T00:00:00.000Z',
    owner: null,
    region: null,
    unit_price: null,
    action_enabled: true,
  },
  {
    id: 'model-2',
    provider_id: 'provider-openai',
    provider_slug: 'openai-main',
    provider_name: 'openai',
    provider_kind: 'openai',
    model_id: 'gpt-5.5',
    display_name: 'GPT-5.5',
    description: 'Mock GPT-5.5 model',
    model_type: 'llm',
    status: 'available',
    context_window: 128000,
    max_output_tokens: 4096,
    lifecycle_status: 'active',
    sync_status: 'synced',
    source: 'manual',
    month_calls: 0,
    today_calls: 0,
    month_tokens: 0,
    month_cost_amount: 0,
    currency: 'USD',
    avg_latency_ms: null,
    recent_exception_count: 0,
    last_run_at: null,
    last_synced_at: '2026-02-06T00:00:00.000Z',
    updated_at: '2026-02-06T00:00:00.000Z',
    owner: null,
    region: null,
    unit_price: null,
    action_enabled: true,
  },
]

const mockThread = {
  id: 'thread-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  agent_id: null,
  title: 'Demo Thread',
  status: 'active',
  thread_type: 'chat',
  source: 'web',
  owner_user_id: 'user-1',
  summary: null,
  system_prompt: null,
  default_model_ref: 'gpt-4o',
  default_temperature: null,
  default_max_tokens: null,
  default_top_p: null,
  context_window: null,
  max_history_messages: null,
  max_history_chars: null,
  message_count: 2,
  last_message_at: '2026-02-06T00:00:02.000Z',
  last_user_message_at: '2026-02-06T00:00:01.000Z',
  last_assistant_message_at: '2026-02-06T00:00:02.000Z',
  archived_at: null,
  pinned_at: null,
  knowledge_config_json: {},
  tool_config_json: {},
  metadata_json: {},
  latest_run_id: 'run-1',
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-06T00:00:00.000Z',
  updated_at: '2026-02-06T00:00:02.000Z',
  deleted_at: null,
}

const mockAgent = {
  id: 'agent-citations',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Support Agent',
  description: 'Answers with support policy citations',
  status: 'active',
  visibility: 'private',
  published_version_id: 'agent-version-1',
  current_version_id: 'agent-version-1',
  latest_version: 1,
  run_count: 0,
  last_run_at: null,
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-06T00:00:00.000Z',
  updated_at: '2026-02-06T00:00:00.000Z',
  deleted_at: null,
}

const mockMessages = [
  {
    id: 'msg-user-1',
    tenant_id: 'tenant-1',
    workspace_id: 'workspace-1',
    thread_id: 'thread-1',
    run_id: null,
    task_id: null,
    response_id: null,
    parent_message_id: null,
    sequence_no: 1,
    role: 'user',
    content: 'history user message',
    message_type: 'text',
    status: 'completed',
    content_json: {},
    summary: null,
    model_ref: null,
    tokens_prompt: null,
    tokens_completion: null,
    finish_reason: null,
    citations_json: [],
    attachments_json: [
      {
        id: 'att-history-1',
        name: 'history-notes.txt',
        type: 'file',
        size: 19,
      },
    ],
    tool_calls_json: [],
    error_code: null,
    error_message: null,
    metadata_json: {},
    created_by: 'user-1',
    created_at: '2026-02-06T00:00:01.000Z',
    edited_at: null,
    deleted_at: null,
  },
  {
    id: 'msg-assistant-1',
    tenant_id: 'tenant-1',
    workspace_id: 'workspace-1',
    thread_id: 'thread-1',
    run_id: 'run-1',
    task_id: null,
    response_id: 'resp-1',
    parent_message_id: 'msg-user-1',
    sequence_no: 2,
    role: 'assistant',
    content: 'history assistant message',
    message_type: 'text',
    status: 'completed',
    content_json: {},
    summary: null,
    model_ref: 'gpt-4o',
    tokens_prompt: 10,
    tokens_completion: 20,
    finish_reason: 'stop',
    citations_json: [],
    attachments_json: [],
    tool_calls_json: [],
    error_code: null,
    error_message: null,
    metadata_json: { reasoning: 'Historical reasoning from persisted metadata.' },
    created_by: null,
    created_at: '2026-02-06T00:00:02.000Z',
    edited_at: null,
    deleted_at: null,
  },
]

async function mockChatApi(page: Page) {
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          summary: {
            total_models: mockModels.length,
            available: mockModels.length,
            disabled: 0,
            abnormal: 0,
            active_providers: 1,
            today_calls: 0,
            month_cost_amount: 0,
            currency: 'USD',
            updated_at: '2026-02-06T00:00:00.000Z',
          },
          tabs: {
            all: mockModels.length,
            llm: mockModels.length,
            embedding: 0,
            rerank: 0,
            available: mockModels.length,
            disabled: 0,
            abnormal: 0,
          },
          items: mockModels,
          total: mockModels.length,
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: mockModels,
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/agents/agent-citations', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockAgent }),
    })
  })

  await page.route('**/api/v1/agents**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [mockAgent],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/threads**', async (route) => {
    const url = new URL(route.request().url())
    if (route.request().method() === 'POST' && url.pathname.endsWith('/threads')) {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            ...mockThread,
            id: 'thread-new',
            title: 'New Chat',
            message_count: 0,
            latest_run_id: null,
          },
        }),
      })
      return
    }
    if (url.pathname.endsWith('/threads/thread-new')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            thread: {
              ...mockThread,
              id: 'thread-new',
              title: 'New Chat',
              message_count: 0,
              latest_run_id: null,
            },
            messages: [],
          },
        }),
      })
      return
    }
    if (url.pathname.endsWith('/threads/thread-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            thread: mockThread,
            messages: mockMessages,
          },
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [mockThread],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockChatApi(page)
})

test('chat page renders and composer accepts input', async ({ page }) => {
  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })

  const input = page.locator('textarea').first()
  await expect(input).toBeVisible({ timeout: 15_000 })
  await input.fill('hello world')
  await expect(input).toHaveValue('hello world')
})

test('GPT-5.5 direct chat forwards hosted tool toggles', async ({ page }) => {
  let capturedPayload: any = null
  await page.route('**/api/v1/responses', async (route) => {
    capturedPayload = JSON.parse(route.request().postData() || '{}')
    const runId = capturedPayload.runId
    const responseThreadId = capturedPayload.threadId
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-hosted:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: responseThreadId, runId })}`,
        '',
        'id: resp-hosted:2',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-hosted","role":"assistant"}',
        '',
        'id: resp-hosted:3',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-hosted","delta":"Hosted tools enabled"}',
        '',
        'id: resp-hosted:4',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-hosted"}',
        '',
        'id: resp-hosted:5',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: responseThreadId, runId, result: { status: 'succeeded' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  await page.getByRole('combobox').filter({ hasText: 'GPT-4o' }).click()
  await page.getByText('GPT-5.5', { exact: true }).click()
  await expect.poll(() => page.evaluate(() => localStorage.getItem('chat_default_model')))
    .toBe('model:openai-main:gpt-5.5')

  const searchToggle = page.getByRole('button', { name: 'Toggle search' })
  const codeToggle = page.getByRole('button', { name: 'Toggle code' })
  await searchToggle.click()
  await codeToggle.click()
  await expect(searchToggle).toHaveAttribute('aria-pressed', 'true')
  await expect(codeToggle).toHaveAttribute('aria-pressed', 'true')

  const input = page.locator('textarea').first()
  await input.fill('Research current data and analyze it with Python')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => capturedPayload).not.toBeNull()
  expect(capturedPayload.forwardedProps.soit).toMatchObject({
    mode: 'direct',
    modelRef: 'model:openai-main:gpt-5.5',
    webSearch: true,
    codeInterpreter: true,
  })
})

test('deep thinking toggle applies to the immediately following request', async ({ page }) => {
  let capturedPayload: any = null
  let capturedHeaders: Record<string, string> = {}
  await page.route('**/api/v1/responses', async (route) => {
    capturedPayload = JSON.parse(route.request().postData() || '{}')
    capturedHeaders = route.request().headers()
    const runId = capturedPayload.runId
    const responseThreadId = capturedPayload.threadId
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-deep:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: responseThreadId, runId })}`,
        '',
        'id: resp-deep:2',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-deep', executionRunId: 'run-deep', threadId: responseThreadId } })}`,
        '',
        'id: resp-deep:3',
        'data: {"type":"REASONING_START","messageId":"msg-deep-reasoning"}',
        '',
        'id: resp-deep:4',
        'data: {"type":"REASONING_MESSAGE_START","messageId":"msg-deep-reasoning","role":"reasoning"}',
        '',
        'id: resp-deep:5',
        'data: {"type":"REASONING_MESSAGE_CONTENT","messageId":"msg-deep-reasoning","delta":"Checked the constraints."}',
        '',
        'id: resp-deep:6',
        'data: {"type":"REASONING_MESSAGE_END","messageId":"msg-deep-reasoning"}',
        '',
        'id: resp-deep:7',
        'data: {"type":"REASONING_END","messageId":"msg-deep-reasoning"}',
        '',
        'id: resp-deep:8',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-deep","role":"assistant"}',
        '',
        'id: resp-deep:9',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-deep","delta":"Deep answer"}',
        '',
        'id: resp-deep:10',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-deep"}',
        '',
        'id: resp-deep:11',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: responseThreadId, runId, result: { status: 'succeeded', responseId: 'resp-deep', executionRunId: 'run-deep' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => page.evaluate(() => localStorage.getItem('chat_default_model')))
    .toBe('model:openai-main:gpt-4o')
  await page.getByRole('button', { name: 'Toggle deepthink' }).click()
  const input = page.locator('textarea').first()
  await input.fill('Use deep thinking now')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => capturedPayload?.forwardedProps?.soit?.deepThinking).toBe(true)
  expect(capturedPayload.forwardedProps.soit.reasoningEffort).toBe('high')
  expect(capturedPayload.forwardedProps.soit.modelRef).toBe('model:openai-main:gpt-4o')
  expect(capturedPayload.forwardedProps.soit.provider).toBe('openai-main')
  expect(capturedHeaders['content-type']).toBe('application/json')
  expect(capturedHeaders.accept).toBe('text/event-stream')
})

test('chat retries a transient network failure before the AG-UI stream starts', async ({ page }) => {
  let requestAttempts = 0
  let requestCompleted = false
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'Retry the initial request',
            message_count: requestCompleted ? 2 : 0,
            latest_run_id: requestCompleted ? 'run-network-retry' : null,
          },
          messages: requestCompleted
            ? [
                {
                  ...mockMessages[0],
                  id: 'msg-network-retry-user',
                  thread_id: 'thread-new',
                  content: 'Retry the initial request',
                  attachments_json: [],
                },
                {
                  ...mockMessages[1],
                  id: 'msg-network-retry',
                  thread_id: 'thread-new',
                  run_id: 'run-network-retry',
                  response_id: 'resp-network-retry',
                  parent_message_id: 'msg-network-retry-user',
                  content: 'Recovered initial request',
                },
              ]
            : [],
        },
      }),
    })
  })
  await page.route('**/api/v1/responses', async (route) => {
    requestAttempts += 1
    if (requestAttempts === 1) {
      await route.abort('connectionfailed')
      return
    }
    const payload = JSON.parse(route.request().postData() || '{}')
    const runId = payload.runId
    requestCompleted = true
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-network-retry:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId })}`,
        '',
        'id: resp-network-retry:2',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-network-retry","role":"assistant"}',
        '',
        'id: resp-network-retry:3',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-network-retry","delta":"Recovered initial request"}',
        '',
        'id: resp-network-retry:4',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-network-retry"}',
        '',
        'id: resp-network-retry:5',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId, result: { status: 'succeeded', responseId: 'resp-network-retry' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  const input = page.locator('textarea').first()
  await input.fill('Retry the initial request')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => requestAttempts, { timeout: 15_000 }).toBe(2)
  await expect(page.getByText('Recovered initial request')).toBeVisible({ timeout: 15_000 })
})

test('chat reconnect discards a partial SSE frame and resumes from the last event', async ({ page }) => {
  let replayLastEventId = ''
  const replayLastEventIds: string[] = []
  let replayAttempts = 0
  let interactionRunId = ''
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'Recover the stream',
            message_count: replayLastEventId ? 2 : 0,
            latest_run_id: replayLastEventId ? 'run-reconnect' : null,
          },
          messages: replayLastEventId
            ? [
                {
                  ...mockMessages[0],
                  id: 'msg-reconnect-user',
                  thread_id: 'thread-new',
                  content: 'Recover the stream',
                  attachments_json: [],
                },
                {
                  ...mockMessages[1],
                  id: 'msg-reconnect',
                  thread_id: 'thread-new',
                  run_id: 'run-reconnect',
                  response_id: 'resp-reconnect',
                  parent_message_id: 'msg-reconnect-user',
                  content: 'Recovered answer',
                },
              ]
            : [],
        },
      }),
    })
  })
  await page.route('**/api/v1/responses/resp-reconnect/stream', async (route) => {
    replayLastEventId = route.request().headers()['last-event-id'] || ''
    replayLastEventIds.push(replayLastEventId)
    replayAttempts += 1
    if (replayAttempts === 1) {
      await route.abort('connectionfailed')
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-reconnect:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-reconnect","delta":"Recovered answer"}',
        '',
        'id: resp-reconnect:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-reconnect"}',
        '',
        'id: resp-reconnect:6',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId: interactionRunId, result: { status: 'succeeded', responseId: 'resp-reconnect', executionRunId: 'run-reconnect' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })
  await page.route('**/api/v1/responses', async (route) => {
    const payload = JSON.parse(route.request().postData() || '{}')
    interactionRunId = payload.runId
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-reconnect:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId: interactionRunId })}`,
        '',
        'id: resp-reconnect:2',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: interactionRunId, responseId: 'resp-reconnect', executionRunId: 'run-reconnect', threadId: 'thread-new' } })}`,
        '',
        'id: resp-reconnect:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-reconnect","role":"assistant"}',
        '',
        'id: resp-reconnect:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-reconnect","delta":"must be discarded',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  const input = page.locator('textarea').first()
  await input.fill('Recover the stream')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => replayAttempts, { timeout: 15_000 }).toBe(2)
  expect(replayLastEventIds).toEqual(['resp-reconnect:3', 'resp-reconnect:3'])
  await expect(page.getByText('Recovered answer')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText(/must be discarded/)).toHaveCount(0)
})

test('cancel is a normal terminal and the thread accepts a later turn', async ({ page }) => {
  let responseCalls = 0
  let cancelCalls = 0
  let cancelStreamCalls = 0
  let canceledRunId = ''
  const browserErrors: string[] = []
  page.on('pageerror', (error) => browserErrors.push(error.message))

  await page.route('**/api/v1/threads/thread-new', async (route) => {
    const completedMessages = responseCalls >= 2
      ? [
          {
            ...mockMessages[0],
            id: 'msg-after-cancel-user',
            thread_id: 'thread-new',
            content: 'Continue normally',
            attachments_json: [],
          },
          {
            ...mockMessages[1],
            id: 'msg-after-cancel',
            thread_id: 'thread-new',
            run_id: 'run-after-cancel',
            response_id: 'resp-after-cancel',
            parent_message_id: 'msg-after-cancel-user',
            content: 'Continued after cancellation',
          },
        ]
      : []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'Cancellation recovery',
            message_count: completedMessages.length,
            latest_run_id: completedMessages.length ? 'run-after-cancel' : null,
          },
          messages: completedMessages,
        },
      }),
    })
  })

  await page.route('**/api/v1/responses/resp-cancel/cancel', async (route) => {
    cancelCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          action: 'cancel',
          response: {
            id: 'resp-cancel',
            status: 'canceled',
          },
        },
      }),
    })
  })

  await page.route('**/api/v1/responses/resp-cancel/stream', async (route) => {
    cancelStreamCalls += 1
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-cancel:4',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-cancel"}',
        '',
        'id: resp-cancel:5',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId: canceledRunId, result: { status: 'canceled', finishReason: 'cancelled' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.route('**/api/v1/responses', async (route) => {
    responseCalls += 1
    const payload = JSON.parse(route.request().postData() || '{}')
    const runId = payload.runId
    if (responseCalls === 1) {
      canceledRunId = runId
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
          'id: resp-cancel:1',
          `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId })}`,
          '',
          'id: resp-cancel:2',
          `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-cancel', executionRunId: 'run-cancel', threadId: 'thread-new' } })}`,
          '',
          'id: resp-cancel:3',
          'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-cancel","role":"assistant"}',
          '',
          '',
        ].join('\n'),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-after-cancel:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId })}`,
        '',
        'id: resp-after-cancel:2',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-after-cancel', executionRunId: 'run-after-cancel', threadId: 'thread-new' } })}`,
        '',
        'id: resp-after-cancel:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-after-cancel","role":"assistant"}',
        '',
        'id: resp-after-cancel:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-after-cancel","delta":"Continued after cancellation"}',
        '',
        'id: resp-after-cancel:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-after-cancel"}',
        '',
        'id: resp-after-cancel:6',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId, result: { status: 'succeeded', responseId: 'resp-after-cancel', executionRunId: 'run-after-cancel' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  const input = page.locator('textarea').first()
  await input.fill('Start a long task')
  await page.getByRole('button', { name: /send/i }).click()
  await page.getByRole('button', { name: /cancel/i }).click()

  await expect.poll(() => cancelCalls).toBe(1)
  await expect.poll(() => cancelStreamCalls).toBe(1)
  await expect(page).toHaveURL(/\/chat\/default\/thread-new$/)
  await expect(page.getByText(/Chat request failed/)).toHaveCount(0)

  const nextInput = page.locator('textarea').first()
  await nextInput.fill('Continue normally')
  await expect(page.getByRole('button', { name: /send/i })).toBeEnabled()
  await page.getByRole('button', { name: /send/i }).click()
  await expect.poll(() => responseCalls).toBe(2)
  await expect(page.getByText('Continued after cancellation')).toBeVisible()
  expect(browserErrors).toEqual([])
})

test('thread history renders current thread messages', async ({ page }) => {
  await page.goto('/chat/default/thread-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('history user message')).toBeVisible()
  await expect(page.getByText('history-notes.txt')).toBeVisible()
  await expect(page.getByText('history assistant message')).toBeVisible()
  await page.getByRole('button', { name: 'Reasoning' }).click()
  await expect(page.getByText('Historical reasoning from persisted metadata.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Demo Thread' })).toBeVisible()
})

test('failed history remains visible and the same thread accepts the next turn', async ({ page }) => {
  let responseCalls = 0
  const failedMessages = [
    {
      ...mockMessages[0],
      id: 'msg-failed-user',
      thread_id: 'thread-failed',
      content: 'Trigger a provider failure',
      attachments_json: [],
    },
    {
      ...mockMessages[1],
      id: 'msg-failed-assistant',
      thread_id: 'thread-failed',
      parent_message_id: 'msg-failed-user',
      response_id: 'resp-failed',
      run_id: 'run-failed',
      content: 'Agent execution failed',
      status: 'failed',
      error_code: 'agent_execution_failed',
      error_message: 'Agent execution failed',
      metadata_json: {},
    },
  ]

  await page.route('**/api/v1/threads/thread-failed', async (route) => {
    const recoveredMessages = responseCalls > 0
      ? [
          ...failedMessages,
          {
            ...mockMessages[0],
            id: 'msg-recovery-user',
            thread_id: 'thread-failed',
            parent_message_id: 'msg-failed-assistant',
            sequence_no: 3,
            content: 'Try the next turn',
            attachments_json: [],
          },
          {
            ...mockMessages[1],
            id: 'msg-recovery-assistant',
            thread_id: 'thread-failed',
            parent_message_id: 'msg-recovery-user',
            sequence_no: 4,
            response_id: 'resp-recovered',
            run_id: 'run-recovered',
            content: 'Recovered on the same thread',
            metadata_json: {},
          },
        ]
      : failedMessages
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-failed',
            title: 'Failed Thread',
            message_count: recoveredMessages.length,
          },
          messages: recoveredMessages,
        },
      }),
    })
  })

  await page.route('**/api/v1/responses', async (route) => {
    responseCalls += 1
    const payload = JSON.parse(route.request().postData() || '{}')
    const runId = payload.runId
    expect(payload.threadId).toBe('thread-failed')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-recovered:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-failed', runId })}`,
        '',
        'id: resp-recovered:2',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-recovered', executionRunId: 'run-recovered', threadId: 'thread-failed' } })}`,
        '',
        'id: resp-recovered:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-recovered","role":"assistant"}',
        '',
        'id: resp-recovered:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-recovered","delta":"Recovered on the same thread"}',
        '',
        'id: resp-recovered:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-recovered"}',
        '',
        'id: resp-recovered:6',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-failed', runId, result: { status: 'succeeded', responseId: 'resp-recovered', executionRunId: 'run-recovered' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default/thread-failed', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('paragraph').filter({ hasText: 'Agent execution failed' })).toBeVisible()
  await expect(page.locator('.aui-message-error-message')).toContainText('Agent execution failed')

  const input = page.locator('textarea').first()
  await input.fill('Try the next turn')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => responseCalls).toBe(1)
  await expect(page.getByText('Recovered on the same thread', { exact: true })).toBeVisible()
})

test('regenerate reuses the persisted user turn as a branch head', async ({ page }) => {
  let capturedPayload: any = null
  await page.route('**/api/v1/responses', async (route) => {
    capturedPayload = JSON.parse(route.request().postData() || '{}')
    const runId = capturedPayload.runId
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-branch:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-1', runId })}`,
        '',
        'id: resp-branch:2',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-branch', executionRunId: 'run-branch', threadId: 'thread-1' } })}`,
        '',
        'id: resp-branch:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-branch","role":"assistant"}',
        '',
        'id: resp-branch:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-branch","delta":"Alternative answer"}',
        '',
        'id: resp-branch:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-branch"}',
        '',
        'id: resp-branch:6',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-1', runId, result: { status: 'succeeded', responseId: 'resp-branch', executionRunId: 'run-branch' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default/thread-1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Regenerate response' }).click()

  await expect.poll(() => capturedPayload?.runId).toBeTruthy()
  const users = capturedPayload.messages.filter((message: any) => message.role === 'user')
  expect(users.at(-1)?.id).toBe('msg-user-1')
  expect(JSON.stringify(users.at(-1)?.content)).toContain('history user message')
  expect(capturedPayload.forwardedProps.soit).toMatchObject({
    mode: 'direct',
    modelRef: 'model:openai-main:gpt-4o',
  })
})

test('chat page shows a retryable error when bootstrap data fails', async ({ page }) => {
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'model bootstrap unavailable' }),
    })
  })

  const modelBootstrapFailure = page.waitForResponse((response) => {
    return response.url().includes('/api/v1/modelhub/workbench/models') && response.status() === 500
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })
  await modelBootstrapFailure

  await expect(page.getByRole('alert')).toContainText('Failed to load chat workspace', { timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
})

test('chat send retries transient response failure and includes attachments', async ({ page }) => {
  let responseAttempts = 0
  let uploadAttempts = 0
  let capturedPayload: any = null
  await page.route('**/api/v1/attachments', async (route) => {
    uploadAttempts += 1
    expect(route.request().headers()['content-type']).toContain('multipart/form-data')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          id: 'att-new-1',
          filename: 'support-notes.txt',
          content_type: 'text/plain',
          size_bytes: 13,
          checksum: 'sha256:contract',
          status: 'ready',
          thread_id: null,
          created_at: '2026-07-16T00:00:00Z',
          updated_at: '2026-07-16T00:00:00Z',
        },
      }),
    })
  })
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'New Chat',
            message_count: responseAttempts >= 2 ? 2 : 0,
            latest_run_id: responseAttempts >= 2 ? 'run-retry' : null,
          },
          messages:
            responseAttempts >= 2
              ? [
                  {
                    ...mockMessages[0],
                    id: 'msg-new-user',
                    thread_id: 'thread-new',
                    run_id: 'run-retry',
                    response_id: 'resp-retry',
                    content: 'summarize attachment',
                    attachments_json: [
                      {
                        id: 'att-new-1',
                        name: 'support-notes.txt',
                        type: 'document',
                        size: 13,
                      },
                    ],
                  },
                  {
                    ...mockMessages[1],
                    id: 'msg-new-assistant',
                    thread_id: 'thread-new',
                    run_id: 'run-retry',
                    response_id: 'resp-retry',
                    parent_message_id: 'msg-new-user',
                    content: 'retry ok',
                  },
                ]
              : [],
        },
      }),
    })
  })

  await page.route('**/api/v1/responses', async (route) => {
    responseAttempts += 1
    capturedPayload = JSON.parse(route.request().postData() || '{}')
    if (responseAttempts === 1) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'temporary provider outage' }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-retry:1',
        'data: {"type":"RUN_STARTED","threadId":"thread-new","runId":"interaction-retry"}',
        '',
        'id: resp-retry:2',
        'data: {"type":"CUSTOM","name":"soit.resources","value":{"schemaVersion":1,"interactionId":"interaction-retry","responseId":"resp-retry","executionRunId":"run-retry","threadId":"thread-new"}}',
        '',
        'id: resp-retry:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-retry","role":"assistant"}',
        '',
        'id: resp-retry:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-retry","delta":"retry ok"}',
        '',
        'id: resp-retry:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-retry"}',
        '',
        'id: resp-retry:6',
        'data: {"type":"CUSTOM","name":"soit.usage","value":{"schemaVersion":1,"model":"gpt-4o","usage":{"prompt_tokens":4,"completion_tokens":2}}}',
        '',
        'id: resp-retry:7',
        'data: {"type":"RUN_FINISHED","threadId":"thread-new","runId":"interaction-retry","result":{"status":"succeeded","responseId":"resp-retry","executionRunId":"run-retry"}}',
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })

  const fileChooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Add images or files' }).click()
  await (await fileChooser).setFiles({
    name: 'support-notes.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('refund policy'),
  })
  await expect(page.getByText('support-notes.txt')).toBeVisible()

  const input = page.locator('textarea').first()
  await input.fill('summarize attachment')
  await page.getByRole('button', { name: /send/i }).click()

  await expect.poll(() => responseAttempts).toBe(2)
  expect(uploadAttempts).toBe(1)
  await expect(page.getByText('retry ok')).toBeVisible()
  expect(capturedPayload.threadId).toBe('thread-new')
  expect(capturedPayload.runId).toBeTruthy()
  expect(capturedPayload.forwardedProps.soit).toMatchObject({
    mode: 'direct',
    modelRef: 'model:openai-main:gpt-4o',
    attachmentIds: ['att-new-1'],
  })
  const userMessage = capturedPayload.messages.find((message: any) => message.role === 'user')
  expect(userMessage.content).toEqual(expect.arrayContaining([
    expect.objectContaining({
      type: 'document',
      source: expect.objectContaining({
        type: 'url',
        value: expect.stringMatching(/\/api\/v1\/attachments\/att-new-1\/content$/),
      }),
      metadata: { filename: 'support-notes.txt' },
    }),
  ]))
  expect(JSON.stringify(capturedPayload)).not.toContain('data:text/plain')
})

test('agent chat stream renders sources and governed artifacts', async ({ page }) => {
  let capturedPayload: any = null
  let feedbackPayload: any = null
  let artifactDownloads = 0
  const renderLoopErrors: string[] = []
  page.on('pageerror', (error) => {
    if (/maximum update depth|infinite loop|result of getSnapshot/i.test(error.message)) {
      renderLoopErrors.push(error.message)
    }
  })
  page.on('console', (message) => {
    if (
      message.type() === 'error' &&
      /maximum update depth|infinite loop|result of getSnapshot/i.test(message.text())
    ) {
      renderLoopErrors.push(message.text())
    }
  })
  await page.route('**/api/v1/runs/run-citation/artifacts/art-report/content', async (route) => {
    artifactDownloads += 1
    expect(route.request().headers().authorization).toBe('Bearer test-token')
    await route.fulfill({ status: 200, contentType: 'text/csv', body: 'name,value\nSOIT,1\n' })
  })
  await page.route('**/api/v1/observe/feedback', async (route) => {
    feedbackPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { id: 'feedback-chat-1', ...feedbackPayload } }),
    })
  })
  const citation = {
    knowledge_id: 'kb_support',
    document_id: 'doc_refund',
    chunk_id: 'chunk_refund_1',
    rank: 1,
    score: 0.93,
    doc_key: 'refund-policy.md',
    title: 'Refund Policy',
    url: 'https://example.com/refund-policy',
    source_uri: 's3://kb/refund-policy.md',
    chunk_no: 2,
    snippet: 'Refund tickets require account verification before workflow escalation.',
  }
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'How should I handle a refund ticket?',
            message_count: 2,
            latest_run_id: 'run-citation',
          },
          messages: [
            {
              ...mockMessages[0],
              id: 'msg-citation-user',
              thread_id: 'thread-new',
              run_id: 'run-citation',
              response_id: 'resp-citation',
              content: 'How should I handle a refund ticket?',
              attachments_json: [],
            },
            {
              ...mockMessages[1],
              id: 'msg-citation-assistant',
              thread_id: 'thread-new',
              run_id: 'run-citation',
              response_id: 'resp-citation',
              task_id: 'task-citation',
              parent_message_id: 'msg-citation-user',
              content: 'Refund tickets require account verification.',
              model_ref: 'gpt-4o',
              tokens_prompt: 8,
              tokens_completion: 6,
              finish_reason: 'stop',
              citations_json: [citation],
              tool_calls_json: [
                {
                  id: 'tool-call-1',
                  name: 'lookup_refund_policy',
                  arguments_json: { ticket_id: 'ticket-1' },
                  result_json: { verified: true },
                  status: 'succeeded',
                },
              ],
              metadata_json: {
                branch_id: 'branch-citation',
                budget_exceeded: false,
                budget_reason: 'within configured limits',
                cost_total: 0.0014,
                artifacts: [
                  {
                    id: 'art-report',
                    type: 'file',
                    name: 'report.csv',
                    mime: 'text/csv',
                    size_bytes: 128,
                    download_url: '/api/v1/runs/run-citation/artifacts/art-report/content',
                  },
                ],
              },
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/responses', async (route) => {
    capturedPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-citation:1',
        'data: {"type":"RUN_STARTED","threadId":"thread-new","runId":"interaction-citation"}',
        '',
        'id: resp-citation:2',
        'data: {"type":"CUSTOM","name":"soit.resources","value":{"schemaVersion":1,"interactionId":"interaction-citation","responseId":"resp-citation","executionRunId":"run-citation","taskId":"task-citation","threadId":"thread-new","agentId":"agent-citations"}}',
        '',
        'id: resp-citation:3',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-citation","role":"assistant"}',
        '',
        'id: resp-citation:4',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-citation","delta":"Refund tickets require account verification."}',
        '',
        'id: resp-citation:5',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-citation"}',
        '',
        'id: resp-citation:6',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.source', value: { schemaVersion: 1, ...citation } })}`,
        '',
        'id: resp-citation:7',
        'data: {"type":"CUSTOM","name":"soit.artifact","value":{"schemaVersion":1,"id":"art-report","type":"file","name":"report.csv","mime":"text/csv","size_bytes":128,"download_url":"/api/v1/runs/run-citation/artifacts/art-report/content"}}',
        '',
        'id: resp-citation:8',
        'data: {"type":"CUSTOM","name":"soit.usage","value":{"schemaVersion":1,"model":"gpt-4o","usage":{"prompt_tokens":8,"completion_tokens":6,"total_tokens":14}}}',
        '',
        'id: resp-citation:9',
        'data: {"type":"RUN_FINISHED","threadId":"thread-new","runId":"interaction-citation","result":{"status":"succeeded","responseId":"resp-citation","executionRunId":"run-citation","taskId":"task-citation"}}',
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/agent-citations', { waitUntil: 'domcontentloaded' })

  const input = page.getByPlaceholder('Send a message to the current agent...')
  await input.fill('How should I handle a refund ticket?')
  const sendButton = page.getByRole('button', { name: /send/i })
  await expect(sendButton).toBeEnabled()
  await sendButton.click()

  await expect(page.getByText('Refund tickets require account verification.')).toBeVisible()
  const runPanel = page.getByRole('button', { name: 'Run details', exact: true })
  await expect(runPanel).toHaveAttribute('aria-expanded', 'false')
  await expect(page.getByText('Tokens: prompt 8 · completion 6 · total 14')).toBeHidden()
  await expect(async () => {
    if ((await runPanel.getAttribute('aria-expanded')) !== 'true') {
      await runPanel.click()
    }
    await expect(runPanel).toHaveAttribute('aria-expanded', 'true')
    await expect(page.getByText('Tokens: prompt 8 · completion 6 · total 14')).toBeVisible()
    await expect(page.getByText('run-citation', { exact: true })).toBeVisible()
    await expect(page.getByText('resp-citation', { exact: true })).toBeVisible()
    await expect(page.getByText('task-citation', { exact: true })).toBeVisible()
    await expect(page.getByText('gpt-4o', { exact: true })).toBeVisible()
    await expect(page.getByText('1 tool call')).toBeVisible()
    await expect(page.getByText('Budget: within limit · within configured limits')).toBeVisible()
    await expect(page.getByText('Cost: 0.0014')).toBeVisible()
    await expect(page.getByRole('button', { name: 'View run details' })).toBeVisible()
  }).toPass({ timeout: 15_000 })
  await expect(page.getByText(/Source: Refund Policy/)).toBeVisible()
  await expect(page.getByRole('link', { name: 'Source: Refund Policy' })).toHaveAttribute(
    'href',
    'https://example.com/refund-policy'
  )
  await expect(page.getByText('Refund tickets require account verification before workflow escalation.')).toBeVisible()
  await expect(page.getByText('report.csv')).toBeVisible()
  await page.getByRole('button', { name: 'Download report.csv' }).click()
  await expect.poll(() => artifactDownloads).toBe(1)
  await page.getByRole('button', { name: 'Helpful', exact: true }).click()
  await expect.poll(() => feedbackPayload?.rating).toBe(5)
  expect(feedbackPayload).toMatchObject({
    run_id: 'run-citation',
    thread_id: 'thread-new',
    agent_id: 'agent-citations',
    category: 'chat_response',
    metadata_json: {
      message_id: 'msg-citation-assistant',
      response_id: 'resp-citation',
      feedback_type: 'positive',
    },
  })
  expect(capturedPayload.forwardedProps.soit).toMatchObject({
    mode: 'agent',
    agentId: 'agent-citations',
  })
  expect(capturedPayload.forwardedProps.soit.modelRef).toBeUndefined()
  expect(renderLoopErrors).toEqual([])
})

test('agent approval interrupt can be approved and resumed', async ({ page }) => {
  let responseCalls = 0
  let resumePayload: any = null
  let interruptedRunId = ''

  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          thread: {
            ...mockThread,
            id: 'thread-new',
            title: 'Approve sensitive action',
            message_count: responseCalls >= 2 ? 2 : 0,
            latest_run_id: responseCalls >= 2 ? 'run-approval' : null,
          },
          messages:
            responseCalls >= 2
              ? [
                  {
                    ...mockMessages[0],
                    id: 'msg-approval-user',
                    thread_id: 'thread-new',
                    run_id: 'run-approval',
                    response_id: 'resp-approval',
                    content: 'Approve sensitive action',
                    attachments_json: [],
                  },
                  {
                    ...mockMessages[1],
                    id: 'msg-approval-assistant',
                    thread_id: 'thread-new',
                    run_id: 'run-approval',
                    response_id: 'resp-approval',
                    parent_message_id: 'msg-approval-user',
                    content: 'Sensitive action completed.',
                  },
                ]
              : [],
        },
      }),
    })
  })

  await page.route('**/api/v1/responses', async (route) => {
    responseCalls += 1
    const payload = JSON.parse(route.request().postData() || '{}')
    const runId = payload.runId
    if (responseCalls === 1) {
      interruptedRunId = runId
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: [
          'id: resp-approval:1',
          `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId })}`,
          '',
          'id: resp-approval:2',
          `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-approval', executionRunId: 'run-approval', taskId: 'task-approval', threadId: 'thread-new', agentId: 'agent-citations' } })}`,
          '',
          'id: resp-approval:3',
          `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.approval', value: { schemaVersion: 1, status: 'pending' } })}`,
          '',
          'id: resp-approval:4',
          `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId, outcome: { type: 'interrupt', interrupts: [{ id: 'approval_e2e', reason: 'tool_call', message: 'Approve sensitive tool call', toolCallId: 'call-approval', metadata: { toolRef: 'tool:test:sensitive' } }] } })}`,
          '',
          '',
        ].join('\n'),
      })
      return
    }

    resumePayload = payload
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-approval:5',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: 'thread-new', runId })}`,
        '',
        'id: resp-approval:6',
        `data: ${JSON.stringify({ type: 'CUSTOM', name: 'soit.resources', value: { schemaVersion: 1, interactionId: runId, responseId: 'resp-approval', executionRunId: 'run-approval', taskId: 'task-approval', threadId: 'thread-new', agentId: 'agent-citations' } })}`,
        '',
        'id: resp-approval:7',
        'data: {"type":"TEXT_MESSAGE_START","messageId":"msg-approval","role":"assistant"}',
        '',
        'id: resp-approval:8',
        'data: {"type":"TEXT_MESSAGE_CONTENT","messageId":"msg-approval","delta":"Sensitive action completed."}',
        '',
        'id: resp-approval:9',
        'data: {"type":"TEXT_MESSAGE_END","messageId":"msg-approval"}',
        '',
        'id: resp-approval:10',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: 'thread-new', runId, outcome: { type: 'success' }, result: { status: 'succeeded', responseId: 'resp-approval', executionRunId: 'run-approval', taskId: 'task-approval' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat/agent-citations', { waitUntil: 'domcontentloaded' })
  const input = page.getByPlaceholder('Send a message to the current agent...')
  await input.fill('Approve sensitive action')
  await page.getByRole('button', { name: /send/i }).click()

  await expect(page.getByText('Human approval required')).toBeVisible()
  await expect(page.getByText('Approve sensitive tool call')).toBeVisible()
  await page.getByRole('button', { name: 'Approve', exact: true }).click()
  await page.getByRole('button', { name: 'Submit and continue' }).click()

  await expect.poll(() => responseCalls).toBe(2)
  await expect(page.getByText('Sensitive action completed.')).toBeVisible()
  expect(resumePayload.resume).toEqual([
    {
      interruptId: 'approval_e2e',
      status: 'resolved',
      payload: { decision: 'approved' },
    },
  ])
  expect(resumePayload.parentRunId).toBe(interruptedRunId)
  expect(resumePayload.forwardedProps.soit).toMatchObject({
    mode: 'agent',
    agentId: 'agent-citations',
  })
})
