import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'
import {
  CanonicalNodeValidationError,
  conditionForEdge,
  parseWorkflowVersion,
  serializeCanonicalNode,
  serializeWorkflowSpec,
  serializeWorkflowSpecForExport,
  UnsupportedWorkflowEdgeError,
} from '../app/features/workflow-builder/ui/workflow-spec'
import { canonicalBuilderTypes } from '../app/features/workflow-builder/ui/canonical-node-registry'
import historicalAppendixFixtures from './fixtures/workflow-historical-appendix'

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

const mockWorkflowGrant = (workflowId: string, userId: string) => ({
  id: `grant-${workflowId}-${userId}`,
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  resource_type: 'workflow',
  resource_id: workflowId,
  user_id: userId,
  actions: ['read'],
  created_by: 'user-1',
  created_at: '2026-07-19T00:00:00.000Z',
  updated_at: '2026-07-19T00:00:00.000Z',
})

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

const mockWorkflowCapabilities = {
  capabilities: [
    { type: 'input', ui_type: 'input-node', category: 'input', executable: true },
    { type: 'transform', ui_type: 'transform-node', category: 'data', executable: true },
    { type: 'set_var', ui_type: 'variable-assignment-node', category: 'data', executable: true },
    { type: 'llm', ui_type: 'llm-node', category: 'model', executable: true },
    { type: 'retrieve', ui_type: 'knowledge-search-node', category: 'data', executable: true },
    { type: 'tool', ui_type: 'tool-node', category: 'tool', executable: true },
    { type: 'condition', ui_type: 'conditional-node', category: 'flow', executable: true },
    { type: 'output', ui_type: 'output-node', category: 'output', executable: true },
  ],
  builder_node_types: [...canonicalRuntimeTypes],
  compatibility_node_types: ['http', 'node'],
}

const mockModelWorkbenchResponse = (items: Record<string, unknown>[]) => ({
  summary: {
    total_models: items.length,
    available_models: items.filter((item) => item.status === 'available').length,
    total_providers: items.length ? 1 : 0,
    online_providers: items.length ? 1 : 0,
    month_calls: 0,
    month_tokens: 0,
    month_cost_amount: 0,
    abnormal_models: 0,
    updated_at: '2026-07-19T00:00:00.000Z',
  },
  tabs: {
    all: items.length,
    text: items.filter((item) => item.model_type === 'text').length,
    embedding: 0,
    multimodal: 0,
    rerank: 0,
    disabled: 0,
    abnormal: 0,
  },
  items,
  next_page_token: null,
  page_size: items.length,
})

const mockKnowledgeListResponse = (items: Record<string, unknown>[]) => ({
  items,
  next_page_token: null,
  page_size: items.length,
  has_next: false,
})

const mockKnowledgeBase = (overrides: Record<string, unknown>) => ({
  id: 'knowledge-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Knowledge base',
  description: null,
  status: 'active',
  visibility: 'private',
  knowledge_type: 'document',
  settings_json: {},
  chunking_json: {},
  retrieval_json: {},
  doc_count: 0,
  chunk_count: 0,
  created_at: '2026-07-19T00:00:00.000Z',
  updated_at: '2026-07-19T00:00:00.000Z',
  ...overrides,
})

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

const legacyConditionHandleWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Legacy Condition Handles',
    description: 'Legacy branch port identifiers must attach to canonical visual handles',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'legacy-condition',
          type: 'condition',
          name: 'Legacy Condition',
          params: { condition: 'true' },
          ui: { builder_type: 'conditional-node', position: { x: 160, y: 160 }, data: { label: 'Legacy Condition' } },
        },
        {
          id: 'true-output',
          type: 'output',
          name: 'True Output',
          params: { value: true },
          ui: { builder_type: 'output-node', position: { x: 520, y: 80 }, data: { label: 'True Output' } },
        },
        {
          id: 'false-output',
          type: 'output',
          name: 'False Output',
          params: { value: false },
          ui: { builder_type: 'output-node', position: { x: 520, y: 280 }, data: { label: 'False Output' } },
        },
      ],
      edges: [
        { id: 'legacy-true-edge', from: 'legacy-condition', to: 'true-output', from_port: 'output-true', to_port: 'input', condition: 'true' },
        { id: 'legacy-false-edge', from: 'legacy-condition', to: 'false-output', from_port: 'output-false', to_port: 'input', condition: 'false' },
      ],
    },
  },
}

const editorInteractionWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Editor Interaction Workflow',
    description: 'Controlled property editors must retain sequential input',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'interaction-input',
          type: 'input',
          name: 'Interaction Input',
          params: {},
          ui: { builder_type: 'input-node', position: { x: 560, y: 80 }, data: { label: 'Interaction Input' } },
        },
        {
          id: 'interaction-transform',
          type: 'transform',
          name: 'Interaction Transform',
          params: { mapping: { initial: true } },
          ui: { builder_type: 'transform-node', position: { x: 560, y: 240 }, data: { label: 'Interaction Transform' } },
        },
        {
          id: 'interaction-variable',
          type: 'set_var',
          name: 'Interaction Variable',
          params: { key: 'old', value: 'old' },
          ui: { builder_type: 'variable-assignment-node', position: { x: 560, y: 400 }, data: { label: 'Interaction Variable' } },
        },
        {
          id: 'interaction-condition',
          type: 'condition',
          name: 'Interaction Condition',
          params: { condition: 'true' },
          ui: { builder_type: 'conditional-node', position: { x: 560, y: 560 }, data: { label: 'Interaction Condition' } },
        },
      ],
      edges: [],
    },
  },
}

const scopedResourceWorkflowVersion = {
  ...mockWorkflowVersion,
  graph_json: {
    name: 'Scoped Resource Workflow',
    description: 'Builder resource references come from workspace-scoped inventories',
    inputs_schema: { type: 'object', properties: {} },
    outputs_schema: { type: 'object', properties: {} },
    graph: {
      nodes: [
        {
          id: 'scoped-llm',
          type: 'llm',
          name: 'Scoped LLM',
          params: { model: 'model:legacy:missing', prompt: '{{ inputs.question }}' },
          ui: { builder_type: 'llm-node', position: { x: 560, y: 80 }, data: { label: 'Scoped LLM' } },
        },
        {
          id: 'scoped-knowledge',
          type: 'retrieve',
          name: 'Scoped Knowledge',
          params: { knowledge_ref: 'knowledge:legacy-missing', query: '{{ inputs.question }}', top_k: 3 },
          ui: { builder_type: 'knowledge-search-node', position: { x: 560, y: 280 }, data: { label: 'Scoped Knowledge' } },
        },
        {
          id: 'scoped-tool',
          type: 'tool',
          name: 'Scoped Tool',
          params: { tool_ref: 'tool:legacy:missing', arguments: {}, input: '{{ steps.scoped-knowledge.output.result }}' },
          ui: { builder_type: 'tool-node', position: { x: 560, y: 480 }, data: { label: 'Scoped Tool' } },
        },
      ],
      edges: [],
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

type HistoricalWorkflowNodeFixture = {
  id: `H${string}`
  editable: boolean
  node: Record<string, any>
  edges: Record<string, any>[]
}

export const HISTORICAL_WORKFLOW_NODE_FIXTURES = historicalAppendixFixtures as unknown as HistoricalWorkflowNodeFixture[]

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

    if (method === 'GET' && url.pathname.endsWith('/api/v1/workflows/capabilities')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowCapabilities }),
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

async function importWorkflowFile(page: Page, value: unknown, name = 'workflow.json') {
  const fileChooserPromise = page.waitForEvent('filechooser')
  const importButton = page.getByRole('button').filter({ has: page.locator('svg.lucide-upload') })
  await expect(importButton).toBeEnabled()
  await importButton.click()
  const fileChooser = await fileChooserPromise
  await fileChooser.setFiles({
    name,
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(value)),
  })
}

async function downloadWorkflowFile(page: Page) {
  const downloadPromise = page.waitForEvent('download')
  const exportButton = page.getByRole('button').filter({ has: page.locator('svg.lucide-download') })
  await expect(exportButton).toBeEnabled()
  await exportButton.click()
  const download = await downloadPromise
  const stream = await download.createReadStream()
  const chunks: Buffer[] = []
  for await (const chunk of stream) chunks.push(Buffer.from(chunk))
  return JSON.parse(Buffer.concat(chunks).toString('utf8'))
}

async function selectWorkflowNode(page: Page, nodeId: string) {
  const node = page.locator(`.react-flow__node[data-id="${nodeId}"]`)
  await expect(node).toBeVisible()
  await node.dispatchEvent('click')
}

async function navigateClientRoute(page: Page, path: string) {
  await page.evaluate((nextPath) => {
    window.history.pushState({}, '', nextPath)
    window.dispatchEvent(new PopStateEvent('popstate'))
  }, path)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockWorkflowApi(page)
})

test('Test Run saves the exact draft, previews it, and opens the evidence Run', async ({ page }) => {
  const requestOrder: string[] = []
  const previewRequests: Array<{ workflowId: string, versionId: string, inputs: Record<string, unknown> }> = []
  const savedVersion = {
    ...mockWorkflowVersion,
    id: 'workflow-version-draft-2',
  }
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    requestOrder.push('save')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: savedVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') {
      requestOrder.push('metadata')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    const url = new URL(route.request().url())
    const segments = url.pathname.split('/')
    const workflowId = segments[segments.indexOf('workflows') + 1]
    const versionId = segments[segments.indexOf('versions') + 1]
    previewRequests.push({
      workflowId,
      versionId,
      inputs: JSON.parse(route.request().postData() || '{}').inputs,
    })
    requestOrder.push('preview')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { run_id: 'run-preview-1', workflow_version_id: versionId, output: { value: 'draft' } },
      }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  const testRun = page.getByRole('button', { name: 'Test Run' })
  await testRun.click()

  await expect.poll(() => previewRequests).toEqual([
    { workflowId: 'workflow-1', versionId: 'workflow-version-draft-2', inputs: {} },
  ])
  expect(requestOrder).toEqual(['save', 'metadata', 'preview'])
  await expect(page).toHaveURL(/\/observe\/runs\/run-preview-1$/)
})

test('Test Run stops after a draft save failure and does not claim execution success', async ({ page }) => {
  let saveRequests = 0
  let previewRequests = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    saveRequests += 1
    await route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'INTERNAL_ERROR', message: 'save failed', data: null }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    previewRequests += 1
    await route.fulfill({ status: 500, contentType: 'application/json', body: '{}' })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Test Run' }).click()

  await expect.poll(() => saveRequests).toBe(1)
  await expect.poll(() => previewRequests).toBe(0)
  await expect(page).toHaveURL(/\/workflow\/workflow-1\/build$/)
  await expect(page.getByText('Failed to save workflow version.')).toBeVisible()
  await expect(page.getByText('Workflow is running...')).toHaveCount(0)
})

test('Test Run suppresses a stale preview failure after the route changes', async ({ page }) => {
  let releasePreview!: () => void
  const previewGate = new Promise<void>((resolve) => { releasePreview = resolve })
  let previewRequests = 0
  let previewResponses = 0
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    previewRequests += 1
    await previewGate
    previewResponses += 1
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'late preview failure', data: null }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionB }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Test Run' }).click()
  await expect.poll(() => previewRequests).toBe(1)
  await navigateClientRoute(page, '/workflow/workflow-b/build')
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Builder B')

  releasePreview()
  await expect.poll(() => previewResponses).toBe(1)
  await page.waitForTimeout(300)
  await expect(page.getByText('Failed to start workflow test run.')).toHaveCount(0)
  await expect(page).toHaveURL(/\/workflow\/workflow-b\/build$/)
})

test('Test Run does not navigate after a pending preview succeeds on an unmounted Builder', async ({ page }) => {
  let releasePreview!: () => void
  const previewGate = new Promise<void>((resolve) => { releasePreview = resolve })
  let previewRequests = 0
  let previewResponses = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    previewRequests += 1
    await previewGate
    previewResponses += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { run_id: 'stale-preview-success', workflow_version_id: mockWorkflowVersion.id },
      }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Test Run' }).click()
  await expect.poll(() => previewRequests).toBe(1)
  await navigateClientRoute(page, '/workflow/workflow-1/setting')
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')

  releasePreview()
  await expect.poll(() => previewResponses).toBe(1)
  await page.waitForTimeout(200)
  await expect(page).toHaveURL(/\/workflow\/workflow-1\/setting$/)
})

test('Test Run suppresses a pending preview failure after Builder unmount', async ({ page }) => {
  let releasePreview!: () => void
  const previewGate = new Promise<void>((resolve) => { releasePreview = resolve })
  let previewRequests = 0
  let previewResponses = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    previewRequests += 1
    await previewGate
    previewResponses += 1
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'stale preview failure', data: null }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Test Run' }).click()
  await expect.poll(() => previewRequests).toBe(1)
  await navigateClientRoute(page, '/workflow/workflow-1/setting')
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')

  releasePreview()
  await expect.poll(() => previewResponses).toBe(1)
  await page.waitForTimeout(200)
  await expect(page).toHaveURL(/\/workflow\/workflow-1\/setting$/)
  expect(await page.getByText('stale preview failure', { exact: true }).count()).toBe(0)
  expect(await page.getByText('Failed to start workflow test run.', { exact: true }).count()).toBe(0)
})

test('Test Run stops after a pending version save when Builder unmounts', async ({ page }) => {
  let releaseSave!: () => void
  const saveGate = new Promise<void>((resolve) => { releaseSave = resolve })
  let saveRequests = 0
  let saveResponses = 0
  let metadataRequests = 0
  let previewRequests = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    saveRequests += 1
    await saveGate
    saveResponses += 1
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') metadataRequests += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions/*/preview', async (route) => {
    previewRequests += 1
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { run_id: 'must-not-run' } }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Test Run' }).click()
  await expect.poll(() => saveRequests).toBe(1)
  await navigateClientRoute(page, '/workflow/workflow-1/setting')
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')

  releaseSave()
  await expect.poll(() => saveResponses).toBe(1)
  await page.waitForTimeout(300)
  expect(metadataRequests).toBe(0)
  expect(previewRequests).toBe(0)
  await expect(page).toHaveURL(/\/workflow\/workflow-1\/setting$/)
  expect(await page.getByText('Workflow saved successfully', { exact: true }).count()).toBe(0)
  expect(await page.getByText('Failed to start workflow test run.', { exact: true }).count()).toBe(0)
})

test('Builder operation lock prevents duplicate saves and editing while a save is pending', async ({ page }) => {
  let releaseSave!: () => void
  const saveGate = new Promise<void>((resolve) => { releaseSave = resolve })
  let saveRequests = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    saveRequests += 1
    await saveGate
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowVersion }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await selectWorkflowNode(page, 'interaction-condition')
  const condition = page.locator('#conditional-expression')
  const originalCondition = await condition.inputValue()
  const save = page.getByRole('button', { name: 'Save Workflow' })
  const testRun = page.getByRole('button', { name: 'Test Run' })
  await save.click()
  await expect.poll(() => saveRequests).toBe(1)

  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()
  await expect(condition).toBeDisabled()
  await expect(page.getByRole('tabpanel', { name: 'Nodes' }).getByRole('button').first()).toBeDisabled()
  await expect(page.locator('.workflow-editor')).toHaveAttribute('data-interaction-disabled', 'true')

  await save.evaluate((element: HTMLButtonElement) => element.click())
  await testRun.evaluate((element: HTMLButtonElement) => element.click())
  await condition.evaluate((element: HTMLInputElement) => {
    element.value = 'must-not-apply'
    element.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await expect.poll(() => saveRequests).toBe(1)

  releaseSave()
  await expect(save).toBeEnabled()
  await expect(testRun).toBeEnabled()
  await selectWorkflowNode(page, 'interaction-condition')
  await expect(condition).toBeEnabled()
  await expect(condition).toHaveValue(originalCondition)
  await expect(page.locator('.workflow-editor')).toHaveAttribute('data-interaction-disabled', 'false')
})

test('Builder blocks mutations while its workflow and current version are loading', async ({ page }) => {
  let releaseWorkflow!: () => void
  let releaseVersion!: () => void
  const workflowGate = new Promise<void>((resolve) => { releaseWorkflow = resolve })
  const versionGate = new Promise<void>((resolve) => { releaseVersion = resolve })
  let mutations = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await versionGate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'GET') {
      await workflowGate
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }
    mutations += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    mutations += 1
    await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  const workflowName = page.getByPlaceholder('Workflow name')
  const save = page.getByRole('button', { name: 'Save Workflow' })
  const testRun = page.getByRole('button', { name: 'Test Run' })
  await expect(workflowName).toBeDisabled()
  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()
  await expect(page.locator('.workflow-editor')).toHaveAttribute('data-interaction-disabled', 'true')
  await save.evaluate((element: HTMLButtonElement) => element.click())
  await testRun.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => mutations).toBe(0)

  releaseWorkflow()
  releaseVersion()
  await expect(workflowName).toBeEnabled()
  await expect(save).toBeEnabled()
  await expect(testRun).toBeEnabled()
})

test('Builder remains fail closed when workflow loading fails', async ({ page }) => {
  let mutations = 0
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'workflow unavailable', data: null }),
      })
      return
    }
    mutations += 1
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    mutations += 1
    await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Failed to load workflow builder state.')).toBeVisible()
  const workflowName = page.getByPlaceholder('Workflow name')
  const save = page.getByRole('button', { name: 'Save Workflow' })
  const testRun = page.getByRole('button', { name: 'Test Run' })
  await expect(workflowName).toBeDisabled()
  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()
  await save.evaluate((element: HTMLButtonElement) => element.click())
  await testRun.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => mutations).toBe(0)
})

test('Builder treats a current-version 503 as a load failure', async ({ page }) => {
  let mutations = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'version unavailable', data: null }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1/versions', async (route) => {
    mutations += 1
    await route.fulfill({ status: 201, contentType: 'application/json', body: '{}' })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Failed to load workflow builder state.')).toBeVisible()
  const save = page.getByRole('button', { name: 'Save Workflow' })
  const testRun = page.getByRole('button', { name: 'Test Run' })
  await expect(page.getByPlaceholder('Workflow name')).toBeDisabled()
  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()
  await save.evaluate((element: HTMLButtonElement) => element.click())
  await testRun.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => mutations).toBe(0)
})

test('Builder treats a missing current version as an editable new draft', async ({ page }) => {
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'NOT_FOUND', message: 'version not found', data: null }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Demo Workflow')
  await expect(page.getByPlaceholder('Workflow name')).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeEnabled()
  await expect(page.getByRole('button', { name: 'Test Run' })).toBeEnabled()
  await expect(page.locator('.react-flow__node[data-id="transform-1"]')).toBeVisible()
  expect(await page.getByText('version not found').count()).toBe(0)
})

test('Builder toolbar stays inside the central canvas at the default viewport', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 720 })
  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })

  const leftPanel = page.getByPlaceholder('Workflow name').locator('xpath=ancestor::div[contains(@class, "w-80")]')
  const rightPanel = page.getByText('Select a node to edit its properties').locator('xpath=ancestor::div[contains(@class, "w-100")]')
  await expect(leftPanel).toBeVisible()
  await expect(rightPanel).toBeVisible()
  const leftPanelBox = await leftPanel.boundingBox()
  const rightPanelBox = await rightPanel.boundingBox()
  const toolbar = page.getByRole('toolbar', { name: 'Workflow editor controls' })
  await expect(toolbar).toBeVisible()
  const toolbarBox = await toolbar.boundingBox()

  expect(leftPanelBox).not.toBeNull()
  expect(rightPanelBox).not.toBeNull()
  expect(toolbarBox).not.toBeNull()
  expect(toolbarBox!.x).toBeGreaterThanOrEqual(leftPanelBox!.x + leftPanelBox!.width)
  expect(toolbarBox!.x + toolbarBox!.width).toBeLessThanOrEqual(rightPanelBox!.x)

  const toolbarButtons = toolbar.getByRole('button')
  await expect(toolbarButtons).toHaveCount(9)
  for (let index = 0; index < 9; index += 1) {
    await expect(toolbarButtons.nth(index)).toHaveAccessibleName(/.+/)
  }

  const initialScroll = await toolbar.evaluate((element) => ({
    clientWidth: element.clientWidth,
    scrollWidth: element.scrollWidth,
  }))
  expect(initialScroll.scrollWidth).toBeGreaterThan(initialScroll.clientWidth)
  const scrollLeft = await toolbar.evaluate((element) => {
    element.scrollLeft = element.scrollWidth
    return element.scrollLeft
  })
  expect(scrollLeft).toBeGreaterThan(0)

  const importButton = toolbar.getByRole('button', { name: 'Import Workflow' })
  const layoutButton = toolbar.getByRole('button', { name: /Switch to (?:horizontal|tree) layout/ })
  const initialLayoutLabel = await layoutButton.getAttribute('aria-label')
  const scrolledToolbarBox = await toolbar.boundingBox()
  const importBox = await importButton.boundingBox()
  const layoutBox = await layoutButton.boundingBox()
  for (const buttonBox of [importBox, layoutBox]) {
    expect(buttonBox).not.toBeNull()
    expect(buttonBox!.x).toBeGreaterThanOrEqual(scrolledToolbarBox!.x)
    expect(buttonBox!.x + buttonBox!.width).toBeLessThanOrEqual(
      scrolledToolbarBox!.x + scrolledToolbarBox!.width,
    )
  }

  await importButton.focus()
  await expect(importButton).toBeFocused()
  const fileChooserPromise = page.waitForEvent('filechooser')
  await importButton.click()
  await fileChooserPromise

  await layoutButton.focus()
  await expect(layoutButton).toBeFocused()
  await layoutButton.click()
  const expectedLayoutLabel = initialLayoutLabel === 'Switch to horizontal layout'
    ? 'Switch to tree layout'
    : 'Switch to horizontal layout'
  await expect(layoutButton).toHaveAccessibleName(expectedLayoutLabel)
})

test('Builder ignores stale workflow and version responses after a client-side route change', async ({ page }) => {
  let releaseWorkflowA!: () => void
  let releaseVersionA!: () => void
  const workflowAGate = new Promise<void>((resolve) => { releaseWorkflowA = resolve })
  const versionAGate = new Promise<void>((resolve) => { releaseVersionA = resolve })
  let workflowARequests = 0
  let versionARequests = 0
  let workflowAResponses = 0
  let versionAResponses = 0
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  const versionA = structuredClone(editorInteractionWorkflowVersion)
  versionA.workflow_id = 'workflow-a'
  versionA.graph_json.name = 'Builder A'
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'

  await page.route('**/api/v1/workflows/workflow-*/**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/workflows/workflow-a/version/current')) {
      versionARequests += 1
      await versionAGate
      versionAResponses += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionA }),
      })
      return
    }
    if (url.pathname.endsWith('/workflows/workflow-b/version/current')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionB }),
      })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/workflows/workflow-a')) {
      workflowARequests += 1
      await workflowAGate
      workflowAResponses += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowA }),
      })
      return
    }
    if (url.pathname.endsWith('/workflows/workflow-b')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-a/build', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => workflowARequests).toBeGreaterThan(0)
  await expect.poll(() => versionARequests).toBeGreaterThan(0)
  await navigateClientRoute(page, '/workflow/workflow-b/build')
  const workflowName = page.getByPlaceholder('Workflow name')
  await expect(workflowName).toHaveValue('Builder B')
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeEnabled()

  releaseWorkflowA()
  releaseVersionA()
  await expect.poll(() => workflowAResponses).toBe(workflowARequests)
  await expect.poll(() => versionAResponses).toBe(versionARequests)
  await page.waitForTimeout(300)
  await expect(workflowName).toHaveValue('Builder B')
  await expect(page).toHaveURL(/\/workflow\/workflow-b\/build$/)
})

test('Builder rejects an old import confirmation after the workflow ID changes', async ({ page }) => {
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'
  versionB.graph_json.description = 'Builder B description'
  const importedGraph = structuredClone(canonicalWorkflowVersion.graph_json)
  importedGraph.name = 'Imported From Workflow A'
  importedGraph.description = 'This graph must never reach Workflow B'
  let versionPayload: Record<string, any> | null = null

  await page.route('**/api/v1/workflows/workflow-b/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionB }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b/versions', async (route) => {
    versionPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { ...mockWorkflowVersion, workflow_id: 'workflow-b' } }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Demo Workflow')
  await importWorkflowFile(page, {
    format: 'soit-workflow-spec-v1',
    graph_json: importedGraph,
  }, 'workflow-a-import.json')
  const staleDialog = page.getByRole('dialog')
  await expect(staleDialog.getByText('Import workflow', { exact: true })).toBeVisible()
  const staleConfirm = await staleDialog.getByRole('button', { name: 'Import' }).elementHandle()
  expect(staleConfirm).not.toBeNull()

  await navigateClientRoute(page, '/workflow/workflow-b/build')
  const workflowName = page.getByPlaceholder('Workflow name')
  await expect(workflowName).toHaveValue('Builder B')
  await expect(page.locator('.react-flow__node[data-id="interaction-input"]')).toBeVisible()
  const staleDialogVisibleAfterRoute = await staleDialog.isVisible().catch(() => false)

  await staleConfirm!.evaluate((element: HTMLButtonElement) => element.click())
  await page.waitForTimeout(200)
  const nameAfterStaleConfirm = await workflowName.inputValue()
  const nodeIdsAfterStaleConfirm = await page.locator('.react-flow__node').evaluateAll((elements) => (
    elements.map((element) => element.getAttribute('data-id'))
  ))
  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()

  expect(staleDialogVisibleAfterRoute).toBe(false)
  expect(nameAfterStaleConfirm).toBe('Builder B')
  expect(nodeIdsAfterStaleConfirm).toEqual(versionB.graph_json.graph.nodes.map((node) => node.id))
  expect((versionPayload as unknown as Record<string, any>).graph_json.name).toBe('Builder B')
  expect((versionPayload as unknown as Record<string, any>).graph_json.graph.nodes.map((node: Record<string, unknown>) => node.id)).toEqual(
    versionB.graph_json.graph.nodes.map((node) => node.id),
  )
})

test('Builder ignores a stale import file selection after the workflow ID changes', async ({ page }) => {
  await page.addInitScript(() => {
    const originalReadAsText = FileReader.prototype.readAsText
    ;(window as any).__workflowImportReadCount = 0
    FileReader.prototype.readAsText = function (blob: Blob, encoding?: string) {
      ;(window as any).__workflowImportReadCount += 1
      return originalReadAsText.call(this, blob, encoding)
    }
  })
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'
  await page.route('**/api/v1/workflows/workflow-b/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionB }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  const fileChooserPromise = page.waitForEvent('filechooser')
  await page.getByRole('button', { name: 'Import Workflow' }).click()
  const fileChooser = await fileChooserPromise
  await navigateClientRoute(page, '/workflow/workflow-b/build')
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Builder B')
  await fileChooser.setFiles({
    name: 'stale-selection.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify({
      format: 'soit-workflow-spec-v1',
      graph_json: canonicalWorkflowVersion.graph_json,
    })),
  })
  await page.waitForTimeout(200)

  expect(await page.evaluate(() => (window as any).__workflowImportReadCount)).toBe(0)
  expect(await page.getByRole('dialog').count()).toBe(0)
  expect(await page.getByText('Import failed: invalid workflow file format', { exact: true }).count()).toBe(0)
})

test('Builder suppresses stale import load and parse results after the workflow ID changes', async ({ page }) => {
  await page.addInitScript(() => {
    const originalReadAsText = FileReader.prototype.readAsText
    const pendingReads: Array<() => void> = []
    ;(window as any).__workflowImportPendingReads = 0
    ;(window as any).__workflowImportCompletedReads = 0
    ;(window as any).__releaseWorkflowImportReads = () => {
      pendingReads.splice(0).forEach((release) => release())
    }
    FileReader.prototype.readAsText = function (blob: Blob, encoding?: string) {
      const reader = this
      pendingReads.push(() => {
        reader.addEventListener('loadend', () => {
          ;(window as any).__workflowImportCompletedReads += 1
        }, { once: true })
        originalReadAsText.call(reader, blob, encoding)
      })
      ;(window as any).__workflowImportPendingReads = pendingReads.length
    }
  })
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'
  await page.route('**/api/v1/workflows/workflow-b/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: versionB }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-b', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await importWorkflowFile(page, {
    format: 'soit-workflow-spec-v1',
    graph_json: canonicalWorkflowVersion.graph_json,
  }, 'pending-valid-import.json')
  await importWorkflowFile(page, { format: 'invalid' }, 'pending-invalid-import.json')
  await expect.poll(() => page.evaluate(() => (window as any).__workflowImportPendingReads)).toBe(2)

  await navigateClientRoute(page, '/workflow/workflow-b/build')
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Builder B')
  await page.evaluate(() => (window as any).__releaseWorkflowImportReads())
  await expect.poll(() => page.evaluate(() => (window as any).__workflowImportCompletedReads)).toBe(2)
  await page.waitForTimeout(200)

  expect(await page.getByRole('dialog').count()).toBe(0)
  expect(await page.getByText('Import failed: invalid workflow file format', { exact: true }).count()).toBe(0)
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Builder B')
})

test('workflow sidebar ignores every late Workflow A response after navigating to Workflow B', async ({ page }) => {
  let releaseWorkflowA!: () => void
  const workflowAGate = new Promise<void>((resolve) => { releaseWorkflowA = resolve })
  let workflowARequests = 0
  let workflowAResponses = 0
  const workflowA = {
    ...mockWorkflow,
    id: 'workflow-a',
    name: 'Workflow A Sidebar Title',
    description: 'Workflow A sidebar description',
  }
  const workflowB = {
    ...mockWorkflow,
    id: 'workflow-b',
    name: 'Workflow B Sidebar Title',
    description: 'Workflow B sidebar description',
  }
  const versionA = structuredClone(editorInteractionWorkflowVersion)
  versionA.workflow_id = 'workflow-a'
  versionA.graph_json.name = 'Builder A'
  const versionB = structuredClone(editorInteractionWorkflowVersion)
  versionB.workflow_id = 'workflow-b'
  versionB.graph_json.name = 'Builder B'

  const handleWorkflowRequest = async (route: Parameters<Parameters<typeof page.route>[1]>[0]) => {
    const url = new URL(route.request().url())
    const isWorkflowA = url.pathname.includes('/workflows/workflow-a')
    if (isWorkflowA) {
      workflowARequests += 1
      await workflowAGate
      workflowAResponses += 1
    }
    const isVersion = url.pathname.endsWith('/version/current')
    const data = isWorkflowA
      ? (isVersion ? versionA : workflowA)
      : (isVersion ? versionB : workflowB)
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data }),
    })
  }
  await page.route('**/api/v1/workflows/workflow-*/version/current', handleWorkflowRequest)
  await page.route('**/api/v1/workflows/workflow-*', handleWorkflowRequest)

  await page.goto('/workflow/workflow-a/build', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => workflowARequests).toBeGreaterThanOrEqual(3)
  await navigateClientRoute(page, '/workflow/workflow-b/build')
  await expect(page.getByPlaceholder('Workflow name')).toHaveValue('Builder B')
  const workflowSidebarHeader = page.locator('[data-sidebar="header"]').filter({
    has: page.getByText('Status', { exact: true }),
  })
  await expect(workflowSidebarHeader).toHaveCount(1)
  await expect(workflowSidebarHeader.getByText('Workflow B Sidebar Title', { exact: true })).toBeVisible()
  await expect(workflowSidebarHeader.getByText('Workflow B sidebar description', { exact: true })).toBeVisible()

  const pendingWorkflowAResponses = workflowARequests
  releaseWorkflowA()
  await expect.poll(() => workflowAResponses).toBe(pendingWorkflowAResponses)
  await page.waitForTimeout(200)

  await expect(workflowSidebarHeader.getByText('Workflow B Sidebar Title', { exact: true })).toBeVisible()
  await expect(workflowSidebarHeader.getByText('Workflow B sidebar description', { exact: true })).toBeVisible()
  expect(await workflowSidebarHeader.getByText('Workflow A Sidebar Title', { exact: true }).count()).toBe(0)
  expect(await workflowSidebarHeader.getByText('Workflow A sidebar description', { exact: true }).count()).toBe(0)
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

for (const templateOutcome of [
  { name: 'success', status: 201, rawMessage: 'OK' },
  { name: 'failure', status: 503, rawMessage: 'late template failure' },
] as const) {
  test(`ticket triage template suppresses a pending ${templateOutcome.name} after Builder unmount`, async ({ page }) => {
    let releaseTemplate!: () => void
    const templateGate = new Promise<void>((resolve) => { releaseTemplate = resolve })
    let templateRequests = 0
    let templateResponses = 0
    await page.route('**/api/v1/workflows/templates/ticket-triage', async (route) => {
      templateRequests += 1
      await templateGate
      templateResponses += 1
      await route.fulfill({
        status: templateOutcome.status,
        contentType: 'application/json',
        body: JSON.stringify({
          success: templateOutcome.status === 201,
          code: templateOutcome.status === 201 ? 'OK' : 'SERVICE_UNAVAILABLE',
          message: templateOutcome.rawMessage,
          data: templateOutcome.status === 201
            ? { ...mockWorkflow, id: 'stale-template-workflow', name: 'Ticket triage' }
            : null,
        }),
      })
    })
    await page.route('**/api/v1/resource-grants**', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
      })
    })

    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    await page.getByRole('tab', { name: 'Templates' }).click()
    await page.getByRole('button', { name: /Ticket triage/ }).click()
    await expect.poll(() => templateRequests).toBe(1)

    await navigateClientRoute(page, '/workflow/workflow-1/setting')
    await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')
    releaseTemplate()
    await expect.poll(() => templateResponses).toBe(1)
    await page.waitForTimeout(200)
    await expect(page).toHaveURL(/\/workflow\/workflow-1\/setting$/)
    expect(await page.getByText('Ticket triage workflow created', { exact: true }).count()).toBe(0)
    expect(await page.getByText('Failed to create ticket triage workflow', { exact: true }).count()).toBe(0)
    if (templateOutcome.status !== 201) {
      expect(await page.getByText(templateOutcome.rawMessage, { exact: true }).count()).toBe(0)
    }
  })
}

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

test('workflow palette shows only canonical supported nodes', async ({ page }) => {
  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })

  const palette = page.getByRole('tabpanel', { name: 'Nodes' })
  await expect(palette.getByRole('button')).toHaveCount(8)
  for (const label of ['Input', 'Transform', 'Variable Assignment', 'LLM', 'Knowledge Search', 'Tool Call', 'Condition', 'Output']) {
    await expect(palette.getByRole('button', { name: new RegExp(`^${label}`) })).toBeVisible({ timeout: 15_000 })
  }
  await expect(page.getByText('Loop', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Code Execution', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Agent', { exact: true })).toHaveCount(0)

  const inputPaletteItem = palette.getByRole('button', { name: /^Input/ })
  expect(await inputPaletteItem.evaluate((element) => element.tagName)).toBe('BUTTON')
  const nodeCount = await page.locator('.react-flow__node').count()
  const scrollY = await page.evaluate(() => window.scrollY)
  await inputPaletteItem.focus()
  await inputPaletteItem.press('Space')
  await expect(page.locator('.react-flow__node')).toHaveCount(nodeCount + 1)
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollY)
})

test('workflow palette localizes loading, error, and empty capability states', async ({ page }) => {
  let releaseLoading!: () => void
  const loadingGate = new Promise<void>((resolve) => { releaseLoading = resolve })
  await page.route('**/api/v1/workflows/capabilities', async (route) => {
    await loadingGate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflowCapabilities }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('status')).toHaveText('Loading supported workflow nodes...')
  releaseLoading()
  await expect(page.getByText('Input', { exact: true }).first()).toBeVisible({ timeout: 15_000 })

  await page.unroute('**/api/v1/workflows/capabilities')
  await page.route('**/api/v1/workflows/capabilities', async (route) => {
    await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: 'unavailable' }) })
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('status')).toHaveText('Unable to load workflow capabilities. Adding nodes is disabled.')

  await page.unroute('**/api/v1/workflows/capabilities')
  await page.route('**/api/v1/workflows/capabilities', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { ...mockWorkflowCapabilities, capabilities: [] },
      }),
    })
  })
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('status')).toHaveText('No workflow capabilities are available. Adding nodes is disabled.')
})

test('unsupported historical node is read only and preserves its runtime type', async ({ page }) => {
  const legacy: any = structuredClone(mockWorkflowVersion)
  legacy.graph_json.graph.nodes = [
    {
      id: 'legacy-loop',
      type: 'loop',
      name: 'Legacy Loop',
      params: { max_iterations: 3 },
      ui: { builder_type: 'loop-node', position: { x: 80, y: 80 }, data: { label: 'Legacy Loop' } },
    },
    {
      id: 'legacy-transform',
      type: 'transform',
      name: 'Legacy Transform',
      params: { mapping: { value: true } },
      ui: { builder_type: 'transform-node', position: { x: 360, y: 280 }, data: { label: 'Legacy Transform' } },
    },
    {
      id: 'legacy-output',
      type: 'output',
      name: 'Legacy Output',
      params: { value: true },
      ui: { builder_type: 'output-node', position: { x: 680, y: 280 }, data: { label: 'Legacy Output' } },
    },
  ]
  legacy.graph_json.graph.edges = [
    { id: 'legacy-canonical-edge', from: 'legacy-transform', to: 'legacy-output', from_port: 'output', to_port: 'input', condition: null },
  ]
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: legacy }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Unsupported historical node', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('loop', { exact: true })).toBeVisible()
  await expect(page.getByText('This node is read only and cannot be republished.')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()

  const pane = page.locator('.react-flow__pane')
  const paneBox = await pane.boundingBox()
  expect(paneBox).not.toBeNull()
  await page.mouse.move(paneBox!.x + paneBox!.width / 2, paneBox!.y + paneBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(paneBox!.x + paneBox!.width / 2 + 320, paneBox!.y + paneBox!.height / 2)
  await page.mouse.up()
  await page.locator('.react-flow__node-compatibility-node').click()
  await expect(page.getByText('Original parameters', { exact: true })).toBeVisible()
  await expect(page.getByText('Original UI data', { exact: true })).toBeVisible()
  const compatibilityJson = page.locator('pre')
  await expect(compatibilityJson.nth(0)).toContainText('"max_iterations": 3')
  await expect(compatibilityJson.nth(1)).toContainText('"builder_type": "loop-node"')

  const compatibilityNode = page.locator('.react-flow__node-compatibility-node')
  const deleteButton = page.getByRole('button', { name: 'Delete selected node' })
  await expect(deleteButton).toBeDisabled()
  const initialNodeStyle = await compatibilityNode.getAttribute('style')
  const initialEdgeCount = await page.locator('.react-flow__edge').count()
  const nodeBox = await compatibilityNode.boundingBox()
  expect(nodeBox).not.toBeNull()
  await page.mouse.move(nodeBox!.x + nodeBox!.width / 2, nodeBox!.y + nodeBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(nodeBox!.x + nodeBox!.width / 2 + 120, nodeBox!.y + nodeBox!.height / 2 + 80)
  await page.mouse.up()
  await expect(compatibilityNode).toHaveAttribute('style', initialNodeStyle!)

  await compatibilityNode.press('Delete')
  await expect(compatibilityNode).toHaveCount(1)
  await expect(page.locator('.react-flow__edge')).toHaveCount(initialEdgeCount)

  await expect(compatibilityNode.locator('.react-flow__handle.source')).toHaveCount(0)
  const outputTarget = page.locator('.react-flow__node[data-id="legacy-output"] .react-flow__handle.target')
  const targetBox = await outputTarget.boundingBox()
  expect(targetBox).not.toBeNull()
  await page.mouse.move(nodeBox!.x + nodeBox!.width - 2, nodeBox!.y + nodeBox!.height / 2)
  await page.mouse.down()
  await page.mouse.move(targetBox!.x + targetBox!.width / 2, targetBox!.y + targetBox!.height / 2)
  await page.mouse.up()
  await expect(page.locator('.react-flow__edge')).toHaveCount(initialEdgeCount)
})

test('compatibility workflow exports its original persisted DSL without republishing', async ({ page }) => {
  const graphJson = {
    name: 'Lossless legacy workflow',
    version: 'legacy-v7',
    description: 'Retain the original envelope',
    inputs_schema: { type: 'object', required: ['question'] },
    outputs_schema: { type: 'object', properties: { result: { type: 'string' } } },
    limits: { max_steps: 0 },
    runtime: { engine: 'legacy-engine', flags: ['preserve', false, 0] },
    policy: null,
    semantics: { on_error: 'legacy' },
    extension_envelope: { owner: '<script>window.__importInjected = true</script>', enabled: false },
    graph: {
      nodes: [
        {
          id: 'legacy-loop',
          type: 'loop',
          name: 'Legacy Loop',
          params: { max_iterations: 3, items: [null, false, 0, ''] },
          ui: {
            builder_type: 'loop-node',
            position: { x: 80, y: 80 },
            data: { label: 'Legacy Loop', nested: { collapsed: false } },
            ports: { input: null, output: 'legacy-result' },
          },
        },
        {
          id: 'legacy-output',
          type: 'output',
          name: 'Legacy Output',
          params: { value: '{{ steps.legacy-loop.output }}' },
          ui: { builder_type: 'output-node', position: { x: 420, y: 80 }, data: { label: 'Legacy Output' } },
        },
      ],
      edges: [
        {
          id: 'legacy-edge',
          from: 'legacy-loop',
          to: 'legacy-output',
          from_port: null,
          to_port: 'input',
          condition: '{{ legacy.custom.branch }}',
          legacy_metadata: { retries: 0, enabled: false },
        },
      ],
    },
  }
  const legacyVersion = { ...mockWorkflowVersion, graph_json: graphJson }
  let mutationRequests = 0
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: legacyVersion }),
    })
  })
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/api/v1/workflows/workflow-1')) mutationRequests += 1
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Unsupported historical node', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()

  const exported = await downloadWorkflowFile(page)
  expect(exported).toMatchObject({ format: 'soit-workflow-spec-v1' })
  expect(exported.graph_json).toEqual(graphJson)
  expect(mutationRequests).toBe(0)
})

test('loaded legacy condition branches attach to canonical visual handles', async ({ page }) => {
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: legacyConditionHandleWorkflowVersion }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  const conditionNode = page.locator('.react-flow__node[data-id="legacy-condition"]')
  await expect(conditionNode).toBeVisible({ timeout: 15_000 })
  await expect(conditionNode.locator('.react-flow__handle.source[data-handleid="true"]')).toHaveCount(1)
  await expect(conditionNode.locator('.react-flow__handle.source[data-handleid="false"]')).toHaveCount(1)
  await expect(conditionNode.locator('[data-handleid="output-true"], [data-handleid="output-false"]')).toHaveCount(0)
  for (const edgeId of ['legacy-true-edge', 'legacy-false-edge']) {
    const edge = page.locator(`.react-flow__edge[data-id="${edgeId}"]`)
    await expect(edge).toBeVisible()
    await expect(edge.locator('.react-flow__edge-path')).toHaveAttribute('d', /\S+/)
  }
})

test('properties label edit is preserved in the workflow save request', async ({ page }) => {
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
  await page.locator('.react-flow__node[data-id="llm"]').click()
  await page.locator('#node-name').fill('Renamed Canonical LLM')
  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()
  const savedLlm = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes.find(
    (node: Record<string, unknown>) => node.id === 'llm',
  )
  expect(savedLlm.name).toBe('Renamed Canonical LLM')
  expect(savedLlm.params).toEqual(canonicalNodeParams.llm)
  expect(savedLlm.ui.data).toEqual({
    label: 'Renamed Canonical LLM',
    modelName: 'stale:model',
    presentation: 'model-card',
  })
})

test('scoped workflow resources load accessible inventory options and save only canonical references', async ({ page }) => {
  let versionPayload: Record<string, any> | null = null
  const requestedInventories: string[] = []

  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: scopedResourceWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    requestedInventories.push(new URL(route.request().url()).pathname)
    expect(route.request().headers()['x-workspace-id']).toBe('workspace-1')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockModelWorkbenchResponse([{
          id: 'model-1',
          provider_id: 'provider-1',
          provider_slug: 'provider-1',
          provider_name: 'Primary Provider',
          provider_kind: 'openai',
          model_id: 'gpt-primary',
          display_name: 'Primary GPT',
          model_type: 'text',
          status: 'available',
          sync_status: 'synced',
          source: 'manual',
          month_calls: 0,
          today_calls: 0,
          month_tokens: 0,
          month_cost_amount: 0,
          recent_exception_count: 0,
          updated_at: '2026-07-19T00:00:00.000Z',
          action_enabled: true,
        }]) }),
    })
  })
  await page.route('**/api/v1/knowledge**', async (route) => {
    requestedInventories.push(new URL(route.request().url()).pathname)
    expect(route.request().headers()['x-workspace-id']).toBe('workspace-1')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockKnowledgeListResponse([
        mockKnowledgeBase({ id: 'kb-support', name: 'Support KB', status: 'active' }),
      ]) }),
    })
  })
  await page.route('**/api/v1/plugins/runtime/tools', async (route) => {
    requestedInventories.push(new URL(route.request().url()).pathname)
    expect(route.request().headers()['x-workspace-id']).toBe('workspace-1')
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
        tools: [{
          tool_ref: 'tool:plugin:tickets:create',
          version: '1.10.0',
          plugin: { name: 'tickets', version: '1.10.0' },
          tool_spec: { name: 'Create ticket', description: 'Create a support ticket', input_schema: {} },
        }],
      } }),
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

  await page.locator('.react-flow__node[data-id="scoped-llm"]').click()
  await expect(page.locator('#modelRef')).toContainText('Unavailable: model:legacy:missing')
  await page.locator('#modelRef').click()
  await expect(page.getByRole('option', { name: 'Primary GPT' })).toBeVisible()
  await page.getByRole('option', { name: 'Primary GPT' }).click()

  await page.locator('.react-flow__node[data-id="scoped-knowledge"]').click()
  await expect(page.locator('#knowledgeRef')).toContainText('Unavailable: knowledge:legacy-missing')
  await page.locator('#knowledgeRef').click()
  await expect(page.getByRole('option', { name: 'Support KB' })).toBeVisible()
  await page.getByRole('option', { name: 'Support KB' }).click()

  await page.locator('.react-flow__node[data-id="scoped-tool"]').click()
  await expect(page.locator('#toolRef')).toContainText('Unavailable: tool:legacy:missing')
  await page.locator('#toolRef').click()
  const createTicketOption = page.getByRole('option', {
    name: /Create ticket.*tool:plugin:tickets:create.*v1\.10\.0/,
  })
  await expect(createTicketOption).toBeVisible()
  await createTicketOption.click()

  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()

  const savedNodes = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'scoped-llm').params).toEqual({
    model: 'model:provider-1:gpt-primary',
    prompt: '{{ inputs.question }}',
  })
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'scoped-knowledge').params).toEqual({
    knowledge_ref: 'knowledge:kb-support',
    query: '{{ inputs.question }}',
    top_k: 3,
  })
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'scoped-tool').params).toEqual({
    tool_ref: 'tool:plugin:tickets:create',
    arguments: {},
    input: '{{ steps.scoped-knowledge.output.result }}',
  })
  expect(requestedInventories.sort()).toEqual([
    '/api/v1/knowledge',
    '/api/v1/modelhub/workbench/models',
    '/api/v1/plugins/runtime/tools',
  ])
})

test('scoped workflow resources preserve broad ModelHub references and save them exactly', async ({ page }) => {
  let versionPayload: Record<string, any> | null = null
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: scopedResourceWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockModelWorkbenchResponse([{
        id: 'versioned-model',
        provider_id: 'provider-openrouter',
        provider_slug: 'openrouter',
        provider_name: 'OpenRouter',
        provider_kind: 'openrouter',
        model_id: 'meta-llama/llama-3.1@stable',
        display_name: 'OpenRouter Llama',
        model_type: 'text',
        status: 'available',
        sync_status: 'synced',
        source: 'manual',
        month_calls: 0,
        today_calls: 0,
        month_tokens: 0,
        month_cost_amount: 0,
        recent_exception_count: 0,
        updated_at: '2026-07-19T00:00:00.000Z',
        action_enabled: true,
      }]) }),
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
  await page.locator('.react-flow__node[data-id="scoped-llm"]').click()
  await page.locator('#modelRef').click()
  await page.getByRole('option', { name: 'OpenRouter Llama' }).click()
  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()

  const savedLlm = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes.find(
    (node: Record<string, unknown>) => node.id === 'scoped-llm',
  )
  expect(savedLlm.params.model).toBe('model:openrouter:meta-llama/llama-3.1@stable')
})

test('scoped workflow resources refetch after a workspace route transition instead of reusing cached options', async ({ page }) => {
  const requestedWorkspaces: string[] = []
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: scopedResourceWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    const workspaceId = route.request().headers()['x-workspace-id'] || 'missing'
    requestedWorkspaces.push(workspaceId)
    const suffix = workspaceId === 'workspace-b' ? 'B' : 'A'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockModelWorkbenchResponse([{
        id: `workspace-${suffix.toLowerCase()}-model`,
        provider_id: `provider-${suffix.toLowerCase()}`,
        provider_slug: `workspace-${suffix.toLowerCase()}`,
        provider_name: `Workspace ${suffix}`,
        provider_kind: 'openai',
        model_id: 'primary',
        display_name: `Workspace ${suffix} Model`,
        model_type: 'text',
        status: 'available',
        sync_status: 'synced',
        source: 'manual',
        month_calls: 0,
        today_calls: 0,
        month_tokens: 0,
        month_cost_amount: 0,
        recent_exception_count: 0,
        updated_at: '2026-07-19T00:00:00.000Z',
        action_enabled: true,
      }]) }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await page.locator('.react-flow__node[data-id="scoped-llm"]').click()
  await page.locator('#modelRef').click()
  await expect(page.getByRole('option', { name: 'Workspace A Model' })).toBeVisible()
  await page.keyboard.press('Escape')

  await page.getByRole('button').filter({ has: page.locator('svg.lucide-workflow') }).first().click()
  await expect(page).toHaveURL(/\/workflow$/)
  await page.evaluate(() => localStorage.setItem('workspace_id', 'workspace-b'))
  await page.goBack({ waitUntil: 'domcontentloaded' })
  await page.locator('.react-flow__node[data-id="scoped-llm"]').click()
  await page.locator('#modelRef').click()
  await expect(page.getByRole('option', { name: 'Workspace B Model' })).toBeVisible()
  await expect(requestedWorkspaces).toEqual(['workspace-1', 'workspace-b'])
})

test('scoped workflow resources keep restored references visible and fail closed on malformed inventories', async ({ page }) => {
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: scopedResourceWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockModelWorkbenchResponse([{
        id: 'malformed-model',
        provider_slug: '',
        model_id: '',
        display_name: '',
        model_type: 'text',
        status: 'available',
        updated_at: '2026-07-19T00:00:00.000Z',
      }]) }),
    })
  })
  await page.route('**/api/v1/knowledge**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockKnowledgeListResponse([
        mockKnowledgeBase({ id: 'malformed-knowledge', name: '', status: 'active' }),
      ]) }),
    })
  })
  await page.route('**/api/v1/plugins/runtime/tools', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
        tools: [{
          tool_ref: 'tool:malformed',
          version: '',
          plugin: { name: 'malformed', version: '' },
          tool_spec: {},
        }],
      } }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })

  for (const resource of [
    { nodeId: 'scoped-llm', trigger: '#modelRef', ref: 'model:legacy:missing', error: 'Unable to load models.' },
    { nodeId: 'scoped-knowledge', trigger: '#knowledgeRef', ref: 'knowledge:legacy-missing', error: 'Unable to load knowledge bases.' },
    { nodeId: 'scoped-tool', trigger: '#toolRef', ref: 'tool:legacy:missing', error: 'Unable to load tools.' },
  ]) {
    await page.locator(`.react-flow__node[data-id="${resource.nodeId}"]`).click()
    await expect(page.locator(resource.trigger)).toBeDisabled()
    await expect(page.locator(resource.trigger)).toContainText(`Unavailable: ${resource.ref}`)
    await expect(page.getByText(resource.error, { exact: true })).toBeVisible()
  }
})

test('scoped workflow resources localize loading, empty, and disabled inventory states', async ({ page }) => {
  let releaseModels: (() => void) | undefined
  const modelsReady = new Promise<void>((resolve) => {
    releaseModels = resolve
  })
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: scopedResourceWorkflowVersion }),
    })
  })
  await page.route('**/api/v1/modelhub/workbench/models**', async (route) => {
    await modelsReady
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockModelWorkbenchResponse([]) }),
    })
  })
  await page.route('**/api/v1/knowledge**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockKnowledgeListResponse([
        mockKnowledgeBase({ id: 'kb-archived', name: 'Archived KB', status: 'archived' }),
      ]) }),
    })
  })
  await page.route('**/api/v1/plugins/runtime/tools', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { tools: [] } }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })

  await page.locator('.react-flow__node[data-id="scoped-llm"]').click()
  await expect(page.getByText('Loading models...', { exact: true })).toBeVisible()
  await expect(page.locator('#modelRef')).toBeDisabled()
  releaseModels?.()
  await expect(page.getByText('No models available.', { exact: true })).toBeVisible()
  await expect(page.locator('#modelRef')).toContainText('Unavailable: model:legacy:missing')

  await page.locator('.react-flow__node[data-id="scoped-knowledge"]').click()
  await expect(page.locator('#knowledgeRef')).toBeEnabled()
  await page.locator('#knowledgeRef').click()
  const disabledKnowledge = page.getByRole('option', { name: 'Archived KB (Unavailable)' })
  await expect(disabledKnowledge).toBeVisible()
  await expect(disabledKnowledge).toHaveAttribute('aria-disabled', 'true')
  await page.keyboard.press('Escape')

  await page.locator('.react-flow__node[data-id="scoped-tool"]').click()
  await expect(page.getByText('No tools available.', { exact: true })).toBeVisible()
  await expect(page.locator('#toolRef')).toBeDisabled()
  await expect(page.locator('#toolRef')).toContainText('Unavailable: tool:legacy:missing')
})

test('property editors retain sequential input and save the latest combined values', async ({ page }) => {
  let versionPayload: Record<string, any> | null = null
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
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

  await page.locator('.react-flow__node[data-id="interaction-input"]').click()
  const inputSelect = page.locator('#input-select')
  await inputSelect.pressSequentially('question')
  await inputSelect.press('Enter')
  await inputSelect.pressSequentially('locale')
  await expect(inputSelect).toHaveValue('question\nlocale')

  await page.locator('.react-flow__node[data-id="interaction-variable"]').click()
  const variableKey = page.locator('#variable-key')
  await variableKey.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
  await variableKey.pressSequentially('approved')
  await expect(variableKey).toHaveValue('approved')
  const variableValue = page.locator('#variable-value')
  await variableValue.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
  await variableValue.pressSequentially('{"nested":{"enabled":false},"count":0}')
  await expect(variableValue).toHaveValue('{\n  "nested": {\n    "enabled": false\n  },\n  "count": 0\n}')

  await selectWorkflowNode(page, 'interaction-condition')
  const condition = page.locator('#conditional-expression')
  await condition.press(process.platform === 'darwin' ? 'Meta+A' : 'Control+A')
  await condition.pressSequentially('{{ inputs.approved }}')
  await expect(condition).toHaveValue('{{ inputs.approved }}')

  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()
  const savedNodes = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'interaction-input').params).toEqual({
    select: ['question', 'locale'],
  })
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'interaction-variable').params).toEqual({
    key: 'approved',
    value: { nested: { enabled: false }, count: 0 },
  })
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'interaction-condition').params).toEqual({
    condition: '{{ inputs.approved }}',
  })
})

test('invalid JSON drafts block save and test run until exact JSON values are repaired', async ({ page }) => {
  let versionPayload: Record<string, any> | null = null
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: editorInteractionWorkflowVersion }),
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
  const save = page.getByRole('button', { name: 'Save Workflow' })
  const testRun = page.getByRole('button', { name: 'Test Run' })

  await page.locator('.react-flow__node[data-id="interaction-transform"]').click()
  const mapping = page.locator('#transform-mapping')
  await mapping.fill('{')
  await expect(mapping).toHaveAttribute('aria-invalid', 'true')
  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()
  const exportWorkflow = page.getByRole('button', { name: 'Export Workflow' })
  await expect(exportWorkflow).toBeDisabled()
  await expect(exportWorkflow).toHaveAccessibleDescription('Repair invalid JSON before exporting the workflow.')
  expect(versionPayload).toBeNull()

  await mapping.fill('{"nested":{"enabled":false},"count":0}')
  await expect(mapping).toHaveValue('{\n  "nested": {\n    "enabled": false\n  },\n  "count": 0\n}')
  await expect(save).toBeEnabled()
  await expect(testRun).toBeEnabled()

  await page.locator('.react-flow__node[data-id="interaction-variable"]').click()
  const variableValue = page.locator('#variable-value')
  await variableValue.fill('[')
  await expect(variableValue).toHaveAttribute('aria-invalid', 'true')
  await expect(save).toBeDisabled()
  await expect(testRun).toBeDisabled()

  for (const value of [null, false, 0, '', ['a', 0, false], { nested: { enabled: false }, count: 0 }]) {
    const text = JSON.stringify(value)
    await variableValue.fill(text)
    await expect(variableValue).toHaveValue(JSON.stringify(value, null, 2))
    await expect(variableValue).toHaveAttribute('aria-invalid', 'false')
    await expect(save).toBeEnabled()
    await expect(testRun).toBeEnabled()
  }

  await save.click()
  await expect.poll(() => versionPayload).not.toBeNull()
  const savedNodes = (versionPayload as unknown as Record<string, any>).graph_json.graph.nodes
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'interaction-transform').params).toEqual({
    mapping: { nested: { enabled: false }, count: 0 },
  })
  expect(savedNodes.find((node: Record<string, unknown>) => node.id === 'interaction-variable').params).toEqual({
    key: 'old',
    value: { nested: { enabled: false }, count: 0 },
  })
})

test('workflow export import save round-trip preserves the canonical persisted contract', async ({ page }) => {
  const exportedVersion: any = structuredClone(canonicalWorkflowVersion)
  const exportedLlm = exportedVersion.graph_json.graph.nodes.find((node: Record<string, unknown>) => node.id === 'llm')
  exportedLlm.ui.nested_metadata = { layout: { width: 360, pinned: false }, tags: ['canonical', 'export'] }
  let servedVersion: any = exportedVersion
  let versionPayload: Record<string, any> | null = null

  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: servedVersion }),
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
  const exportedData = await downloadWorkflowFile(page)
  expect(exportedData).not.toHaveProperty('nodes')
  expect(exportedData.graph_json.graph.nodes.find((node: Record<string, unknown>) => node.id === 'llm').ui).toEqual(exportedLlm.ui)

  servedVersion = externalCanonicalNullUiWorkflowVersion
  await page.reload({ waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Import Workflow' })).toBeVisible()
  await importWorkflowFile(page, exportedData, 'canonical-workflow.json')
  const importDialog = page.getByRole('dialog')
  await expect(importDialog.getByText('Import workflow', { exact: true })).toBeVisible()
  await expect(importDialog.getByRole('button', { name: 'Cancel' })).toBeVisible()
  await importDialog.getByRole('button', { name: 'Import' }).click()
  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()
  expect((versionPayload as unknown as Record<string, any>).graph_json).toEqual(exportedData.graph_json)
})

test('hostile and canceled imports leave the complete editor state untouched', async ({ page }) => {
  const originalVersion: any = structuredClone(editorInteractionWorkflowVersion)
  originalVersion.graph_json.version = 'preserved-local-base-v1'
  originalVersion.graph_json.limits = { max_steps: 9, timeout_ms: 12_345 }
  await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: originalVersion }),
    })
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  const workflowName = page.getByPlaceholder('Workflow name')
  const workflowDescription = page.getByPlaceholder('Workflow description')
  await workflowName.fill('Unsaved local name')
  await workflowDescription.fill('Unsaved local description')
  await page.locator('.react-flow__node[data-id="interaction-transform"]').click()
  const mapping = page.locator('#transform-mapping')
  await mapping.fill('{')
  const originalNodeCount = await page.locator('.react-flow__node').count()

  const invalidImports = [
    { format: 'wrong-format', graph_json: canonicalWorkflowVersion.graph_json },
    { format: 'soit-workflow-spec-v1', graph_json: 1 },
    { format: 'soit-workflow-spec-v1', graph_json: [] },
    { format: 'soit-workflow-spec-v1', graph_json: {} },
    {
      format: 'soit-workflow-spec-v1',
      graph_json: {
        name: 'Empty graph',
        inputs_schema: {},
        outputs_schema: {},
        graph: { nodes: [], edges: [] },
      },
    },
  ]
  for (const [index, invalidImport] of invalidImports.entries()) {
    await importWorkflowFile(page, invalidImport, `invalid-${index}.json`)
    await expect(page.getByText('Import failed: invalid workflow file format').last()).toBeVisible()
  }

  const canceledGraph = structuredClone(canonicalWorkflowVersion.graph_json)
  canceledGraph.name = '<img src=x onerror="window.__importInjected=true">'
  await importWorkflowFile(page, { format: 'soit-workflow-spec-v1', graph_json: canceledGraph }, 'cancel.json')
  const dialog = page.getByRole('dialog')
  await expect(dialog).toContainText(canceledGraph.name)
  await expect(dialog.locator('img')).toHaveCount(0)
  await expect(dialog.getByRole('button', { name: 'Import' })).toBeVisible()
  await dialog.getByRole('button', { name: 'Cancel' }).click()

  await expect(workflowName).toHaveValue('Unsaved local name')
  await expect(workflowDescription).toHaveValue('Unsaved local description')
  await expect(page.locator('.react-flow__node')).toHaveCount(originalNodeCount)
  await expect(mapping).toBeVisible()
  await expect(mapping).toHaveValue('{')
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Export Workflow' })).toBeDisabled()
  expect(await page.evaluate(() => (window as any).__importInjected)).toBeUndefined()

  await mapping.fill('{"initial":true}')
  const exported = await downloadWorkflowFile(page)
  expect(exported.graph_json).toMatchObject({
    name: 'Unsaved local name',
    description: 'Unsaved local description',
    version: originalVersion.graph_json.version,
    limits: originalVersion.graph_json.limits,
    inputs_schema: originalVersion.graph_json.inputs_schema,
    outputs_schema: originalVersion.graph_json.outputs_schema,
  })
  expect(exported.graph_json.graph.nodes.map((node: Record<string, unknown>) => node.id)).toEqual(
    originalVersion.graph_json.graph.nodes.map((node: Record<string, unknown>) => node.id),
  )
})

for (const malformedStructure of [
  {
    label: 'nodes container',
    graphJson: { ...canonicalWorkflowVersion.graph_json, graph: { ...canonicalWorkflowVersion.graph_json.graph, nodes: {} } },
  },
  {
    label: 'edges container',
    graphJson: { ...canonicalWorkflowVersion.graph_json, graph: { ...canonicalWorkflowVersion.graph_json.graph, edges: 'malformed' } },
  },
  {
    label: 'inputs schema container',
    graphJson: { ...canonicalWorkflowVersion.graph_json, inputs_schema: [] },
  },
  {
    label: 'outputs schema container',
    graphJson: { ...canonicalWorkflowVersion.graph_json, outputs_schema: 'malformed' },
  },
]) {
  test(`import rejects a malformed ${malformedStructure.label} without mutating editor state`, async ({ page }) => {
    await page.route('**/api/v1/workflows/workflow-1/version/current', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: canonicalWorkflowVersion }),
      })
    })
    await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
    const workflowName = page.getByPlaceholder('Workflow name')
    await workflowName.fill('Keep local workflow name')
    await page.locator('.react-flow__node[data-id="llm"]').click()
    const originalNodeCount = await page.locator('.react-flow__node').count()

    await importWorkflowFile(page, {
      format: 'soit-workflow-spec-v1',
      graph_json: malformedStructure.graphJson,
    }, `malformed-${malformedStructure.label}.json`)

    await expect(page.getByText('Import failed: invalid workflow file format')).toBeVisible()
    await expect(page.getByRole('dialog')).toHaveCount(0)
    await expect(workflowName).toHaveValue('Keep local workflow name')
    await expect(page.locator('.react-flow__node')).toHaveCount(originalNodeCount)
    await expect(page.locator('#node-name')).toHaveValue('Canonical LLM')
  })
}

test('compatibility import stays read only and remains losslessly exportable', async ({ page }) => {
  const graphJson = {
    name: 'Imported compatibility workflow',
    description: 'Unsupported node and malformed edge',
    inputs_schema: { type: 'object' },
    outputs_schema: { type: 'object' },
    runtime: { legacy: true },
    extension_envelope: { retained: ['exact', false, 0, null] },
    graph: {
      nodes: [
        {
          id: 'legacy-node',
          type: 'http',
          name: 'Legacy HTTP',
          params: { url: 'https://example.invalid/<script>', body: { enabled: false } },
          ui: { builder_type: 'http-node', position: { x: 90, y: 120 }, data: { label: 'Legacy HTTP' } },
        },
        {
          id: 'output',
          type: 'output',
          name: 'Output',
          params: { value: null },
          ui: { builder_type: 'output-node', position: { x: 420, y: 120 }, data: { label: 'Output' } },
        },
      ],
      edges: [
        { id: 'malformed-edge', from: 'legacy-node', to: 'output', from_port: null, condition: false, extra: '<b>raw</b>' },
        false,
      ],
    },
  }
  let mutationRequests = 0
  page.on('request', (request) => {
    if (request.method() !== 'GET' && request.url().includes('/api/v1/workflows/workflow-1')) mutationRequests += 1
  })

  await page.goto('/workflow/workflow-1/build', { waitUntil: 'domcontentloaded' })
  await importWorkflowFile(page, { format: 'soit-workflow-spec-v1', graph_json: graphJson }, 'compatibility.json')
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('Import workflow', { exact: true })).toBeVisible()
  await dialog.getByRole('button', { name: 'Import' }).click()

  await expect(page.getByText('Unsupported historical node', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
  const exported = await downloadWorkflowFile(page)
  expect(exported.graph_json).toEqual(graphJson)
  expect(mutationRequests).toBe(0)
})

test('workflow palette blocks capability mismatch and excludes unknown entries from serialization', async ({ page }) => {
  let versionPayload: Record<string, any> | null = null
  const mismatch = structuredClone(mockWorkflowCapabilities)
  mismatch.capabilities[3] = { ...mismatch.capabilities[3], ui_type: 'unknown-ui-node' }
  await page.route('**/api/v1/workflows/capabilities', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mismatch }),
    })
  })
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
  await expect(page.getByText('Workflow capability contract mismatch. Adding nodes is disabled.')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('unknown-ui-node', { exact: true })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeEnabled()
  await page.getByRole('button', { name: 'Save Workflow' }).click()
  await expect.poll(() => versionPayload).not.toBeNull()
  expect((versionPayload as unknown as Record<string, any>).graph_json.graph.nodes).not.toContainEqual(
    expect.objectContaining({ ui: expect.objectContaining({ builder_type: 'unknown-ui-node' }) }),
  )
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

  test('lossless mixed export keeps raw unsupported data without reverting changed canonical edges', () => {
    const compatibilityNode = {
      id: 'legacy-loop',
      type: 'loop',
      name: 'Legacy Loop',
      params: { max_iterations: 3, values: [null, false, 0] },
      ui: { builder_type: 'loop-node', position: { x: 40, y: 40 }, data: { label: 'Legacy Loop' } },
    }
    const unsupportedEdge = {
      id: 'legacy-edge',
      from: 'legacy-loop',
      to: 'output',
      from_port: null,
      condition: false,
      legacy_metadata: { keep: true },
    }
    const originalBranch = {
      id: 'canonical-branch',
      from: 'condition',
      to: 'output',
      from_port: 'output-true',
      to_port: 'input',
      condition: 'true',
    }
    const unchangedCanonicalEdge = {
      id: 'canonical-unchanged',
      from: 'transform',
      to: 'output',
      from_port: 'result',
      to_port: null,
      condition: null,
    }
    const graphJson = {
      name: 'Mixed compatibility graph',
      inputs_schema: {},
      outputs_schema: {},
      graph: {
        nodes: [
          compatibilityNode,
          {
            id: 'condition',
            type: 'condition',
            name: 'Condition',
            params: { condition: '{{ inputs.approved }}' },
            ui: { builder_type: 'conditional-node', position: { x: 280, y: 40 }, data: { label: 'Condition' } },
          },
          {
            id: 'transform',
            type: 'transform',
            name: 'Transform',
            params: { mapping: { original: true } },
            ui: { builder_type: 'transform-node', position: { x: 520, y: 40 }, data: { label: 'Transform' } },
          },
          {
            id: 'output',
            type: 'output',
            name: 'Output',
            params: { value: true },
            ui: { builder_type: 'output-node', position: { x: 760, y: 40 }, data: { label: 'Output' } },
          },
        ],
        edges: [originalBranch, unchangedCanonicalEdge, unsupportedEdge],
      },
    }
    const restored = parseWorkflowVersion({ graph_json: graphJson })
    const changedNodes = restored.nodes.map((node) => node.id === 'transform'
      ? { ...node, data: { ...node.data, mapping: { edited: false, count: 0 } } }
      : node)
    const changedEdges = restored.edges.map((edge) => edge.id === 'canonical-branch'
      ? { ...edge, target: 'transform', sourceHandle: 'false', targetHandle: 'replacement-input' }
      : edge)

    const exported = serializeWorkflowSpecForExport(
      restored.base,
      restored.name,
      restored.description,
      changedNodes,
      changedEdges,
    ) as any

    expect(exported.graph.nodes.find((node: Record<string, unknown>) => node.id === 'legacy-loop')).toEqual(compatibilityNode)
    expect(exported.graph.nodes.find((node: Record<string, unknown>) => node.id === 'transform').params).toEqual({
      mapping: { edited: false, count: 0 },
    })
    expect(exported.graph.edges.find((edge: Record<string, unknown>) => edge.id === 'legacy-edge')).toEqual(unsupportedEdge)
    expect(exported.graph.edges.find((edge: Record<string, unknown>) => edge.id === 'canonical-unchanged')).toEqual(
      unchangedCanonicalEdge,
    )
    expect(exported.graph.edges.find((edge: Record<string, unknown>) => edge.id === 'canonical-branch')).toEqual({
      id: 'canonical-branch',
      from: 'condition',
      to: 'transform',
      from_port: 'false',
      to_port: 'replacement-input',
      condition: '{{ steps.condition.output.result }} == false',
    })
  })

  test('applies UI-data edits as a delta over the exact persisted UI baseline', () => {
    const parsed = parseWorkflowVersion(canonicalWorkflowVersion)
    const originalNode = canonicalWorkflowVersion.graph_json.graph.nodes.find((node) => node.id === 'llm')!
    const llm = parsed.nodes.find((node) => node.id === 'llm')!

    expect(serializeCanonicalNode(llm).ui).toEqual(originalNode.ui)

    const uiEditedData: Record<string, unknown> = {
      ...llm.data,
      label: 'UI-only rename',
      description: 'UI-only description',
      cache: true,
      timeout: 45,
    }
    delete uiEditedData.presentation
    llm.data = uiEditedData
    const uiEdited = serializeCanonicalNode(llm)
    expect(uiEdited.params).toEqual(originalNode.params)
    expect(uiEdited.ui.data).toEqual({
      label: 'UI-only rename',
      modelName: 'stale:model',
      description: 'UI-only description',
      cache: true,
      timeout: 45,
    })

    const reparsed = parseWorkflowVersion({
      ...canonicalWorkflowVersion,
      graph_json: {
        ...canonicalWorkflowVersion.graph_json,
        graph: { nodes: [uiEdited], edges: [] },
      },
    })
    expect(reparsed.nodes[0].data).toMatchObject({
      label: 'UI-only rename',
      description: 'UI-only description',
      cache: true,
      timeout: 45,
    })
    expect(reparsed.nodes[0].data).not.toHaveProperty('presentation')

    reparsed.nodes[0].data = { ...reparsed.nodes[0].data, prompt: 'Updated canonical prompt' }
    const paramEdited = serializeCanonicalNode(reparsed.nodes[0])
    expect(paramEdited.params).toEqual({ ...originalNode.params, prompt: 'Updated canonical prompt' })
    expect(paramEdited.ui.data).toMatchObject({
      label: 'UI-only rename',
      description: 'UI-only description',
      cache: true,
      timeout: 45,
      prompt: 'Updated canonical prompt',
    })
  })

  test('unsupported historical fixtures retain all H01-H21 persisted data without fallback conversion', () => {
    expect(HISTORICAL_WORKFLOW_NODE_FIXTURES.map((fixture) => fixture.id)).toEqual(
      Array.from({ length: 21 }, (_, index) => `H${String(index + 1).padStart(2, '0')}`),
    )
    expect(HISTORICAL_WORKFLOW_NODE_FIXTURES.find((fixture) => fixture.id === 'H04')).toMatchObject({
      editable: false,
      node: { params: { tool_ref: '' }, ui: { data: { toolName: '' } } },
    })

    for (const fixture of HISTORICAL_WORKFLOW_NODE_FIXTURES) {
      const version = {
        ...mockWorkflowVersion,
        graph_json: {
          ...mockWorkflowVersion.graph_json,
          graph: { nodes: [fixture.node], edges: fixture.edges },
        },
      }
      const parsed = parseWorkflowVersion(version)
      const parsedNode = parsed.nodes[0]

      if (fixture.editable) {
        expect(parsedNode.type, fixture.id).toBe(fixture.node.ui.builder_type)
        const serializedNode = serializeCanonicalNode(parsedNode)
        expect(serializedNode.type, fixture.id).toBe(fixture.node.type)
        expect(serializedNode.params, fixture.id).toEqual(fixture.node.params)
        expect(serializedNode.ui, fixture.id).toEqual(fixture.node.ui)
      } else {
        expect(parsedNode, fixture.id).toMatchObject({
          id: fixture.node.id,
          type: 'compatibility-node',
          data: {
            unsupported: true,
            originalRuntimeType: fixture.node.type,
            originalParams: fixture.node.params,
            originalUi: fixture.node.ui,
            originalNode: fixture.node,
          },
        })
      }

      expect(parsed.edges, fixture.id).toHaveLength(fixture.edges.length)
      fixture.edges.forEach((edge, index) => {
        const parsedEdge = parsed.edges[index]
        const expectedSourceHandle = fixture.node.type === 'condition' && edge.from === fixture.node.id
          && (edge.from_port === 'true' || edge.from_port === 'output-true') ? 'true'
          : fixture.node.type === 'condition' && edge.from === fixture.node.id
            && (edge.from_port === 'false' || edge.from_port === 'output-false') ? 'false'
            : edge.from_port
        expect(parsedEdge, `${fixture.id}:${edge.id}`).toMatchObject({
          source: edge.from,
          target: edge.to,
          sourceHandle: expectedSourceHandle,
          targetHandle: edge.to_port,
          data: { originalEdge: edge },
        })
        expect((parsedEdge.data?.originalEdge as Record<string, unknown>).condition).toBe(edge.condition)
      })
    }
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

  test('serializes every supported variable JSON primitive and composite exactly', () => {
    for (const value of [null, false, 0, '', ['a', 0, false], { nested: { enabled: false }, count: 0 }]) {
      const node = {
        id: 'json-variable',
        type: 'variable-assignment-node',
        position: { x: 0, y: 0 },
        data: { label: 'JSON Variable', key: 'result', value },
      } as any
      expect(serializeCanonicalNode(node).params).toEqual({ key: 'result', value })
    }
  })

  test('round-trips condition predicates independently from persisted source-port state', () => {
    const resultRef = '{{ steps.cond.output.result }}'
    const conditionCases = [
      { id: 'canonical-absent', condition: resultRef, from_port: undefined, port: { present: false }, handle: 'true', savedCondition: resultRef },
      { id: 'canonical-null', condition: resultRef, from_port: null, port: { present: true, value: null }, handle: 'true', savedCondition: resultRef },
      { id: 'canonical-empty', condition: resultRef, from_port: '', port: { present: true, value: '' }, handle: 'true', savedCondition: resultRef },
      { id: 'legacy-false-absent', condition: 'false', from_port: undefined, port: { present: false }, handle: 'false', savedCondition: `${resultRef} == false` },
      { id: 'legacy-false-null', condition: 'false', from_port: null, port: { present: true, value: null }, handle: 'false', savedCondition: `${resultRef} == false` },
      { id: 'legacy-false-empty', condition: 'false', from_port: '', port: { present: true, value: '' }, handle: 'false', savedCondition: `${resultRef} == false` },
      { id: 'canonical-true-port', condition: resultRef, from_port: 'true', port: { present: true, value: 'true' }, handle: 'true', savedCondition: resultRef },
      { id: 'legacy-false-port', condition: 'false', from_port: 'false', port: { present: true, value: 'false' }, handle: 'false', savedCondition: `${resultRef} == false` },
      { id: 'historical-true-port', condition: 'true', from_port: 'output-true', port: { present: true, value: 'output-true' }, handle: 'true', savedCondition: resultRef },
      { id: 'historical-false-port', condition: 'false', from_port: 'output-false', port: { present: true, value: 'output-false' }, handle: 'false', savedCondition: `${resultRef} == false` },
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
    expect(savedNodes.find((node) => node.id === 'llm')?.ui.data).toEqual(
      canonicalWorkflowVersion.graph_json.graph.nodes.find((node) => node.id === 'llm')?.ui.data,
    )
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
    await expect(page.getByText('Unsupported historical node', { exact: true }).first()).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('python', { exact: true })).toBeVisible()

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

    await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
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
    await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
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
      'This workflow contains incompatible edge data. Repair or migrate it before saving or running the workflow.'
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

    await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
    await expect(page.getByText(
      'This workflow contains incompatible edge data. Repair or migrate it before saving or running the workflow.'
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
    await expect(page.getByText('Unsupported historical node', { exact: true })).toBeVisible({ timeout: 15_000 })
    await expect(page.getByText('llm', { exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
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
    await expect(page.getByText('Unsupported historical node', { exact: true })).toHaveCount(
      malformedCanonicalWorkflowVersion.graph_json.graph.nodes.length,
    )

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

    await expect(page.getByRole('button', { name: 'Save Workflow' })).toBeDisabled()
    await expect(page.getByRole('button', { name: 'Test Run' })).toBeDisabled()
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

