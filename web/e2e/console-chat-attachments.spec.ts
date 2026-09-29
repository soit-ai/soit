import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

// The console chat's composer is assistant-ui's: these hold its attachment
// handling to what the console needs across assistant-ui upgrades, which have
// changed it before without a type error to show for it.

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const NOW = '2026-09-29T08:00:00Z'

const model = {
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
  last_synced_at: NOW,
  updated_at: NOW,
  owner: null,
  region: null,
  unit_price: null,
  action_enabled: true,
}

const thread = {
  id: 'thread_attach',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  agent_id: null,
  title: 'Attachment review',
  status: 'active',
  thread_type: 'chat',
  source: 'web',
  owner_user_id: 'user-1',
  default_model_ref: 'gpt-4o',
  message_count: 0,
  last_message_at: NOW,
  knowledge_config_json: {},
  tool_config_json: {},
  metadata_json: {},
  latest_run_id: null,
  created_by: 'user-1',
  created_at: NOW,
  updated_at: NOW,
  deleted_at: null,
}

async function mockChat(page: Page) {
  await page.route('**/api/v1/modelhub/workbench/models**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        summary: {
          total_models: 1,
          available: 1,
          disabled: 0,
          abnormal: 0,
          active_providers: 1,
          today_calls: 0,
          month_cost_amount: 0,
          currency: 'USD',
          updated_at: NOW,
        },
        tabs: { all: 1, llm: 1, embedding: 0, rerank: 0, available: 1, disabled: 0, abnormal: 0 },
        items: [model],
        total: 1,
        page_size: 200,
        next_page_token: null,
      }),
    }),
  )
  await page.route('**/api/v1/models**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items: [model], page_size: 200, next_page_token: null }),
    }),
  )
  await page.route('**/api/v1/threads?**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items: [thread], next_page_token: null, page_size: 100 }),
    }),
  )
  await page.route(`**/api/v1/threads/${thread.id}`, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ thread, messages: [] }),
    }),
  )
}

async function pickFile(page: Page, name: string, content: string) {
  const chooser = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Add images or files' }).click()
  await (await chooser).setFiles({ name, mimeType: 'text/plain', buffer: Buffer.from(content) })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await mockChat(page)
})

test('a failed attachment upload comes back to the composer and sending again retries it', async ({ page }) => {
  let uploads = 0
  let sent: any = null
  await page.route('**/api/v1/attachments', (route) => {
    uploads += 1
    if (uploads === 1) {
      return route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'SERVICE_UNAVAILABLE',
          message: 'Attachment upload temporarily unavailable',
          data: null,
        }),
      })
    }
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: ok({
        id: 'att-retry-1',
        filename: 'retry.txt',
        content_type: 'text/plain',
        size_bytes: 5,
        checksum: 'sha256:retry',
        status: 'ready',
        thread_id: null,
        created_at: NOW,
        updated_at: NOW,
      }),
    })
  })
  await page.route('**/api/v1/responses', (route) => {
    sent = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: [
        'id: resp-attachment-retry:1',
        `data: ${JSON.stringify({ type: 'RUN_STARTED', threadId: sent.threadId, runId: sent.runId })}`,
        '',
        'id: resp-attachment-retry:2',
        `data: ${JSON.stringify({ type: 'RUN_FINISHED', threadId: sent.threadId, runId: sent.runId, result: { status: 'succeeded' } })}`,
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/chat', { waitUntil: 'domcontentloaded' })
  const composer = page.getByRole('textbox').last()
  await composer.fill('summarize the attached file')
  await pickFile(page, 'retry.txt', 'retry')
  const send = page.getByRole('button', { name: 'Send message' })
  await send.click()

  await expect.poll(() => uploads).toBe(1)
  await expect(page.getByText('Attachment upload temporarily unavailable')).toBeVisible()
  // Nothing was sent: the text and the file are back in the composer, the
  // file marked as failed.
  expect(sent).toBeNull()
  await expect(composer).toHaveValue('summarize the attached file')
  await expect(page.getByText('retry.txt')).toBeVisible()
  await expect(page.getByText('Upload failed')).toBeVisible()
  await expect(send).toBeEnabled()

  await send.click()
  await expect.poll(() => uploads).toBe(2)
  await expect.poll(() => sent).not.toBeNull()
  expect(sent.forwardedProps.soit.attachmentIds).toEqual(['att-retry-1'])
})

test('an attachment can be removed before sending', async ({ page }) => {
  await page.goto('/chat', { waitUntil: 'domcontentloaded' })
  await pickFile(page, 'cancel.txt', 'cancel')

  await expect(page.getByText('cancel.txt')).toBeVisible()
  await page.getByRole('button', { name: 'Remove file' }).click()
  await expect(page.getByText('cancel.txt')).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Send message' })).toBeDisabled()
})
