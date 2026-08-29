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

const runsPage = {
  items: [
    { id: 'run_01J9KD84QF', trace_id: 'trace_4d19a2', attempt_no: 1, mode: 'chat', subject_kind: 'agent', subject_id: 'support-triage', status: 'succeeded', started_at: NOW, ended_at: NOW, duration_ms: 3100, created_at: NOW, updated_at: NOW, observe_summary: { step_count: 6, tool_call_count: 2, child_run_count: 0, response_event_count: 14, citation_count: 1, audit_count: 2, cost_entry_count: 3 } },
    { id: 'run_01J9KD7Z2M', trace_id: 'trace_4d19a3', attempt_no: 1, mode: 'workflow', subject_kind: 'workflow', subject_id: 'ticket-escalation', status: 'succeeded', started_at: NOW, ended_at: NOW, duration_ms: 8900, created_at: NOW, updated_at: NOW, observe_summary: { step_count: 7, tool_call_count: 1, child_run_count: 0, response_event_count: 9, citation_count: 0, audit_count: 2, cost_entry_count: 2 } },
    { id: 'run_01J9KD6H0T', trace_id: 'trace_4d19a4', attempt_no: 1, mode: 'task', subject_kind: 'agent', subject_id: 'billing-audit', status: 'failed', started_at: NOW, ended_at: NOW, duration_ms: 1200, created_at: NOW, updated_at: NOW, observe_summary: { step_count: 3, tool_call_count: 0, child_run_count: 0, response_event_count: 4, citation_count: 0, audit_count: 1, cost_entry_count: 1 } },
  ],
  next_page_token: null,
  page_size: 200,
}

const runAudits = {
  items: [
    { audit_id: 'aud_77b2', run_id: 'run_01J9KD84QF', step_id: 'st_1', step_type: 'policy_gate', outcome: 'succeeded', gateway_type: 'intent-screen', preview: 'matched "infra.restart.staging"', truncated: false, timestamp: NOW },
    { audit_id: 'aud_77b9', run_id: 'run_01J9KD6H0T', step_id: 'st_3', step_type: 'tool_call', outcome: 'blocked', gateway_type: 'egress-allowlist', preview: 'destination not in allowlist', truncated: false, timestamp: NOW },
  ],
  next_page_token: null,
  page_size: 5,
}

const agentWorkbench = {
  summary: { total_agents: 2, configured_agents: 2, running_agents: 1, today_calls: 699, avg_latency_ms: 1800, success_rate: 0.983, pending_exceptions: 1, updated_at: NOW },
  tabs: { all: 2, high_calls: 1, low_success: 0, long_latency: 0, unconfigured: 0 },
  items: [
    { id: 'support-triage', name: 'support-triage', description: 'Ticket triage', status: 'running', capabilities: [{ type: 'tool', label: 'helpdesk-api' }], today_calls: 412, avg_latency_ms: 1800, success_rate: 0.983, recent_exception_count: 0, owner: 'Jude', last_run_at: NOW, action_enabled: true, updated_at: NOW },
    { id: 'billing-audit', name: 'billing-audit', description: 'Invoice checks', status: 'abnormal', capabilities: [], today_calls: 64, avg_latency_ms: 2400, success_rate: 0.81, recent_exception_count: 3, owner: 'Ming', last_run_at: NOW, action_enabled: true, updated_at: NOW },
  ],
  next_page_token: null,
  page_size: 4,
}

const observeDashboard = {
  overview: { workspace_health_score: 92, workspace_health_status: 'healthy', active_alert_count: 1, sampling_rate: 1, sampling_status: 'full', refreshed_at: NOW },
  metric_cards: [
    { id: 'cost_today', label: 'Spend', value: '$41.32', delta: '−8.1%', trend: [], tone: 'green' },
  ],
  priority_alert: null,
  tabs: [],
  section: { id: 'agent_health', empty_state: null },
  recent_runs: [],
}

const threads = {
  items: [
    { id: 'thread_8f2c', tenant_id: 't1', workspace_id: 'w1', agent_id: 'ops-copilot', title: 'checkout-api 502s', status: 'active', thread_type: 'chat', message_count: 4, last_message_at: NOW, knowledge_config_json: {}, tool_config_json: {}, metadata_json: {}, default_model_ref: 'claude-sonnet-5', created_at: NOW, updated_at: NOW },
  ],
  next_page_token: null,
  page_size: 50,
}

const threadDetail = {
  thread: threads.items[0],
  messages: [
    { id: 'm1', tenant_id: 't1', workspace_id: 'w1', thread_id: 'thread_8f2c', sequence_no: 1, role: 'user', content: 'restart the checkout-api deployment in staging', message_type: 'text', status: 'completed', content_json: {}, citations_json: [], attachments_json: [], tool_calls_json: [], metadata_json: {}, created_by: 'Jude', created_at: NOW },
    { id: 'm2', tenant_id: 't1', workspace_id: 'w1', thread_id: 'thread_8f2c', run_id: 'run_01J9KD7Z2M', sequence_no: 2, role: 'assistant', content: 'Restarted deployment/checkout-api in ns/staging.', message_type: 'text', status: 'completed', content_json: {}, citations_json: [], attachments_json: [], tool_calls_json: [], metadata_json: {}, created_at: NOW },
  ],
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await json(page, '**/api/v1/runs?**', runsPage)
  await json(page, '**/api/v1/runs/audits**', runAudits)
  await json(page, '**/api/v1/agents/workbench**', agentWorkbench)
  await json(page, '**/api/v1/observe/dashboard**', observeDashboard)
  await json(page, '**/api/v1/threads?**', threads)
  await json(page, '**/api/v1/threads/thread_8f2c', threadDetail)
  await json(page, '**/api/v1/workflows/workbench**', workflowWorkbench)
  await json(page, '**/api/v1/knowledge/workbench**', knowledgeWorkbench)
  await json(page, '**/api/v1/plugins?**', plugins)
  await json(page, '**/api/v1/modelhub/workbench/overview**', modelOverview)
  await json(page, '**/api/v1/modelhub/workbench/models**', modelLibrary)
  await json(page, '**/api/v1/modelhub/workbench/providers**', modelProviders)
})

test('overview aggregates runs into the outcome chart and recent list', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  // Three runs sampled: two settled succeeded, one failed → 66.7% pass.
  await expect(page.getByText('66.7%')).toBeVisible()
  await expect(page.locator('.bars .col')).toHaveCount(24)
  await expect(page.locator('.runid', { hasText: 'run_01J9KD84QF' })).toBeVisible()

  // The governance feed reads gateway audits, not a fixture list.
  await expect(page.locator('.feed').getByText('intent-screen')).toBeVisible()
})

test('overview recent-run row opens the run detail route', async ({ page }) => {
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })
  await page.locator('.runid', { hasText: 'run_01J9KD6H0T' }).click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD6H0T/)
})

test('overview surfaces an empty governance feed rather than fixtures', async ({ page }) => {
  await json(page, '**/api/v1/runs/audits**', { items: [], next_page_token: null, page_size: 5 })
  await page.goto('/v2', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Quiet so far.', { exact: false })).toBeVisible()
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

test('chat renders the thread ledger and links replies to run evidence', async ({ page }) => {
  await page.goto('/v2/chat', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Chat' })).toBeVisible()
  await expect(page.locator('.thread.on')).toContainText('checkout-api 502s')
  await expect(page.getByText('restart the checkout-api deployment', { exact: false })).toBeVisible()

  // The assistant turn's evidence chip carries the real run verdict.
  const evidence = page.locator('.evd', { hasText: 'run_01J9KD7Z2M' })
  await expect(evidence).toContainText('7 steps')
  await evidence.click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD7Z2M/)
})

test('chat posts a turn to the responses API', async ({ page }) => {
  let sent: Record<string, unknown> | null = null
  await page.route('**/api/v1/responses', (route) => {
    sent = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'resp_1', tenant_id: 't1', workspace_id: 'w1', thread_id: 'thread_8f2c', status: 'completed' }),
    })
  })

  await page.goto('/v2/chat', { waitUntil: 'domcontentloaded' })
  await page.locator('.composer-box input').fill('tail the error logs')
  await page.getByRole('button', { name: 'Send' }).click()

  await expect.poll(() => sent).not.toBeNull()
  expect(sent).toMatchObject({ thread_id: 'thread_8f2c', agent_id: 'ops-copilot' })
})

test('settings redirects to account and navigates sections via the subnav', async ({ page }) => {
  await json(page, '**/api/v1/workspaces/*/members', [
    { user_id: 'u_1', email: 'zzpd106@gmail.com', name: 'Jude', role: 'owner', status: 'active' },
    { user_id: 'u_2', email: 'wei@acme.io', name: 'Wei', role: 'admin', status: 'active' },
  ])
  await json(page, '**/api/v1/billing/credits/balance', {
    currency: 'USD',
    balance: '3600.00',
    granted_total: '4212.40',
    consumed_total: '612.40',
    updated_at: NOW,
  })
  await json(page, '**/api/v1/billing/credits/entries**', {
    items: [
      { id: 'ce_001', tenant_id: 't1', kind: 'grant', currency: 'USD', amount: '4212.40', note: 'annual allocation', created_at: NOW },
    ],
    next_page_token: null,
    page_size: 20,
  })

  await page.goto('/v2/settings', { waitUntil: 'domcontentloaded' })
  await expect(page).toHaveURL(/\/v2\/settings\/account/)
  await expect(page.getByText('Display name')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'Team' }).click()
  await expect(page).toHaveURL(/\/v2\/settings\/team/)
  await expect(page.getByText('wei@acme.io')).toBeVisible()

  // Billing reads the credit ledger, the only billing object that exists.
  await page.locator('.subnav .sl', { hasText: 'Billing' }).click()
  await expect(page.getByText('ce_001')).toBeVisible()
  await expect(page.getByText('annual allocation')).toBeVisible()

  await page.locator('.subnav .sl', { hasText: 'About' }).click()
  await expect(page.getByText('github.com/soit-ai/soit')).toBeVisible()
})

test('side panel shows live counts for the pillar on screen', async ({ page }) => {
  await page.goto('/v2/build/agents', { waitUntil: 'domcontentloaded' })

  const counted = async (label: string) =>
    page.locator('.subnav .sl', { hasText: label }).locator('.ct').textContent()

  await expect(page.locator('.subnav .sl', { hasText: 'Agents' }).locator('.ct')).toBeVisible()
  expect(await counted('Agents')).toBe('2')
  expect(await counted('Workflows')).toBe('3')
  expect(await counted('Knowledge')).toBe('3')
  // Only installed plugins are counted, matching what the page lists.
  expect(await counted('Plugins')).toBe('4')
  expect(await counted('Models')).toBe('6')
})

test('side panel omits a count it could not load rather than guessing', async ({ page }) => {
  await page.route('**/api/v1/agents/workbench**', (route) => route.abort())
  await page.goto('/v2/build/agents', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('.subnav .sl', { hasText: 'Workflows' }).locator('.ct')).toBeVisible()
  await expect(page.locator('.subnav .sl', { hasText: 'Agents' }).locator('.ct')).toHaveCount(0)
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
