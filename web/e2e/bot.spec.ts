import { test, expect, type Page } from '@playwright/test'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockBot = {
  id: 'bot-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Demo Bot',
  description: 'Bot for e2e test',
  status: 'active',
  visibility: 'private',
  tags: ['demo'],
  current_version_id: 'ver-1',
  published_version_id: 'ver-1',
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
  updated_at: '2026-02-16T10:00:00.000Z',
  deleted_at: null,
}

const mockVersion = {
  id: 'ver-1',
  bot_id: 'bot-1',
  version: '1',
  status: 'draft',
  system_prompt: 'You are demo bot',
  model_ref: 'gpt-4o',
  temperature: 0.7,
  max_tokens: 0,
  top_p: 1,
  tool_refs: ['tool:http:weather'],
  metadata_json: {
    variables: [],
    skills: {},
    knowledge: {
      enabled: false,
      dataset_ids: [],
    },
  },
  display_version: 'v1.0.0',
  triggers: {},
  channels: {},
  limits: {},
  created_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
}

async function mockBotApi(page: Page) {
  await page.route('**/api/v1/bots', async (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockBot }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockBot],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/versions/ver-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: mockVersion }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/versions**', async (route) => {
    const method = route.request().method()
    if (method === 'POST' || method === 'PUT') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockVersion }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockVersion],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/execute', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          run_id: 'run-1',
          output: 'mock assistant reply',
          model: 'gpt-4o',
          tokens_prompt: 10,
          tokens_completion: 12,
          finish_reason: 'stop',
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/logs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [
            {
              id: 'log-1',
              run_id: 'run-1',
              step_id: 'step-1',
              level: 'info',
              message: 'step completed',
              code: null,
              status: 'succeeded',
              created_at: '2026-02-16T10:01:00.000Z',
              details: { step_type: 'llm' },
            },
            {
              id: 'log-2',
              run_id: 'run-2',
              step_id: 'step-2',
              level: 'error',
              message: 'step failed',
              code: 'ERR_TIMEOUT',
              status: 'failed',
              created_at: '2026-02-16T10:02:00.000Z',
              details: { step_type: 'tool' },
            },
          ],
          page_size: 2,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [
            {
              id: 'run-1',
              bot_id: 'bot-1',
              status: 'succeeded',
              mode: 'bot',
              user_id: 'user-1',
              message_count: 2,
              input_summary: '{"messages":[{"role":"user","content":"hello"}]}',
              output_summary: '{"text":"ok"}',
              created_at: '2026-02-16T10:00:00.000Z',
              updated_at: '2026-02-16T10:00:02.000Z',
            },
          ],
          page_size: 1,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1/metrics**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          runs_total: 0,
          runs_succeeded: 0,
          runs_failed: 0,
          success_rate: 0,
          avg_latency_ms: 0,
          tokens_prompt: 0,
          tokens_completion: 0,
          active_users: 1,
          usage_distribution: [
            { name: 'succeeded', value: 90 },
            { name: 'failed', value: 10 },
          ],
          resource_usage: {
            cpu_percent: 40,
            memory_percent: 35,
            network_percent: 20,
            storage_percent: 10,
          },
          points: [],
        },
      }),
    })
  })

  await page.route('**/api/v1/api-keys', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.continue()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          api_key: 'sk-test-key-123',
          item: {
            id: 'key-1',
            tenant_id: 'tenant-1',
            workspace_id: 'workspace-1',
            user_id: 'user-1',
            name: 'bot-bot-1-publish',
            key_prefix: 'sk-test',
            status: 'active',
            created_at: '2026-02-16T10:00:00.000Z',
            updated_at: '2026-02-16T10:00:00.000Z',
          },
        },
      }),
    })
  })

  await page.route('**/api/v1/bots/bot-1', async (route) => {
    const method = route.request().method()
    const status = method === 'PUT' ? 200 : 200
    await route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify({ data: mockBot }),
    })
  })

  await page.route('**/api/v1/datasets**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page_size: 0,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockBotApi(page)
})

test('bot build page can send test message via execute api', async ({ page }) => {
  await page.goto('/bot/bot-1/build', { waitUntil: 'domcontentloaded' })

  const input = page.getByPlaceholder('Type a message to test...')
  await expect(input).toBeVisible()
  await input.fill('hello bot')
  await input.press('Enter')

  await expect(page.getByText('mock assistant reply')).toBeVisible()
})

test('bot publish page can request api key from backend', async ({ page }) => {
  await page.goto('/bot/bot-1/publish', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: '后端服务 API' }).click()
  await page.getByRole('button', { name: 'API 密钥' }).click()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByDisplayValue('sk-test-key-123')).toBeVisible()
})

test('bot log page renders backend runs and logs', async ({ page }) => {
  await page.goto('/bot/bot-1/log', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('run-1')).toBeVisible()
  await expect(page.getByText('step completed')).toBeVisible()
  await page.getByRole('tab', { name: '错误记录' }).click()
  await expect(page.getByText('ERR_TIMEOUT')).toBeVisible()
})

test('bot monitor page renders metrics from backend', async ({ page }) => {
  await page.goto('/bot/bot-1/monitor', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('40%')).toBeVisible()
  await expect(page.getByText('90%')).toBeVisible()
})
