import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'
import {
  CanonicalNodeValidationError,
  conditionForEdge,
  parseWorkflowVersion,
  serializeCanonicalNode,
  serializeWorkflowSpec,
  UnsupportedWorkflowEdgeError,
} from '../app/routes/workflow/detail/ui/build/workflow-spec'
import { canonicalBuilderTypes } from '../app/routes/workflow/detail/ui/build/canonical-node-registry'

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

const canonicalRuntimeTypes = [
  'input',
  'transform',
  'set_var',
  'llm',
  'retrieve',
  'tool',
  'condition',
  'output',
] as const

const canonicalNodeParams = {
  input: { select: ['question', 'locale'] },
  transform: {
    mapping: {
      question: '{{ steps.input.output.question }}',
      enabled: false,
      attempts: 0,
      metadata: { tags: [], source: '' },
    },
  },
  set_var: { key: 'approved', value: false },
  llm: {
    model: 'model:openai:gpt-4.1-mini',
    prompt: '{{ steps.transform.output.question }}',
    system: '',
    temperature: 0,
    max_tokens: 321,
  },
  retrieve: {
    knowledge_ref: 'knowledge:policy-handbook',
    query: '{{ steps.llm.output.result }}',
    top_k: 7,
    filters: { locale: 'en-US', archived: false },
    rerank_model: 'model:cohere:rerank-v3.5',
  },
  tool: {
    tool_ref: 'tool:http:create-ticket',
    arguments: { priority: 0, notify: false },
    input: '{{ steps.retrieve.output.result }}',
  },
  condition: { condition: '{{ steps.set-var.output.result }}' },
  output: { value: { answer: '{{ steps.llm.output.result }}', accepted: false } },
} as const

const canonicalWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Canonical Contract Workflow',
    version: '2026-07-19-custom',
    description: 'Preserve this workflow envelope',
    inputs_schema: {
      type: 'object',
      required: ['question'],
      properties: { question: { type: 'string', minLength: 2 } },
    },
    outputs_schema: {
      type: 'object',
      required: ['answer'],
      properties: { answer: { type: 'string' }, accepted: { type: 'boolean' } },
    },
    limits: { max_steps: 17, timeout_ms: 45_000, budget: 0, max_tool_calls: 0 },
    runtime: { engine: 'workflow_engine_v1' },
    policy: {
      registry_only_tools: true,
      default_timeout_ms: 12_000,
      default_retry_policy: { max_retries: 2, backoff_ms: 0 },
    },
    semantics: { on_error: 'compensate', concurrency: 3, pause_poll_ms: 250 },
    graph: {
      nodes: [
        {
          id: 'input',
          type: 'input',
          name: 'Canonical Input',
          params: canonicalNodeParams.input,
          ui: { builder_type: 'input-node', position: { x: 80, y: 80 }, data: { label: 'Canonical Input', presentation: 'source' } },
        },
        {
          id: 'transform',
          type: 'transform',
          name: 'Canonical Transform',
          params: canonicalNodeParams.transform,
          ui: { builder_type: 'transform-node', position: { x: 320, y: 80 }, data: { label: 'Canonical Transform', presentation: 'mapping' } },
        },
        {
          id: 'set-var',
          type: 'set_var',
          name: 'Canonical Variable',
          params: canonicalNodeParams.set_var,
          ui: { builder_type: 'variable-assignment-node', position: { x: 560, y: 80 }, data: { label: 'Canonical Variable', presentation: 'variable' } },
        },
        {
          id: 'llm',
          type: 'llm',
          name: 'Canonical LLM',
          params: canonicalNodeParams.llm,
          ui: {
            builder_type: 'llm-node',
            position: { x: 800, y: 80 },
            data: { label: 'Canonical LLM', modelName: 'stale:model', presentation: 'model-card' },
            panel_size: { width: 360, height: 240 },
            collapsed: false,
          },
        },
        {
          id: 'retrieve',
          type: 'retrieve',
          name: 'Canonical Retrieval',
          params: canonicalNodeParams.retrieve,
          ui: { builder_type: 'knowledge-search-node', position: { x: 1040, y: 80 }, data: { label: 'Canonical Retrieval', presentation: 'knowledge' } },
        },
        {
          id: 'tool',
          type: 'tool',
          name: 'Canonical Tool',
          params: canonicalNodeParams.tool,
          ui: { builder_type: 'tool-node', position: { x: 1280, y: 80 }, data: { label: 'Canonical Tool', presentation: 'action' } },
        },
        {
          id: 'cond',
          type: 'condition',
          name: 'Canonical Condition',
          params: canonicalNodeParams.condition,
          ui: { builder_type: 'conditional-node', position: { x: 1520, y: 80 }, data: { label: 'Canonical Condition', presentation: 'branch' } },
        },
        {
          id: 'output',
          type: 'output',
          name: 'Canonical Output',
          params: canonicalNodeParams.output,
          ui: { builder_type: 'output-node', position: { x: 1760, y: 80 }, data: { label: 'Canonical Output', presentation: 'sink' } },
        },
      ],
      edges: [
        { id: 'input-transform', from: 'input', to: 'transform', from_port: 'result', to_port: 'input', condition: null },
        { id: 'condition-true', from: 'cond', to: 'output', from_port: 'true', to_port: 'input' },
        { id: 'condition-false', from: 'cond', to: 'tool', from_port: 'false', to_port: 'input', condition: null },
        { id: 'condition-legacy-false', from: 'cond', to: 'retrieve', from_port: 'output-false', to_port: 'legacy-input', condition: 'false' },
        { id: 'condition-no-handle', from: 'cond', to: 'transform', condition: null },
        { id: 'condition-custom-null', from: 'cond', to: 'input', from_port: 'custom', condition: null },
      ],
    },
  },
}

const unsupportedWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Historical Workflow',
    version: 'legacy-v7',
    description: 'Must remain recoverable',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'legacy-python',
          type: 'python',
          name: 'Historical Python',
          params: { script: 'return input', timeout_seconds: 0 },
          ui: {
            builder_type: 'code-execution-node',
            position: { x: 42, y: 84 },
            data: { label: 'Historical Python', language: 'python', payload: { keep: true } },
            collapsed: false,
          },
        },
        {
          id: 'legacy-output',
          type: 'output',
          name: 'Historical Output',
          params: { value: '{{ steps.legacy-python.output.result }}' },
          ui: { builder_type: 'output-node', position: { x: 420, y: 84 }, data: { label: 'Historical Output' } },
        },
      ],
      edges: [
        {
          id: 'legacy-edge',
          from: 'legacy-python',
          to: 'legacy-output',
          from_port: 'legacy-result',
          to_port: 'legacy-input',
          condition: '{{ legacy.branch }}',
        },
      ],
    },
  },
}

const arbitraryConditionWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Arbitrary Condition Workflow',
    description: 'An unrecognized condition cannot be normalized safely',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'arbitrary-condition',
          type: 'condition',
          name: 'Arbitrary Condition',
          params: { condition: '{{ custom.predicate }}' },
          ui: {
            builder_type: 'conditional-node',
            position: { x: 120, y: 120 },
            data: { label: 'Arbitrary Condition' },
          },
        },
        {
          id: 'arbitrary-output',
          type: 'output',
          name: 'Arbitrary Output',
          params: { value: '{{ steps.arbitrary-condition.output.result }}' },
          ui: {
            builder_type: 'output-node',
            position: { x: 420, y: 120 },
            data: { label: 'Arbitrary Output' },
          },
        },
      ],
      edges: [
        {
          id: 'arbitrary-edge',
          from: 'arbitrary-condition',
          to: 'arbitrary-output',
          from_port: null,
          to_port: null,
          condition: '{{ custom.branch_expression }}',
        },
      ],
    },
  },
}

const invalidCanonicalWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Invalid Canonical Workflow',
    description: 'Missing canonical fields must not be invented',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'invalid-llm',
          type: 'llm',
          name: 'Invalid Canonical LLM',
          params: { prompt: '' },
          ui: {
            builder_type: 'llm-node',
            position: { x: 120, y: 120 },
            data: { label: 'Invalid Canonical LLM', modelName: 'stale:model-must-not-win' },
          },
        },
      ],
      edges: [],
    },
  },
}

const malformedCanonicalWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Malformed Canonical Metadata Workflow',
    description: 'Canonical runtime nodes with lossy metadata must remain recoverable',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'builder-non-string',
          type: 'llm',
          name: 'Builder Non String',
          params: { model: 'model:test:llm', prompt: 'hello' },
          ui: { builder_type: 42, position: { x: 40, y: 40 }, data: { label: 'Builder Non String' } },
        },
        {
          id: 'builder-noncanonical',
          type: 'llm',
          name: 'Builder Noncanonical',
          params: { model: 'model:test:llm', prompt: 'hello' },
          ui: { builder_type: 'prompt-node', position: { x: 280, y: 40 }, data: { label: 'Builder Noncanonical' } },
        },
        {
          id: 'builder-mismatch',
          type: 'llm',
          name: 'Builder Mismatch',
          params: { model: 'model:test:llm', prompt: 'hello' },
          ui: { builder_type: 'tool-node', position: { x: 520, y: 40 }, data: { label: 'Builder Mismatch' } },
        },
        {
          id: 'params-null',
          type: 'tool',
          name: 'Params Null',
          params: null,
          ui: { builder_type: 'tool-node', position: { x: 760, y: 40 }, data: { label: 'Params Null' } },
        },
        {
          id: 'params-array',
          type: 'output',
          name: 'Params Array',
          params: ['unexpected'],
          ui: { builder_type: 'output-node', position: { x: 1000, y: 40 }, data: { label: 'Params Array' } },
        },
        {
          id: 'params-primitive',
          type: 'condition',
          name: 'Params Primitive',
          params: 'unexpected',
          ui: { builder_type: 'conditional-node', position: { x: 1240, y: 40 }, data: { label: 'Params Primitive' } },
        },
        {
          id: 'params-unknown-key',
          type: 'transform',
          name: 'Params Unknown Key',
          params: { mapping: { value: '{{ inputs.value }}' }, legacy_mode: true },
          ui: { builder_type: 'transform-node', position: { x: 1480, y: 40 }, data: { label: 'Params Unknown Key' } },
        },
        {
          id: 'ui-array',
          type: 'input',
          name: 'UI Array',
          params: { select: ['value'] },
          ui: ['unexpected'],
        },
        {
          id: 'ui-data-array',
          type: 'llm',
          name: 'UI Data Array',
          params: { model: 'model:test:llm', prompt: 'hello' },
          ui: { builder_type: 'llm-node', position: { x: 1960, y: 40 }, data: ['unexpected'] },
        },
        {
          id: 'ui-position-malformed',
          type: 'output',
          name: 'UI Position Malformed',
          params: { value: '{{ inputs.value }}' },
          ui: { builder_type: 'output-node', position: { x: 'unexpected', y: 40 }, data: { label: 'UI Position Malformed' } },
        },
      ],
      edges: [],
    },
  },
}

const externalCanonicalNullUiWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'External Canonical Null UI Workflow',
    description: 'Canonical external workflow without Builder UI metadata',
    inputs_schema: { type: 'object', properties: { question: { type: 'string' } } },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'external-input',
          type: 'input',
          name: 'External Input',
          params: { select: ['question', 'locale'] },
          ui: null,
        },
      ],
      edges: [],
    },
  },
}

const malformedObjectEdgeWorkflowVersion = {
  ...canonicalWorkflowVersion,
  graph_json: {
    ...canonicalWorkflowVersion.graph_json,
    name: 'Malformed Object Edge Workflow',
    description: 'An object edge with unknown keys must remain recoverable',
    graph: {
      ...canonicalWorkflowVersion.graph_json.graph,
      edges: [
        {
          id: 'unknown-key-edge',
          from: 'input',
          to: 'output',
          from_port: '',
          to_port: null,
          condition: null,
          legacy_tag: 'preserve-me',
        },
      ],
    },
  },
}

async function mockWorkflowApi(page: Page) {
  await page.route('**/api/v1/workflows**', async (route) => {
    const method = route.request().method()
    const url = new URL(route.request().url())
    if (method === 'POST' && url.pathname.endsWith('/api/v1/workflows/templates/ticket-triage')) {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowWorkbench }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workflow-1/version/current')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
      return
    }

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/workflow-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

async function trackWorkflowUpdates(page: Page) {
  const state = { count: 0 }
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') {
      state.count += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }
    await route.fallback()
  })
  return state
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

test('workflow playground sends real HTTP and SSE requests without fake adapters', async ({ page }) => {
  let httpPayload: Record<string, unknown> | null = null
  let ssePayload: Record<string, unknown> | null = null
  await page.route('**/api/v1/workflows/workflow-1/execute', async (route) => {
    httpPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { run_id: 'run-http', status: 'succeeded', outputs: { accepted: true } },
      }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/stream', async (route) => {
    ssePayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      headers: { 'Cache-Control': 'no-cache' },
      body: [
        'event: start',
        'data: {"run_id":"run-sse","status":"started"}',
        '',
        'event: complete',
        'data: {"run_id":"run-sse","status":"succeeded"}',
        '',
        '',
      ].join('\n'),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Call config' }).click()

  await expect(page.getByRole('heading', { name: 'Workflow playground' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'HTTP' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'SSE' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Function Call' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: 'MCP Protocol' })).toHaveCount(0)

  const input = page.getByLabel('Inputs JSON')
  await input.fill('{"customer_id":"123"}')
  await page.getByRole('button', { name: 'Send HTTP request' }).click()
  await expect.poll(() => httpPayload).toEqual({ customer_id: '123' })
  await expect(page.getByText('run-http')).toBeVisible()

  await page.getByRole('tab', { name: 'SSE' }).click()
  await page.getByRole('button', { name: 'Start SSE stream' }).click()
  await expect.poll(() => ssePayload).toEqual({ inputs: { customer_id: '123' } })
  await expect(page.getByText('start', { exact: true })).toBeVisible()
  await expect(page.getByText('complete', { exact: true })).toBeVisible()
})

test.describe('canonical node types', () => {
  test('exports the exact canonical builder type order', () => {
    expect(canonicalBuilderTypes).toEqual([
      'input-node',
      'transform-node',
      'variable-assignment-node',
      'llm-node',
      'knowledge-search-node',
      'tool-node',
      'conditional-node',
      'output-node',
    ])
  })

  test('creates branch predicates only for new explicit canonical condition handles', () => {
    const edge = (sourceHandle?: string) => ({
      id: `new-${sourceHandle || 'missing'}`,
      source: 'cond',
      target: 'output',
      sourceHandle,
    }) as any
    const resultRef = '{{ steps.cond.output.result }}'

    expect(conditionForEdge(edge('true'), 'condition')).toBe(resultRef)
    expect(conditionForEdge(edge('output-true'), 'condition')).toBe(resultRef)
    expect(conditionForEdge(edge('false'), 'condition')).toBe(`${resultRef} == false`)
    expect(conditionForEdge(edge('output-false'), 'condition')).toBe(`${resultRef} == false`)
    expect(conditionForEdge(edge(), 'condition')).toBeUndefined()
    expect(conditionForEdge(edge('custom'), 'condition')).toBeUndefined()
  })

  test('accepts only plain JSON records and dense arrays in canonical params', () => {
    const shared = { keep: true }
    const nullPrototypeRecord = Object.assign(Object.create(null), { shared })
    const denseSharedValue = [shared, shared, nullPrototypeRecord]
    const nodeForValue = (value: unknown) => ({
      id: 'json-output',
      type: 'output-node',
      position: { x: 0, y: 0 },
      data: { label: 'JSON Output', value },
    }) as any

    expect(serializeCanonicalNode(nodeForValue(denseSharedValue)).params.value).toBe(denseSharedValue)

    class CustomJsonRepresentation {
      value = 'custom'
    }
    const sparseArray = new Array(2)
    sparseArray[1] = 'present'
    const sparseArrayWithCompensatingKey = new Array(2) as unknown[] & { extra?: string }
    sparseArrayWithCompensatingKey[1] = 'present'
    sparseArrayWithCompensatingKey.extra = 'must not hide the missing index'
    const cyclic: Record<string, unknown> = {}
    cyclic.self = cyclic

    for (const invalidValue of [
      new Date('2026-07-19T00:00:00.000Z'),
      new Map([['key', 'value']]),
      sparseArray,
      sparseArrayWithCompensatingKey,
      new CustomJsonRepresentation(),
      cyclic,
      undefined,
      Number.POSITIVE_INFINITY,
    ]) {
      expect(() => serializeCanonicalNode(nodeForValue(invalidValue))).toThrow(CanonicalNodeValidationError)
    }
  })

  test('rejects sparse input select arrays', () => {
    const sparseSelect = new Array(2)
    sparseSelect[1] = 'question'
    const inputNode = {
      id: 'sparse-input',
      type: 'input-node',
      position: { x: 0, y: 0 },
      data: { label: 'Sparse Input', select: sparseSelect },
    } as any

    expect(() => serializeCanonicalNode(inputNode)).toThrow(CanonicalNodeValidationError)
  })

  test('round-trips condition predicates independently from persisted source-port state', () => {
    const resultRef = '{{ steps.cond.output.result }}'
    const conditionCases = [
      { id: 'canonical-absent', condition: resultRef, from_port: undefined, port: { present: false }, handle: 'output-true', savedCondition: resultRef },
      { id: 'canonical-null', condition: resultRef, from_port: null, port: { present: true, value: null }, handle: 'output-true', savedCondition: resultRef },
      { id: 'canonical-empty', condition: resultRef, from_port: '', port: { present: true, value: '' }, handle: 'output-true', savedCondition: resultRef },
      { id: 'legacy-false-absent', condition: 'false', from_port: undefined, port: { present: false }, handle: 'output-false', savedCondition: `${resultRef} == false` },
      { id: 'legacy-false-null', condition: 'false', from_port: null, port: { present: true, value: null }, handle: 'output-false', savedCondition: `${resultRef} == false` },
      { id: 'legacy-false-empty', condition: 'false', from_port: '', port: { present: true, value: '' }, handle: 'output-false', savedCondition: `${resultRef} == false` },
      { id: 'canonical-true-port', condition: resultRef, from_port: 'true', port: { present: true, value: 'true' }, handle: 'output-true', savedCondition: resultRef },
      { id: 'legacy-false-port', condition: 'false', from_port: 'false', port: { present: true, value: 'false' }, handle: 'output-false', savedCondition: `${resultRef} == false` },
    ] as const
    const edgeVersion = {
      ...canonicalWorkflowVersion,
      graph_json: {
        ...canonicalWorkflowVersion.graph_json,
        graph: {
          ...canonicalWorkflowVersion.graph_json.graph,
          edges: [
            { id: 'empty-ports', from: 'input', to: 'output', from_port: '', to_port: '', condition: null },
            { id: 'null-ports', from: 'input', to: 'output', from_port: null, to_port: null, condition: null },
            ...conditionCases.map(({ id, condition, from_port }) => ({
              id,
              from: 'cond',
              to: 'output',
              ...(from_port !== undefined ? { from_port } : {}),
              condition,
            })),
            { id: 'persisted-empty-condition', from: 'cond', to: 'output', from_port: 'output-true', condition: null },
          ],
        },
      },
    }

    const restored = parseWorkflowVersion(edgeVersion)
    const serialized = serializeWorkflowSpec(
      restored.base,
      restored.name,
      restored.description,
      restored.nodes,
      restored.edges
    )
    const serializedEdges = serialized.graph.edges

    expect(serializedEdges.find((edge) => edge.id === 'empty-ports')).toMatchObject({
      from_port: '',
      to_port: '',
    })
    const nullPortsEdge = serializedEdges.find((edge) => edge.id === 'null-ports')
    expect(nullPortsEdge).toMatchObject({ from_port: null, to_port: null })
    expect(nullPortsEdge?.condition).toBeUndefined()

    for (const conditionCase of conditionCases) {
      const restoredEdge = restored.edges.find((edge) => edge.id === conditionCase.id)
      const serializedEdge = serializedEdges.find((edge) => edge.id === conditionCase.id)

      expect(restoredEdge).toMatchObject({
        sourceHandle: conditionCase.handle,
        data: {
          persistedFromPort: conditionCase.port,
          restoredSourceHandle: conditionCase.handle,
        },
      })
      expect(Object.prototype.hasOwnProperty.call(serializedEdge, 'from_port')).toBe(conditionCase.port.present)
      if (conditionCase.port.present) {
        expect(serializedEdge?.from_port).toBe(conditionCase.port.value)
      }
      expect(serializedEdge?.condition).toBe(conditionCase.savedCondition)
    }

    const emptyConditionEdge = serializedEdges.find((edge) => edge.id === 'persisted-empty-condition')
    expect(emptyConditionEdge).toMatchObject({ from_port: 'output-true' })
    expect(emptyConditionEdge).not.toHaveProperty('condition')
  })

  test('serializes changed and new condition handles as explicit branch contracts', () => {
    const resultRef = '{{ steps.cond.output.result }}'
    const restored = parseWorkflowVersion({
      ...canonicalWorkflowVersion,
      graph_json: {
        ...canonicalWorkflowVersion.graph_json,
        graph: {
          ...canonicalWorkflowVersion.graph_json.graph,
          edges: [
            { id: 'changed-predicate', from: 'cond', to: 'output', condition: resultRef },
            { id: 'changed-empty', from: 'cond', to: 'output', from_port: null, condition: null },
          ],
        },
      },
    })
    const changedEdges = restored.edges.map((edge) => ({ ...edge, sourceHandle: 'output-false' }))
    const newEdges = [
      { id: 'new-true', source: 'cond', target: 'output', sourceHandle: 'output-true' },
      { id: 'new-false', source: 'cond', target: 'output', sourceHandle: 'output-false' },
    ] as any[]

    const serialized = serializeWorkflowSpec(
      restored.base,
      restored.name,
      restored.description,
      restored.nodes,
      [...changedEdges, ...newEdges]
    )

    for (const edgeId of ['changed-predicate', 'changed-empty', 'new-false']) {
      expect(serialized.graph.edges.find((edge) => edge.id === edgeId)).toMatchObject({
        from_port: 'output-false',
        condition: `${resultRef} == false`,
      })
    }
    expect(serialized.graph.edges.find((edge) => edge.id === 'new-true')).toMatchObject({
      from_port: 'output-true',
      condition: resultRef,
    })
  })

  test('marks every malformed object edge as lossless unsupported data', () => {
    const malformedEdges: Record<string, unknown>[] = [
      { from: 'input', to: 'output' },
      { id: '', from: 'input', to: 'output' },
      { id: 'empty-from', from: '', to: 'output' },
      { id: 'missing-to', from: 'input' },
      { id: 'bad-from-port', from: 'input', to: 'output', from_port: 0 },
      { id: 'bad-to-port', from: 'input', to: 'output', to_port: [] },
      { id: 'bad-condition', from: 'cond', to: 'output', condition: { expression: 'true' } },
      { id: 'unknown-key', from: 'input', to: 'output', condition: null, legacy_tag: 'keep' },
    ]
    const restored = parseWorkflowVersion({
      ...canonicalWorkflowVersion,
      graph_json: {
        ...canonicalWorkflowVersion.graph_json,
        graph: {
          ...canonicalWorkflowVersion.graph_json.graph,
          edges: malformedEdges,
        },
      },
    })

    restored.edges.forEach((edge, index) => {
      expect(edge.data).toMatchObject({
        unsupported: true,
        compatibilityKind: 'unsupported-edge',
        validationError: expect.any(String),
        originalEdge: malformedEdges[index],
      })
    })
  })

  test('keeps complete primitive raw values in compatibility metadata', () => {
    const primitiveVersion = {
      graph_json: {
        graph: {
          nodes: [17],
          edges: [null],
        },
      },
    }

    const restored = parseWorkflowVersion(primitiveVersion)

    expect(restored.nodes[0]).toMatchObject({
      id: 'unsupported-0',
      type: 'compatibility-node',
      data: {
        unsupported: true,
        originalNode: 17,
      },
    })
    expect(restored.edges[0]).toMatchObject({
      id: 'edge-0',
      data: {
        unsupported: true,
        compatibilityKind: 'unsupported-edge',
        originalEdge: null,
      },
    })

    const validNodeWithPrimitiveEdge = parseWorkflowVersion({
      ...externalCanonicalNullUiWorkflowVersion,
      graph_json: {
        ...externalCanonicalNullUiWorkflowVersion.graph_json,
        graph: {
          ...externalCanonicalNullUiWorkflowVersion.graph_json.graph,
          edges: [null],
        },
      },
    })
    expect(() => serializeWorkflowSpec(
      validNodeWithPrimitiveEdge.base,
      validNodeWithPrimitiveEdge.name,
      validNodeWithPrimitiveEdge.description,
      validNodeWithPrimitiveEdge.nodes,
      validNodeWithPrimitiveEdge.edges
    )).toThrow(UnsupportedWorkflowEdgeError)
  })

  test('saves the canonical runtime contract without erasing its envelope or supplying actor identity', async ({ page }) => {
    let versionPayload: Record<string, any> | null = null

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: canonicalWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPayload = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Canonical Condition', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect.poll(() => versionPayload).not.toBeNull()

    const payload = versionPayload as unknown as Record<string, any>
    const savedSpec = payload.graph_json as Record<string, any>
    const savedNodes = savedSpec.graph.nodes as Record<string, any>[]
    const savedEdges = savedSpec.graph.edges as Record<string, any>[]
    const restoredGraph = parseWorkflowVersion(canonicalWorkflowVersion)
    const restoredFalseEdge = restoredGraph.edges.find((edge) => edge.id === 'condition-false')

    expect(Object.keys(payload)).toEqual(['graph_json'])
    expect(payload).not.toHaveProperty('created_by')
    expect(savedNodes.map((node) => node.type)).toEqual(canonicalRuntimeTypes)
    expect(restoredFalseEdge?.data?.originalEdge).toEqual(
      canonicalWorkflowVersion.graph_json.graph.edges.find((edge) => edge.id === 'condition-false')
    )

    for (const runtimeType of canonicalRuntimeTypes) {
      expect(savedNodes.find((node) => node.type === runtimeType)?.params).toEqual(canonicalNodeParams[runtimeType])
    }
    expect(savedNodes.find((node) => node.id === 'llm')?.ui.data).toMatchObject({
      modelName: canonicalNodeParams.llm.model,
      presentation: 'model-card',
    })
    expect(savedNodes.find((node) => node.id === 'llm')?.ui).toMatchObject({
      panel_size: { width: 360, height: 240 },
      collapsed: false,
    })
    expect(savedNodes.find((node) => node.id === 'cond')?.ui.position).toEqual({ x: 1520, y: 80 })

    for (const edgeId of [
      'input-transform',
      'condition-true',
      'condition-false',
      'condition-no-handle',
      'condition-custom-null',
    ]) {
      expect(savedEdges.find((edge) => edge.id === edgeId)).not.toHaveProperty('condition')
    }
    expect(savedEdges.find((edge) => edge.id === 'condition-legacy-false')).toMatchObject({
      from_port: 'output-false',
      condition: '{{ steps.cond.output.result }} == false',
    })

    for (const key of ['version', 'inputs_schema', 'outputs_schema', 'limits', 'runtime', 'policy', 'semantics']) {
      expect(savedSpec[key]).toEqual(canonicalWorkflowVersion.graph_json[key as keyof typeof canonicalWorkflowVersion.graph_json])
    }
    expect(savedSpec).toMatchObject({
      limits: { max_steps: 17, timeout_ms: 45_000, budget: 0, max_tool_calls: 0 },
      runtime: { engine: 'workflow_engine_v1' },
      policy: {
        registry_only_tools: true,
        default_timeout_ms: 12_000,
        default_retry_policy: { max_retries: 2, backoff_ms: 0 },
      },
      semantics: { on_error: 'compensate', concurrency: 3, pause_poll_ms: 250 },
    })
  })

  test('restores unsupported nodes as lossless compatibility data and blocks version creation', async ({ page }) => {
    let versionPosts = 0
    const workflowUpdates = await trackWorkflowUpdates(page)

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: unsupportedWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPosts += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Historical Python', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    const compatibilityGraph = parseWorkflowVersion(unsupportedWorkflowVersion)

    expect(compatibilityGraph.nodes[0]).toMatchObject({
      id: 'legacy-python',
      type: 'compatibility-node',
      position: { x: 42, y: 84 },
      data: {
        label: 'Historical Python',
        unsupported: true,
        originalId: 'legacy-python',
        originalName: 'Historical Python',
        originalRuntimeType: 'python',
        originalBuilderType: 'code-execution-node',
        originalParams: { script: 'return input', timeout_seconds: 0 },
        originalUi: unsupportedWorkflowVersion.graph_json.graph.nodes[0].ui,
        originalNode: unsupportedWorkflowVersion.graph_json.graph.nodes[0],
      },
    })
    expect(compatibilityGraph.edges[0]).toMatchObject({
      id: 'legacy-edge',
      source: 'legacy-python',
      target: 'legacy-output',
      sourceHandle: 'legacy-result',
      targetHandle: 'legacy-input',
    })

    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect(page.getByText(
      'Node "legacy-python" has unsupported builder type "compatibility-node".'
    )).toBeVisible()
    await expect.poll(() => versionPosts).toBe(0)
    await expect.poll(() => workflowUpdates.count).toBe(0)
  })

  test('preserves and blocks an arbitrary historical branch condition instead of rewriting it', async ({ page }) => {
    let versionPosts = 0
    const workflowUpdates = await trackWorkflowUpdates(page)

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: arbitraryConditionWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPosts += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Arbitrary Condition', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect.poll(() => versionPosts).toBe(0)
    await expect.poll(() => workflowUpdates.count).toBe(0)

    const restored = parseWorkflowVersion(arbitraryConditionWorkflowVersion)
    expect(restored.edges[0]).toMatchObject({
      sourceHandle: null,
      targetHandle: null,
      data: {
        unsupported: true,
        originalCondition: '{{ custom.branch_expression }}',
        originalEdge: arbitraryConditionWorkflowVersion.graph_json.graph.edges[0],
      },
    })
    await expect(page.getByText(
      'Edge "arbitrary-edge" has an unsupported persisted condition and cannot be saved safely.'
    )).toBeVisible()
  })

  test('keeps the loaded envelope when an empty persisted graph is seeded with draft nodes', async ({ page }) => {
    let versionPayload: Record<string, any> | null = null
    const emptyGraphVersion = {
      ...canonicalWorkflowVersion,
      graph_json: {
        ...canonicalWorkflowVersion.graph_json,
        graph: { nodes: [], edges: [] },
      },
    }

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: emptyGraphVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPayload = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Canonical Contract Workflow', { timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect.poll(() => versionPayload).not.toBeNull()

    const savedSpec = (versionPayload as unknown as Record<string, any>).graph_json
    for (const key of ['version', 'inputs_schema', 'outputs_schema', 'limits', 'runtime', 'policy', 'semantics']) {
      expect(savedSpec[key]).toEqual(canonicalWorkflowVersion.graph_json[key as keyof typeof canonicalWorkflowVersion.graph_json])
    }
  })

  test('does not update workflow metadata when version validation fails', async ({ page }) => {
    const calls: string[] = []

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: canonicalWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      calls.push('POST version')
      await route.fulfill({
        status: 422,
        contentType: 'application/json',
        body: JSON.stringify({ success: false, code: 'VALIDATION_ERROR', message: 'Invalid workflow spec', data: null }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1', async (route) => {
      if (route.request().method() === 'PUT') {
        calls.push('PUT metadata')
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
        })
        return
      }
      await route.fallback()
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Canonical Condition', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()

    await expect(page.getByText('Failed to save workflow version.')).toBeVisible()
    await expect.poll(() => calls).toEqual(['POST version'])
  })

  test('reports a recoverable partial save when metadata update fails after version creation', async ({ page }) => {
    const calls: string[] = []
    let currentVersionGets = 0

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      currentVersionGets += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: canonicalWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      calls.push('POST version')
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1', async (route) => {
      if (route.request().method() === 'PUT') {
        calls.push('PUT metadata')
        await route.fulfill({
          status: 500,
          contentType: 'application/json',
          body: JSON.stringify({ success: false, code: 'UPDATE_FAILED', message: 'Metadata update failed', data: null }),
        })
        return
      }
      await route.fallback()
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Canonical Condition', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()

    await expect(page.getByText('Workflow version saved, but workflow metadata update failed.')).toBeVisible()
    await expect.poll(() => calls).toEqual(['POST version', 'PUT metadata'])
    await expect.poll(() => currentVersionGets).toBeGreaterThan(1)
  })

  test('blocks malformed object edges before version or metadata mutation', async ({ page }) => {
    let versionPosts = 0
    const workflowUpdates = await trackWorkflowUpdates(page)

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: malformedObjectEdgeWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPosts += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Canonical Input', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    const restored = parseWorkflowVersion(malformedObjectEdgeWorkflowVersion)
    expect(restored.edges[0].data).toMatchObject({
      unsupported: true,
      compatibilityKind: 'unsupported-edge',
      originalEdge: malformedObjectEdgeWorkflowVersion.graph_json.graph.edges[0],
    })

    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect(page.getByText(
      'Edge "unknown-key-edge" has unsupported persisted data and cannot be saved safely.'
    )).toBeVisible()
    await expect.poll(() => versionPosts).toBe(0)
    await expect.poll(() => workflowUpdates.count).toBe(0)
  })

  test('reports the invalid canonical node field and blocks version creation', async ({ page }) => {
    let versionPosts = 0
    const workflowUpdates = await trackWorkflowUpdates(page)

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: invalidCanonicalWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPosts += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Invalid Canonical LLM', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect(page.getByText(
      'Node "invalid-llm" (llm-node) has invalid field "model": a non-empty string is required'
    )).toBeVisible()
    await expect.poll(() => versionPosts).toBe(0)
    await expect.poll(() => workflowUpdates.count).toBe(0)
  })

  test('restores malformed canonical metadata as compatibility data and blocks all save mutations', async ({ page }) => {
    let versionPosts = 0
    const workflowUpdates = await trackWorkflowUpdates(page)

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: malformedCanonicalWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPosts += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('Builder Non String', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    const restored = parseWorkflowVersion(malformedCanonicalWorkflowVersion)
    const restoredById = new Map(restored.nodes.map((node) => [node.id, node]))
    for (const originalNode of malformedCanonicalWorkflowVersion.graph_json.graph.nodes) {
      expect(restoredById.get(originalNode.id)).toMatchObject({
        id: originalNode.id,
        type: 'compatibility-node',
        data: {
          unsupported: true,
          originalId: originalNode.id,
          originalName: originalNode.name,
          originalRuntimeType: originalNode.type,
          originalParams: originalNode.params,
          originalUi: originalNode.ui,
          originalNode,
        },
      })
    }
    expect(restoredById.get('builder-non-string')?.data).toMatchObject({ originalBuilderType: 42 })

    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect(page.getByText(
      'Node "builder-non-string" has unsupported builder type "compatibility-node".'
    )).toBeVisible()
    await expect.poll(() => workflowUpdates.count).toBe(0)
    await expect.poll(() => versionPosts).toBe(0)
  })

  test('loads an external canonical node with null ui as editable builder data and saves its params', async ({ page }) => {
    let versionPayload: Record<string, any> | null = null

    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: externalCanonicalNullUiWorkflowVersion }),
      })
    })
    await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
      versionPayload = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await expect(page.getByText('External Input', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

    const restored = parseWorkflowVersion(externalCanonicalNullUiWorkflowVersion)
    expect(restored.hasUnsupportedNodes).toBe(false)
    expect(restored.nodes[0]).toMatchObject({
      id: 'external-input',
      type: 'input-node',
      data: {
        label: 'External Input',
        select: ['question', 'locale'],
      },
    })
    expect(restored.nodes[0].data).not.toHaveProperty('fallback')

    await page.getByRole('button').filter({ has: page.locator('svg.lucide-save') }).click()
    await expect.poll(() => versionPayload).not.toBeNull()

    const savedNode = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes[0]
    expect(savedNode).toMatchObject({
      id: 'external-input',
      type: 'input',
      ui: { builder_type: 'input-node' },
    })
    expect(savedNode.params).toEqual(externalCanonicalNullUiWorkflowVersion.graph_json.graph.nodes[0].params)
    expect(savedNode.params).not.toHaveProperty('fallback')
  })
})
