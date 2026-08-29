import { expect, test } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const runDetail = {
  run: {
    id: 'run_01J9KD7Z2M',
    trace_id: 'trace_4d19a2',
    attempt_no: 1,
    mode: 'chat',
    subject_kind: 'agent',
    subject_id: 'ops-copilot',
    subject_version_id: 'agtv_0142',
    user_id: 'wei@acme.io',
    status: 'succeeded',
    started_at: '2026-08-28T13:45:31.204Z',
    ended_at: '2026-08-28T13:45:40.104Z',
    duration_ms: 8900,
    created_at: '2026-08-28T13:45:31.204Z',
    updated_at: '2026-08-28T13:45:40.104Z',
  },
  steps: [
    {
      id: 'st_1',
      run_id: 'run_01J9KD7Z2M',
      step_id: 'intent-screen',
      step_type: 'policy_gate',
      node_id: 'intent-screen',
      status: 'succeeded',
      output_summary: 'classified intent "restart staging pod" → allowed with constraints',
      started_at: '2026-08-28T13:45:31.204Z',
      ended_at: '2026-08-28T13:45:31.414Z',
      created_at: '2026-08-28T13:45:31.204Z',
    },
    {
      id: 'st_2',
      run_id: 'run_01J9KD7Z2M',
      step_id: 'plan',
      step_type: 'model_call',
      node_id: 'plan',
      status: 'succeeded',
      output_summary: 'claude-sonnet-5 · plan with 2 tool steps',
      started_at: '2026-08-28T13:45:31.414Z',
      ended_at: '2026-08-28T13:45:33.284Z',
      created_at: '2026-08-28T13:45:31.414Z',
    },
    {
      id: 'st_3',
      run_id: 'run_01J9KD7Z2M',
      step_id: 'restart',
      step_type: 'tool_call',
      node_id: 'k8s.rollout_restart',
      status: 'succeeded',
      output_summary: 'deployment/checkout-api · ns/staging',
      started_at: '2026-08-28T13:45:33.284Z',
      ended_at: '2026-08-28T13:45:36.664Z',
      created_at: '2026-08-28T13:45:33.284Z',
    },
  ],
  artifacts: [
    {
      id: 'art_1',
      run_id: 'run_01J9KD7Z2M',
      type: 'markdown',
      storage_key: 'runs/run_01J9KD7Z2M/run-report.md',
      mime: 'text/markdown',
      size_bytes: 4301,
      sha256: 'sha256:9f31aa00bbccddeeff0011223344556677889900aabbccddeeff0011c2ae',
      meta_json: { name: 'run-report.md' },
      created_at: '2026-08-28T13:45:40.104Z',
    },
  ],
  usage_summary: {
    tokens_prompt: 2482,
    tokens_completion: 500,
    embedding_count: 0,
    rerank_count: 0,
    ms_total: 8900,
    storage_bytes: 4301,
  },
  charge_summary: null,
  costs: [
    {
      id: 'cost_1',
      run_id: 'run_01J9KD7Z2M',
      tenant_id: 't1',
      workspace_id: 'w1',
      currency: 'USD',
      amount: '0.031',
      pricing_snapshot_json: {},
      billing_basis: 'tokens',
      billed_quantity: '2982',
      provider: 'anthropic',
      model_ref: 'claude-sonnet-5',
      created_at: '2026-08-28T13:45:40.104Z',
    },
    {
      id: 'cost_2',
      run_id: 'run_01J9KD7Z2M',
      tenant_id: 't1',
      workspace_id: 'w1',
      currency: 'USD',
      amount: '0.007',
      pricing_snapshot_json: {},
      billing_basis: 'ms',
      billed_quantity: '5340',
      tool_ref: 'k8s-toolkit',
      created_at: '2026-08-28T13:45:40.104Z',
    },
  ],
  response_events: [
    {
      id: 'ev_1',
      tenant_id: 't1',
      workspace_id: 'w1',
      response_id: 'resp_1',
      run_id: 'run_01J9KD7Z2M',
      sequence: 1,
      type: 'RUN_STARTED',
      source: 'runtime',
      payload_json: { threadId: 'thread_8f2c' },
      created_at: '2026-08-28T13:45:31.204Z',
    },
    {
      id: 'ev_2',
      tenant_id: 't1',
      workspace_id: 'w1',
      response_id: 'resp_1',
      run_id: 'run_01J9KD7Z2M',
      sequence: 2,
      type: 'TOOL_CALL_START',
      source: 'runtime',
      payload_json: { tool: 'k8s.rollout_restart' },
      created_at: '2026-08-28T13:45:33.510Z',
    },
  ],
  tool_calls: [
    {
      id: 'tc_1',
      tenant_id: 't1',
      workspace_id: 'w1',
      response_id: 'resp_1',
      run_id: 'run_01J9KD7Z2M',
      tool_name: 'k8s.rollout_restart',
      tool_type: 'mcp',
      status: 'succeeded',
      arguments_json: {},
      result_json: {},
      metadata_json: {},
      created_at: '2026-08-28T13:45:33.510Z',
      updated_at: '2026-08-28T13:45:36.890Z',
    },
  ],
  citations: [],
  audits: [
    {
      audit_id: 'aud_77b2',
      run_id: 'run_01J9KD7Z2M',
      step_id: 'st_1',
      step_type: 'policy_gate',
      outcome: 'succeeded',
      gateway_type: 'intent-screen',
      preview: 'rule: ops.intents.allowed · matched "infra.restart.staging"',
      truncated: false,
    },
    {
      audit_id: 'aud_77b9',
      run_id: 'run_01J9KD7Z2M',
      step_id: 'st_3',
      step_type: 'tool_call',
      outcome: 'succeeded',
      gateway_type: 'tool-permission',
      preview: 'rule: grants.g_44 · k8s.* on ns/staging',
      truncated: false,
    },
  ],
  child_runs: [],
  governance_evidence: [
    { key: 'actor-scope', status: 'pass', label: 'Actor scope', summary: 'Run is tied to tenant, workspace, user and run identifiers.', evidence_refs: ['ws_acme-robotics', 'u_wei'], missing: [] },
    { key: 'subject-version', status: 'pass', label: 'Subject version', summary: 'Run is tied to a versioned subject.', evidence_refs: ['agtv_0142'], missing: [] },
    { key: 'secret-boundary', status: 'pass', label: 'Secret boundary', summary: 'Secrets resolved by reference at call time.', evidence_refs: ['vault:k8s-staging'], missing: [] },
    { key: 'knowledge-citation', status: 'warning', label: 'Knowledge citation', summary: 'No knowledge citations attached although a KB is bound.', evidence_refs: [], missing: ['citations'] },
    { key: 'egress-policy', status: 'not_applicable', label: 'Egress policy', summary: 'This run has no external egress surface.', evidence_refs: [], missing: [] },
    { key: 'child-workflow', status: 'not_applicable', label: 'Child workflow', summary: 'No child workflow runs were triggered.', evidence_refs: [], missing: [] },
  ],
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await page.route('**/api/v1/runs/run_01J9KD7Z2M**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(runDetail) }),
  )
})

test('run detail renders the step ledger from run-service', async ({ page }) => {
  await page.goto('/observe/runs/run_01J9KD7Z2M', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'run_01J9KD7Z2M' })).toBeVisible()
  await expect(page.getByText('ops-copilot')).toBeVisible()

  // Ledger rows come from steps, with waterfall geometry derived from timestamps.
  const ledger = page.locator('.ledger li')
  await expect(ledger).toHaveCount(3)
  await expect(ledger.first()).toContainText('intent-screen')
  await expect(ledger.first()).toContainText('policy·gate')
  await expect(ledger.nth(2)).toContainText('k8s.rollout_restart')
})

test('run detail renders server-computed governance evidence verbatim', async ({ page }) => {
  await page.goto('/observe/runs/run_01J9KD7Z2M', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: /Policy/ }).click()

  // Gates come from gateway audits.
  await expect(page.getByText('rule: ops.intents.allowed', { exact: false })).toBeVisible()

  // The matrix is whatever the server sent — 6 checks here, not a fixed 13.
  await expect(page.locator('.matrix .mrow2')).toHaveCount(6)
  await expect(page.getByText('PASS 3')).toBeVisible()
  await expect(page.getByText('WARN 1')).toBeVisible()
  await expect(page.getByText('N/A 2')).toBeVisible()
  await expect(page.getByText('missing: citations')).toBeVisible()
})

test('run detail events, artifacts and cost come from the payload', async ({ page }) => {
  await page.goto('/observe/runs/run_01J9KD7Z2M', { waitUntil: 'domcontentloaded' })

  await page.getByRole('button', { name: /Events/ }).click()
  await expect(page.locator('.sem li')).toHaveCount(2)
  await expect(page.getByText('RUN_STARTED')).toBeVisible()

  await page.getByRole('button', { name: /Artifacts/ }).click()
  await expect(page.getByText('run-report.md')).toBeVisible()
  await expect(page.getByText('4.2 KB')).toBeVisible()

  // Cost rail totals the entry amounts.
  await expect(page.locator('.kv .v', { hasText: '$0.038' })).toBeVisible()
})

test('run detail surfaces a load error instead of fixtures', async ({ page }) => {
  await page.route('**/api/v1/runs/run_missing**', (route) =>
    route.fulfill({
      status: 404,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'NOT_FOUND', message: 'not found', data: null }),
    }),
  )
  await page.goto('/observe/runs/run_missing', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('This data could not be loaded.')).toBeVisible()
})
