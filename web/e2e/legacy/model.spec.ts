import { expect, test, type Page } from '@playwright/test'
import fs from 'node:fs'
import path from 'node:path'

import { mockShellApi } from '../helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockProvider = {
  id: 'provider-1',
  slug: 'openai-main',
  kind: 'openai',
  name: 'OpenAI',
  base_url: 'https://api.openai.com/v1',
  credential_secret_id: 'sec_id_openai',
  status: 'active',
  sync_policy_json: {
    auto_sync: true,
    interval_minutes: 360,
    recreate_deleted: false,
    default_enabled: true,
    catalog_supported: true,
    include_models: ['gpt-4o-mini'],
    exclude_models: ['*-deprecated'],
  },
  connection_config_json: {
    api_version: '2026-02-01',
    timeout_ms: 30000,
    retry_policy: { max_retries: 3, backoff: 'exponential', retryable_status_codes: [429, 500, 503] },
    rate_limit: { rpm: 1200, tpm: 240000, concurrency: 32 },
  },
  auth_config_json: {
    auth_type: 'bearer',
  },
  runtime_config_json: {
    diagnostics_supported: { healthcheck: true, chat: true, embedding: false },
    runtime_support: { chat: true, stream: true, embedding: false, image: false, rerank: false },
  },
  governance_config_json: {
    currency: 'USD',
    pricing_source: 'catalog',
    egress_policy: { allow_external: true, allowed_domains: ['api.openai.com'] },
    data_policy: { files: true, images: false, sensitive_data: 'confirm' },
    log_level: 'summary',
    trace_enabled: true,
  },
  last_synced_at: '2026-05-31T08:15:00.000Z',
  last_healthcheck_at: '2026-05-31T08:00:00.000Z',
  last_healthcheck_error: null,
  created_at: '2026-05-30T08:00:00.000Z',
  updated_at: '2026-05-31T08:00:00.000Z',
}

const mockClaudeProvider = {
  id: 'provider-anthropic',
  slug: 'claude-main',
  kind: 'anthropic',
  name: 'Claude / Anthropic',
  base_url: 'https://api.anthropic.com',
  credential_secret_id: 'sec_id_anthropic',
  status: 'active',
  sync_policy_json: {
    auto_sync: true,
    interval_minutes: 360,
    recreate_deleted: false,
    default_enabled: true,
    catalog_supported: true,
    include_models: ['claude-opus-4-8', 'claude-sonnet-4-6'],
    exclude_models: [],
  },
  connection_config_json: {
    api_version: '2023-06-01',
    timeout_ms: 30000,
    retry_policy: { max_retries: 3, backoff: 'exponential', retryable_status_codes: [429, 500, 529] },
    rate_limit: { rpm: 1200, tpm: 240000, concurrency: 16 },
  },
  auth_config_json: {
    auth_type: 'api_key',
  },
  runtime_config_json: {
    diagnostics_supported: { healthcheck: true, chat: true, embedding: false },
    runtime_support: { chat: true, stream: true, embedding: false, image: true, rerank: false },
  },
  governance_config_json: {
    currency: 'USD',
    pricing_source: 'catalog',
    egress_policy: { allow_external: true, allowed_domains: ['api.anthropic.com'] },
    data_policy: { files: false, images: true, sensitive_data: 'confirm' },
    log_level: 'summary',
    trace_enabled: true,
  },
  last_synced_at: '2026-06-08T08:15:00.000Z',
  last_healthcheck_at: '2026-06-08T08:00:00.000Z',
  last_healthcheck_error: null,
  created_at: '2026-06-08T08:00:00.000Z',
  updated_at: '2026-06-08T08:00:00.000Z',
}

const mockSummary = {
  total_models: 1,
  available_models: 1,
  total_providers: 1,
  online_providers: 1,
  month_calls: 2,
  month_tokens: 2000,
  month_cost_amount: 2.5,
  currency: 'USD',
  avg_latency_ms: 240,
  abnormal_models: 0,
  updated_at: '2026-05-31T08:00:00.000Z',
}

const mockModelRow = {
  id: 'model-1',
  provider_id: 'provider-1',
  provider_name: 'OpenAI',
  provider_kind: 'openai',
  model_id: 'gpt-4o-mini',
  display_name: 'GPT 4o Mini',
  description: 'Fast model for model workspace tests',
  model_type: 'llm',
  status: 'available',
  context_window: 128000,
  max_output_tokens: null,
  lifecycle: null,
  sync_status: 'in_sync',
  source: 'platform',
  month_calls: 2,
  today_calls: 1,
  month_tokens: 2000,
  month_cost_amount: 2.5,
  currency: 'USD',
  avg_latency_ms: 240,
  recent_exception_count: 0,
  last_run_at: '2026-05-31T08:30:00.000Z',
  last_synced_at: '2026-05-31T08:00:00.000Z',
  updated_at: '2026-05-31T08:00:00.000Z',
  owner: null,
  region: null,
  unit_price: null,
  action_enabled: true,
}

const mockProviderModel = {
  id: 'model-1',
  provider_id: 'provider-1',
  provider_kind: 'openai',
  model_id: 'gpt-4o-mini',
  display_name: 'GPT 4o Mini',
  description: 'Fast model for model workspace tests',
  capabilities_json: {
    model_type: 'llm',
    capabilities: ['chat', 'vision'],
  },
  config_json: {},
  architecture_json: {
    modality: 'text+image->text',
    input_modalities: ['text', 'image'],
    output_modalities: ['text'],
    tokenizer: 'GPT',
  },
  capability_matrix_json: {
    chat: { catalog: 'supported', diagnostics: 'passed', runtime: 'supported', merged: true, user_override: 'auto' },
    image_output: { catalog: 'unsupported', diagnostics: 'skipped', runtime: 'unsupported', merged: false, user_override: 'auto' },
    reasoning: { catalog: 'supported', diagnostics: 'failed', runtime: 'supported', merged: false, user_override: 'enable_after_diagnostics' },
  },
  parameter_config_json: {
    max_input_files: 20,
    max_image_count: 10,
    supported_parameters: ['temperature', 'top_p', 'tools', 'response_format'],
    default_parameters: { temperature: 0.7, top_p: 1, max_tokens: 4096 },
  },
  pricing_json: {
    currency: 'USD',
    pricing_source: 'catalog',
    prompt: { amount: 0.15, unit: '1M_tokens' },
    completion: { amount: 0.6, unit: '1M_tokens' },
  },
  diagnostics_json: {
    last_test_status: 'failed',
    last_test_error: 'reasoning.effort rejected by upstream',
    support: { catalog: 'trusted', diagnostics: 'partial', runtime: 'callable' },
    runtime_stats: { month_calls: 12840, month_tokens: 38200000, avg_latency_ms: 1749, error_rate: 0.008 },
  },
  context_window: 128000,
  max_output_tokens: 16384,
  status: 'active',
  lifecycle_status: 'stable',
  raw_meta: { id: 'gpt-4o-mini' },
  source: 'platform',
  platform_model_id: 'platform-gpt-4o-mini',
  sync_status: 'in_sync',
  user_overrides_json: { fields: ['pricing_json'] },
  last_synced_at: '2026-05-31T08:00:00.000Z',
  created_at: '2026-05-30T08:00:00.000Z',
  updated_at: '2026-05-31T08:00:00.000Z',
}

const mockClaudeProviderModel = {
  id: 'model-claude-opus',
  provider_id: 'provider-anthropic',
  provider_kind: 'anthropic',
  model_id: 'claude-opus-4-8',
  display_name: 'Claude Opus 4.8',
  description: 'Latest Claude Opus model for model workspace tests',
  capabilities_json: {
    model_type: 'multimodal',
    capabilities: ['chat', 'vision'],
  },
  config_json: {},
  architecture_json: {
    family: 'claude',
    provider: 'anthropic',
    generation: '4.8',
  },
  capability_matrix_json: {
    chat: { catalog: 'supported', diagnostics: 'passed', runtime: 'supported', merged: true, user_override: 'auto' },
    vision: { catalog: 'supported', diagnostics: 'passed', runtime: 'supported', merged: true, user_override: 'auto' },
    embedding: { catalog: 'unsupported', diagnostics: 'skipped', runtime: 'unsupported', merged: false, user_override: 'auto' },
  },
  parameter_config_json: {
    supported_parameters: ['temperature', 'top_p', 'max_tokens'],
    default_parameters: { temperature: 0.7, top_p: 1, max_tokens: 1024 },
    limits: { context_window: 1000000, max_output_tokens: 128000 },
  },
  pricing_json: {
    currency: 'USD',
    unit: 'mtok',
    input: 5,
    output: 25,
  },
  diagnostics_json: {
    test_chat_supported: true,
    test_embeddings_supported: false,
  },
  context_window: 1000000,
  max_output_tokens: 128000,
  status: 'active',
  lifecycle_status: 'stable',
  raw_meta: { id: 'claude-opus-4-8' },
  source: 'platform',
  platform_model_id: 'platform-claude-opus-4-8',
  sync_status: 'in_sync',
  user_overrides_json: null,
  last_synced_at: '2026-06-08T08:15:00.000Z',
  created_at: '2026-06-08T08:00:00.000Z',
  updated_at: '2026-06-08T08:00:00.000Z',
}

const mockProviderRow = {
  id: 'provider-1',
  name: 'OpenAI',
  kind: 'openai',
  status: 'online',
  available_models: 1,
  total_models: 1,
  model_types: ['llm'],
  month_calls: 2,
  month_tokens: 2000,
  month_cost_amount: 2.5,
  currency: 'USD',
  avg_latency_ms: 240,
  recent_exception_count: 0,
  availability: null,
  last_sync_at: '2026-05-31T08:00:00.000Z',
  last_healthcheck_at: '2026-05-31T08:00:00.000Z',
  updated_at: '2026-05-31T08:00:00.000Z',
  owner: null,
  region: null,
  quota_used: null,
  quota_limit: null,
  quota_percent: null,
}

const mockClaudeProviderRow = {
  ...mockProviderRow,
  id: 'provider-anthropic',
  name: 'Claude / Anthropic',
  kind: 'anthropic',
  available_models: 1,
  total_models: 1,
  model_types: ['multimodal'],
  month_cost_amount: 0,
  last_sync_at: '2026-06-08T08:15:00.000Z',
  last_healthcheck_at: '2026-06-08T08:00:00.000Z',
  updated_at: '2026-06-08T08:00:00.000Z',
}

async function mockModelApi(page: Page) {
  const modelRequests: string[] = []
  const providerRequests: string[] = []
  const providerCreateRequests: any[] = []
  const providerPatchRequests: any[] = []
  const providerHealthRequests: string[] = []
  const providerSyncRequests: string[] = []
  const providerSyncJobRequests: string[] = []
  const modelCreateRequests: any[] = []
  const modelPatchRequests: any[] = []
  const modelDeleteRequests: string[] = []
  const providers: any[] = [{ ...mockProvider }, { ...mockClaudeProvider }]
  const providerRows: any[] = [{ ...mockProviderRow }, { ...mockClaudeProviderRow }]
  const providerModels: any[] = [{ ...mockProviderModel }, { ...mockClaudeProviderModel }]
  let nextProviderId = 2
  let nextModelId = 2

  await page.route('**/api/v1/modelhub/workbench/overview', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          summary: mockSummary,
          model_tabs: { all: 1, text: 1, embedding: 0, multimodal: 0, rerank: 0, disabled: 0, abnormal: 0 },
          provider_tabs: { all: 1, online: 1, disabled: 0, error: 0 },
          trend: [{ date: '2026-05-31', calls: 2, tokens: 2000, cost_amount: 2.5, avg_latency_ms: 240 }],
          cost_share: [{ id: 'provider-1', label: 'OpenAI', provider_kind: 'openai', value: 2.5, currency: 'USD' }],
          top_models: [mockModelRow],
          top_providers: [mockProviderRow],
          quota_reminders: [{ id: 'provider-1', label: 'OpenAI', status: 'normal', quota_used: null, quota_limit: null, quota_percent: null, remaining_quota: null }],
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    modelRequests.push(route.request().url())
    const requestUrl = new URL(route.request().url())
    const pageSize = Number(requestUrl.searchParams.get('page_size') || 50)
    const useNextPage = requestUrl.searchParams.get('page_token') === 'next-model-page'
    const rows = useNextPage ? [] : providerModels.map((model) => ({
      ...mockModelRow,
      id: model.id,
      provider_id: model.provider_id,
      provider_name: providers.find((provider) => provider.id === model.provider_id)?.name || mockModelRow.provider_name,
      provider_kind: model.provider_kind,
      model_id: model.model_id,
      display_name: model.display_name,
      description: model.description,
      model_type: model.capabilities_json?.model_type || mockModelRow.model_type,
      status: model.status === 'disabled' ? 'disabled' : model.status === 'error' ? 'abnormal' : 'available',
      context_window: model.context_window,
      max_output_tokens: model.max_output_tokens,
      lifecycle_status: model.lifecycle_status,
      sync_status: model.sync_status,
      source: model.source,
      last_synced_at: model.last_synced_at,
      updated_at: model.updated_at,
    }))
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          summary: { ...mockSummary, total_models: providerModels.length, available_models: providerModels.filter((model) => model.status === 'active').length },
          tabs: { all: providerModels.length, text: providerModels.length, embedding: 0, multimodal: 0, rerank: 0, disabled: providerModels.filter((model) => model.status === 'disabled').length, abnormal: providerModels.filter((model) => model.status === 'error').length },
          items: rows,
          page_size: pageSize,
          next_page_token: !useNextPage ? 'next-model-page' : null,
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/workbench/providers**', async (route) => {
    providerRequests.push(route.request().url())
    const requestUrl = new URL(route.request().url())
    const pageSize = Number(requestUrl.searchParams.get('page_size') || 50)
    const useNextPage = requestUrl.searchParams.get('page_token') === 'next-provider-page'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          summary: { ...mockSummary, total_providers: providerRows.length, online_providers: providerRows.filter((provider) => provider.status === 'online').length },
          tabs: {
            all: providerRows.length,
            online: providerRows.filter((provider) => provider.status === 'online').length,
            disabled: providerRows.filter((provider) => provider.status === 'disabled').length,
            error: providerRows.filter((provider) => provider.status === 'error').length,
          },
          items: useNextPage ? [] : providerRows,
          page_size: pageSize,
          next_page_token: !useNextPage ? 'next-provider-page' : null,
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/providers/support-matrix', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          providers: [
            {
              provider_kind: 'openai',
              display_name: 'OpenAI',
              support_status: 'supported',
              configured: true,
              provider_count: 1,
              configured_provider_ids: ['provider-1'],
              chat_supported: true,
              embeddings_supported: true,
              catalog_supported: true,
              notes: null,
            },
            {
              provider_kind: 'anthropic',
              display_name: 'Claude / Anthropic',
              support_status: 'supported',
              configured: true,
              provider_count: 1,
              configured_provider_ids: ['provider-anthropic'],
              chat_supported: true,
              embeddings_supported: false,
              catalog_supported: true,
              notes: 'Claude catalog, healthcheck, and chat diagnostics are supported; embeddings are not supported by Anthropic.',
            },
          ],
          adapter_backends: [
            {
              adapter_backend: 'native',
              display_name: 'Native',
              available: true,
              install_hint: null,
            },
            {
              adapter_backend: 'litellm',
              display_name: 'LiteLLM SDK',
              available: true,
              install_hint: null,
            },
          ],
          provider_presets: [
            {
              provider_kind: 'openai',
              display_name: 'OpenAI',
              default_adapter_backend: 'native',
              supported_adapter_backends: ['native', 'litellm'],
              litellm_provider: 'openai',
              requires_base_url: false,
              credential_optional: false,
            },
            {
              provider_kind: 'anthropic',
              display_name: 'Claude / Anthropic',
              default_adapter_backend: 'litellm',
              supported_adapter_backends: ['litellm'],
              litellm_provider: 'anthropic',
              requires_base_url: false,
              credential_optional: false,
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/providers/*/models**', async (route) => {
    const url = route.request().url()
    const modelMatch = url.match(/\/api\/v1\/modelhub\/providers\/([^/]+)\/models(?:\/([^/?]+))?/)
    const providerId = modelMatch?.[1] || mockProvider.id
    const provider = providers.find((item) => item.id === providerId) || mockProvider
    const modelId = modelMatch?.[2]
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      modelCreateRequests.push(body)
      const created = {
        ...mockProviderModel,
        ...body,
        id: `model-${nextModelId++}`,
        provider_id: providerId,
        provider_kind: provider.kind,
        sync_status: 'never_synced',
        created_at: '2026-05-31T09:00:00.000Z',
        updated_at: '2026-05-31T09:00:00.000Z',
      }
      providerModels.push(created)
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: created }),
      })
      return
    }

    if (route.request().method() === 'PATCH') {
      const body = route.request().postDataJSON()
      modelPatchRequests.push(body)
      const existing = providerModels.find((model) => model.id === modelId) || providerModels[0]
      Object.assign(existing, body, { updated_at: '2026-05-31T09:00:00.000Z' })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: existing,
        }),
      })
      return
    }

    if (route.request().method() === 'DELETE') {
      modelDeleteRequests.push(url)
      const index = providerModels.findIndex((model) => model.id === modelId)
      if (index >= 0) providerModels.splice(index, 1)
      await route.fulfill({ status: 204 })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: providerModels.filter((model) => model.provider_id === providerId),
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/providers**', async (route) => {
    const url = route.request().url()
    if (url.includes('/api/v1/modelhub/providers/support-matrix')) {
      await route.fallback()
      return
    }
    if (/\/api\/v1\/modelhub\/providers\/[^/]+\/models/.test(url)) {
      await route.fallback()
      return
    }

    if (/\/api\/v1\/modelhub\/providers\/[^/]+\/healthcheck/.test(url)) {
      providerHealthRequests.push(url)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { status: 'ok', message: 'healthcheck_ok', checked_at: '2026-05-31T09:00:00.000Z' } }),
      })
      return
    }

    if (/\/api\/v1\/modelhub\/providers\/[^/]+\/sync-from-platform/.test(url)) {
      providerSyncRequests.push(url)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            id: 'sync-job-1',
            provider_id: 'provider-1',
            status: 'succeeded',
            diff_json: { added: ['gpt-4.1'], updated: [], skipped_removed: [] },
            error: null,
            started_at: '2026-05-31T09:00:00.000Z',
            ended_at: '2026-05-31T09:00:01.000Z',
            created_at: '2026-05-31T09:00:00.000Z',
            updated_at: '2026-05-31T09:00:01.000Z',
          },
        }),
      })
      return
    }

    if (/\/api\/v1\/modelhub\/providers\/[^/]+\/sync-jobs/.test(url)) {
      providerSyncJobRequests.push(url)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            items: [{
              id: 'sync-job-1',
              provider_id: 'provider-1',
              status: 'succeeded',
              diff_json: { added: ['gpt-4.1'] },
              error: null,
              started_at: '2026-05-31T09:00:00.000Z',
              ended_at: '2026-05-31T09:00:01.000Z',
              created_at: '2026-05-31T09:00:00.000Z',
              updated_at: '2026-05-31T09:00:01.000Z',
            }],
            page_size: 1,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON()
      providerCreateRequests.push(body)
      const created = {
        ...mockProvider,
        ...body,
        id: `provider-${nextProviderId++}`,
        created_at: '2026-05-31T09:00:00.000Z',
        updated_at: '2026-05-31T09:00:00.000Z',
      }
      providers.push(created)
      providerRows.push({
        ...mockProviderRow,
        id: created.id,
        name: created.name,
        kind: created.kind,
        status: created.status === 'error' ? 'error' : created.status === 'disabled' ? 'disabled' : 'online',
        available_models: 0,
        total_models: 0,
        model_types: [],
        last_sync_at: null,
        last_healthcheck_at: null,
        updated_at: created.updated_at,
      })
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: created }),
      })
      return
    }

    if (route.request().method() === 'PATCH') {
      const body = route.request().postDataJSON()
      providerPatchRequests.push(body)
      const providerId = url.match(/\/providers\/([^/?]+)/)?.[1]
      const existing = providers.find((provider) => provider.id === providerId) || providers[0]
      Object.assign(existing, body, { updated_at: '2026-05-31T09:00:00.000Z' })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: existing,
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: providers,
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  return {
    modelRequests,
    providerRequests,
    providerCreateRequests,
    providerPatchRequests,
    providerHealthRequests,
    providerSyncRequests,
    providerSyncJobRequests,
    modelCreateRequests,
    modelPatchRequests,
    modelDeleteRequests,
  }
}

let apiState: Awaited<ReturnType<typeof mockModelApi>>

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  apiState = await mockModelApi(page)
})

test('model sidebar reads runtime summary instead of generating fake usage', () => {
  const source = fs.readFileSync(path.resolve(process.cwd(), 'app/routes/model/ui/box-sidebar.tsx'), 'utf-8')
  expect(source).toContain('getModelWorkbenchOverview')
  expect(source).not.toContain('Math.random')
  expect(source).not.toContain('totalModels: 42')
  expect(source).not.toContain('apiUsage: 8750')
})

test('model routes expose overview library and provider pages separately', async ({ page }) => {
  await page.goto('/models', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Model Overview' })).toBeVisible({ timeout: 30000 })

  await page.goto('/models/library', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Model Library' })).toBeVisible({ timeout: 30000 })
  await expect(page.getByText('GPT 4o Mini')).toBeVisible()
  await expect(page.getByText('Claude Opus 4.8')).toBeVisible()
  await page.getByRole('button', { name: /Text generation/ }).click()
  await page.getByPlaceholder('Search model name, provider, or type...').fill('GPT')
  await expect.poll(() => apiState.modelRequests.some((url) => {
    const parsed = new URL(url)
    return parsed.searchParams.get('tab') === 'text' && parsed.searchParams.get('keyword') === 'GPT'
  })).toBeTruthy()

  await page.goto('/models/providers', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Providers' })).toBeVisible({ timeout: 30000 })
  await expect(page.getByRole('row', { name: /OpenAI/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Claude \/ Anthropic/ })).toBeVisible()
})

test('provider settings exposes five tabs and saves provider configuration groups', async ({ page }) => {
  await page.goto('/models/providers', { waitUntil: 'domcontentloaded' })
  const openAiRow = page.getByRole('row', { name: /OpenAI/ })
  await expect(openAiRow).toBeVisible({ timeout: 30000 })

  await openAiRow.locator('button').first().click()
  await expect(page.getByRole('heading', { name: 'Provider Settings' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Basic' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Connection Auth' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Catalog Sync' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Diagnostics Runtime' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Security Observability' })).toBeVisible()

  await expect(page.getByLabel('Provider ID')).toHaveValue('provider-1')
  await page.getByLabel('Provider slug').fill('openai-production')
  await page.getByRole('tab', { name: 'Connection Auth' }).click()
  await page.getByLabel('Timeout (ms)').fill('45000')
  await page.getByLabel('Max retries').fill('4')
  await page.getByLabel('Retryable status codes').fill('429, 500, 502, 503, 504')
  await page.getByRole('tab', { name: 'Catalog Sync' }).click()
  await expect(page.locator('#last-synced-at')).toHaveValue('2026-05-31T08:15:00.000Z')
  await page.getByRole('switch', { name: 'Recreate removed models on sync' }).click()
  await page.getByLabel('Include models').fill('gpt-4o-mini\ngpt-4.1')
  await page.getByRole('tab', { name: 'Diagnostics Runtime' }).click()
  await expect(page.getByText('Capability display uses catalog, diagnostics, and runtime results.')).toBeVisible()
  await expect(page.getByText('Capability source matrix')).toBeVisible()
  await expect(page.locator('#last-healthcheck-at')).toHaveValue('2026-05-31T08:00:00.000Z')
  await page.getByRole('tab', { name: 'Security Observability' }).click()
  await page.getByRole('switch', { name: 'Trace enabled' }).click()
  await page.getByRole('button', { name: 'Save changes' }).click()

  await expect.poll(() => apiState.providerPatchRequests.length).toBe(1)
  const payload = apiState.providerPatchRequests[0]
  expect(payload.slug).toBe('openai-production')
  expect(payload.connection_config_json.timeout_ms).toBe(45000)
  expect(payload.connection_config_json.retry_policy.max_retries).toBe(4)
  expect(payload.connection_config_json.retry_policy.retryable_status_codes).toEqual([429, 500, 502, 503, 504])
  expect(payload.sync_policy_json.recreate_deleted).toBe(true)
  expect(payload.sync_policy_json.include_models).toEqual(['gpt-4o-mini', 'gpt-4.1'])
  expect(payload.auth_config_json.auth_type).toBe('bearer')
  expect(payload.runtime_config_json.runtime_support.chat).toBe(true)
  expect(payload.governance_config_json.trace_enabled).toBe(false)
})

test('model settings exposes five tabs and saves split model configuration groups', async ({ page }) => {
  await page.goto('/models/library', { waitUntil: 'domcontentloaded' })
  const modelRow = page.getByRole('row', { name: /GPT 4o Mini/ })
  await expect(modelRow).toBeVisible({ timeout: 30000 })

  await modelRow.locator('button').nth(1).click()
  await expect(page.getByRole('heading', { name: 'Edit model' })).toBeVisible()
  const modelListDialog = page.getByRole('dialog', { name: 'Edit model' })
  await modelListDialog.getByRole('button', { name: 'Edit' }).click()

  await expect(page.getByRole('heading', { name: 'Edit model' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Basic Info' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Capabilities' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Limits Params' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Pricing' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Diagnostics' })).toBeVisible()

  await page.getByLabel('Display name').fill('GPT 4o Mini Prod')
  await page.getByLabel('Source').selectOption('override')
  await page.getByLabel('Platform model ID').fill('platform-gpt-4o-mini-override')
  await page.getByLabel('Last seen at').fill('2026-06-08T09:30:00.000Z')
  await page.getByLabel('Lifecycle status').selectOption('preview')
  await page.getByLabel('Architecture modality').fill('text+image+file->text')
  await page.getByRole('tab', { name: 'Capabilities' }).click()
  await expect(page.getByText('Capability display uses catalog, diagnostics, and runtime results.')).toBeVisible()
  await expect(page.getByLabel('image_output merged')).toBeDisabled()
  await page.getByLabel('reasoning override').selectOption('force_on')
  await page.getByRole('tab', { name: 'Limits Params' }).click()
  await page.getByLabel('Context window').fill('256000')
  await page.getByLabel('Default max tokens').fill('8192')
  await page.getByRole('tab', { name: 'Pricing' }).click()
  await page.getByLabel('Completion price').fill('0.9')
  await page.getByRole('tab', { name: 'Diagnostics' }).click()
  await page.getByLabel('Last test error').fill('No current error.')
  await page.getByLabel('Support runtime').selectOption('not_callable')
  await page.getByLabel('Override reason').fill('Manual verification passed for reasoning.')
  await page.getByLabel('User overrides JSON').fill('{"fields":["pricing_json","capability_matrix_json"],"reason":"manual"}')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => apiState.modelPatchRequests.length).toBe(1)
  const payload = apiState.modelPatchRequests[0]
  expect(payload.display_name).toBe('GPT 4o Mini Prod')
  expect(payload.source).toBe('override')
  expect(payload.platform_model_id).toBe('platform-gpt-4o-mini-override')
  expect(payload.last_synced_at).toBe('2026-06-08T09:30:00.000Z')
  expect(payload.lifecycle_status).toBe('preview')
  expect(payload.architecture_json.modality).toBe('text+image+file->text')
  expect(payload.capabilities_json.image_output).toBe(false)
  expect(payload.capability_matrix_json.reasoning.user_override).toBe('force_on')
  expect(payload.capability_matrix_json.image_output.merged).toBe(false)
  expect(payload.context_window).toBe(256000)
  expect(payload.parameter_config_json.default_parameters.max_tokens).toBe(8192)
  expect(payload.pricing_json.completion.amount).toBe(0.9)
  expect(payload.diagnostics_json.last_test_error).toBe('No current error.')
  expect(payload.diagnostics_json.support.runtime).toBe('not_callable')
  expect(payload.diagnostics_json.override_reason).toBe('Manual verification passed for reasoning.')
  expect(payload.user_overrides_json.reason).toBe('manual')
})

test('provider page creates providers and runs healthcheck and sync actions', async ({ page }) => {
  await page.goto('/models/providers', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Providers' })).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: 'Add Provider' }).click()
  await expect(page.getByRole('heading', { name: 'Provider Settings' })).toBeVisible()
  await page.getByRole('combobox').first().click()
  await page.getByRole('option', { name: 'Claude / Anthropic' }).click()
  await page.getByLabel('Provider slug').fill('claude-main-e2e')
  await page.getByLabel('Provider name').fill('Claude Main E2E')
  await page.getByRole('tab', { name: 'Connection Auth' }).click()
  await page.getByLabel('Base URL').fill('https://api.anthropic.com')
  await page.getByLabel('Credential secret ID').fill('sec_id_anthropic')
  await page.getByLabel('Timeout (ms)').fill('51000')
  await page.getByRole('tab', { name: 'Catalog Sync' }).click()
  await page.getByLabel('Include models').fill('claude-opus-4-8\nclaude-sonnet-4-6')
  await page.getByLabel('Exclude models').fill('claude-legacy')
  await page.getByRole('tab', { name: 'Security Observability' }).click()
  await page.getByLabel('Allowed domains').fill('api.anthropic.com')
  await page.getByRole('button', { name: 'Save changes' }).click()

  await expect.poll(() => apiState.providerCreateRequests.length).toBe(1)
  const createPayload = apiState.providerCreateRequests[0]
  expect(createPayload.kind).toBe('anthropic')
  expect(createPayload.slug).toBe('claude-main-e2e')
  expect(createPayload.name).toBe('Claude Main E2E')
  expect(createPayload.base_url).toBe('https://api.anthropic.com')
  expect(createPayload.credential_secret_id).toBe('sec_id_anthropic')
  expect(createPayload.connection_config_json.timeout_ms).toBe(51000)
  expect(createPayload.sync_policy_json.include_models).toEqual(['claude-opus-4-8', 'claude-sonnet-4-6'])
  expect(createPayload.sync_policy_json.exclude_models).toEqual(['claude-legacy'])
  expect(createPayload.governance_config_json.egress_policy.allowed_domains).toEqual(['api.anthropic.com'])
  await expect(page.getByRole('row', { name: /Claude Main E2E/ })).toBeVisible()

  const openAiRow = page.getByRole('row', { name: /OpenAI/ }).first()
  await openAiRow.locator('button').nth(1).click()
  await expect.poll(() => apiState.providerHealthRequests.length).toBe(1)
  await expect(page.getByText('Provider connection is healthy.')).toBeVisible()

  await openAiRow.locator('button').nth(2).click()
  await expect.poll(() => apiState.providerSyncRequests.length).toBe(1)
  await expect(page.getByText('Model sync job submitted.')).toBeVisible()
})

test('provider page surfaces healthcheck and sync failures without losing row state', async ({ page }) => {
  await page.route('**/api/v1/modelhub/providers/*/healthcheck', async (route) => {
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'health failed' }) })
  }, { times: 1 })
  await page.route('**/api/v1/modelhub/providers/*/sync-from-platform', async (route) => {
    await route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'sync failed' }) })
  }, { times: 1 })

  await page.goto('/models/providers', { waitUntil: 'domcontentloaded' })
  const openAiRow = page.getByRole('row', { name: /OpenAI/ }).first()
  await expect(openAiRow).toBeVisible({ timeout: 15000 })

  await openAiRow.locator('button').nth(1).click()
  await expect(page.getByText('Provider connection failed.')).toBeVisible()
  await expect(openAiRow).toBeVisible()

  await openAiRow.locator('button').nth(2).click()
  await expect(page.getByText('Unable to start model sync.')).toBeVisible()
  await expect(openAiRow).toBeVisible()
})

test('model management creates toggles and deletes provider models', async ({ page }) => {
  await page.goto('/models/library', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Model Library' })).toBeVisible({ timeout: 15000 })

  await page.getByRole('button', { name: 'Create / Import Model' }).click()
  await expect(page.getByRole('heading', { name: 'Create / Import Model' })).toBeVisible()
  await page.getByRole('button', { name: 'Add model' }).click()
  await expect(page.getByRole('heading', { name: 'Add model' })).toBeVisible()
  await page.getByLabel('Model ID', { exact: true }).fill('gpt-local-test')
  await page.getByLabel('Display name').fill('GPT Local Test')
  await page.getByLabel('Description').fill('Local model created from e2e')
  await page.getByRole('tab', { name: 'Limits Params' }).click()
  await page.getByLabel('Context window').fill('64000')
  await page.getByLabel('Default max tokens').fill('2048')
  await page.getByRole('tab', { name: 'Pricing' }).click()
  await page.getByLabel('Prompt price').fill('0.2')
  await page.getByLabel('Completion price').fill('0.8')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => apiState.modelCreateRequests.length).toBe(1)
  const createPayload = apiState.modelCreateRequests[0]
  expect(createPayload.model_id).toBe('gpt-local-test')
  expect(createPayload.display_name).toBe('GPT Local Test')
  expect(createPayload.description).toBe('Local model created from e2e')
  expect(createPayload.context_window).toBe(64000)
  expect(createPayload.parameter_config_json.default_parameters.max_tokens).toBe(2048)
  expect(createPayload.pricing_json.prompt.amount).toBe(0.2)
  expect(createPayload.pricing_json.completion.amount).toBe(0.8)

  await page.goto('/models/library', { waitUntil: 'domcontentloaded' })
  const modelRow = page.getByRole('row', { name: /GPT 4o Mini/ })
  await expect(modelRow).toBeVisible({ timeout: 15000 })
  await modelRow.locator('button').nth(1).click()
  const gptMiniSwitch = page.getByRole('switch', { name: 'Disable model' }).first()
  await expect(gptMiniSwitch).toBeVisible()
  await gptMiniSwitch.click()
  await expect.poll(() => apiState.modelPatchRequests.some((payload) => payload.status === 'disabled')).toBeTruthy()

  page.once('dialog', async (dialog) => {
    expect(dialog.message()).toContain('delete this model')
    await dialog.accept()
  })
  await page.getByRole('button', { name: /Delete GPT 4o Mini/ }).click()
  await expect.poll(() => apiState.modelDeleteRequests.some((url) => url.includes('/providers/provider-1/models/model-1'))).toBeTruthy()
})

test('model and provider filters include query params and pagination tokens', async ({ page }) => {
  await page.goto('/models/library', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Model Library' })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: /Text generation/ }).click()
  await page.getByPlaceholder('Search model name, provider, or type...').fill('GPT')
  await page.getByRole('button', { name: '2', exact: true }).click()
  await expect.poll(() => apiState.modelRequests.some((url) => {
    const parsed = new URL(url)
    return parsed.searchParams.get('tab') === 'text' &&
      parsed.searchParams.get('keyword') === 'GPT' &&
      parsed.searchParams.get('page_token') === 'next-model-page'
  })).toBeTruthy()

  await page.goto('/models/providers', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('heading', { name: 'Providers' })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: /Enabled/ }).click()
  await page.getByPlaceholder('Search provider name...').fill('OpenAI')
  await page.getByRole('button', { name: '2', exact: true }).click()
  await expect.poll(() => apiState.providerRequests.some((url) => {
    const parsed = new URL(url)
    return parsed.searchParams.get('tab') === 'online' &&
      parsed.searchParams.get('keyword') === 'OpenAI' &&
      parsed.searchParams.get('page_token') === 'next-provider-page'
  })).toBeTruthy()
})
