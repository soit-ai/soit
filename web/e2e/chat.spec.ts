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
    metadata_json: {},
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
      body: JSON.stringify({
        data: {
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
      body: JSON.stringify({
        data: {
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
      body: JSON.stringify({ data: mockAgent }),
    })
  })

  await page.route('**/api/v1/agents**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
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
        body: JSON.stringify({
          data: {
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
        body: JSON.stringify({
          data: {
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
        body: JSON.stringify({
          data: {
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
      body: JSON.stringify({
        data: {
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

test('thread history renders current thread messages', async ({ page }) => {
  await page.goto('/chat/default/thread-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('history user message')).toBeVisible()
  await expect(page.getByText('history-notes.txt')).toBeVisible()
  await expect(page.getByText('history assistant message')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Demo Thread' })).toBeVisible()
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
  let capturedPayload: any = null
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
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
        'event: response.created',
        'data: {"response_id":"resp-retry","run_id":"run-retry","thread_id":"thread-new"}',
        '',
        'event: response.output_text.delta',
        'data: {"delta":"retry ok"}',
        '',
        'event: response.output_text.completed',
        'data: {"text":"retry ok"}',
        '',
        'event: response.completed',
        'data: {"response_id":"resp-retry","run_id":"run-retry","model":"gpt-4o","finish_reason":"stop","usage":{"prompt_tokens":4,"completion_tokens":2}}',
        '',
        'data: [DONE]',
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
  await expect(page.getByText('retry ok')).toBeVisible()
  expect(capturedPayload.input.messages[0].metadata.attachments[0]).toMatchObject({
    name: 'support-notes.txt',
    type: 'document',
    size: 13,
  })
})

test('agent chat stream renders citation title and snippet', async ({ page }) => {
  const citation = {
    knowledge_id: 'kb_support',
    document_id: 'doc_refund',
    chunk_id: 'chunk_refund_1',
    rank: 1,
    score: 0.93,
    doc_key: 'refund-policy.md',
    title: 'Refund Policy',
    source_uri: 's3://kb/refund-policy.md',
    chunk_no: 2,
    snippet: 'Refund tickets require account verification before workflow escalation.',
  }
  await page.route('**/api/v1/threads/thread-new', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
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
              parent_message_id: 'msg-citation-user',
              content: 'Refund tickets require account verification.',
              citations_json: [citation],
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/agents/agent-citations/stream', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'event: agent.run.started',
        'data: {"run_id":"run-citation"}',
        '',
        'event: agent.response.completed',
        'data: {"output":"Refund tickets require account verification."}',
        '',
        'event: agent.result',
        `data: ${JSON.stringify({ run_id: 'run-citation', response_id: 'resp-citation', thread_id: 'thread-new', model: 'gpt-4o', finish_reason: 'stop', tokens_prompt: 8, tokens_completion: 6, citations: [citation] })}`,
        '',
        'data: [DONE]',
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
  await expect(page.getByText(/Source: Refund Policy/)).toBeVisible()
  await expect(page.getByText('Refund tickets require account verification before workflow escalation.')).toBeVisible()
})
