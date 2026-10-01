import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) => JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string | RegExp, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-10-01T09:00:00Z'

const dataset = {
  id: 'regds_1',
  subject_kind: 'agent',
  subject_id: 'agt_support',
  name: 'refund-policy',
  description: 'Policy questions the support agent must answer',
  revision: 3,
  status: 'active',
  case_count: 2,
  latest_report: {
    id: 'regrep_2',
    passed: false,
    total: 2,
    passed_count: 1,
    pass_rate: 0.5,
    dataset_revision: 3,
    subject_version_id: 'ver_9',
    model_ref: null,
    created_at: NOW,
  },
  created_by: 'user-1',
  created_at: NOW,
  updated_at: NOW,
}

const untouched = {
  ...dataset,
  id: 'regds_2',
  name: 'tone',
  description: '',
  revision: 1,
  case_count: 0,
  latest_report: null,
}

const cases = [
  {
    id: 'regcase_1',
    name: 'refund-window',
    input: 'How long do refunds take?',
    expected_features_json: { minimum_output_terms: ['14 days'], max_latency_ms: 2000 },
    dataset: 'refund-policy',
    dataset_revision: 2,
    source_run_id: null,
    created_by: 'user-1',
    created_at: NOW,
  },
  {
    id: 'regcase_2',
    name: 'tone',
    input: { messages: [{ role: 'user', content: 'I am angry' }] },
    expected_features_json: { llm_judge: { rubric: 'Stays calm', min_score: 0.8 } },
    dataset: 'refund-policy',
    dataset_revision: 3,
    source_run_id: 'run_frozen',
    created_by: 'user-1',
    created_at: NOW,
  },
]

const report = {
  id: 'regrep_2',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  subject_kind: 'agent',
  subject_id: 'agt_support',
  subject_version_id: 'ver_9',
  passed: false,
  dataset: 'refund-policy',
  dataset_revision: 3,
  baseline_report_id: 'regrep_1',
  regressed_case_ids_json: ['regcase_2'],
  fixed_case_ids_json: [],
  summary_json: { total: 2, passed: 1, failed: 1, regressed: 1, fixed: 0 },
  metrics_json: { avg_latency_ms: 840, total_cost_amount: 0.0123 },
  case_results_json: [
    { case_id: 'regcase_1', name: 'refund-window', passed: true, latency_ms: 800, run_id: 'run_a' },
    {
      case_id: 'regcase_2',
      name: 'tone',
      passed: false,
      latency_ms: 880,
      run_id: 'run_b',
      failure_reasons: ['llm_judge_below_threshold'],
      judge: { score: 0.4, min_score: 0.8 },
    },
  ],
  created_by: 'user-1',
  created_at: NOW,
}

const reportSummary = Object.fromEntries(
  Object.entries(report).filter(([key]) => key !== 'case_results_json'),
)

const versions = [
  {
    id: 'regdsv_3',
    dataset_id: 'regds_1',
    revision: 3,
    case_count: 2,
    content_hash: 'c0ffee0123456789abcdef',
    changes: { added: 1, removed: 0, changed: 0 },
    note: 'Imported from JSONL',
    created_by: 'user-1',
    created_at: NOW,
  },
  {
    id: 'regdsv_2',
    dataset_id: 'regds_1',
    revision: 2,
    case_count: 1,
    content_hash: 'deadbeef0123456789abcd',
    changes: { added: 1, removed: 0, changed: 0 },
    note: '',
    created_by: 'user-1',
    created_at: NOW,
  },
]

const page_of = (items: unknown[], total = items.length) => ({
  items,
  next_page_token: null,
  page_size: items.length,
  total,
})

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('workspace_id', 'workspace-1')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

async function mockDetail(page: Page) {
  await json(page, '**/api/v1/evaluations/datasets/regds_1', dataset)
  await json(page, '**/api/v1/evaluations/datasets/regds_1/cases**', page_of(cases))
  await json(page, '**/api/v1/evaluations/datasets/regds_1/versions?**', versions)
  await json(page, '**/api/v1/evaluations/regression-reports/trend**', {
    subject_kind: 'agent',
    subject_id: 'agt_support',
    dataset: 'refund-policy',
    points: [
      {
        report_id: 'regrep_1',
        subject_version_id: 'ver_8',
        dataset: 'refund-policy',
        dataset_revision: 2,
        created_at: NOW,
        passed: true,
        total: 1,
        passed_count: 1,
        pass_rate: 1,
        regressed: 0,
        fixed: 0,
      },
      {
        report_id: 'regrep_2',
        subject_version_id: 'ver_9',
        dataset: 'refund-policy',
        dataset_revision: 3,
        created_at: NOW,
        passed: false,
        total: 2,
        passed_count: 1,
        pass_rate: 0.5,
        regressed: 1,
        fixed: 0,
      },
    ],
  })
  await json(page, '**/api/v1/evaluations/reports?**', page_of([reportSummary]))
  await json(page, '**/api/v1/evaluations/reports/regrep_2', report)
}

test('the evaluations page lists datasets with their revision and latest result', async ({
  page,
}) => {
  await json(page, '**/api/v1/evaluations/datasets**', [dataset, untouched])

  await page.goto('/observe/evaluations', { waitUntil: 'domcontentloaded' })

  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('refund-policy')
  await expect(rows.first()).toContainText('r3')
  await expect(rows.first()).toContainText('1/2')
  await expect(rows.first()).toContainText('50.0%')
  await expect(rows.nth(1)).toContainText('never run')
})

test('the Observe panel links to evaluations', async ({ page }) => {
  await json(page, '**/api/v1/evaluations/datasets**', [dataset])

  await page.goto('/observe/evaluations', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('link', { name: /Evaluations/ }).first()).toBeVisible()
})

test('a dataset is created for an agent and its JSONL import goes to the import route', async ({
  page,
}) => {
  await json(page, '**/api/v1/evaluations/datasets**', [])
  await json(page, '**/api/v1/agents/workbench**', {
    summary: { total_agents: 1, updated_at: NOW },
    tabs: { all: 1 },
    items: [{ id: 'agt_support', name: 'support' }],
    next_page_token: null,
    page_size: 50,
  })

  let created: unknown = null
  let imported: unknown = null
  await page.route('**/api/v1/evaluations/datasets', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    created = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: ok({ ...untouched, id: 'regds_9', name: 'new-set' }),
    })
  })
  await json(page, '**/api/v1/evaluations/datasets/regds_9', { ...untouched, id: 'regds_9' })
  await json(page, '**/api/v1/evaluations/datasets/regds_9/**', page_of([]))
  await page.route('**/api/v1/evaluations/datasets/regds_9/import', async (route) => {
    imported = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: ok({
        imported: 1,
        dataset: { ...untouched, id: 'regds_9', name: 'new-set', revision: 2 },
      }),
    })
  })

  await page.goto('/observe/evaluations', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'New dataset' }).click()
  await page.locator('#evaluation-agent').selectOption('agt_support')
  await page.locator('#evaluation-name').fill('new-set')
  await page
    .locator('#evaluation-import-content')
    .fill('{"name":"a","input":"hi","expected_features":{"minimum_output_terms":["x"]}}')
  await page.locator('.console-modal').getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => created).toMatchObject({ subject_id: 'agt_support', name: 'new-set' })
  await expect
    .poll(() => imported)
    .toMatchObject({ content: expect.stringContaining('"name":"a"') })
  await expect(page).toHaveURL(/\/observe\/evaluations\/regds_9$/)
})

test('a refused import lists every bad line and keeps the dialog open', async ({ page }) => {
  await mockDetail(page)
  await page.route('**/api/v1/evaluations/datasets/regds_1/import', (route) =>
    route.fulfill({
      status: 400,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        code: 'VALIDATION_ERROR',
        message: '2 of 3 lines are not valid cases; nothing was imported',
        details: {
          error_count: 2,
          errors: [
            { line: 2, message: 'not valid JSON: Expecting value' },
            { line: 3, message: '/expected_features: {} should be non-empty' },
          ],
        },
      }),
    }),
  )

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Import JSONL' }).click()
  await page.locator('#evaluation-import-content').fill('{}\nnope\n{}')
  await page.locator('.console-modal').getByRole('button', { name: 'Import' }).click()

  const alert = page.locator('.console-modal').getByRole('alert')
  await expect(alert).toContainText('line 2: not valid JSON')
  await expect(alert).toContainText('line 3')
  await expect(page.locator('.console-modal')).toBeVisible()
})

test('the dataset page shows its cases with what each one expects', async ({ page }) => {
  await mockDetail(page)

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })

  await expect(page.locator('h1')).toContainText('refund-policy')
  const rows = page.locator('tbody tr')
  await expect(rows).toHaveCount(2)
  await expect(rows.first()).toContainText('refund-window')
  await expect(rows.first()).toContainText('terms ×1')
  await expect(rows.first()).toContainText('≤ 2000 ms')
  await expect(rows.nth(1)).toContainText('judge ≥ 0.8')
  await expect(rows.nth(1)).toContainText('frozen from run_frozen')
})

test('adding a case posts it in the dataset case format', async ({ page }) => {
  await mockDetail(page)
  let posted: unknown = null
  await page.route('**/api/v1/evaluations/datasets/regds_1/cases', async (route) => {
    if (route.request().method() !== 'POST') return route.fallback()
    posted = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({ status: 201, contentType: 'application/json', body: ok(cases[0]) })
  })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Add case' }).click()
  await page.locator('#evaluation-case-name').fill('shipping-cost')
  await page.locator('#evaluation-case-input').fill('Who pays for return shipping?')
  await page.locator('#evaluation-case-terms').fill('customer\nlabel')
  await page.locator('#evaluation-case-latency').fill('1500')
  await page.locator('.console-modal').getByRole('button', { name: 'Save' }).click()

  await expect
    .poll(() => posted)
    .toEqual({
      name: 'shipping-cost',
      input: 'Who pays for return shipping?',
      expected_features: { minimum_output_terms: ['customer', 'label'], max_latency_ms: 1500 },
    })
})

test('a case with no expectation is refused before anything is sent', async ({ page }) => {
  await mockDetail(page)
  let posted = false
  await page.route('**/api/v1/evaluations/datasets/regds_1/cases', (route) => {
    if (route.request().method() === 'POST') posted = true
    return route.fallback()
  })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Add case' }).click()
  await page.locator('#evaluation-case-name').fill('empty')
  await page.locator('#evaluation-case-input').fill('anything')
  await page.locator('.console-modal').getByRole('button', { name: 'Save' }).click()

  await expect(page.locator('.console-modal').getByRole('alert')).toContainText(
    'at least one expectation',
  )
  expect(posted).toBe(false)
})

test('removing a case goes through the delete route', async ({ page }) => {
  await mockDetail(page)
  let removed = false
  await page.route('**/api/v1/evaluations/datasets/regds_1/cases/regcase_1', (route) => {
    if (route.request().method() !== 'DELETE') return route.fallback()
    removed = true
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...dataset, revision: 4, case_count: 1 }),
    })
  })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.locator('tbody tr').first().getByRole('button', { name: 'Delete' }).click()
  await page.locator('.console-modal').getByRole('button', { name: 'Delete' }).click()

  await expect.poll(() => removed).toBe(true)
})

test('the reports tab shows a report against its baseline, with regressed cases marked', async ({
  page,
}) => {
  await mockDetail(page)

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Reports/ }).click()
  await page.locator('tbody tr').first().click()

  const detail = page.locator('.panel', { hasText: 'regrep_2' })
  await expect(detail).toContainText('regrep_1')
  await expect(detail).toContainText('REGRESSED')
  await expect(detail).toContainText('llm_judge_below_threshold')
  await expect(detail).toContainText('judge 0.4 (min 0.8)')
})

test('the versions tab shows each revision with its change counts and hash', async ({ page }) => {
  await mockDetail(page)
  await json(page, '**/api/v1/evaluations/datasets/regds_1/versions/3', {
    ...versions[0],
    snapshot: [
      {
        name: 'refund-window',
        input: 'How long do refunds take?',
        expected_features: { max_latency_ms: 2000 },
      },
    ],
  })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: /Versions/ }).click()

  const rows = page.locator('tbody tr')
  await expect(rows.first()).toContainText('r3')
  await expect(rows.first()).toContainText('+1')
  await expect(rows.first()).toContainText('c0ffee012345')
  await rows.first().click()
  await expect(page.locator('.panel', { hasText: 'Revision r3' })).toContainText('refund-window')
})

test('running an evaluation posts the dataset and opens the report it recorded', async ({
  page,
}) => {
  await mockDetail(page)
  let ran: unknown = null
  await page.route('**/api/v1/evaluations/run', async (route) => {
    ran = JSON.parse(route.request().postData() || '{}')
    return route.fulfill({ status: 201, contentType: 'application/json', body: ok(report) })
  })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Run evaluation' }).first().click()
  await page.locator('#evaluation-run-max').fill('10')
  await page.locator('.console-modal').getByRole('button', { name: 'Run', exact: true }).click()

  await expect
    .poll(() => ran)
    .toEqual({
      subject_kind: 'agent',
      subject_id: 'agt_support',
      dataset: 'refund-policy',
      max_cases: 10,
    })
  await expect(page.getByRole('tab', { name: /Reports/ })).toHaveAttribute('aria-selected', 'true')
  await expect(page.locator('.panel', { hasText: 'regrep_2' })).toContainText('REGRESSED')
})

test('export downloads the JSONL the server renders', async ({ page }) => {
  await mockDetail(page)
  await page.route('**/api/v1/evaluations/datasets/regds_1/export', (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/x-ndjson',
      headers: { 'content-disposition': 'attachment; filename="soit-dataset-refund-policy.jsonl"' },
      body: '{"name":"refund-window","input":"hi","expected_features":{"max_latency_ms":2000}}\n',
    }),
  )

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: 'Export' }).click()

  expect((await download).suggestedFilename()).toBe('soit-dataset-refund-policy.jsonl')
})

test('an archived dataset cannot be run or edited and offers a restore', async ({ page }) => {
  await mockDetail(page)
  await json(page, '**/api/v1/evaluations/datasets/regds_1', { ...dataset, status: 'archived' })

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('button', { name: 'Restore' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Run evaluation' }).first()).toBeDisabled()
  await expect(page.getByRole('button', { name: 'Add case' })).toHaveCount(0)
})

test('the dataset page stays inside a phone viewport', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 800 })
  await mockDetail(page)

  await page.goto('/observe/evaluations/regds_1', { waitUntil: 'domcontentloaded' })
  await expect(page.locator('h1')).toContainText('refund-policy')

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1)
})
