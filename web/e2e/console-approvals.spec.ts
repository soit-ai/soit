import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const CREATED = '2026-08-29T13:00:00Z'
const inMinutes = (minutes: number) => new Date(Date.now() + minutes * 60_000).toISOString()

const base = {
  run_id: 'run_1',
  task_id: null,
  thread_id: null,
  agent_id: 'support-triage',
  policy_ref: 'tool_spec:plugin:pagerduty.page',
  details_json: { tool_ref: 'plugin:pagerduty.page', parameters: { service: 'checkout' } },
  requested_by: 'u_alice',
  resolved_by: null,
  resolution_note: null,
  resolved_at: null,
  created_at: CREATED,
  updated_at: CREATED,
}

const mine = {
  ...base,
  id: 'apr_mine',
  title: 'Page the checkout on-call',
  status: 'pending',
  assignee_user_ids: ['user-1'],
  assignee_roles: [],
  expires_at: inMinutes(30),
  can_decide: true,
  can_cancel: true,
  assigned_to_me: true,
}

const someoneElses = {
  ...base,
  id: 'apr_other',
  title: 'Refund the order',
  status: 'pending',
  assignee_user_ids: [],
  assignee_roles: ['Admin'],
  expires_at: null,
  can_decide: false,
  can_cancel: false,
  assigned_to_me: false,
}

const expired = {
  ...base,
  id: 'apr_expired',
  title: 'Rotate the key',
  status: 'expired',
  resolved_by: 'system',
  resolution_note: 'No decision before the deadline',
  resolved_at: CREATED,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await page.route('**/api/v1/observe/approvals?**', (route) => {
    const status = new URL(route.request().url()).searchParams.get('status')
    const items = status === 'pending' ? [mine, someoneElses] : status === 'expired' ? [expired] : []
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items, next_page_token: null, page_size: 50 }),
    })
  })
  await json(page, '**/api/v1/workspaces/workspace-1/members', [
    { user_id: 'user-1', email: 'me@x.io', name: 'Test User', role: 'Owner', status: 'active' },
    { user_id: 'u_bob', email: 'bob@x.io', name: 'Bob', role: 'Dev', status: 'active' },
    { user_id: 'u_vera', email: 'vera@x.io', name: 'Vera', role: 'Viewer', status: 'active' },
  ])
  await json(page, '**/api/v1/observe/approvals/apr_mine/decisions', [])
  await json(page, '**/api/v1/observe/approvals/apr_other/decisions', [
    {
      id: 'apd_1',
      approval_id: 'apr_other',
      action: 'delegated',
      actor_id: 'u_bob',
      actor_role: 'Dev',
      note: 'Out this week',
      assignees_before_json: { user_ids: ['u_bob'], roles: [] },
      assignees_after_json: { user_ids: [], roles: ['Admin'] },
      created_at: CREATED,
    },
  ])
})

test('the pending queue says who decides each request and narrows to mine', async ({ page }) => {
  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  const rows = page.locator('tbody tr')
  const mineRow = rows.filter({ hasText: 'Page the checkout on-call' })
  const otherRow = rows.filter({ hasText: 'Refund the order' })
  await expect(mineRow).toContainText('Test User · you')
  await expect(mineRow).toContainText('Due in 30m')
  await expect(mineRow.getByRole('button', { name: 'Approve' })).toBeVisible()
  // Not an approver of this one: the queue does not offer a decision.
  await expect(otherRow).toContainText('Admin')
  await expect(otherRow.getByRole('button', { name: 'Approve' })).toHaveCount(0)

  await page.getByRole('button', { name: /Assigned to me/ }).click()
  await expect(rows.filter({ hasText: 'Refund the order' })).toHaveCount(0)
  await expect(rows.filter({ hasText: 'Page the checkout on-call' })).toHaveCount(1)
})

test('an approver delegates a request to a member who can decide it', async ({ page }) => {
  let delegated: Record<string, unknown> | null = null
  await page.route('**/api/v1/observe/approvals/apr_mine/delegate', (route) => {
    delegated = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...mine, assignee_user_ids: ['u_bob'], can_decide: false, assigned_to_me: false }),
    })
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })
  await page.locator('tbody tr').filter({ hasText: 'Page the checkout on-call' }).getByRole('button', { name: 'Details' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('plugin:pagerduty.page')
  const member = dialog.getByLabel('Delegate to')
  // A Viewer cannot decide, so cannot be handed the request.
  await expect(member.locator('option', { hasText: 'Vera' })).toHaveCount(0)
  await member.selectOption('u_bob')
  await dialog.getByLabel('Note').fill('Out this week')
  await dialog.getByRole('button', { name: 'Delegate' }).click()

  await expect.poll(() => delegated).not.toBeNull()
  expect(delegated).toEqual({ user_id: 'u_bob', note: 'Out this week' })
})

test('a request shows its history and offers nothing to someone who may not act', async ({ page }) => {
  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })
  await page.locator('tbody tr').filter({ hasText: 'Refund the order' }).getByRole('button', { name: 'Details' }).click()

  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText('Bob (Dev) delegated to')
  await expect(dialog).toContainText('Out this week')
  await expect(dialog.getByLabel('Delegate to')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Cancel request' })).toHaveCount(0)
})

test('an expired request is shown as expired among the decided', async ({ page }) => {
  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Decided/ }).click()

  const row = page.locator('tbody tr').filter({ hasText: 'Rotate the key' })
  await expect(row).toContainText('EXPIRED')
  await expect(row).toContainText('No decision before the deadline')
})

test('a requester who may not approve their own request can still reject it', async ({ page }) => {
  const own = { ...mine, id: 'apr_own', title: 'My own refund', can_approve: false }
  await page.route('**/api/v1/observe/approvals?**', (route) => {
    const status = new URL(route.request().url()).searchParams.get('status')
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items: status === 'pending' ? [own] : [], next_page_token: null, page_size: 50 }),
    })
  })
  await json(page, '**/api/v1/observe/approvals/apr_own/decisions', [])

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })
  const row = page.locator('tbody tr').filter({ hasText: 'My own refund' })
  await expect(row.getByRole('button', { name: 'Reject' })).toBeVisible()
  await expect(row.getByRole('button', { name: 'Approve' })).toHaveCount(0)

  await row.getByRole('button', { name: 'Details' }).click()
  await expect(page.getByRole('dialog')).toContainText('needs another approver to approve it')
})
