import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const workflowWorkbench = {
  summary: {
    total_workflows: 1,
    published_workflows: 0,
    running_workflows: 0,
    today_runs: 0,
    avg_latency_ms: null,
    success_rate: null,
    recent_exceptions: 0,
    updated_at: NOW,
  },
  tabs: { all: 1, high_volume: 0, publishing: 1, abnormal: 0, draft: 0 },
  items: [
    {
      id: 'docs-nightly-sync',
      name: 'docs-nightly-sync',
      summary: 'crawl → chunk → embed',
      status: 'publishing',
      linked_agents: [],
      linked_agent_count: 0,
      today_runs: 0,
      avg_latency_ms: null,
      success_rate: null,
      recent_exception_count: 0,
      owner: 'Wei',
      last_run_at: null,
      action_enabled: true,
      updated_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 50,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('publishing a workflow promotes its current version', async ({ page }) => {
  let publishedTo: string | null = null
  await json(page, '**/api/v1/workflows/workbench**', workflowWorkbench)
  await json(page, '**/api/v1/workflows/docs-nightly-sync', {
    id: 'docs-nightly-sync',
    name: 'docs-nightly-sync',
    status: 'draft',
    visibility: 'workspace',
    current_version_id: 'wfv_9',
    published_version_id: null,
    metadata_json: {},
    created_at: NOW,
    updated_at: NOW,
  })
  await page.route('**/api/v1/workflows/docs-nightly-sync/publish', (route) => {
    publishedTo = JSON.stringify(route.request().postDataJSON())
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok({ id: 'docs-nightly-sync' }) })
  })

  await page.goto('/v2/build/workflows', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Publish/ }).click()
  await page.getByRole('button', { name: 'Publish', exact: true }).click()

  // The confirm names the workflow so it is clear what is being promoted.
  await expect(page.getByText('docs-nightly-sync', { exact: false }).last()).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Publish' }).click()

  await expect.poll(() => publishedTo).not.toBeNull()
  expect(publishedTo).toContain('wfv_9')
})

test('archiving a workflow asks first and then deletes', async ({ page }) => {
  let deleted = false
  await json(page, '**/api/v1/workflows/workbench**', workflowWorkbench)
  await page.route('**/api/v1/workflows/docs-nightly-sync**', (route) => {
    if (route.request().method() === 'DELETE') {
      deleted = true
      return route.fulfill({ status: 204, body: '' })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok({}) })
  })

  await page.goto('/v2/build/workflows', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Publish/ }).click()
  await page.getByRole('button', { name: 'Archive' }).click()

  await expect(page.getByRole('heading', { name: 'Archive workflow' })).toBeVisible()
  expect(deleted).toBe(false)

  await page.locator('.console-modal').getByRole('button', { name: 'Archive' }).click()
  await expect.poll(() => deleted).toBe(true)
})

test('chat threads can be created and renamed', async ({ page }) => {
  const thread = {
    id: 'thread_8f2c',
    tenant_id: 't1',
    workspace_id: 'w1',
    agent_id: 'ops-copilot',
    title: 'checkout-api 502s',
    status: 'active',
    thread_type: 'chat',
    message_count: 0,
    last_message_at: NOW,
    knowledge_config_json: {},
    tool_config_json: {},
    metadata_json: {},
    created_at: NOW,
    updated_at: NOW,
  }

  let created: Record<string, unknown> | null = null
  let renamed: Record<string, unknown> | null = null

  await page.route('**/api/v1/threads?**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items: [thread], next_page_token: null, page_size: 100 }),
    }),
  )
  await page.route('**/api/v1/threads', (route) => {
    if (route.request().method() === 'POST') {
      created = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ ...thread, id: 'thread_new', title: 'incident review' }),
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items: [thread], next_page_token: null, page_size: 100 }),
    })
  })
  await page.route('**/api/v1/threads/thread_8f2c', (route) => {
    if (route.request().method() === 'PATCH') {
      renamed = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(thread) })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ thread, messages: [] }),
    })
  })

  await page.goto('/v2/chat', { waitUntil: 'domcontentloaded' })

  // Rename first: creating switches the selection to the new thread, whose
  // detail this test does not mock, so the header actions would fall away.
  await page.getByRole('button', { name: 'Rename' }).click()
  await page.locator('.console-modal input.input').first().fill('checkout-api incident')
  await page.locator('.console-modal').getByRole('button', { name: 'Save' }).click()
  await expect.poll(() => renamed).not.toBeNull()
  expect(renamed).toMatchObject({ title: 'checkout-api incident' })

  await page.getByRole('button', { name: 'New thread' }).click()
  await page.locator('.console-modal input.input').first().fill('incident review')
  await page.locator('.console-modal').getByRole('button', { name: 'Create' }).click()
  await expect.poll(() => created).not.toBeNull()
  expect(created).toMatchObject({ title: 'incident review' })
})
