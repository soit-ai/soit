import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string | RegExp, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const agentWorkbench = {
  summary: {
    total_agents: 2, configured_agents: 2, running_agents: 1, today_calls: 0,
    avg_latency_ms: null, success_rate: null, pending_exceptions: 0, updated_at: NOW,
  },
  tabs: { all: 2, high_calls: 0, low_success: 0, long_latency: 0, unconfigured: 0 },
  items: [
    { id: 'support-triage', name: 'support-triage', status: 'running', capabilities: [], today_calls: 0, recent_exception_count: 0, owner: 'Jude', action_enabled: true, updated_at: NOW },
    { id: 'ops-copilot', name: 'ops-copilot', status: 'running', capabilities: [], today_calls: 0, recent_exception_count: 0, owner: 'Wei', action_enabled: true, updated_at: NOW },
  ],
  next_page_token: null, page_size: 50,
}

const emptyWorkbench = (summaryKey: string) => ({
  summary: { [summaryKey]: 0, updated_at: NOW },
  tabs: { all: 0 },
  items: [],
  next_page_token: null,
  page_size: 50,
})

const members = [
  { user_id: 'u_1', email: 'zzpd106@gmail.com', name: 'Jude', role: 'Owner', status: 'active' },
  { user_id: 'u_2', email: 'wei@acme.io', name: 'Wei', role: 'Admin', status: 'active' },
  { user_id: 'u_3', email: 'ming@acme.io', name: 'Ming', role: 'Dev', status: 'active' },
]

/** One workspace-scoped read returns every grant, whatever it protects. */
const workspaceGrants = [
  { id: 'g_1', tenant_id: 't1', workspace_id: 'workspace-1', resource_type: 'agent', resource_id: 'support-triage', user_id: 'u_3', actions: ['read', 'run'], created_by: 'u_1', created_at: NOW, updated_at: NOW },
  { id: 'g_2', tenant_id: 't1', workspace_id: 'workspace-1', resource_type: 'agent', resource_id: 'support-triage', user_id: 'u_2', actions: ['read', 'run', 'update'], created_by: 'u_1', created_at: NOW, updated_at: NOW },
]

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await json(page, '**/api/v1/agents/workbench**', agentWorkbench)
  await json(page, '**/api/v1/workflows/workbench**', emptyWorkbench('total_workflows'))
  await json(page, '**/api/v1/knowledge/workbench**', emptyWorkbench('total_knowledge_bases'))
  await json(page, '**/api/v1/workspaces/*/members', members)
  await json(page, '**/api/v1/resource-grants?**', workspaceGrants)
})

test('access lists grants joined to the resource they protect', async ({ page }) => {
  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Access' })).toBeVisible()

  // The API returns a grant without the resource's name; the page joins them.
  const rows = page.locator('.panel tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('support-triage')
  // Members resolve to names rather than raw ids.
  await expect(page.getByText('Ming', { exact: true })).toBeVisible()
  await expect(page.getByText('Wei', { exact: true })).toBeVisible()
})

test('access counts write-capable grants separately from read-only ones', async ({ page }) => {
  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })

  // Only the grant carrying `update` is write-capable.
  await page.locator('.fchip', { hasText: 'Write-capable' }).click()
  const rows = page.locator('.panel tbody tr')
  await expect(rows).toHaveCount(1)
  await expect(rows.first()).toContainText('Wei')
})

test('access groups the same grants by the resource they protect', async ({ page }) => {
  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })

  await page.getByRole('tab', { name: /By resource/ }).click()
  const rows = page.locator('.panel tbody tr')
  await expect(rows).toHaveCount(1)
  // Two people on one resource, and the strongest action they hold between them.
  await expect(rows.first()).toContainText('support-triage')
  await expect(rows.first()).toContainText('2')
  await expect(rows.first()).toContainText('update')
})

test('granting access posts the resource, person and actions', async ({ page }) => {
  let posted: Record<string, unknown> | null = null
  await page.route('**/api/v1/resource-grants', (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    posted = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok({ id: 'g_new' }) })
  })

  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Grant access' }).click()

  await expect(page.getByRole('heading', { name: 'Grant access' })).toBeVisible()
  // `run` is the second checkbox; it joins the default `read`.
  await page.locator('.console-modal input[type=checkbox]').nth(1).check()
  await page.locator('.console-modal .btn.primary').click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toMatchObject({ resource_type: 'agent', resource_id: 'support-triage' })
  expect((posted as unknown as Record<string, string[]>).actions).toContain('read')
})

test('revoking access confirms first and names who loses what', async ({ page }) => {
  let deleted: string | null = null
  await page.route('**/api/v1/resource-grants/**', (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    deleted = new URL(route.request().url()).pathname
    return route.fulfill({ status: 204, body: '' })
  })

  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Revoke' }).first().click()

  await expect(page.getByRole('heading', { name: 'Revoke access' })).toBeVisible()
  await expect(page.locator('.console-modal')).toContainText('support-triage')
  expect(deleted).toBeNull()

  await page.locator('.console-modal .btn.primary').click()
  await expect.poll(() => deleted).toContain('/resource-grants/agent/support-triage/')
})

test('access says grant history has no source rather than inventing one', async ({ page }) => {
  await page.goto('/govern/access', { waitUntil: 'domcontentloaded' })

  await page.getByRole('tab', { name: /Changes/ }).click()
  await expect(
    page.getByText('Grant changes are not recorded as their own audit object yet.'),
  ).toBeVisible()
})
