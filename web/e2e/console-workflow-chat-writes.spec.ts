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

  await page.goto('/build/workflows', { waitUntil: 'domcontentloaded' })
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

  await page.goto('/build/workflows', { waitUntil: 'domcontentloaded' })
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

  await page.goto('/chat', { waitUntil: 'domcontentloaded' })

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

test('workflow run controls act on the run the status permits', async ({ page }) => {
  const calls: string[] = []
  const runs = (status: string) => ({
    items: [
      {
        id: 'run_wf_1',
        trace_id: 't1',
        attempt_no: 1,
        mode: 'workflow',
        subject_kind: 'workflow',
        subject_id: 'docs-nightly-sync',
        status,
        started_at: NOW,
        ended_at: NOW,
        duration_ms: 4200,
        created_at: NOW,
        updated_at: NOW,
        observe_summary: { step_count: 5, tool_call_count: 1, child_run_count: 0, response_event_count: 6, citation_count: 0, audit_count: 2, cost_entry_count: 1 },
      },
    ],
    next_page_token: null,
    page_size: 20,
  })

  await json(page, '**/api/v1/workflows/docs-nightly-sync', {
    id: 'docs-nightly-sync', name: 'docs-nightly-sync', status: 'running', visibility: 'workspace',
    current_version_id: 'wfv_9', published_version_id: 'wfv_9', metadata_json: {}, created_at: NOW, updated_at: NOW,
  })
  await json(page, '**/api/v1/workflows/docs-nightly-sync/version/current', { id: 'wfv_9', workflow_id: 'docs-nightly-sync', graph_json: { graph: { nodes: [], edges: [] } }, created_at: NOW })
  await json(page, '**/api/v1/workflows/docs-nightly-sync/versions**', { items: [], next_page_token: null, page_size: 20 })
  await json(page, '**/api/v1/workflows/capabilities', { node_types: [], compatibility_node_types: [] })
  await json(page, '**/api/v1/runs?**', runs('running'))

  for (const verb of ['pause', 'resume', 'cancel', 'retry', 'replay']) {
    await page.route(`**/api/v1/workflows/docs-nightly-sync/runs/run_wf_1/${verb}`, (route) => {
      calls.push(verb)
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok({ status: 'ok' }) })
    })
  }

  await page.goto('/build/workflows/docs-nightly-sync', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /Monitor/ }).click()

  // A running run offers pause and cancel — not retry or replay.
  await expect(page.getByRole('button', { name: 'Pause' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Replay' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Pause' }).click()
  await expect.poll(() => calls).toContain('pause')

  // Cancel is destructive, so it confirms first.
  await page.getByRole('button', { name: 'Cancel', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Cancel run' })).toBeVisible()
  expect(calls).not.toContain('cancel')
  // The modal has both a dismiss "Cancel" and the confirm "Cancel run" action;
  // the confirm is the primary one.
  await page.locator('.console-modal .btn.primary').click()
  await expect.poll(() => calls).toContain('cancel')
})
