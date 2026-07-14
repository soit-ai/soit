import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockAgent = {
  id: 'agent-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Demo Agent',
  description: 'Agent for e2e test',
  status: 'active',
  visibility: 'private',
  icon_url: null,
  category: null,
  is_public: false,
  featured: false,
  downloads_count: 0,
  rating: null,
  reviews_count: 0,
  published_at: null,
  tags: ['demo'],
  current_version_id: 'ver-1',
  published_version_id: 'ver-1',
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
  updated_at: '2026-02-16T10:00:00.000Z',
  deleted_at: null,
}

const mockAgentVersion = {
  id: 'ver-1',
  agent_id: 'agent-1',
  version: 1,
  status: 'draft',
  spec_schema: 'agent_spec_v1',
  spec_json: {
    system_prompt: 'Use workspace tools when needed.',
    bindings: {
      model_ref: 'model:test:primary',
      knowledge_refs: [],
      tool_refs: [],
      workflow_refs: [],
      skill_refs: [],
    },
    params: {
      temperature: 0.2,
    },
    limits: {
      max_iterations: 8,
    },
  },
  checksum: 'checksum-1',
  created_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
}

const mockCapabilities = [
  {
    ref: 'tool:http:plugin_search',
    kind: 'tool',
    name: 'plugin_search',
    source_kind: 'plugin',
    source_id: 'search',
    source_version: '2.3.4',
    metadata_json: {
      plugin: {
        name: 'search',
        version: '2.3.4',
      },
      metadata_json: {
        adapter: 'plugin',
      },
    },
  },
  {
    ref: 'tool:http:request',
    kind: 'tool',
    name: 'HTTP Request',
    source_kind: 'builtin',
    source_id: 'tool:http:request',
    source_version: '1.0.0',
    metadata_json: {},
  },
]

const mockWorkbench = {
  summary: {
    total_agents: 1,
    configured_agents: 1,
    running_agents: 1,
    today_calls: 12,
    avg_latency_ms: 180,
    success_rate: 100,
    pending_exceptions: 0,
    updated_at: '2026-02-16T10:00:00.000Z',
  },
  tabs: {
    all: 1,
    high_calls: 0,
    low_success: 0,
    long_latency: 0,
    unconfigured: 0,
  },
  items: [
    {
      id: mockAgent.id,
      name: mockAgent.name,
      description: mockAgent.description,
      status: 'running',
      capabilities: [
        {
          type: 'model',
          target_id: null,
          target_key: 'model:test:primary',
          label: 'model:test:primary',
        },
        {
          type: 'knowledge',
          target_id: null,
          target_key: 'knowledge:demo',
          label: 'knowledge:demo',
        },
      ],
      today_calls: 12,
      avg_latency_ms: 180,
      success_rate: 100,
      recent_exception_count: 0,
      owner: 'user-1',
      last_run_at: '2026-02-16T10:05:00.000Z',
      action_enabled: true,
      updated_at: mockAgent.updated_at,
    },
  ],
  page_size: 1,
  next_page_token: null,
}

async function mockAgentApi(page: Page) {
  await page.route('**/api/v1/agents**', async (route) => {
    const method = route.request().method()
    const url = new URL(route.request().url())

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/agent-1/versions')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            items: [mockAgentVersion],
            page_size: 50,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (method === 'POST' && url.pathname.endsWith('/api/v1/agents/agent-1/versions')) {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            ...mockAgentVersion,
            id: 'ver-2',
            version: 2,
            spec_json: route.request().postDataJSON(),
          },
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/agent-1/releases')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            items: [],
            page_size: 20,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/agent-1/bindings')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: [],
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/agent-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockAgent }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/workbench/items')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            items: mockWorkbench.items,
            page_size: 1,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/agents/workbench')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockWorkbench }),
      })
      return
    }

    if (method === 'POST' && url.pathname.endsWith('/api/v1/agents')) {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockAgent }),
      })
      return
    }

    if (method !== 'GET' || !url.pathname.endsWith('/api/v1/agents')) {
      await route.fallback()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockAgent],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

async function mockAgentDetailDependencies(page: Page) {
  await page.route('**/api/v1/evaluations/regression-reports/latest**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          id: 'report-1',
          tenant_id: 'tenant-1',
          workspace_id: 'workspace-1',
          subject_kind: 'agent',
          subject_id: 'agent-1',
          subject_version_id: 'ver-1',
          passed: true,
          summary_json: { total: 2, passed: 2, failed: 0 },
          metrics_json: { avg_latency_ms: 120, avg_cost_amount: 0.07 },
          case_results_json: [
            { case_id: 'case-1', name: 'refund policy', passed: true },
            { case_id: 'case-2', name: 'ticket handoff', passed: true },
          ],
          created_by: 'user-1',
          created_at: '2026-02-16T10:02:00.000Z',
        },
      }),
    })
  })

  await page.route('**/api/v1/agents/capabilities**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: mockCapabilities,
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/knowledge**', async (route) => {
    const url = new URL(route.request().url())
    if (!url.pathname.endsWith('/api/v1/knowledge')) {
      await route.fallback()
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          summary: {
            total_models: 1,
            available_models: 1,
            total_providers: 1,
            online_providers: 1,
            month_calls: 0,
            month_tokens: 0,
            month_cost_amount: 0,
            abnormal_models: 0,
            updated_at: '2026-02-16T10:00:00.000Z',
          },
          tabs: {
            all: 1,
            text: 1,
            embedding: 0,
            multimodal: 0,
            rerank: 0,
            disabled: 0,
            abnormal: 0,
          },
          items: [
            {
              id: 'model-1',
              provider_id: 'provider-1',
              provider_name: 'Test Provider',
              provider_kind: 'test',
              model_id: 'model:test:primary',
              display_name: 'Test Primary',
              model_type: 'llm',
              status: 'available',
              sync_status: 'in_sync',
              source: 'platform',
              month_calls: 0,
              today_calls: 0,
              month_tokens: 0,
              month_cost_amount: 0,
              recent_exception_count: 0,
              action_enabled: true,
              updated_at: '2026-02-16T10:00:00.000Z',
            },
          ],
          page_size: 200,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/runs**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page_size: 5,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockAgentApi(page)
  await mockAgentDetailDependencies(page)
})

test('agent list renders api data', async ({ page }) => {
  await page.goto('/agents', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Demo Agent')).toBeVisible({ timeout: 15_000 })
})

test('agent create form accepts current agent semantics', async ({ page }) => {
  await page.goto('/agents', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: 'Create Agent' }).click()
  const dialog = page.getByRole('dialog', { name: 'Create Agent' })
  await dialog.getByPlaceholder('Agent name').fill('New Agent')
  await dialog.getByPlaceholder('Short description').fill('Created through e2e')
  await dialog.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('Demo Agent', { exact: true })).toBeVisible()
})

test('agent detail binds plugin-exported tools as tool refs', async ({ page }) => {
  let createVersionPayload: any
  await page.route('**/api/v1/agents/agent-1/versions', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    createVersionPayload = route.request().postDataJSON()
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          ...mockAgentVersion,
          id: 'ver-2',
          version: 2,
          spec_json: createVersionPayload,
        },
      }),
    })
  })

  await page.goto('/agents/agent-1', { waitUntil: 'domcontentloaded' })

  const pluginTool = page.getByRole('button', { name: /plugin_search/ })
  await expect(pluginTool).toBeVisible({ timeout: 15_000 })
  await expect(pluginTool).toContainText('tool:http:plugin_search')
  await expect(pluginTool).toContainText('Plugin')
  await expect(pluginTool).toContainText('search@2.3.4')

  await pluginTool.click()
  await page.getByRole('button', { name: 'Create Draft Version' }).click()

  await expect.poll(() => createVersionPayload).toBeTruthy()
  expect(createVersionPayload.bindings.tool_refs).toEqual(['tool:http:plugin_search'])
  expect(createVersionPayload.bindings).not.toHaveProperty('plugin_refs')
})

test('agent detail shows latest regression report before publishing', async ({ page }) => {
  await page.goto('/agents/agent-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Regression Gate', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Passed', { exact: true })).toBeVisible()
  await expect(page.getByText('2 / 2 cases')).toBeVisible()
  await expect(page.getByText('120 ms avg')).toBeVisible()
  await expect(page.getByText('$0.07 avg')).toBeVisible()
})
