import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockWorkflowWorkbench = {
  summary: {
    total_workflows: 1,
    published_workflows: 1,
    running_workflows: 1,
    today_runs: 8,
    avg_latency_ms: 1500,
    success_rate: 100,
    recent_exceptions: 0,
    updated_at: '2026-02-16T10:00:00.000Z',
  },
  tabs: {
    all: 1,
    high_volume: 0,
    publishing: 0,
    abnormal: 0,
    draft: 0,
  },
  items: [
    {
      id: 'workflow-1',
      name: 'Demo Workflow',
      description: 'Workflow for e2e test',
      summary: 'Runtime-backed workflow row',
      status: 'running',
      linked_agents: ['DA'],
      linked_agent_count: 1,
      today_runs: 8,
      avg_latency_ms: 1500,
      success_rate: 100,
      recent_exception_count: 0,
      owner: 'user-1',
      last_run_at: '2026-02-16T10:05:00.000Z',
      action_enabled: true,
      updated_at: '2026-02-16T10:00:00.000Z',
    },
  ],
  page_size: 1,
  next_page_token: null,
}

const mockWorkflow = {
  id: 'workflow-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Demo Workflow',
  description: 'Workflow for e2e test',
  summary: 'Runtime-backed workflow row',
  status: 'active',
  visibility: 'private',
  icon_url: null,
  category: 'support',
  tags: [],
  owner_user_id: 'user-1',
  current_version_id: 'workflow-version-1',
  published_version_id: null,
  metadata_json: {},
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
  updated_at: '2026-02-16T10:00:00.000Z',
  deleted_at: null,
}

const mockWorkflowVersion = {
  id: 'workflow-version-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  workflow_id: 'workflow-1',
  graph_json: {
    name: 'Demo Workflow',
    description: 'Workflow for e2e test',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: { value: { type: 'object' } } },
    graph: {
      nodes: [
        { id: 'input-1', type: 'transform', name: 'Input', params: {}, ui: { builder_type: 'text-node', position: { x: 100, y: 100 }, data: { label: 'Input' } } },
        { id: 'output-1', type: 'output', name: 'Output', params: { value: '{{ steps.input-1.output }}' }, ui: { builder_type: 'output-node', position: { x: 420, y: 100 }, data: { label: 'Output' } } },
      ],
      edges: [{ id: 'e1', from: 'input-1', to: 'output-1' }],
    },
  },
  created_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
}

async function mockWorkflowApi(page: Page) {
  await page.route('**/api/v1/workflows**', async (route) => {
    const method = route.request().method()
    const url = new URL(route.request().url())
    if (method === 'POST' && url.pathname.endsWith('/api/v1/workflows/templates/ticket-triage')) {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            ...mockWorkflow,
            id: 'workflow-ticket-template',
            name: 'Ticket triage',
            current_version_id: 'workflow-version-ticket-template',
            metadata_json: { template_key: 'ticket_triage' },
          },
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workbench/items')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          data: {
            items: mockWorkflowWorkbench.items,
            page_size: 1,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workbench')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockWorkflowWorkbench }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workflow-1/version/current')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockWorkflowVersion }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workflow-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockWorkflow }),
      })
      return
    }

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
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockWorkflowApi(page)
})

test('workflow workbench renders api data', async ({ page }) => {
  await page.goto('/workflow', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Demo Workflow', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Runtime-backed workflow row')).toBeVisible()
  await expect(page.getByRole('table').getByText('1.5s')).toBeVisible()
})

test('workflow builder creates ticket triage template from templates tab', async ({ page }) => {
  let templateRequests = 0
  page.on('request', (request) => {
    if (request.method() === 'POST' && request.url().endsWith('/api/v1/workflows/templates/ticket-triage')) {
      templateRequests += 1
    }
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Templates' }).click()
  await page.getByRole('button', { name: /Ticket triage/ }).click()

  await expect.poll(() => templateRequests).toBe(1)
  await expect(page).toHaveURL(/\/workflow\/workflow-ticket-template\/build$/)
})
