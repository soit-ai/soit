import { expect, test, type Page } from '@playwright/test'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('chat_default_model', 'gpt-4o')
  localStorage.setItem('chat_default_provider', 'openai')
}

const mockModels = [
  {
    id: 'model-1',
    name: 'GPT-4o',
    provider: 'openai',
    model_ref: 'gpt-4o',
    description: 'Mock model',
    capabilities_json: { model_type: 'llm', capabilities: ['chat'] },
    config_json: { contextLength: 128000 },
    metadata_json: { isActive: true },
    created_at: '2026-02-06T00:00:00.000Z',
    updated_at: '2026-02-06T00:00:00.000Z',
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
    attachments_json: [],
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

  await page.route('**/api/v1/threads**', async (route) => {
    const url = new URL(route.request().url())
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
  await mockChatApi(page)
})

test('chat page renders and composer accepts input', async ({ page }) => {
  await page.goto('/chat/default', { waitUntil: 'domcontentloaded' })

  const input = page.locator('textarea').first()
  await expect(input).toBeVisible()
  await input.fill('hello world')
  await expect(input).toHaveValue('hello world')
})

test('thread history renders current thread messages', async ({ page }) => {
  await page.goto('/chat/default/thread-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('history user message')).toBeVisible()
  await expect(page.getByText('history assistant message')).toBeVisible()
  await expect(page.getByText('Demo Thread')).toBeVisible()
})
