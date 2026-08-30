import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string | RegExp, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const emptyWorkbench = (summaryKey: string) => ({
  summary: { [summaryKey]: 0, updated_at: NOW },
  tabs: { all: 0 },
  items: [],
  next_page_token: null,
  page_size: 50,
})

const healthy = {
  generated_at: NOW,
  version: '1.0.3',
  environment: 'production',
  overall_status: 'healthy',
  dependencies: [],
  process: { uptime_seconds: 900, rss_bytes: 1, thread_count: 8 },
  workspace: {},
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await json(page, '**/api/v1/workflows/workbench**', emptyWorkbench('total_workflows'))
  await json(page, '**/api/v1/knowledge/workbench**', emptyWorkbench('total_knowledge_bases'))
  await json(page, '**/api/v1/tasks/workbench**', emptyWorkbench('total_tasks'))
  await json(page, '**/api/v1/workspaces/workspace-1', {
    id: 'workspace-1',
    tenant_id: 'tenant-1',
    name: 'acme-robotics',
    created_at: NOW,
  })
})

test('side panel names the workspace and environment it is pointed at', async ({ page }) => {
  await json(page, '**/api/v1/diagnostics', healthy)

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  // Which workspace and which environment — not a restatement of the pillar.
  await expect(page.locator('.subnav-head .mono')).toHaveText('acme-robotics · production')
})

test('side panel draws the prototype glyph on every primary link', async ({ page }) => {
  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  const links = page.locator('.subnav a.sl')
  await expect(links).toHaveCount(5)
  // Each of the five carries its own 14px icon, as the prototype does.
  await expect(page.locator('.subnav a.sl > svg')).toHaveCount(5)
})

test('side panel reports health and version from the diagnostics snapshot', async ({ page }) => {
  await json(page, '**/api/v1/diagnostics', healthy)

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav-foot')).toContainText('all systems normal · v1.0.3')
  await expect(page.locator('.subnav-foot')).toContainText('⌘K to jump')
})

test('side panel says health is unavailable rather than claiming all is normal', async ({
  page,
}) => {
  // The prototype's foot is a flat "all systems normal". Rendering that with no
  // snapshot behind it would assert something the console has not checked.
  await page.route('**/api/v1/diagnostics', (route) => route.abort())

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav-foot')).toContainText('health unavailable')
  await expect(page.locator('.subnav-foot')).not.toContainText('all systems normal')
})

test('side panel reports a degraded snapshot as degraded', async ({ page }) => {
  await json(page, '**/api/v1/diagnostics', { ...healthy, overall_status: 'degraded' })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav-foot')).toContainText('degraded · v1.0.3')
})

test('observe panel lists a running run with the live indicator', async ({ page }) => {
  await json(page, /\/api\/v1\/runs\?.*status=running/, {
    items: [
      {
        id: 'run_01J9KD84QF',
        attempt_no: 1,
        mode: 'agent',
        subject_id: 'support-triage',
        status: 'running',
        started_at: NOW,
        created_at: NOW,
      },
    ],
    next_page_token: null,
    page_size: 3,
  })

  await page.goto('/observe/runs', { waitUntil: 'domcontentloaded' })

  const live = page.locator('.subnav .sub-mini', { hasText: 'run_01J9KD84QF' })
  await expect(live).toBeVisible()
  await expect(live).toContainText('support-triage')
  // The in-flight row pulses instead of carrying a static figure.
  await expect(page.locator('.subnav .sub-note .livedot')).toBeVisible()
})

test('observe panel drops the Live caption when nothing is running', async ({ page }) => {
  await json(page, /\/api\/v1\/runs\?.*status=running/, {
    items: [],
    next_page_token: null,
    page_size: 3,
  })

  await page.goto('/observe/runs', { waitUntil: 'domcontentloaded' })

  // Saved views still render, so the panel loaded; only the empty group is gone.
  await expect(page.locator('.subnav .sub-cap', { hasText: 'Saved views' })).toBeVisible()
  await expect(page.locator('.subnav .sub-cap', { hasText: 'Live' })).toHaveCount(0)
})

test('chat panel groups threads by the agent that owns them', async ({ page }) => {
  await json(page, '**/api/v1/threads**', {
    items: [
      { id: 't1', tenant_id: 'x', workspace_id: 'workspace-1', agent_id: 'ops-copilot', title: 'checkout-api 502s', status: 'active', thread_type: 'chat', updated_at: NOW, created_at: NOW },
      { id: 't2', tenant_id: 'x', workspace_id: 'workspace-1', agent_id: 'ops-copilot', title: 'staging deploy window', status: 'active', thread_type: 'chat', updated_at: NOW, created_at: NOW },
      { id: 't3', tenant_id: 'x', workspace_id: 'workspace-1', agent_id: 'support-triage', title: 'quota report', status: 'active', thread_type: 'chat', updated_at: NOW, created_at: NOW },
    ],
    next_page_token: null,
    page_size: 100,
  })

  await page.goto('/chat', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav .sl', { hasText: 'All threads' }).locator('.ct')).toHaveText('3')
  // Two owners, ordered by how many threads each holds.
  const byAgent = page.locator('.subnav .idm')
  await expect(byAgent).toHaveCount(2)
  await expect(byAgent.first()).toContainText('ops-copilot')
  await expect(
    page.locator('.subnav .sl', { hasText: 'ops-copilot' }).locator('.ct'),
  ).toHaveText('2')
})

test('govern panel raises pending approvals in the attention group', async ({ page }) => {
  await json(page, '**/api/v1/observe/approvals**', {
    items: [{ id: 'ap_1' }, { id: 'ap_2' }],
    next_page_token: null,
    page_size: 100,
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  const attention = page.locator('.subnav .sub-note', { hasText: 'Approvals pending' })
  await expect(attention.locator('.ct')).toHaveText('2')
  await attention.click()
  await expect(page).toHaveURL(/\/govern\/approvals/)
})

test('govern panel omits the attention group when nothing is pending', async ({ page }) => {
  // A "Needs attention" caption over an empty list reads as a failed fetch; a
  // zero-count row reads as a measurement. Neither is true, so neither renders.
  await json(page, '**/api/v1/observe/approvals**', {
    items: [],
    next_page_token: null,
    page_size: 100,
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  // The pillar's own links are there, so the panel rendered; only the group is gone.
  await expect(page.locator('.subnav .sl', { hasText: 'Approvals' })).toBeVisible()
  await expect(page.locator('.subnav .sub-cap', { hasText: 'Needs attention' })).toHaveCount(0)
})

test('saved views do not claim to be the page they filter', async ({ page }) => {
  await json(page, /\/api\/v1\/runs\?.*status=running/, {
    items: [],
    next_page_token: null,
    page_size: 3,
  })

  await page.goto('/observe/runs', { waitUntil: 'domcontentloaded' })

  // They all point at /observe/runs with a query, which NavLink matches on
  // pathname alone — left to its default every one of them lights up at once.
  await expect(page.locator('.subnav .sl.active')).toHaveCount(1)
  await expect(page.locator('.subnav .sl.active')).toHaveText(/Runs/)
})

test('chat panel addresses a thread by the route that can open it', async ({ page }) => {
  await json(page, '**/api/v1/threads**', {
    items: [
      { id: 'thread-9', tenant_id: 'x', workspace_id: 'workspace-1', agent_id: 'ops-copilot', title: 'checkout-api 502s', status: 'active', thread_type: 'chat', updated_at: NOW, created_at: NOW },
    ],
    next_page_token: null,
    page_size: 100,
  })

  await page.goto('/chat', { waitUntil: 'domcontentloaded' })

  // /chat/:agentId?/:threadId? — a query string would land on the bare route.
  await page.locator('.subnav .sub-mini', { hasText: 'checkout-api 502s' }).click()
  await expect(page).toHaveURL(/\/chat\/ops-copilot\/thread-9$/)
})

test('caption spacing follows the prototype after the first group', async ({ page }) => {
  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  const padding = (index: number) =>
    page
      .locator('.subnav .sub-cap')
      .nth(index)
      .evaluate((node) => getComputedStyle(node).paddingTop)

  // `.sub-panel .sub-cap:first-child` tightens only the opening caption. Wrap
  // each group in an element and every caption becomes a first-child, which
  // silently collapses the spacing down the whole panel.
  expect(await padding(0)).toBe('2px')
  expect(await padding(1)).toBe('12px')
})
