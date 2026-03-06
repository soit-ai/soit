import { test, expect, type Page } from '@playwright/test'

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

const mockConversation = {
  id: 'conv-1',
  title: 'Demo Conversation',
  status: 'active',
  metadata_json: { provider: 'openai' },
  system_prompt: null,
  default_model_ref: 'gpt-4o',
  default_temperature: null,
  default_max_tokens: null,
  default_top_p: null,
  message_count: 0,
  last_message_at: null,
  created_by: null,
  updated_by: null,
  created_at: '2026-02-06T00:00:00.000Z',
  updated_at: '2026-02-06T00:00:00.000Z',
}

const mockMessages = [
  {
    id: 'msg-user-1',
    conversation_id: 'conv-1',
    role: 'USER',
    content: 'history user message',
    model_ref: null,
    tokens_prompt: null,
    tokens_completion: null,
    finish_reason: null,
    run_id: null,
    created_by: 'user-1',
    metadata_json: {},
    created_at: '2026-02-06T00:00:01.000Z',
  },
  {
    id: 'msg-assistant-1',
    conversation_id: 'conv-1',
    role: 'ASSISTANT',
    content: 'history assistant message',
    model_ref: 'gpt-4o',
    tokens_prompt: 10,
    tokens_completion: 20,
    finish_reason: 'stop',
    run_id: 'run-1',
    created_by: null,
    metadata_json: {},
    created_at: '2026-02-06T00:00:02.000Z',
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

  await page.route('**/api/v1/chat/conversations/*/messages**', async (route) => {
    const url = route.request().url()
    const items = url.includes('/chat/conversations/conv-1/messages') ? mockMessages : []
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items,
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/chat/conversations/*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: mockConversation }),
    })
  })

  await page.route('**/api/v1/chat/conversations**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockConversation],
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

test('history messages keep user-right and assistant-left alignment', async ({ page }) => {
  await page.goto('/chat/default/conv-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('history user message')).toBeVisible()
  await expect(page.getByText('history assistant message')).toBeVisible()

  await expect(page.getByTestId('chat-message-user-row').first()).toHaveClass(/justify-end/)
  await expect(page.getByTestId('chat-message-assistant-row').first()).not.toHaveClass(/justify-end/)
})
