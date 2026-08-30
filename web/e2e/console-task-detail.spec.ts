import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const task = {
  id: 'tsk_1',
  tenant_id: 't1',
  workspace_id: 'w1',
  agent_id: 'support-triage',
  thread_id: null,
  run_id: 'run_1',
  task_type: 'agent',
  status: 'waiting_approval',
  input_json: {},
  output_json: {},
  progress_json: {},
  error_code: null,
  error_message: null,
  started_at: NOW,
  finished_at: null,
  created_by: 'u_1',
  updated_by: null,
  created_at: NOW,
  updated_at: NOW,
}

const approval = {
  id: 'apr_1',
  run_id: 'run_1',
  task_id: 'tsk_1',
  thread_id: null,
  agent_id: 'support-triage',
  title: 'Approve tool call: plugin:pagerduty.page',
  policy_ref: 'tool_spec:plugin:pagerduty.page',
  status: 'pending',
  details_json: {
    tool_call_id: 'call_1',
    tool_ref: 'plugin:pagerduty.page',
    parameters: { service: 'checkout' },
    risk_level: 'high',
  },
  requested_by: 'u_1',
  resolved_by: null,
  resolution_note: null,
  resolved_at: null,
  created_at: NOW,
  updated_at: NOW,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await json(page, '**/api/v1/tasks/tsk_1', {
    task,
    checkpoints: [],
    events: [],
    available_actions: ['resume', 'cancel'],
  })
})

test('a task waiting on a tool call shows the approval it is waiting for', async ({
  page,
}) => {
  await json(page, '**/api/v1/observe/approvals?**', {
    items: [approval],
    next_page_token: null,
    page_size: 10,
  })

  await page.goto('/execute/tasks/tsk_1', { waitUntil: 'domcontentloaded' })

  const panel = page.locator('.panel').filter({ hasText: 'Pending approval' })
  await expect(panel).toContainText('Approve tool call: plugin:pagerduty.page')
  // The approver has to see what they are approving, not only the tool name.
  await expect(panel).toContainText('checkout')
})

test('approving from the task records the decision', async ({ page }) => {
  let resolved: Record<string, unknown> | null = null

  await json(page, '**/api/v1/observe/approvals?**', {
    items: [approval],
    next_page_token: null,
    page_size: 10,
  })
  await page.route('**/api/v1/observe/approvals/apr_1/resolve', (route) => {
    resolved = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...approval, status: 'approved' }),
    })
  })

  await page.goto('/execute/tasks/tsk_1', { waitUntil: 'domcontentloaded' })
  await page
    .locator('.panel')
    .filter({ hasText: 'Pending approval' })
    .getByRole('button', { name: 'Approve' })
    .click()

  await expect.poll(() => resolved).not.toBeNull()
  expect(resolved).toMatchObject({ status: 'approved' })
})

test('a task with nothing pending says so rather than inventing a request', async ({
  page,
}) => {
  await json(page, '**/api/v1/observe/approvals?**', {
    items: [],
    next_page_token: null,
    page_size: 10,
  })

  await page.goto('/execute/tasks/tsk_1', { waitUntil: 'domcontentloaded' })

  const panel = page.locator('.panel').filter({ hasText: 'Pending approval' })
  await expect(panel).not.toContainText('Approve tool call')
})
