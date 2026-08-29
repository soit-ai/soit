import { expect, test } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const runs = [
  {
    id: 'run_01J9KD84QF',
    attempt_no: 1,
    mode: 'chat',
    subject_kind: 'agent',
    subject_id: 'support-triage',
    status: 'running',
    started_at: '2026-08-29T13:47:10Z',
    duration_ms: 3100,
    created_at: '2026-08-29T13:47:10Z',
    updated_at: '2026-08-29T13:47:10Z',
    observe_summary: {
      step_count: 6,
      tool_call_count: 2,
      child_run_count: 0,
      response_event_count: 14,
      citation_count: 1,
      audit_count: 2,
      cost_entry_count: 3,
    },
  },
  {
    id: 'run_01J9KD7Z2M',
    attempt_no: 1,
    mode: 'workflow',
    subject_kind: 'workflow',
    subject_id: 'ticket-escalation',
    status: 'succeeded',
    started_at: '2026-08-29T13:45:31Z',
    duration_ms: 8900,
    created_at: '2026-08-29T13:45:31Z',
    updated_at: '2026-08-29T13:45:31Z',
    observe_summary: {
      step_count: 7,
      tool_call_count: 1,
      child_run_count: 0,
      response_event_count: 9,
      citation_count: 0,
      audit_count: 2,
      cost_entry_count: 2,
    },
  },
  {
    id: 'run_01J9KD6H0T',
    attempt_no: 1,
    mode: 'task',
    subject_kind: 'agent',
    subject_id: 'billing-audit',
    status: 'failed',
    started_at: '2026-08-29T13:38:02Z',
    duration_ms: 1200,
    created_at: '2026-08-29T13:38:02Z',
    updated_at: '2026-08-29T13:38:02Z',
    observe_summary: {
      step_count: 3,
      tool_call_count: 0,
      child_run_count: 0,
      response_event_count: 4,
      citation_count: 0,
      audit_count: 1,
      cost_entry_count: 1,
    },
  },
]

async function mockRunsApi(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/runs/costs/summary**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({
        tokens_prompt: 3_600_000,
        tokens_completion: 1_100_000,
        embedding_count: 0,
        rerank_count: 0,
        ms_total: 812_000,
        storage_bytes: 0,
        request_count: 1284,
      }),
    }),
  )
  await page.route('**/api/v1/runs/costs/by-provider**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok([
        { provider: 'anthropic', tokens_prompt: 1_500_000, tokens_completion: 400_000, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 },
        { provider: 'dashscope', tokens_prompt: 600_000, tokens_completion: 200_000, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 },
      ]),
    }),
  )
  await page.route('**/api/v1/runs/costs/by-model**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok([
        { model_ref: 'claude-sonnet-5', tokens_prompt: 1_400_000, tokens_completion: 380_000, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 },
      ]),
    }),
  )
  await page.route('**/api/v1/runs/costs/by-day**', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok([
        { date: '2026-08-28', tokens_prompt: 1_900_000, tokens_completion: 500_000, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 },
        { date: '2026-08-29', tokens_prompt: 1_700_000, tokens_completion: 600_000, embedding_count: 0, rerank_count: 0, ms_total: 0, storage_bytes: 0 },
      ]),
    }),
  )
  await page.route('**/api/v1/runs?**', (route) => {
    const url = new URL(route.request().url())
    const status = url.searchParams.get('status')
    const items = status ? runs.filter((run) => run.status === status) : runs
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ items, page_size: 20, next_page_token: null }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
  await mockRunsApi(page)
})

test('console runs renders the prototype workbench with live data', async ({ page }) => {
  await page.goto('/v2/observe/runs', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible()

  // Cost overview aggregates.
  await expect(page.getByText('Cost overview')).toBeVisible()
  await expect(page.getByText('4.7M tok')).toBeVisible()
  await expect(page.getByText('anthropic')).toBeVisible()
  await expect(page.getByText('claude-sonnet-5')).toBeVisible()

  // Table rows with the unified status vocabulary.
  await expect(page.getByText('run_01J9KD84QF')).toBeVisible()
  await expect(page.getByText('support-triage')).toBeVisible()
  const firstRow = page.locator('[data-slot=table-row]', { hasText: 'run_01J9KD84QF' })
  await expect(firstRow.getByText('Running')).toBeVisible()
  await expect(page.getByText('3 runs on this page')).toBeVisible()
})

test('console runs quick status filter narrows the query', async ({ page }) => {
  await page.goto('/v2/observe/runs', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('run_01J9KD84QF')).toBeVisible()

  await page.locator('.fchip', { hasText: 'Failed' }).click()
  await expect(page).toHaveURL(/status=failed/)
  await expect(page.getByText('run_01J9KD6H0T')).toBeVisible()
  await expect(page.getByText('run_01J9KD84QF')).toHaveCount(0)
  await expect(page.getByText('1 runs on this page')).toBeVisible()
})

test('console runs row click opens the run detail route', async ({ page }) => {
  await page.goto('/v2/observe/runs', { waitUntil: 'domcontentloaded' })
  await page.getByText('run_01J9KD7Z2M').click()
  await expect(page).toHaveURL(/\/v2\/observe\/runs\/run_01J9KD7Z2M/)
})
