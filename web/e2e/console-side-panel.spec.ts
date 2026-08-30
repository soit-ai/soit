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
  // Seeded only when absent: this script re-runs on every navigation, and
  // overwriting would undo anything the app itself stored — a workspace
  // switch, for one.
  await page.addInitScript(() => {
    if (!localStorage.getItem('token')) localStorage.setItem('token', 'e2e-token')
    if (!localStorage.getItem('workspace_id')) localStorage.setItem('workspace_id', 'workspace-1')
    if (!localStorage.getItem('soit-console-theme')) {
      localStorage.setItem('soit-console-theme', 'dark')
    }
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
  await json(page, '**/api/v1/me/views**', savedViews)
})

const savedViews = [
  {
    id: 'sv_failed',
    surface: 'runs',
    name: 'Failed only',
    query: 'status=failed',
    is_default: false,
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 'sv_audited',
    surface: 'runs',
    name: 'Has audit',
    query: 'audited=true',
    is_default: true,
    created_at: NOW,
    updated_at: NOW,
  },
]

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

  const attention = page.locator('.subnav .sub-note', { hasText: '2 awaiting approval' })
  await expect(attention).toBeVisible()
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

  // The pillar's own links are there, so the panel rendered.
  await expect(page.locator('.subnav .sl', { hasText: 'Approvals' })).toBeVisible()
  // The group survives on its fixture rows, but nothing claims a pending count.
  await expect(page.locator('.subnav .sub-note', { hasText: 'awaiting approval' })).toHaveCount(0)
})

test('side panel counts team and API keys from their real services', async ({ page }) => {
  await json(page, '**/api/v1/workspaces/workspace-1/members', [
    { user_id: 'u1', email: 'a@x.io', role: 'Owner', status: 'active' },
    { user_id: 'u2', email: 'b@x.io', role: 'Admin', status: 'active' },
    { user_id: 'u3', email: 'c@x.io', role: 'Dev', status: 'active' },
    { user_id: 'u4', email: 'd@x.io', role: 'Dev', status: 'active' },
  ])
  await json(page, '**/api/v1/api-keys**', {
    items: [{ id: 'k1' }, { id: 'k2' }, { id: 'k3' }],
    next_page_token: null,
    page_size: 100,
  })

  await page.goto('/settings/account', { waitUntil: 'domcontentloaded' })

  // Both have services, so they are read rather than filled from a fixture.
  await expect(page.locator('.subnav .sl', { hasText: 'Team' }).locator('.ct')).toHaveText('4')
  await expect(page.locator('.subnav .sl', { hasText: 'API keys' }).locator('.ct')).toHaveText('3')
})

test('the policies figure names the revision in force', async ({ page }) => {
  await json(page, '**/api/v1/security/policies/bundle**', {
    scope: 'workspace',
    scope_id: 'w_1',
    bundle_id: 'pb_abcdef0123456789',
    revision: 7,
    document: { egress_allowlist: [], egress_blocklist: [] },
    activated_at: '2026-08-29T13:00:00Z',
    activated_by: 'u_1',
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  const figure = (label: string) =>
    page.locator('.subnav .sl', { hasText: label }).locator('.ct')
  await expect(figure('Policies')).toHaveText('r7')
})

test('the policies figure falls back to the content identifier', async ({ page }) => {
  // A policy in force that matches no recorded revision still has an
  // identifier, and it is the one refusals are recorded against.
  await json(page, '**/api/v1/security/policies/bundle**', {
    scope: 'workspace',
    scope_id: 'w_1',
    bundle_id: 'pb_abcdef0123456789',
    revision: 0,
    document: { egress_allowlist: [], egress_blocklist: [] },
    activated_at: null,
    activated_by: null,
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  await expect(
    page.locator('.subnav .sl', { hasText: 'Policies' }).locator('.ct'),
  ).toHaveText('abcdef01')
})

test('the access figure counts the workspace grants the server returned', async ({ page }) => {
  await json(page, /\/api\/v1\/resource-grants/, [
    { id: 'g1', resource_type: 'agent', resource_id: 'a1', user_id: 'u1', actions: ['read'] },
    { id: 'g2', resource_type: 'workflow', resource_id: 'w1', user_id: 'u1', actions: ['write'] },
  ])

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  await expect(
    page.locator('.subnav .sl').filter({ hasText: /^Access/ }).locator('.ct'),
  ).toHaveText('2')
})

test('audit and run figures are counted by the server, not filled in', async ({ page }) => {
  await json(page, /\/api\/v1\/runs\/audits\?.*with_total=true/, {
    items: [],
    next_page_token: null,
    page_size: 1,
    total: 47,
  })
  await json(page, /\/api\/v1\/runs\?.*with_total=true/, {
    items: [],
    next_page_token: null,
    page_size: 1,
    total: 1284,
  })
  await json(page, /\/api\/v1\/runs\/steps\?.*with_total=true/, {
    items: [],
    next_page_token: null,
    page_size: 1,
    total: 41200,
  })

  // Anchored: the observe panel also carries a saved view named "Slow traces",
  // which a loose substring match would pick up alongside the nav row.
  const figure = (label: string) =>
    page.locator('.subnav .sl').filter({ hasText: new RegExp(`^${label}`) }).locator('.ct')

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })
  await expect(figure('Audit log')).toHaveText('47 · 24h')

  await page.goto('/observe/runs', { waitUntil: 'domcontentloaded' })
  await expect(figure('Runs')).toHaveText('1,284')
  await expect(figure('Traces')).toHaveText('41.2k spans')
})

test('a figure the server did not count is left blank, not zeroed', async ({ page }) => {
  // The count is optional in the payload. A missing one must read as "not
  // measured" rather than as a workspace with no audit history.
  await json(page, /\/api\/v1\/runs\/audits/, {
    items: [],
    next_page_token: null,
    page_size: 1,
  })

  await page.goto('/govern/approvals', { waitUntil: 'domcontentloaded' })

  const auditRow = page.locator('.subnav .sl', { hasText: 'Audit log' })
  await expect(auditRow).toBeVisible()
  await expect(auditRow.locator('.ct')).toHaveCount(0)
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
  // The rows come from the caller's own saved views, and the default one says
  // so rather than carrying an invented result count.
  const saved = page.locator('.subnav .sl', { hasText: 'Has audit' })
  await expect(saved).toHaveAttribute('href', '/observe/runs?audited=true')
  await expect(saved.locator('.ct')).toHaveText('default')
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

test('seats keeps a live numerator against the fixture cap', async ({ page }) => {
  // The only tile that mixes a measurement with a fixture. If a later change
  // swaps the whole value for the prototype's "4 / 25", the real member count
  // stops being reported and nobody notices — so assert the numerator moves.
  await json(page, '**/api/v1/workspaces/workspace-1/members', [
    { user_id: 'u1', email: 'a@x.io', role: 'Owner', status: 'active' },
    { user_id: 'u2', email: 'b@x.io', role: 'Admin', status: 'active' },
  ])
  await json(page, '**/api/v1/billing/credits/balance', {
    currency: 'USD',
    balance: '3600.00',
    granted_total: '4212.40',
    consumed_total: '612.40',
    updated_at: NOW,
  })
  await json(page, '**/api/v1/billing/credits/entries**', {
    items: [],
    next_page_token: null,
    page_size: 20,
  })

  await page.goto('/settings/billing', { waitUntil: 'domcontentloaded' })

  // Two real members, not the prototype's four; the cap stays the fixture.
  await expect(page.locator('.tile', { hasText: 'Seats' })).toContainText('2 / 25')
})

test('head sub-line still identifies the workspace when the name cannot load', async ({
  page,
}) => {
  // Both lookups failing left the line empty, so the panel head said only
  // which pillar was open -- not which workspace the operator was acting on.
  await page.route('**/api/v1/workspaces/**', (route) => route.abort())
  await page.route('**/api/v1/diagnostics', (route) => route.abort())

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  // The id is already in hand; the environment stays off rather than guessed.
  await expect(page.locator('.subnav-head .mono')).toHaveText('workspace-1')
})

test('head sub-line prefers the workspace name over its id', async ({ page }) => {
  await json(page, '**/api/v1/diagnostics', healthy)

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav-head .mono')).toHaveText('acme-robotics · production')
})

test('the head switches workspace and drops everything read under the old one', async ({
  page,
}) => {
  await json(page, '**/api/v1/me/workspaces', [
    { id: 'workspace-1', name: 'acme-robotics', role: 'Owner', created_at: NOW },
    { id: 'workspace-2', name: 'acme-labs', role: 'Dev', created_at: NOW },
  ])

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.locator('.ws-switch-trigger').click()

  const menu = page.locator('.ws-switch-menu')
  await expect(menu).toBeVisible()
  // The one you are in is marked, not hidden: a switcher that omits the
  // current workspace makes you guess where you are.
  await expect(menu.getByRole('option', { name: /acme-robotics/ })).toHaveAttribute(
    'aria-selected',
    'true',
  )

  await menu.getByRole('option', { name: /acme-labs/ }).click()

  // A full reload, so nothing read under the old scope survives in memory.
  await expect.poll(() => page.evaluate(() => localStorage.getItem('workspace_id'))).toBe(
    'workspace-2',
  )
  await expect(page).toHaveURL(/\/$|\/overview/)

  // And every request after the switch is scoped to the workspace chosen. This
  // is the guarantee the archived builder test was written to protect: the old
  // workspace's inventory must not answer the new one's screens.
  const scopes: string[] = []
  page.on('request', (request) => {
    if (request.url().includes('/api/v1/')) {
      scopes.push(request.headers()['x-workspace-id'] || 'missing')
    }
  })
  await page.goto('/build/workflows', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => scopes.length).toBeGreaterThan(0)
  expect(scopes.every((scope) => scope === 'workspace-2')).toBe(true)
})

test('switching to the workspace already open changes nothing', async ({ page }) => {
  await json(page, '**/api/v1/me/workspaces', [
    { id: 'workspace-1', name: 'acme-robotics', role: 'Owner', created_at: NOW },
  ])

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.locator('.ws-switch-trigger').click()
  await page.locator('.ws-switch-menu').getByRole('option', { name: /acme-robotics/ }).click()

  await expect(page).toHaveURL(/\/build\/agents/)
  await expect(page.locator('.ws-switch-menu')).toHaveCount(0)
})

test('the overview panel pins what the caller pinned, not a fixture', async ({ page }) => {
  await json(page, '**/api/v1/me/pins**', [
    {
      id: 'pin_1',
      object_type: 'agent',
      object_id: 'agt_support',
      label: 'support-triage',
      created_at: NOW,
    },
    {
      id: 'pin_2',
      object_type: 'knowledge',
      object_id: 'knw_docs',
      label: 'product-docs',
      created_at: NOW,
    },
  ])

  await page.goto('/', { waitUntil: 'domcontentloaded' })

  const pinned = page.locator('.subnav .sub-mini')
  await expect(pinned.filter({ hasText: 'support-triage' })).toHaveAttribute(
    'href',
    '/build/agents/agt_support',
  )
  await expect(pinned.filter({ hasText: 'product-docs' })).toHaveAttribute(
    'href',
    '/build/knowledge/knw_docs',
  )
})

test('a caller with nothing pinned gets no Pinned group at all', async ({ page }) => {
  // An empty group with a caption would read as "your pins failed to load".
  await json(page, '**/api/v1/me/pins**', [])

  await page.goto('/', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav .sub-cap', { hasText: 'Pinned' })).toHaveCount(0)
})
