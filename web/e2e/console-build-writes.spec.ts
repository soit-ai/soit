import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'

const plugin = (over: Record<string, unknown>) => ({
  name: 'plugin',
  version: '1.0.0',
  publisher: 'soit-labs',
  plugin_type: 'tool',
  status: 'active',
  description: 'A registry plugin',
  spec_json: {},
  manifest_json: {},
  publish_status: 'published',
  installed_count: 0,
  created_at: NOW,
  updated_at: NOW,
  ...over,
})

const plugins = {
  items: [
    plugin({ id: 'k8s-toolkit', name: 'k8s-toolkit', plugin_type: 'mcp', installed: true, enabled: true }),
    plugin({ id: 's3-tools', name: 's3-tools', installed: false, enabled: null }),
  ],
  next_page_token: null,
  page_size: 100,
}

const modelOverview = {
  summary: {
    total_models: 2,
    available_models: 2,
    total_providers: 1,
    online_providers: 1,
    month_calls: 100,
    month_tokens: 1000,
    month_cost_amount: 1.5,
    currency: 'USD',
    avg_latency_ms: 900,
    abnormal_models: 0,
    updated_at: NOW,
  },
  model_tabs: { all: 2, text: 1, embedding: 1, multimodal: 0, rerank: 0, disabled: 0, abnormal: 0 },
  provider_tabs: { all: 1, online: 1, disabled: 0, error: 0 },
  trend: [],
  cost_share: [],
  top_models: [],
  top_providers: [],
  quota_reminders: [],
}

const workbenchProviders = {
  summary: modelOverview.summary,
  tabs: modelOverview.provider_tabs,
  items: [
    {
      id: 'p1',
      name: 'Anthropic',
      kind: 'anthropic',
      status: 'online',
      available_models: 2,
      total_models: 2,
      model_types: ['llm'],
      month_calls: 100,
      month_tokens: 1000,
      month_cost_amount: 1.5,
      currency: 'USD',
      avg_latency_ms: 900,
      recent_exception_count: 0,
      updated_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 200,
}

const workbenchModels = {
  summary: modelOverview.summary,
  tabs: modelOverview.model_tabs,
  items: [
    {
      id: 'pm_1',
      provider_id: 'p1',
      provider_slug: 'anthropic',
      provider_name: 'Anthropic',
      provider_kind: 'anthropic',
      model_id: 'claude-sonnet-5',
      display_name: 'claude-sonnet-5',
      description: 'flagship',
      model_type: 'llm',
      status: 'available',
      context_window: 200000,
      max_output_tokens: 8192,
      sync_status: 'synced',
      source: 'platform',
      month_calls: 100,
      today_calls: 4,
      month_tokens: 1000,
      month_cost_amount: 1.5,
      currency: 'USD',
      avg_latency_ms: 900,
      recent_exception_count: 0,
      updated_at: NOW,
      unit_price: 3,
      action_enabled: true,
    },
  ],
  next_page_token: null,
  page_size: 200,
}

/** The full provider record `GET /modelhub/providers` returns. */
const providerRecord = {
  id: 'p1',
  adapter_backend: 'native',
  slug: 'anthropic',
  kind: 'anthropic',
  name: 'Anthropic',
  base_url: 'https://api.anthropic.com',
  credential_secret_id: 'sec_1',
  status: 'active',
  sync_policy_json: { auto_sync: true, interval_minutes: 360 },
  connection_config_json: {},
  auth_config_json: {},
  runtime_config_json: {},
  governance_config_json: {},
  created_at: NOW,
  updated_at: NOW,
}

const supportMatrix = {
  providers: [],
  adapter_backends: [
    { adapter_backend: 'native', display_name: 'Native', available: true, install_hint: null },
  ],
  provider_presets: [
    {
      provider_kind: 'anthropic',
      display_name: 'Anthropic',
      default_adapter_backend: 'native',
      supported_adapter_backends: ['native'],
      litellm_provider: 'anthropic',
      requires_base_url: false,
      credential_optional: false,
    },
    {
      provider_kind: 'openai',
      display_name: 'OpenAI',
      default_adapter_backend: 'native',
      supported_adapter_backends: ['native'],
      litellm_provider: 'openai',
      requires_base_url: false,
      credential_optional: false,
    },
  ],
}

const providerModelRecord = {
  id: 'pm_1',
  provider_id: 'p1',
  provider_kind: 'anthropic',
  model_id: 'claude-sonnet-5',
  model_ref: 'model:anthropic:claude-sonnet-5',
  display_name: 'claude-sonnet-5',
  status: 'active',
  source: 'platform',
  sync_status: 'synced',
  created_at: NOW,
  updated_at: NOW,
}

type Captured = { method: string; path: string; body: unknown } | null

/**
 * One dispatcher for everything under `/modelhub/providers` — the list, the
 * support matrix, the provider itself and its models all share that prefix,
 * so a single handler keeps the routing order unambiguous.
 */
async function mockProviderApi(page: Page, capture: { current: Captured }) {
  await page.route('**/api/v1/modelhub/providers**', (route) => {
    const request = route.request()
    const method = request.method()
    const path = new URL(request.url()).pathname
    const fulfill = (data: unknown) =>
      route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) })

    if (path.endsWith('/support-matrix')) return fulfill(supportMatrix)

    const record = (body: unknown) => {
      capture.current = { method, path, body }
    }

    if (path.endsWith('/modelhub/providers')) {
      if (method === 'POST') {
        record(request.postDataJSON())
        return fulfill(providerRecord)
      }
      return fulfill({ items: [providerRecord], next_page_token: null, page_size: 200 })
    }

    if (path.includes('/models')) {
      if (method === 'POST' || method === 'PATCH') {
        record(request.postDataJSON())
        return fulfill(providerModelRecord)
      }
      if (method === 'DELETE') {
        record(null)
        return fulfill(null)
      }
      return fulfill({ items: [providerModelRecord], next_page_token: null, page_size: 200 })
    }

    if (method === 'PATCH') {
      record(request.postDataJSON())
      return fulfill(providerRecord)
    }
    if (method === 'DELETE') {
      record(null)
      return fulfill(null)
    }
    return fulfill(providerRecord)
  })
}

async function mockModelsPage(page: Page) {
  await json(page, '**/api/v1/modelhub/workbench/overview**', modelOverview)
  await json(page, '**/api/v1/modelhub/workbench/models**', workbenchModels)
  await json(page, '**/api/v1/modelhub/workbench/providers**', workbenchProviders)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

// ---------------------------------------------------------------- plugins ---

test('a registry plugin that is not installed can be installed', async ({ page }) => {
  let installed: { url: string; body: unknown } | null = null
  await json(page, '**/api/v1/plugins?**', plugins)
  await json(page, '**/api/v1/plugins', plugins)
  await page.route('**/api/v1/plugins/*/install', (route) => {
    installed = { url: route.request().url(), body: route.request().postDataJSON() }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ id: 'inst_9', plugin_id: 's3-tools', installed_at: NOW }),
    })
  })

  await page.goto('/v2/build/plugins', { waitUntil: 'domcontentloaded' })

  // The Installed tab lists installed rows; the registry remainder is one chip away.
  await expect(page.getByText('s3-tools', { exact: true })).toHaveCount(0)
  await page.locator('.fchip', { hasText: 'Not installed' }).click()
  await expect(page.getByText('s3-tools', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Install…' }).click()

  await expect.poll(() => installed).not.toBeNull()
  expect(installed!.url).toContain('/plugins/s3-tools/install')
  expect(installed!.body).toMatchObject({ config_json: {} })
})

test('an installed plugin can be uninstalled after confirmation', async ({ page }) => {
  let uninstalled: string | null = null
  await json(page, '**/api/v1/plugins?**', plugins)
  await json(page, '**/api/v1/plugins', plugins)
  await page.route('**/api/v1/plugins/*/install', (route) => {
    if (route.request().method() === 'DELETE') {
      uninstalled = route.request().url()
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })

  await page.goto('/v2/build/plugins', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Uninstall' }).first().click()

  const modal = page.locator('.console-modal')
  await expect(modal.getByText('Uninstall k8s-toolkit?', { exact: false })).toBeVisible()
  await modal.getByRole('button', { name: 'Uninstall' }).click()

  await expect.poll(() => uninstalled).not.toBeNull()
  expect(uninstalled).toContain('/plugins/k8s-toolkit/install')
})

test('a plugin package is uploaded as multipart with the auto mode', async ({ page }) => {
  let upload: { url: string; body: string | null } | null = null
  await json(page, '**/api/v1/plugins?**', plugins)
  await json(page, '**/api/v1/plugins', plugins)
  await page.route('**/api/v1/plugins/package**', (route) => {
    upload = { url: route.request().url(), body: route.request().postData() }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        action: 'created',
        plugin: plugins.items[1],
        install: {
          install_dir: '/plugins/demo',
          package_path: '/plugins/demo.zip',
          manifest_path: '/plugins/demo/manifest.json',
          spec_path: '/plugins/demo/spec.json',
        },
      }),
    })
  })

  await page.goto('/v2/build/plugins', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Upload package' }).click()

  // Upload stays disabled until a package is chosen.
  const confirm = page.getByRole('button', { name: 'Upload', exact: true })
  await expect(confirm).toBeDisabled()

  await page.locator('.console-modal input[type="file"]').setInputFiles({
    name: 'demo-plugin.zip',
    mimeType: 'application/zip',
    buffer: Buffer.from('PK not-a-real-zip'),
  })
  await expect(confirm).toBeEnabled()
  await confirm.click()

  await expect.poll(() => upload).not.toBeNull()
  expect(upload!.url).toContain('mode=auto')
  expect(upload!.body).toContain('demo-plugin.zip')
})

// ----------------------------------------------------------------- models ---

test('a provider is created from the header action', async ({ page }) => {
  const capture: { current: Captured } = { current: null }
  await mockModelsPage(page)
  await mockProviderApi(page, capture)

  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Add provider' }).click()

  // Create stays disabled until a name and a kind are both present.
  const create = page.getByRole('button', { name: 'Create' })
  await expect(create).toBeDisabled()

  const modal = page.locator('.console-modal')
  // Kind and adapter backend both render as selects once the support matrix lands.
  await expect(modal.locator('select')).toHaveCount(2)
  await modal.locator('input.input').first().fill('OpenAI staging')
  await modal.locator('select').first().selectOption('openai')
  await modal.locator('input.input').nth(1).fill('https://oai.internal/v1')
  await modal.locator('input.input').nth(2).fill('sec_openai')

  await expect(create).toBeEnabled()
  await create.click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('POST')
  expect(capture.current!.body).toMatchObject({
    name: 'OpenAI staging',
    kind: 'openai',
    slug: 'openai',
    adapter_backend: 'native',
    base_url: 'https://oai.internal/v1',
    credential_secret_id: 'sec_openai',
    status: 'active',
  })
})

test('editing a provider keeps the config it does not show', async ({ page }) => {
  const capture: { current: Captured } = { current: null }
  await mockModelsPage(page)
  await mockProviderApi(page, capture)

  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Edit' }).click()

  const modal = page.locator('.console-modal')
  // The form is prefilled from the provider record, not from the workbench row.
  await expect(modal.locator('input.input').nth(1)).toHaveValue('https://api.anthropic.com')
  await modal.locator('input.input').first().fill('Anthropic EU')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('PATCH')
  expect(capture.current!.path).toContain('/modelhub/providers/p1')
  expect(capture.current!.body).toMatchObject({
    name: 'Anthropic EU',
    kind: 'anthropic',
    credential_secret_id: 'sec_1',
    // The sync policy the console never renders survives the round trip.
    sync_policy_json: { auto_sync: true, interval_minutes: 360 },
  })
})

test('a provider is deleted after confirmation', async ({ page }) => {
  const capture: { current: Captured } = { current: null }
  await mockModelsPage(page)
  await mockProviderApi(page, capture)

  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Delete…' }).click()

  const modal = page.locator('.console-modal')
  await expect(modal.getByText('Delete Anthropic?', { exact: false })).toBeVisible()
  await modal.getByRole('button', { name: 'Delete', exact: true }).click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('DELETE')
  expect(capture.current!.path).toContain('/modelhub/providers/p1')
})

test('a model is added to the library under a provider', async ({ page }) => {
  const capture: { current: Captured } = { current: null }
  await mockModelsPage(page)
  await mockProviderApi(page, capture)

  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Library/ }).click()
  await page.getByRole('button', { name: 'Add model' }).click()

  const modal = page.locator('.console-modal')
  await modal.locator('select').first().selectOption('p1')
  await modal.locator('input.input').first().fill('claude-haiku-5')
  await modal.locator('input.input').nth(2).fill('64000')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('POST')
  expect(capture.current!.path).toContain('/modelhub/providers/p1/models')
  expect(capture.current!.body).toMatchObject({
    model_id: 'claude-haiku-5',
    context_window: 64000,
    source: 'local',
    status: 'active',
  })
})

test('a library row opens its settings, saves, tests and deletes', async ({ page }) => {
  const capture: { current: Captured } = { current: null }
  let tested: Record<string, unknown> | null = null
  await mockModelsPage(page)
  await mockProviderApi(page, capture)
  await page.route('**/api/v1/modelhub/test/chat', (route) => {
    tested = route.request().postDataJSON()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ success: true, message: 'pong', response: 'pong', latency_ms: 120 }),
    })
  })

  await page.goto('/v2/build/models', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Library/ }).click()
  await page.getByText('claude-sonnet-5').first().click()

  const modal = page.locator('.console-modal')
  await expect(modal.getByRole('heading', { name: 'Model settings' })).toBeVisible()

  // Test connection: the prompt goes to the chat endpoint for an llm row.
  // Rows: model id (read-only), display name, description, context, max output, test prompt.
  await modal.locator('input.input').nth(5).fill('ping')
  await modal.getByRole('button', { name: 'Test' }).click()
  await expect.poll(() => tested).not.toBeNull()
  expect(tested).toMatchObject({
    provider_id: 'p1',
    model_id: 'claude-sonnet-5',
    input: 'ping',
  })

  // Save patches the model under its provider.
  await modal.locator('input.input').nth(1).fill('Claude Sonnet 5')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('PATCH')
  expect(capture.current!.path).toContain('/modelhub/providers/p1/models/pm_1')
  expect(capture.current!.body).toMatchObject({
    display_name: 'Claude Sonnet 5',
    context_window: 200000,
    max_output_tokens: 8192,
  })

  // Delete goes through the settings dialog into its own confirmation.
  capture.current = null
  await page.getByText('claude-sonnet-5').first().click()
  await modal.getByRole('button', { name: 'Delete…' }).click()
  await expect(page.getByText('Delete claude-sonnet-5 from the library?')).toBeVisible()
  await page.getByRole('button', { name: 'Delete', exact: true }).click()

  await expect.poll(() => capture.current).not.toBeNull()
  expect(capture.current!.method).toBe('DELETE')
  expect(capture.current!.path).toContain('/modelhub/providers/p1/models/pm_1')
})
