import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

/**
 * The gateway governance screens hold wide rows: limits summaries, failover
 * chains, spend bars. On a phone they must scroll inside their tables rather
 * than push the page sideways.
 */

const ok = (data: unknown) => JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-09-27T09:00:00Z'

async function expectNoSidewaysScroll(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
}

test.use({ viewport: { width: 390, height: 844 } })

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('the budgets page fits a phone', async ({ page }) => {
  await json(page, '**/api/v1/billing/budgets/statuses', [
    {
      budget: {
        id: 'bud_1',
        name: 'Partner gateway monthly allowance',
        scope_kind: 'api_key',
        scope_id: 'key_partner_with_a_long_identifier',
        period: 'month',
        amount: '25000.000000',
        currency: 'USD',
        thresholds: [50, 80, 90, 100],
        hard_stop: true,
        status: 'active',
        created_by: 'user-1',
        created_at: NOW,
        updated_at: NOW,
      },
      period_start: '2026-09-01T00:00:00Z',
      resets_at: '2026-10-01T00:00:00Z',
      spent: '21734.120000',
      remaining: '3265.880000',
      percent: '86.94',
      forecast: '26990.000000',
    },
  ])

  await page.goto('/govern/budgets', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Partner gateway monthly allowance')).toBeVisible()
  await expectNoSidewaysScroll(page)
})

test('the API keys pane fits a phone', async ({ page }) => {
  await json(page, '**/api/v1/api-keys**', {
    items: [
      {
        id: 'key_1',
        tenant_id: 't1',
        workspace_id: 'workspace-1',
        user_id: 'user-1',
        name: 'partner-integration-production',
        key_prefix: 'sk_fixture_a',
        status: 'active',
        scopes: ['read', 'write'],
        rate_limit_per_minute: 600,
        daily_request_quota: 250000,
        daily_token_quota: 50000000,
        ip_allowlist: ['203.0.113.0/24', '198.51.100.7/32'],
        allowed_models: ['model:openai:gpt-5.5', 'vmodel:support-chat'],
        allowed_tools: ['tool:function:knowledge_query', 'mcp_tool:github:create_issue'],
        content_capture: 'metadata_only',
        principal_id: 'sp_1',
        last_used_at: NOW,
        created_at: NOW,
        updated_at: NOW,
      },
    ],
    next_page_token: null,
    page_size: 100,
  })
  await json(page, '**/api/v1/service-principals**', [
    {
      id: 'sp_1',
      tenant_id: 't1',
      workspace_id: 'workspace-1',
      name: 'nightly-etl-pipeline',
      description: 'Loads support transcripts into the knowledge base every night',
      owner_user_id: 'user-1',
      workspace_role: 'Dev',
      status: 'active',
      created_by: 'user-1',
      created_at: NOW,
      updated_at: NOW,
    },
  ])

  await page.goto('/settings/api', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('partner-integration-production')).toBeVisible()
  // The client commands are long; they clip in their row, not the page.
  await expect(page.getByText('Connect a client')).toBeVisible()
  await expectNoSidewaysScroll(page)
})

test('the virtual models tab fits a phone', async ({ page }) => {
  await json(page, '**/api/v1/modelhub/workbench/overview**', {
    summary: {},
    model_tabs: { all: 0, text: 0, embedding: 0, rerank: 0 },
    provider_tabs: { all: 0 },
  })
  await json(page, '**/api/v1/modelhub/workbench/models**', {
    summary: {},
    tabs: { all: 0, text: 0, embedding: 0, rerank: 0 },
    items: [],
    next_page_token: null,
    page_size: 200,
  })
  await json(page, '**/api/v1/modelhub/virtual-models**', [
    {
      id: 'vm_1',
      slug: 'support-chat-with-regional-failover',
      name: 'Support chat, regional failover',
      description: null,
      targets: [
        'model:openai-eu-west:gpt-5.5',
        'model:anthropic-eu-central:claude-sonnet-5',
        'model:azure-openai-northeurope:gpt-5.5-mini',
      ],
      status: 'active',
      model_ref: 'vmodel:support-chat-with-regional-failover',
      created_by: 'user-1',
      created_at: NOW,
      updated_at: NOW,
    },
  ])

  await page.goto('/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Virtual models' }).click()
  await expect(page.getByText('vmodel:support-chat-with-regional-failover')).toBeVisible()
  await expectNoSidewaysScroll(page)
})
