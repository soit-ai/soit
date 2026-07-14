import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

async function mockRunDetailApi(page: Page) {
  await page.route('**/api/v1/runs/run-1**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          run: {
            id: 'run-1',
            trace_id: 'trace-1',
            user_id: 'user-1',
            mode: 'agent',
            kind: 'agent',
            subject_kind: 'agent',
            subject_id: 'agent-1',
            subject_version_id: 'agent-version-1',
            status: 'succeeded',
            input_summary: 'demo input',
            output_summary: 'demo output',
            started_at: '2026-05-01T10:00:00.000Z',
            ended_at: '2026-05-01T10:00:01.000Z',
            duration_ms: 1000,
            error_code: null,
            error_message: null,
            error_step_id: null,
            created_at: '2026-05-01T10:00:00.000Z',
            updated_at: '2026-05-01T10:00:01.000Z',
          },
          steps: [
            {
              id: 'step-1',
              run_id: 'run-1',
              trace_id: 'trace-1',
              step_id: 'agent-tool',
              step_type: 'tool',
              node_id: null,
              status: 'succeeded',
              input_summary: 'tool_ref=wf:ticket-triage',
              output_summary: 'workflow completed',
              metrics_json: {},
              error_code: null,
              error_message: null,
              error_details: null,
              started_at: '2026-05-01T10:00:00.500Z',
              ended_at: '2026-05-01T10:00:00.800Z',
              created_at: '2026-05-01T10:00:00.500Z',
            },
          ],
          artifacts: [],
          cost_summary: {
            tokens_prompt: 12,
            tokens_completion: 24,
            embedding_count: 0,
            rerank_count: 0,
            ms_total: 1000,
            storage_bytes: 0,
          },
          costs: [
            {
              id: 'cost-1',
              run_id: 'run-1',
              step_id: 'step-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              currency: 'USD',
              amount: '0.000000',
              unit: 'tokens',
              quantity: '36.000000',
              provider: 'openai',
              model_ref: 'gpt-4o',
              tool_ref: null,
              prompt_tokens: 12,
              completion_tokens: 24,
              total_tokens: 36,
              created_at: '2026-05-01T10:00:00.900Z',
            },
          ],
          response_events: [
            {
              id: 'event-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              response_id: 'resp-1',
              run_id: 'run-1',
              thread_id: 'thread-1',
              task_id: 'task-1',
              agent_id: 'agent-1',
              sequence: 1,
              type: 'response.completed',
              source: 'agent',
              payload_json: { status: 'completed' },
              created_at: '2026-05-01T10:00:01.000Z',
            },
          ],
          tool_calls: [
            {
              id: 'tool-call-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              response_id: 'resp-1',
              run_id: 'run-1',
              step_id: 'step-1',
              thread_id: 'thread-1',
              task_id: 'task-1',
              agent_id: 'agent-1',
              tool_name: 'builtin.ticket.create_review_ticket',
              tool_type: 'builtin',
              status: 'completed',
              arguments_json: { ticket_id: 'TCK-1001' },
              result_json: { result: { ticket_id: 'TICKET-42' } },
              metadata_json: {},
              error_code: null,
              error_message: null,
              started_at: '2026-05-01T10:00:00.500Z',
              completed_at: '2026-05-01T10:00:00.800Z',
              created_at: '2026-05-01T10:00:00.500Z',
              updated_at: '2026-05-01T10:00:00.800Z',
            },
          ],
          citations: [
            {
              chunk_id: 'chunk-1',
              document_id: 'doc-1',
              knowledge_id: 'knowledge-support',
              title: 'Refund Policy',
              doc_key: 'refund-policy.md',
              source_uri: 'kb://refund-policy.md',
              rank: 1,
              score: 0.92,
              snippet: 'Refund tickets require account verification.',
            },
          ],
          audits: [
            {
              run_id: 'run-1',
              step_id: 'step-1',
              step_type: 'tool',
              gateway_type: 'tool',
              request: { tool_ref: 'builtin.ticket.create_review_ticket' },
              response: { success: true },
              timestamp: '2026-05-01T10:00:00.900Z',
              truncated: false,
              preview: null,
              artifact_key: null,
            },
          ],
          child_runs: [
            {
              id: 'run-workflow-1',
              trace_id: 'trace-1',
              user_id: 'user-1',
              mode: 'workflow',
              kind: 'workflow',
              subject_kind: 'workflow',
              subject_id: 'wf-ticket-triage',
              subject_version_id: 'workflow-version-1',
              status: 'succeeded',
              input_summary: 'ticket input',
              output_summary: 'ticket output',
              started_at: '2026-05-01T10:00:00.600Z',
              ended_at: '2026-05-01T10:00:00.900Z',
              duration_ms: 300,
              error_code: null,
              error_message: null,
              error_step_id: null,
              created_at: '2026-05-01T10:00:00.600Z',
              updated_at: '2026-05-01T10:00:00.900Z',
            },
          ],
          governance_evidence: [
            {
              key: 'actor_scope',
              status: 'pass',
              label: 'Actor and scope',
              summary: 'Run is tied to tenant, workspace, user, and run identifiers.',
              evidence_refs: ['tenant-1', 'workspace-1', 'user-1', 'run-1'],
              missing: [],
            },
            {
              key: 'permission_scope',
              status: 'warning',
              label: 'Permission scope',
              summary: 'No explicit permission decision evidence was recorded on run steps.',
              evidence_refs: [],
              missing: ['permission_scope'],
            },
            {
              key: 'knowledge_citation',
              status: 'fail',
              label: 'Knowledge citation',
              summary: 'No knowledge citations are attached.',
              evidence_refs: [],
              missing: ['citations'],
            },
            {
              key: 'child_workflow',
              status: 'not_applicable',
              label: 'Child workflow',
              summary: 'No child workflow runs were recorded for this run.',
              evidence_refs: [],
              missing: [],
            },
          ],
        },
      }),
    })
  })

  await page.route('**/api/v1/responses/by-run/run-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          run_id: 'run-1',
          items: [],
        },
      }),
    })
  })

  await page.route('**/api/v1/runs/audits**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page: {
            page_size: 50,
            next_page_token: null,
          },
        },
      }),
    })
  })
}

async function mockRunListApi(page: Page) {
  await page.route('**/api/v1/runs**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname !== '/api/v1/runs') {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [
            {
              id: 'run-1',
              trace_id: 'trace-1',
              user_id: 'user-1',
              mode: 'agent',
              kind: 'agent',
              subject_kind: 'agent',
              subject_id: 'agent-1',
              subject_version_id: 'agent-version-1',
              status: 'succeeded',
              input_summary: 'demo input',
              output_summary: 'demo output',
              started_at: '2026-05-01T10:00:00.000Z',
              ended_at: '2026-05-01T10:00:01.000Z',
              duration_ms: 1000,
              error_code: null,
              error_message: null,
              error_step_id: null,
              created_at: '2026-05-01T10:00:00.000Z',
              updated_at: '2026-05-01T10:00:01.000Z',
              observe_summary: {
                step_count: 6,
                tool_call_count: 1,
                child_run_count: 1,
                response_event_count: 3,
                citation_count: 2,
                audit_count: 1,
                cost_entry_count: 2,
              },
            },
          ],
          page_size: 1,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/runs/costs/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: route.request().url().includes('/summary') ? { tokens_prompt: 0, tokens_completion: 0, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 } : [] }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockRunDetailApi(page)
  await mockRunListApi(page)
})

test('run detail displays normalized enterprise mvp evidence', async ({ page }) => {
  await page.goto('/observe/runs/run-1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByText('Steps', { exact: true })).toBeVisible()
  await expect(page.getByText('Cost Summary', { exact: true })).toBeVisible()
  await expect(page.getByText('Knowledge citations', { exact: true })).toBeVisible()
  await expect(page.getByText('Workflow child runs', { exact: true })).toBeVisible()
  await expect(page.getByText('External tool calls', { exact: true })).toBeVisible()
  await expect(page.getByText('Audit Records', { exact: true })).toBeVisible()
  await expect(page.getByText('Governance Evidence', { exact: true })).toBeVisible()
  await expect(page.getByText('Passed 1')).toBeVisible()
  await expect(page.getByText('Warning 1')).toBeVisible()
  await expect(page.getByText('Failed 1')).toBeVisible()
  await expect(page.getByText('N/A 1')).toBeVisible()
  await expect(page.getByText('Actor and scope')).toBeVisible()
  await expect(page.getByText('Missing: permission_scope')).toBeVisible()
  await expect(page.getByText('Missing: citations')).toBeVisible()
  await expect(page.getByText('Failure and retry status')).toBeVisible()
  await expect(page.getByText('Refund Policy')).toBeVisible()
  await expect(page.getByText('refund-policy.md')).toBeVisible()
  await expect(page.getByText('run-workflow-1')).toBeVisible()
  await expect(page.getByText('builtin.ticket.create_review_ticket', { exact: true })).toBeVisible()
  await expect(page.getByText('Args: {"ticket_id":"TCK-1001"}')).toBeVisible()
  await expect(page.getByText('Result: {"result":{"ticket_id":"TICKET-42"}}')).toBeVisible()
  await expect(page.getByText('Status: succeeded · Error step: -')).toBeVisible()
})

test('run explorer quick filters and summary columns are visible', async ({ page }) => {
  await page.goto('/observe/runs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('button', { name: '有工具调用' })).toBeVisible({ timeout: 15000 })
  await page.getByRole('button', { name: '有工具调用' }).click()
  await expect(page).toHaveURL(/has_tool_call=true/)
  await expect(page.getByRole('row').filter({ hasText: 'run-1' })).toContainText('步骤 6')
  await expect(page.getByRole('row').filter({ hasText: 'run-1' })).toContainText('工具 1')
  await expect(page.getByRole('row').filter({ hasText: 'run-1' })).toContainText('引用 2')
  await expect(page.getByRole('row').filter({ hasText: 'run-1' })).toContainText('审计 1')

  await page.getByRole('button', { name: '有 citation' }).click()
  await expect(page).toHaveURL(/has_citation=true/)
})

test('observe audit explorer queries governed tool records', async ({ page }) => {
  let auditRequestUrl = ''
  await page.route('**/api/v1/runs/audits**', async (route) => {
    auditRequestUrl = route.request().url()
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [
            {
              run_id: 'run-audit-1',
              step_id: 'step-tool-1',
              step_type: 'tool',
              gateway_type: 'tool',
              request: { tool_ref: 'tool:http:request' },
              response: { success: true },
              timestamp: '2026-05-01T10:00:00.900Z',
              truncated: false,
              preview: 'tool:http:request allowed',
              artifact_key: null,
            },
          ],
          page_size: 1,
          next_page_token: null,
        },
      }),
    })
  })

  await page.goto('/observe/audits?gateway_type=tool&step_type=tool', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Audit Explorer' })).toBeVisible()
  await expect(page.getByText('tool:http:request allowed')).toBeVisible()
  await expect(page.getByRole('row').filter({ hasText: 'run-audit-1' })).toContainText('tool')
  expect(auditRequestUrl).toContain('gateway_type=tool')
  expect(auditRequestUrl).toContain('step_type=tool')
})
