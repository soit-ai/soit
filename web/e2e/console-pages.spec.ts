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
    total_workflows: 3,
    published_workflows: 2,
    running_workflows: 1,
    today_runs: 2148,
    avg_latency_ms: 1800,
    success_rate: 0.984,
    recent_exceptions: 1,
    updated_at: NOW,
  },
  tabs: { all: 3, high_volume: 1, publishing: 1, abnormal: 0, draft: 1 },
  items: [
    { id: 'ticket-escalation', name: 'ticket-escalation', summary: 'triage → enrich → route', status: 'running', linked_agents: [], linked_agent_count: 0, today_runs: 412, avg_latency_ms: 1800, success_rate: 0.992, recent_exception_count: 0, owner: 'Jude', last_run_at: NOW, action_enabled: true, updated_at: NOW },
    { id: 'docs-nightly-sync', name: 'docs-nightly-sync', summary: 'crawl → chunk → embed', status: 'publishing', linked_agents: [], linked_agent_count: 0, today_runs: 96, avg_latency_ms: 4200, success_rate: 0.974, recent_exception_count: 1, owner: 'Wei', last_run_at: NOW, action_enabled: true, updated_at: NOW },
    { id: 'churn-signal-scan', name: 'churn-signal-scan', summary: 'query → score → draft', status: 'draft', linked_agents: [], linked_agent_count: 0, today_runs: 0, avg_latency_ms: null, success_rate: null, recent_exception_count: 0, owner: 'Jude', last_run_at: null, action_enabled: false, updated_at: NOW },
  ],
  next_page_token: null,
  page_size: 50,
}

const knowledgeWorkbench = {
  summary: {
    total_knowledge_bases: 3,
    ready_knowledge_bases: 2,
    total_documents: 1626,
    total_chunks: 24212,
    today_calls: 4044,
    avg_latency_ms: 240,
    hit_rate: 0.87,
    recent_exceptions: 1,
    updated_at: NOW,
  },
  tabs: { all: 3, high_volume: 1, low_hit: 1, slow: 0, unconfigured: 0 },
  items: [
    { id: 'product-docs', name: 'product-docs', description: 'public docs site', status: 'ready', knowledge_type: 'vector', content_source: 'Web Crawl', document_count: 1204, chunk_count: 18392, today_calls: 2381, avg_latency_ms: 212, hit_rate: 0.91, recent_exception_count: 0, owner: 'Jude', last_sync_at: NOW, action_enabled: true, updated_at: NOW },
    { id: 'support-macros', name: 'support-macros', description: 'canned replies', status: 'ready', knowledge_type: 'vector', content_source: 'Upload', document_count: 86, chunk_count: 1022, today_calls: 944, avg_latency_ms: 180, hit_rate: 0.88, recent_exception_count: 0, owner: 'Wei', last_sync_at: NOW, action_enabled: true, updated_at: NOW },
    { id: 'billing-policies', name: 'billing-policies', description: 'scanned PDFs', status: 'error', knowledge_type: 'vector', content_source: 'Upload', document_count: 24, chunk_count: 388, today_calls: 207, avg_latency_ms: 610, hit_rate: 0.61, recent_exception_count: 3, owner: 'Ming', last_sync_at: NOW, action_enabled: true, updated_at: NOW },
  ],
  next_page_token: null,
  page_size: 50,
}

const plugins = {
  items: [
    { id: 'k8s-toolkit', name: 'k8s-toolkit', version: '1.4.2', publisher: 'soit-labs', plugin_type: 'mcp', status: 'active', description: 'Kubernetes operations', spec_json: {}, manifest_json: {}, publish_status: 'published', installed_count: 1, installed: true, enabled: true },
    { id: 'helpdesk-api', name: 'helpdesk-api', version: '2.0.1', publisher: 'builtin', plugin_type: 'tool', status: 'active', description: 'Ticket read/write', spec_json: {}, manifest_json: {}, publish_status: 'published', installed_count: 1, installed: true, enabled: true },
    { id: 'incident-writeup', name: 'incident-writeup', version: '1.2.0', publisher: 'soit-labs', plugin_type: 'skill', status: 'active', description: 'Postmortem structure', spec_json: {}, manifest_json: {}, publish_status: 'published', installed_count: 1, installed: true, enabled: true },
    { id: 'cdn-tools', name: 'cdn-tools', version: '0.3.1', publisher: 'community', plugin_type: 'tool', status: 'active', description: 'CDN purge', spec_json: {}, manifest_json: {}, publish_status: 'published', installed_count: 1, installed: true, enabled: false },
  ],
  next_page_token: null,
  page_size: 100,
}

const modelOverview = {
  summary: {
    total_providers: 3,
    online_providers: 3,
    total_models: 6,
    month_tokens: 5_100_000,
    month_cost_amount: 35.51,
    currency: 'USD',
    avg_latency_ms: 1800,
  },
  model_tabs: { all: 6, text: 4, embedding: 1, rerank: 1 },
  provider_tabs: { all: 3, online: 3, offline: 0 },
  top_models: [
    { model_id: 'claude-sonnet-5', display_name: 'claude-sonnet-5', provider_name: 'Anthropic', request_count: 1942, month_tokens: 1_730_000, avg_latency_ms: 1800, month_cost_amount: 24.63, currency: 'USD' },
  ],
}

const modelLibrary = {
  tabs: { all: 6, text: 4, embedding: 1, rerank: 1 },
  items: [
    { id: 'pm_1', model_id: 'claude-sonnet-5', display_name: 'claude-sonnet-5', provider_id: 'p1', provider_name: 'Anthropic', provider_slug: 'anthropic', model_type: 'llm', status: 'available', context_window: 200000, unit_price: 3, currency: 'USD' },
    { id: 'pm_2', model_id: 'bge-m3', display_name: 'bge-m3', provider_id: 'p3', provider_name: 'vLLM', provider_slug: 'vllm', model_type: 'embedding', status: 'available', context_window: 8000, unit_price: 0, currency: 'USD' },
  ],
  next_page_token: null,
  page_size: 200,
}

const modelProviders = {
  tabs: { all: 3, online: 3, offline: 0 },
  items: [
    { id: 'p1', name: 'Anthropic', slug: 'anthropic', kind: 'anthropic', status: 'online', model_count: 4, available_model_count: 4, month_tokens: 1_900_000, month_cost_amount: 29.11, currency: 'USD' },
  ],
  next_page_token: null,
  page_size: 200,
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await json(page, '**/api/v1/workflows/workbench**', workflowWorkbench)
  await json(page, '**/api/v1/knowledge/workbench**', knowledgeWorkbench)
  await json(page, '**/api/v1/plugins?**', plugins)
  await json(page, '**/api/v1/modelhub/workbench/overview**', modelOverview)
  await json(page, '**/api/v1/modelhub/workbench/models**', modelLibrary)
  await json(page, '**/api/v1/modelhub/workbench/providers**', modelProviders)
})

test('overview renders the dashboard and toggles the empty-state demo', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  await expect(page.getByText('1,284')).toBeVisible()
  await expect(page.getByText('96.4%')).toBeVisible()
  // 24 one-hour buckets in the outcome chart.
  await expect(page.locator('.bars .col')).toHaveCount(24)
  await expect(page.getByText('run_01J9KD84QF')).toBeVisible()

  await page.getByRole('button', { name: 'Demo: empty state' }).click()
  await expect(page.getByText('Get your workspace running')).toBeVisible()
  await expect(page.getByText('No runs yet.', { exact: false })).toBeVisible()
})

test('overview recent-run row opens the run detail route', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })
  await page.getByText('run_01J9KD6H0T').click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD6H0T/)
})

test('knowledge list filters by source kind and opens the library detail', async ({ page }) => {
  await page.goto('/v2/build/knowledge', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('product-docs')).toBeVisible()
  await page.locator('.fchip', { hasText: 'Upload' }).click()
  await expect(page.getByText('support-macros')).toBeVisible()
  await expect(page.getByText('product-docs')).toHaveCount(0)

  await page.locator('.fchip', { hasText: 'All' }).click()
  await page.getByText('product-docs').click()
  await expect(page).toHaveURL(/\/v2\/build\/knowledge\/product-docs/)
})

test('knowledge retrieval testing calls the query endpoint', async ({ page }) => {
  await json(page, '**/api/v1/knowledge/product-docs', {
    id: 'product-docs',
    name: 'product-docs',
    status: 'active',
    visibility: 'workspace',
    knowledge_type: 'vector',
    settings_json: { source_uri: 'https://docs.acme.io' },
    chunking_json: { chunk_size: 512, chunk_overlap: 64 },
    retrieval_json: { top_k: 5, use_rerank: true },
    doc_count: 1204,
    chunk_count: 18392,
    tags: [],
    created_at: NOW,
    updated_at: NOW,
  })
  await json(page, '**/api/v1/knowledge/product-docs/documents**', [])
  await json(page, '**/api/v1/knowledge/product-docs/indexes**', [])
  await json(page, '**/api/v1/knowledge/product-docs/usages**', [])

  let queryBody: Record<string, unknown> | null = null
  await page.route('**/api/v1/knowledge/product-docs/query', (route) => {
    queryBody = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        total: 1,
        citations: [],
        results: [
          {
            chunk_id: 'ck_4a91#13',
            document_id: '/guides/getting-started.md',
            score: 0.92,
            text: 'Secrets are referenced as vault:name and resolved at call time.',
            snippets: [],
            metadata: {},
          },
        ],
      }),
    })
  })

  await page.goto('/v2/build/knowledge/product-docs', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /Retrieval testing/ }).click()

  await page.locator('.fsearch input').fill('how do I rotate a secret?')
  await page.getByText('Run query').click()

  await expect(page.getByText('Secrets are referenced as vault:name', { exact: false })).toBeVisible()
  // The base's configured retrieval settings drive the request, not UI defaults.
  expect(queryBody).toMatchObject({ query: 'how do I rotate a secret?', top_k: 5, use_rerank: true })
})

test('plugins installed table filters and persists the enable toggle', async ({ page }) => {
  let enabledCall: { url: string; body: unknown } | null = null
  await page.route('**/api/v1/plugins/*/enabled', (route) => {
    enabledCall = { url: route.request().url(), body: route.request().postDataJSON() }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'inst_1', plugin_version_id: 'v1', enabled: true, state: 'active', config_json: {} }),
    })
  })

  await page.goto('/v2/build/plugins', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('k8s-toolkit', { exact: true })).toBeVisible()
  await page.locator('.fchip', { hasText: 'Skills' }).click()
  await expect(page.getByText('incident-writeup', { exact: true })).toBeVisible()
  await expect(page.getByText('k8s-toolkit', { exact: true })).toHaveCount(0)

  await page.locator('.fchip', { hasText: 'Disabled' }).click()
  const toggle = page.getByRole('switch', { name: 'cdn-tools' })
  await expect(toggle).toHaveAttribute('aria-checked', 'false')
  await toggle.click()

  // The toggle writes through to the registry, not just local state.
  await expect.poll(() => enabledCall).not.toBeNull()
  expect(enabledCall!.url).toContain('/plugins/cdn-tools/enabled')
  expect(enabledCall!.body).toMatchObject({ enabled: true })
})

test('models library filters by capability', async ({ page }) => {
  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Anthropic', { exact: true }).first()).toBeVisible()
  await page.getByRole('tab', { name: /Library/ }).click()
  await expect(page.getByText('claude-sonnet-5').first()).toBeVisible()

  await page.locator('.fchip', { hasText: 'Embedding' }).click()
  await expect(page.getByText('bge-m3').first()).toBeVisible()
  await expect(page.getByText('claude-sonnet-5')).toHaveCount(0)
})

test('chat switches threads and links replies to run evidence', async ({ page }) => {
  await page.goto('/v2/chat', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Chat' })).toBeVisible()
  await expect(page.locator('.thread.on')).toContainText('checkout-api 502s')

  await page.locator('.thread', { hasText: 'vault rotation runbook' }).click()
  await expect(page.locator('.thread.on')).toContainText('vault rotation runbook')

  await page.locator('.evd', { hasText: 'run_01J9KD7Z2M' }).click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD7Z2M/)
})

test('settings redirects to account and navigates sections via the subnav', async ({ page }) => {
  await page.goto('/v2/settings', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/v2\/settings\/account/)
  await expect(page.getByText('Display name')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'Team' }).click()
  await expect(page).toHaveURL(/\/v2\/settings\/team/)
  await expect(page.getByText('audit-bot')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'Billing & license' }).click()
  await expect(page.getByText('INV-2026-0301')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'About' }).click()
  await expect(page.getByText('github.com/soit-ai/soit')).toBeVisible()
})

test('workflow list renders workbench rows and opens the builder', async ({ page }) => {
  await page.goto('/v2/build/workflows', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('ticket-escalation').first()).toBeVisible()
  // Tiles come from the workbench summary, not from row arithmetic.
  await expect(page.getByText('2,148')).toBeVisible()
  await expect(page.getByText('98.4%')).toBeVisible()

  await page.getByText('docs-nightly-sync').first().click()
  await expect(page).toHaveURL(/\/v2\/build\/workflows\/docs-nightly-sync/)
})

test('workflow publish tab lists only versions awaiting publication', async ({ page }) => {
  await page.goto('/v2/build/workflows', { waitUntil: 'domcontentloaded' })

  await page.getByRole('tab', { name: /Publish/ }).click()
  await expect(page.getByText('docs-nightly-sync').first()).toBeVisible()
  await expect(page.getByText('churn-signal-scan')).toHaveCount(0)
})
