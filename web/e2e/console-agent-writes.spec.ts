import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const agentWorkbench = {
  summary: {
    total_agents: 1,
    configured_agents: 1,
    running_agents: 1,
    today_calls: 412,
    avg_latency_ms: 1800,
    success_rate: 0.98,
    pending_exceptions: 0,
    updated_at: NOW,
  },
  tabs: { all: 1, high_calls: 0, low_success: 0, long_latency: 0, unconfigured: 0 },
  items: [
    {
      id: 'ag_1',
      name: 'support-triage',
      description: 'Ticket triage',
      status: 'running',
      capabilities: [{ type: 'tool', label: 'helpdesk' }],
      today_calls: 412,
      avg_latency_ms: 1800,
      success_rate: 0.98,
      recent_exception_count: 0,
      owner: 'Jude',
      last_run_at: NOW,
      action_enabled: true,
      updated_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 50,
}

const agent = {
  id: 'ag_1',
  tenant_id: 't1',
  workspace_id: 'w1',
  name: 'support-triage',
  description: 'Ticket triage',
  status: 'active',
  visibility: 'private',
  icon_url: null,
  category: null,
  is_public: false,
  featured: false,
  downloads_count: 0,
  rating: null,
  reviews_count: 0,
  published_at: NOW,
  tags: null,
  current_version_id: 'ver_2',
  published_version_id: 'ver_1',
  created_by: 'Jude',
  updated_by: 'Jude',
  created_at: NOW,
  updated_at: NOW,
  deleted_at: null,
}

/**
 * `ver_2` is the draft the Build tab edits. Its spec carries limits and
 * policies the console has no control for (max_iterations, verify, memory,
 * workflow_refs) so the save can be checked for carrying them through.
 */
const draftSpec = {
  runtime: 'agent_runtime_v1',
  planner: null,
  system_prompt: 'Be terse.',
  temperature: 0.2,
  bindings: {
    model_ref: 'claude-sonnet-5',
    knowledge_refs: [],
    tool_refs: ['tool:helpdesk'],
    workflow_refs: ['wf:escalate'],
    skill_refs: [],
  },
  memory: { enabled: true, type: 'planner_only', policy: { top_k: 5 } },
  limits: {
    max_iterations: 8,
    max_tool_calls: 20,
    max_llm_calls: null,
    max_failures: 2,
    timeout_ms: 30000,
    max_tokens: 4096,
    budget: 2.5,
  },
  policies: { verify: true, failure_strategy: 'respond', cost_currency: 'USD' },
}

const versions = {
  items: [
    {
      id: 'ver_1',
      agent_id: 'ag_1',
      version: 1,
      status: 'published',
      spec_schema: 'agent_spec/v1',
      spec_json: { ...draftSpec, system_prompt: 'Be helpful.' },
      checksum: null,
      created_by: 'Jude',
      created_at: NOW,
    },
    {
      id: 'ver_2',
      agent_id: 'ag_1',
      version: 2,
      status: 'draft',
      spec_schema: 'agent_spec/v1',
      spec_json: draftSpec,
      checksum: null,
      created_by: 'Jude',
      created_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 20,
}

const bindings = [
  {
    id: 'bind_1',
    agent_id: 'ag_1',
    agent_version_id: 'ver_2',
    binding_type: 'tool',
    target_id: null,
    target_key: 'tool:helpdesk',
    target_label: 'helpdesk',
    config_json: {},
    sort_order: 0,
    created_at: NOW,
    updated_at: NOW,
  },
]

const capabilities = {
  items: [
    { ref: 'tool:helpdesk', kind: 'tool', name: 'helpdesk', source_kind: 'native', source_id: null, source_version: null, metadata_json: null },
    { ref: 'tool:pager', kind: 'tool', name: 'pager', source_kind: 'native', source_id: null, source_version: null, metadata_json: null },
    { ref: 'skill:triage', kind: 'skill', name: 'triage', source_kind: 'native', source_id: null, source_version: '1.2.0', metadata_json: null },
    { ref: 'kb:runbooks', kind: 'knowledge', name: 'runbooks', source_kind: 'native', source_id: null, source_version: null, metadata_json: { doc_count: 12 } },
  ],
  next_page_token: null,
  page_size: 200,
}

const emptyPage = { items: [], next_page_token: null, page_size: 20 }

/** Everything the detail page reads, so only the writes are under test. */
async function mockAgentReads(page: Page) {
  await json(page, '**/api/v1/runs**', emptyPage)
  await json(page, '**/api/v1/agents/workbench**', agentWorkbench)
  await json(page, '**/api/v1/agents/workbench/items**', {
    items: agentWorkbench.items,
    next_page_token: null,
    page_size: 100,
  })
  await json(page, '**/api/v1/agents/capabilities**', capabilities)
  await json(page, '**/api/v1/agents/ag_1/versions**', versions)
  await json(page, '**/api/v1/agents/ag_1/releases**', emptyPage)
  await json(page, '**/api/v1/agents/ag_1/bindings**', bindings)
  await json(page, '**/api/v1/agents/ag_1', agent)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await mockAgentReads(page)
})

test('the New agent button creates the agent and opens its detail page', async ({ page }) => {
  let posted: Record<string, unknown> | null = null
  await page.route('**/api/v1/agents', async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(emptyPage) })
    }
    posted = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...agent, id: 'ag_new', name: 'refund-checker' }),
    })
  })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New agent' }).click()

  await expect(page.getByRole('heading', { name: 'New agent' })).toBeVisible()
  // Create stays disabled until the agent has a name.
  const create = page.getByRole('button', { name: 'Create' })
  await expect(create).toBeDisabled()

  const inputs = page.locator('.console-modal input.input')
  await inputs.first().fill('refund-checker')
  await inputs.nth(1).fill('Checks refund eligibility')
  await page.locator('.console-modal select.input').selectOption('workspace')
  await expect(create).toBeEnabled()
  await create.click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toMatchObject({
    name: 'refund-checker',
    description: 'Checks refund eligibility',
    visibility: 'workspace',
  })
  await expect(page).toHaveURL(/\/build\/agents\/ag_new/)
})

test('a blank description is omitted from the create payload', async ({ page }) => {
  let posted: Record<string, unknown> | null = null
  await page.route('**/api/v1/agents', async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(emptyPage) })
    }
    posted = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...agent, id: 'ag_new' }),
    })
  })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New agent' }).click()
  await page.locator('.console-modal input.input').first().fill('bare-agent')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => posted).not.toBeNull()
  expect(posted).toMatchObject({ name: 'bare-agent', visibility: 'private' })
  expect(posted && 'description' in posted).toBe(false)
})

test('Save draft writes the agent record and a new version from the edited spec', async ({ page }) => {
  let put: Record<string, unknown> | null = null
  let versionPost: Record<string, unknown> | null = null

  await page.route('**/api/v1/agents/ag_1/versions**', (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(versions) })
    }
    versionPost = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...versions.items[1], id: 'ver_3', version: 3 }),
    })
  })
  await page.route('**/api/v1/agents/ag_1', (route) => {
    if (route.request().method() === 'PUT') {
      put = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })

  // The Build tab is seeded from the draft version, not from a fixture.
  const definition = page.locator('.rdgrid .stack').first()
  await expect(definition.locator('textarea.input')).toHaveValue('Be terse.')

  await definition.locator('input.input').first().fill('support-triage-v2')
  await definition.locator('textarea.input').fill('Be terse and cite sources.')
  // Grant a second tool; the first stays checked from the live bindings.
  await page.locator('.checks label', { hasText: 'pager' }).locator('input').check()

  await page.getByRole('button', { name: 'Save draft' }).click()

  await expect.poll(() => put).not.toBeNull()
  expect(put).toMatchObject({ name: 'support-triage-v2', description: 'Ticket triage' })

  await expect.poll(() => versionPost).not.toBeNull()
  expect(versionPost).toMatchObject({
    system_prompt: 'Be terse and cite sources.',
    temperature: 0.2,
    max_tokens_total: 4096,
    max_cost: 2.5,
    // limits.timeout_ms 30000 renders as "30s per run" and reads back as 30.
    max_runtime_seconds: 30,
    // Spec fields the console has no control for ride along unchanged.
    max_iterations: 8,
    max_tool_calls: 20,
    max_failures: 2,
    cost_currency: 'USD',
    failure_strategy: 'respond',
    verify: true,
    memory_strategy: 'planner_only',
    memory_top_k: 5,
    bindings: {
      model_ref: 'claude-sonnet-5',
      tool_refs: ['tool:helpdesk', 'tool:pager'],
      skill_refs: [],
      knowledge_refs: [],
      // No workflow picker on the Build tab, so the binding is preserved.
      workflow_refs: ['wf:escalate'],
    },
  })
})

test('the header Publish button publishes the current version after confirming', async ({ page }) => {
  let published: Record<string, unknown> | null = null
  await page.route('**/api/v1/agents/ag_1/publish', (route) => {
    published = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Publish v2' }).click()

  await expect(page.getByRole('heading', { name: 'Publish agent version' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Publish' }).click()

  await expect.poll(() => published).not.toBeNull()
  // The header publishes the agent's current (draft) version, not the live one.
  expect(published).toEqual({ version_id: 'ver_2' })
})

test('the Publish tab version rail publishes the version it was clicked on', async ({ page }) => {
  let published: Record<string, unknown> | null = null
  await page.route('**/api/v1/agents/ag_1/publish', (route) => {
    published = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Publish' }).click()
  await page.locator('.bundle', { hasText: 'v2' }).click()

  await expect(page.getByRole('heading', { name: 'Publish agent version' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Publish' }).click()

  await expect.poll(() => published).not.toBeNull()
  expect(published).toEqual({ version_id: 'ver_2' })
})

test('pausing from Settings flips the agent status', async ({ page }) => {
  let put: Record<string, unknown> | null = null
  await page.route('**/api/v1/agents/ag_1', (route) => {
    if (route.request().method() === 'PUT') {
      put = route.request().postDataJSON()
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: ok({ ...agent, status: 'disabled' }),
      })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Settings' }).click()
  await page.getByRole('button', { name: 'Pause agent' }).click()

  await expect.poll(() => put).not.toBeNull()
  expect(put).toEqual({ status: 'disabled' })
})

test('archiving from Settings deletes the agent and returns to the list', async ({ page }) => {
  let deleted = false
  await page.route('**/api/v1/agents/ag_1', (route) => {
    if (route.request().method() === 'DELETE') {
      deleted = true
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(agent) })
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Settings' }).click()
  await page.getByRole('button', { name: 'Archive…' }).click()

  await expect(page.getByRole('heading', { name: 'Archive agent' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Archive…' }).click()

  await expect.poll(() => deleted).toBe(true)
  await expect(page).toHaveURL(/\/build\/agents$/)
})

test('a failing write surfaces the API message instead of navigating away', async ({ page }) => {
  await page.route('**/api/v1/agents', (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(emptyPage) })
    }
    return route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        code: 'VALIDATION_ERROR',
        message: 'An agent named refund-checker already exists',
        data: null,
      }),
    })
  })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New agent' }).click()
  await page.locator('.console-modal input.input').first().fill('refund-checker')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(
    page.getByText('An agent named refund-checker already exists').first(),
  ).toBeVisible()
  await expect(page).toHaveURL(/\/build\/agents$/)
})

test('the publish tab shows the regression trend and what it blocked', async ({
  page,
}) => {
  await json(page, '**/api/v1/evaluations/regression-reports/trend**', {
    subject_kind: 'agent',
    subject_id: 'ag_1',
    dataset: 'default',
    points: [
      {
        report_id: 'rep_2',
        subject_version_id: 'av_2',
        dataset: 'default',
        dataset_revision: 3,
        created_at: NOW,
        passed: false,
        total: 10,
        passed_count: 8,
        pass_rate: 0.8,
        regressed: 2,
        fixed: 0,
        avg_latency_ms: 1800,
        total_cost_amount: 0.12,
      },
      {
        report_id: 'rep_1',
        subject_version_id: 'av_1',
        dataset: 'default',
        dataset_revision: 3,
        created_at: NOW,
        passed: true,
        total: 10,
        passed_count: 10,
        pass_rate: 1,
        regressed: 0,
        fixed: 1,
        avg_latency_ms: 1700,
        total_cost_amount: 0.11,
      },
    ],
  })

  await page.goto('/build/agents/ag_1', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Publish' }).click()

  const panel = page.locator('.panel').filter({ hasText: 'Regression trend' })
  await expect(panel).toContainText('BLOCKED')
  // A case that used to pass is what this change broke, so it is named.
  await expect(panel).toContainText('2 regressed')
  await expect(panel).toContainText('8/10 cases')
})

test('the review tab lists drafts the workspace is waiting on and answers them', async ({
  page,
}) => {
  let reviewed: Record<string, unknown> | null = null

  await json(page, '**/api/v1/agents/drafts/awaiting-review**', [
    {
      version_id: 'av_9',
      agent_id: 'release-notes',
      agent_name: 'release-notes',
      version: 6,
      review_status: 'in_review',
      review_note: 'scope change',
      review_requested_at: '2026-08-29T10:00:00Z',
      review_requested_by: 'Wei',
    },
  ])
  await page.route('**/api/v1/agents/release-notes/versions/av_9/review', (route) => {
    reviewed = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'av_9', review_status: 'approved' }),
    })
  })

  await page.goto('/build/agents', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Review/i }).click()

  const row = page.locator('tbody tr').filter({ hasText: 'release-notes' })
  await expect(row).toContainText('scope change')
  await expect(row).toContainText('Wei')

  await row.getByRole('button', { name: 'Approve' }).click()

  await expect.poll(() => reviewed).not.toBeNull()
  expect(reviewed).toMatchObject({ action: 'approve' })
})
