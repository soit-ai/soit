/**
 * Archived: these cover the pre-rebuild workflow list, settings and permissions
 * pages, which app/routes_old backs up. The console replaced them with its own
 * detail-page tabs, so these drive URLs that now redirect elsewhere. Excluded
 * from the suite by `testIgnore`; delete with the route backup.
 *
 * The preamble is duplicated from e2e/workflow.spec.ts rather than shared,
 * because this whole file is scheduled for deletion.
 */
import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from '../helpers'
import {
  CanonicalNodeValidationError,
  conditionForEdge,
  parseWorkflowVersion,
  serializeCanonicalNode,
  serializeWorkflowSpec,
  serializeWorkflowSpecForExport,
  UnsupportedWorkflowEdgeError,
} from '../../app/features/workflow-builder/ui/workflow-spec'
import { canonicalBuilderTypes } from '../../app/features/workflow-builder/ui/canonical-node-registry'
import historicalAppendixFixtures from '../fixtures/workflow-historical-appendix'

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

test('empty workspace creates a workflow before opening Builder', async ({ page }) => {
  let createPayload: Record<string, unknown> | null = null
  await page.route('**/api/v1/workflows', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    createPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          ...mockWorkflow,
          id: 'workflow-created',
          name: 'Untitled workflow',
          current_version_id: null,
        },
      }),
    })
  })

  await page.goto('/workflow', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create Workflow' }).click()

  await expect.poll(() => createPayload).toMatchObject({ name: 'Untitled workflow' })
  await expect(page).toHaveURL(/\/workflow\/workflow-created\/build$/)
  await expect(page).not.toHaveURL(/\/workflow\/new\/build$/)
})

test('workflow creation failure is recoverable and never opens a synthetic id', async ({ page }) => {
  await page.route('**/api/v1/workflows', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'Workflow creation unavailable', data: null }),
    })
  })

  await page.goto('/workflow', { waitUntil: 'domcontentloaded' })
  const createButton = page.getByRole('button', { name: 'Create Workflow' })
  await createButton.click()

  await expect(page).toHaveURL(/\/workflow$/)
  await expect(page.getByText('Workflow creation unavailable')).toBeVisible()
  await expect(createButton).toBeEnabled()
})

test('truthful settings keep real visibility controls and link execution settings to Builder', async ({ page }) => {
  let workflowUpdate: Record<string, unknown> | null = null
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') {
      workflowUpdate = JSON.parse(route.request().postData() || '{}')
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          code: 'OK',
          message: 'OK',
          data: { ...mockWorkflow, visibility: 'workspace' },
        }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Runtime limits', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Allow anonymous runs', { exact: true })).toHaveCount(0)
  await expect(page.getByText('Enable cache', { exact: true })).toHaveCount(0)
  await page.getByRole('button', { name: 'Setting', exact: true }).first().hover()
  await expect(page.getByRole('tooltip', {
    name: 'Manage workflow information, visibility, and sharing permissions.',
  })).toBeVisible()
  const builderLink = page.getByRole('link', { name: 'Configure execution settings in Builder' })
  await expect(builderLink).toHaveAttribute('href', '/workflow/workflow-1/build')

  await page.getByRole('combobox').click()
  await page.getByRole('option', { name: 'Workspace' }).click()
  await page.getByRole('button', { name: 'Save access' }).click()
  await expect.poll(() => workflowUpdate).toEqual({ visibility: 'workspace' })
})

test('visibility hydration blocks default writes until workflow loading succeeds', async ({ page }) => {
  let releaseWorkflow!: () => void
  const workflowGate = new Promise<void>((resolve) => { releaseWorkflow = resolve })
  let workflowUpdates = 0
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
    if (route.request().method() === 'PUT') {
      workflowUpdates += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
  const visibility = page.getByRole('combobox')
  const saveAccess = page.getByRole('button', { name: 'Save access' })
  await expect(visibility).toBeDisabled()
  await expect(saveAccess).toBeDisabled()
  await saveAccess.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => workflowUpdates).toBe(0)

  releaseWorkflow()
  await expect(visibility).toBeEnabled()
  await expect(saveAccess).toBeEnabled()
})

test('visibility hydration remains blocked after workflow loading fails', async ({ page }) => {
  let workflowUpdates = 0
  const workflowA = {
    ...mockWorkflow,
    id: 'workflow-a',
    name: 'Workflow A',
    description: 'Settings from workflow A',
    visibility: 'tenant',
  }
  await page.route('**/api/v1/workflows/workflow-a', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowA }),
    })
  })
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({ success: false, code: 'SERVICE_UNAVAILABLE', message: 'unavailable', data: null }),
      })
      return
    }
    if (route.request().method() === 'PUT') {
      workflowUpdates += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#workflow-name')).toHaveValue('Workflow A')
  await navigateClientRoute(page, '/workflow/workflow-1/setting')
  const visibility = page.getByRole('combobox')
  const workflowName = page.locator('#workflow-name')
  const workflowDescription = page.locator('#workflow-description')
  const saveBasic = page.getByRole('button', { name: 'Save', exact: true })
  const saveAccess = page.getByRole('button', { name: 'Save access' })
  const deleteButton = page.getByRole('button', { name: 'Delete workflow' })
  await expect(page.getByText('Failed to fetch workflow')).toBeVisible()
  expect(await page.getByText('unavailable', { exact: true }).count()).toBe(0)
  await expect(workflowName).toBeDisabled()
  await expect(workflowName).toHaveValue('')
  await expect(workflowDescription).toBeDisabled()
  await expect(workflowDescription).toHaveValue('')
  await expect(saveBasic).toBeDisabled()
  await expect(visibility).toBeDisabled()
  await expect(saveAccess).toBeDisabled()
  await expect(deleteButton).toBeDisabled()
  await saveBasic.evaluate((element: HTMLButtonElement) => element.click())
  await saveAccess.evaluate((element: HTMLButtonElement) => element.click())
  await deleteButton.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => workflowUpdates).toBe(0)
  expect(await page.getByRole('alertdialog').count()).toBe(0)
})

test('settings show only their localized update error', async ({ page }) => {
  let updateResponses = 0
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') {
      updateResponses += 1
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'SERVICE_UNAVAILABLE',
          message: 'raw workflow update failure',
          data: null,
        }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => updateResponses).toBe(1)
  await expect(page.getByText('Failed to update workflow', { exact: true })).toBeVisible()
  expect(await page.getByText('raw workflow update failure', { exact: true }).count()).toBe(0)
})

test('settings ignore a stale workflow response after a client-side route change', async ({ page }) => {
  let releaseWorkflowA!: () => void
  const workflowAGate = new Promise<void>((resolve) => { releaseWorkflowA = resolve })
  let workflowARequests = 0
  let workflowAResponses = 0
  const updates: Array<{ path: string, payload: Record<string, unknown> }> = []
  const workflowA = {
    ...mockWorkflow,
    id: 'workflow-a',
    name: 'Workflow A',
    description: 'Late settings from A',
    visibility: 'private',
  }
  const workflowB = {
    ...mockWorkflow,
    id: 'workflow-b',
    name: 'Workflow B',
    description: 'Current settings from B',
    visibility: 'tenant',
  }
  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'GET' && url.pathname.endsWith('/workflows/workflow-a')) {
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
    if (request.method() === 'GET' && url.pathname.endsWith('/workflows/workflow-b')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
      })
      return
    }
    if (request.method() === 'PUT') {
      const payload = JSON.parse(request.postData() || '{}') as Record<string, unknown>
      updates.push({ path: url.pathname, payload })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          code: 'OK',
          message: 'OK',
          data: { ...workflowB, ...payload },
        }),
      })
      return
    }
    await route.fallback()
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => workflowARequests).toBeGreaterThan(0)
  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  const workflowName = page.locator('#workflow-name')
  const visibility = page.getByRole('combobox')
  await expect(workflowName).toHaveValue('Workflow B')
  await expect(visibility).toContainText('Tenant')

  releaseWorkflowA()
  await expect.poll(() => workflowAResponses).toBe(workflowARequests)
  await expect(workflowName).toHaveValue('Workflow B')
  await expect(visibility).toContainText('Tenant')

  await workflowName.fill('Workflow B edited')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await expect.poll(() => updates).toEqual([
    {
      path: '/api/v1/workflows/workflow-b',
      payload: { name: 'Workflow B edited', description: 'Current settings from B' },
    },
  ])
})

test('settings suppress stale save failures after the route changes', async ({ page }) => {
  let releaseSaves!: () => void
  const saveGate = new Promise<void>((resolve) => { releaseSaves = resolve })
  let pendingSaves = 0
  let completedSaves = 0
  const workflowB = {
    ...mockWorkflow,
    id: 'workflow-b',
    name: 'Workflow B',
    description: 'Current settings from B',
    visibility: 'workspace',
  }
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() === 'PUT') {
      pendingSaves += 1
      await saveGate
      completedSaves += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK' }),
      })
      return
    }
    await route.fallback()
  })
  await page.route('**/api/v1/workflows/workflow-b', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflowB }),
    })
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await page.getByRole('button', { name: 'Save access' }).click()
  await expect.poll(() => pendingSaves).toBe(2)

  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.locator('#workflow-name')).toHaveValue('Workflow B')
  releaseSaves()
  await expect.poll(() => completedSaves).toBe(2)
  await page.waitForTimeout(500)
  await expect(page.getByText('Failed to update workflow')).toHaveCount(0)
  await expect(page.getByText('Failed to save access settings')).toHaveCount(0)
  await expect(page.locator('#workflow-name')).toHaveValue('Workflow B')
})

test('settings suppress pending basic and access results after unmount', async ({ page }) => {
  let releaseUpdates!: () => void
  const updateGate = new Promise<void>((resolve) => { releaseUpdates = resolve })
  let updateRequests = 0
  let updateResponses = 0
  await page.route('**/api/v1/workflows/workflow-1', async (route) => {
    if (route.request().method() !== 'PUT') {
      await route.fallback()
      return
    }
    updateRequests += 1
    const payload = JSON.parse(route.request().postData() || '{}') as Record<string, unknown>
    await updateGate
    updateResponses += 1
    if ('visibility' in payload) {
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'SERVICE_UNAVAILABLE',
          message: 'late access failure',
          data: null,
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockWorkflow }),
    })
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('#workflow-name')).toHaveValue('Demo Workflow')
  await page.getByRole('button', { name: 'Save', exact: true }).click()
  await page.getByRole('button', { name: 'Save access' }).click()
  await expect.poll(() => updateRequests).toBe(2)

  await navigateClientRoute(page, '/workflow')
  await expect(page.getByRole('table')).toBeVisible()
  releaseUpdates()
  await expect.poll(() => updateResponses).toBe(2)
  await page.waitForTimeout(200)
  await expect(page).toHaveURL(/\/workflow$/)
  expect(await page.getByText('Workflow updated', { exact: true }).count()).toBe(0)
  expect(await page.getByText('Failed to save access settings', { exact: true }).count()).toBe(0)
  expect(await page.getByText('late access failure', { exact: true }).count()).toBe(0)
})

test('settings reject an old delete confirmation after the workflow ID changes', async ({ page }) => {
  const deleteRequests: string[] = []
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }
  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'DELETE') {
      deleteRequests.push(url.pathname)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: null }),
      })
      return
    }
    const workflow = url.pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Delete workflow' }).click()
  const staleConfirm = await page.getByRole('button', { name: 'Delete', exact: true }).elementHandle()
  expect(staleConfirm).not.toBeNull()

  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.locator('#workflow-name')).toHaveValue('Workflow B')
  await staleConfirm!.evaluate((element: HTMLButtonElement) => element.click())
  await page.waitForTimeout(200)
  expect(deleteRequests).toEqual([])
  await expect(page.getByRole('alertdialog')).toHaveCount(0)
  await expect(page).toHaveURL(/\/workflow\/workflow-b\/setting$/)
})

for (const deleteOutcome of [
  { name: 'success', status: 200, rawMessage: 'OK' },
  { name: 'failure', status: 503, rawMessage: 'late delete failure' },
] as const) {
  test(`settings suppress a pending delete ${deleteOutcome.name} after unmount`, async ({ page }) => {
    let releaseDelete!: () => void
    const deleteGate = new Promise<void>((resolve) => { releaseDelete = resolve })
    let deleteRequests = 0
    let deleteResponses = 0
    await page.route('**/api/v1/workflows/workflow-1', async (route) => {
      if (route.request().method() !== 'DELETE') {
        await route.fallback()
        return
      }
      deleteRequests += 1
      await deleteGate
      deleteResponses += 1
      await route.fulfill({
        status: deleteOutcome.status,
        contentType: 'application/json',
        body: JSON.stringify({
          success: deleteOutcome.status === 200,
          code: deleteOutcome.status === 200 ? 'OK' : 'SERVICE_UNAVAILABLE',
          message: deleteOutcome.rawMessage,
          data: null,
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

    await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
    await page.getByRole('button', { name: 'Delete workflow' }).click()
    await page.getByRole('button', { name: 'Delete', exact: true }).click()
    await expect.poll(() => deleteRequests).toBe(1)

    await navigateClientRoute(page, '/workflow/workflow-1/build')
    await expect(page.getByPlaceholder('Workflow name')).toBeEnabled()
    releaseDelete()
    await expect.poll(() => deleteResponses).toBe(1)
    await page.waitForTimeout(200)
    await expect(page).toHaveURL(/\/workflow\/workflow-1\/build$/)
    expect(await page.getByText('Workflow deleted', { exact: true }).count()).toBe(0)
    expect(await page.getByText('Failed to delete workflow', { exact: true }).count()).toBe(0)
    if (deleteOutcome.status !== 200) {
      expect(await page.getByText(deleteOutcome.rawMessage, { exact: true }).count()).toBe(0)
    }
  })
}

test('permissions ignore stale grants after a client-side route change', async ({ page }) => {
  let releaseGrantsA!: () => void
  const grantsAGate = new Promise<void>((resolve) => { releaseGrantsA = resolve })
  let grantsARequests = 0
  let grantsAResponses = 0
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }

  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const url = new URL(route.request().url())
    const workflow = url.pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    const resourceId = new URL(route.request().url()).searchParams.get('resource_id')
    if (resourceId === 'workflow-a') {
      grantsARequests += 1
      await grantsAGate
      grantsAResponses += 1
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          code: 'OK',
          message: 'OK',
          data: [mockWorkflowGrant('workflow-a', 'late-user-a')],
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: [mockWorkflowGrant('workflow-b', 'current-user-b')],
      }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => grantsARequests).toBeGreaterThan(0)
  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.getByText('current-user-b', { exact: true })).toBeVisible()

  releaseGrantsA()
  await expect.poll(() => grantsAResponses).toBe(grantsARequests)
  await page.waitForTimeout(200)
  await expect(page.getByText('current-user-b', { exact: true })).toBeVisible()
  await expect(page.getByText('late-user-a', { exact: true })).toHaveCount(0)
})

test('permissions suppress a stale loading error after a client-side route change', async ({ page }) => {
  let releaseGrantsA!: () => void
  const grantsAGate = new Promise<void>((resolve) => { releaseGrantsA = resolve })
  let grantsARequests = 0
  let grantsAResponses = 0
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }

  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const workflow = new URL(route.request().url()).pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    const resourceId = new URL(route.request().url()).searchParams.get('resource_id')
    if (resourceId === 'workflow-a') {
      grantsARequests += 1
      await grantsAGate
      grantsAResponses += 1
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'SERVICE_UNAVAILABLE',
          message: 'late permissions failure',
          data: null,
        }),
      })
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: [mockWorkflowGrant('workflow-b', 'current-user-b')],
      }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await expect.poll(() => grantsARequests).toBeGreaterThan(0)
  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.getByText('current-user-b', { exact: true })).toBeVisible()

  releaseGrantsA()
  await expect.poll(() => grantsAResponses).toBe(grantsARequests)
  await page.waitForTimeout(200)
  await expect(page.getByText('current-user-b', { exact: true })).toBeVisible()
  expect(await page.getByText('late permissions failure', { exact: true }).count()).toBe(0)
  expect(await page.getByText('Failed to load permissions', { exact: true }).count()).toBe(0)
})

test('permissions fail closed with a localized current loading error', async ({ page }) => {
  await page.route('**/api/v1/resource-grants**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        code: 'SERVICE_UNAVAILABLE',
        message: 'raw permissions failure',
        data: null,
      }),
    })
  })

  await page.goto('/workflow/workflow-1/setting', { waitUntil: 'domcontentloaded' })
  await expect(page.getByRole('button', { name: 'Save grant' })).toBeDisabled()
  await expect(page.getByRole('alert').filter({ hasText: 'Failed to load permissions' })).toBeVisible()
  expect(await page.getByText('No grants yet.', { exact: true }).count()).toBe(0)
  expect(await page.getByText('raw permissions failure', { exact: true }).count()).toBe(0)
})

test('permissions clear old grants and block revoke while the next workflow is loading', async ({ page }) => {
  let releaseGrantsB!: () => void
  const grantsBGate = new Promise<void>((resolve) => { releaseGrantsB = resolve })
  const deleteRequests: string[] = []
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }

  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const url = new URL(route.request().url())
    const workflow = url.pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    if (request.method() === 'DELETE') {
      deleteRequests.push(url.pathname)
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: null }),
      })
      return
    }
    const resourceId = url.searchParams.get('resource_id')
    if (resourceId === 'workflow-b') await grantsBGate
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: [mockWorkflowGrant(resourceId || 'workflow-a', resourceId === 'workflow-b' ? 'user-b' : 'user-a')],
      }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  const oldGrant = page.getByText('user-a', { exact: true }).locator('..')
  await expect(oldGrant).toBeVisible()
  const staleRevokeButton = await oldGrant.getByRole('button', { name: 'Revoke' }).elementHandle()
  expect(staleRevokeButton).not.toBeNull()

  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.locator('#workflow-grant-user')).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Save grant' })).toBeDisabled()
  await expect(page.getByText('user-a', { exact: true })).toHaveCount(0)
  await staleRevokeButton!.evaluate((element: HTMLButtonElement) => element.click())
  await expect.poll(() => deleteRequests).toEqual([])

  releaseGrantsB()
  await expect(page.getByText('user-b', { exact: true })).toBeVisible()
})

test('permissions suppress a pending create result after leaving its workflow', async ({ page }) => {
  let releaseCreate!: () => void
  const createGate = new Promise<void>((resolve) => { releaseCreate = resolve })
  let createRequests = 0
  let createResponses = 0
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }

  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const workflow = new URL(route.request().url()).pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    const request = route.request()
    if (request.method() === 'POST') {
      createRequests += 1
      await createGate
      createResponses += 1
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          code: 'OK',
          message: 'OK',
          data: mockWorkflowGrant('workflow-a', 'created-user-a'),
        }),
      })
      return
    }
    const resourceId = new URL(request.url()).searchParams.get('resource_id') || 'workflow-a'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: resourceId === 'workflow-b' ? [mockWorkflowGrant('workflow-b', 'user-b')] : [],
      }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  const grantUser = page.locator('#workflow-grant-user')
  await expect(grantUser).toBeEnabled()
  await grantUser.fill('created-user-a')
  await page.getByRole('button', { name: 'Save grant' }).click()
  await expect.poll(() => createRequests).toBe(1)

  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.getByText('user-b', { exact: true })).toBeVisible()
  releaseCreate()
  await expect.poll(() => createResponses).toBe(1)
  await page.waitForTimeout(200)
  await expect(page.getByText('user-b', { exact: true })).toBeVisible()
  await expect(page.getByText('created-user-a', { exact: true })).toHaveCount(0)
  expect(await page.getByText('Grant saved', { exact: true }).count()).toBe(0)
})

test('permissions suppress a pending revoke result after leaving its workflow', async ({ page }) => {
  let releaseRevoke!: () => void
  const revokeGate = new Promise<void>((resolve) => { releaseRevoke = resolve })
  let revokeRequests = 0
  let revokeResponses = 0
  const workflowA = { ...mockWorkflow, id: 'workflow-a', name: 'Workflow A' }
  const workflowB = { ...mockWorkflow, id: 'workflow-b', name: 'Workflow B' }

  await page.route('**/api/v1/workflows/workflow-*', async (route) => {
    const workflow = new URL(route.request().url()).pathname.endsWith('/workflow-a') ? workflowA : workflowB
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: workflow }),
    })
  })
  await page.route('**/api/v1/resource-grants**', async (route) => {
    const request = route.request()
    if (request.method() === 'DELETE') {
      revokeRequests += 1
      await revokeGate
      revokeResponses += 1
      await route.fulfill({
        status: 503,
        contentType: 'application/json',
        body: JSON.stringify({
          success: false,
          code: 'SERVICE_UNAVAILABLE',
          message: 'late revoke failure',
          data: null,
        }),
      })
      return
    }
    const resourceId = new URL(request.url()).searchParams.get('resource_id') || 'workflow-a'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: [mockWorkflowGrant(resourceId, resourceId === 'workflow-b' ? 'user-b' : 'revoke-user-a')],
      }),
    })
  })

  await page.goto('/workflow/workflow-a/setting', { waitUntil: 'domcontentloaded' })
  await page.getByText('revoke-user-a', { exact: true }).locator('..').getByRole('button', { name: 'Revoke' }).click()
  await expect.poll(() => revokeRequests).toBe(1)

  await navigateClientRoute(page, '/workflow/workflow-b/setting')
  await expect(page.getByText('user-b', { exact: true })).toBeVisible()
  releaseRevoke()
  await expect.poll(() => revokeResponses).toBe(1)
  await page.waitForTimeout(200)
  await expect(page.getByText('user-b', { exact: true })).toBeVisible()
  expect(await page.getByText('late revoke failure', { exact: true }).count()).toBe(0)
  expect(await page.getByText('Failed to revoke grant', { exact: true }).count()).toBe(0)
})

