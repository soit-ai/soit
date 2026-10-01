import { expect, test, type Page, type Route } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const fulfil = (route: Route, data: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: ok(data) })

const NOW = '2026-10-01T10:00:00Z'
const KB = 'product-docs'
const SOURCES = `**/api/v1/knowledge/${KB}/sources`

const base = {
  id: KB,
  tenant_id: 't1',
  workspace_id: 'w1',
  name: 'product-docs',
  description: 'public docs site',
  status: 'active',
  visibility: 'workspace',
  knowledge_type: 'document',
  settings_json: {},
  chunking_json: { chunk_size: 512, chunk_overlap: 64 },
  retrieval_json: { top_k: 5 },
  doc_count: 2,
  chunk_count: 2,
  tags: [],
  created_at: NOW,
  updated_at: NOW,
}

const connectors = [
  {
    kind: 's3',
    label: 'S3-compatible storage',
    description: 'Sync documents from an S3-compatible bucket.',
    secret: 'required',
    secret_help: 'A secret whose value is JSON with access_key_id and secret_access_key.',
    fields: [
      { key: 'bucket', label: 'Bucket', type: 'string', required: true, options: [] },
      { key: 'region', label: 'Region', type: 'string', required: false, default: 'us-east-1', options: [] },
      { key: 'prefix', label: 'Prefix', type: 'string', required: false, options: [] },
      { key: 'include', label: 'Include patterns', type: 'string_list', required: false, options: [] },
      { key: 'path_style', label: 'Path-style addressing', type: 'boolean', required: false, options: [] },
    ],
  },
  {
    kind: 'web',
    label: 'Website crawl',
    description: 'Crawl a website from seed URLs.',
    secret: 'none',
    fields: [
      { key: 'seed_urls', label: 'Seed URLs', type: 'string_list', required: true, options: [] },
      { key: 'max_depth', label: 'Max depth', type: 'integer', required: false, default: 2, minimum: 0, maximum: 5, options: [] },
    ],
  },
]

const limits = { max_items: 1000, max_item_bytes: 5 * 1024 * 1024, max_total_bytes: 256 * 1024 * 1024 }

const bucketSource = {
  id: 'ksrc_1',
  tenant_id: 't1',
  workspace_id: 'w1',
  knowledge_id: KB,
  name: 'handbook bucket',
  connector_kind: 's3',
  config: { bucket: 'handbook', region: 'eu-west-1', prefix: 'docs/' },
  secret_id: 'sec_aws',
  limits,
  schedule_cron: '0 2 * * *',
  schedule_timezone: 'UTC',
  enabled: true,
  delete_removed: false,
  next_sync_at: '2999-01-01T02:00:00Z',
  last_sync_at: NOW,
  last_status: 'succeeded',
  last_error: null,
  last_counts: { added: 3, updated: 1, unchanged: 12, removed: 0, failed: 0, skipped: 2, truncated: false },
  active_run_id: null,
  created_by: 'user-1',
  created_at: NOW,
  updated_at: NOW,
}

const siteSource = {
  ...bucketSource,
  id: 'ksrc_2',
  name: 'docs site',
  connector_kind: 'web',
  config: { seed_urls: ['https://docs.acme.io/'], max_depth: 2 },
  secret_id: null,
  schedule_cron: null,
  next_sync_at: null,
  last_status: 'failed',
  last_error: 'https://docs.acme.io/: The seed URL was not found',
  last_counts: { added: 0, updated: 0, unchanged: 0, removed: 0, failed: 0, skipped: 0, truncated: false },
}

const runs = [
  {
    id: 'ksync_2',
    source_id: 'ksrc_1',
    knowledge_id: KB,
    trigger: 'manual',
    status: 'running',
    added_count: 1,
    updated_count: 0,
    unchanged_count: 0,
    removed_count: 0,
    failed_count: 0,
    skipped_count: 0,
    truncated: false,
    cancel_requested: false,
    requested_by: 'user-1',
    started_at: NOW,
    finished_at: null,
    created_at: NOW,
  },
  {
    id: 'ksync_1',
    source_id: 'ksrc_1',
    knowledge_id: KB,
    trigger: 'schedule',
    status: 'partial',
    added_count: 3,
    updated_count: 1,
    unchanged_count: 12,
    removed_count: 0,
    failed_count: 1,
    skipped_count: 2,
    truncated: false,
    error_code: null,
    error_message: null,
    cancel_requested: false,
    requested_by: null,
    started_at: '2026-10-01T02:00:00Z',
    finished_at: '2026-10-01T02:01:05Z',
    created_at: '2026-10-01T02:00:00Z',
  },
]

const runDetail = {
  ...runs[1],
  outcomes: [
    { external_id: 'handbook/a.pdf', name: 'a.pdf', outcome: 'added' },
    { external_id: 'handbook/b.md', name: 'b.md', outcome: 'failed', error: 'access denied' },
  ],
}

/** GET mocks the library detail page needs before the Sources tab can be opened. */
async function mockDetail(page: Page, sources: unknown[] = [bucketSource, siteSource]) {
  await json(page, `**/api/v1/knowledge/${KB}`, base)
  await json(page, `**/api/v1/knowledge/${KB}/documents**`, [])
  await json(page, `**/api/v1/knowledge/${KB}/indexes**`, [])
  await json(page, `**/api/v1/knowledge/${KB}/usages**`, [])
  await json(page, `**/api/v1/knowledge/${KB}/runs/costs/summary**`, {
    request_count: 0,
    ms_total: 0,
    embedding_count: 0,
    rerank_count: 0,
  })
  await json(page, '**/api/v1/knowledge/connectors', connectors)
  await json(page, SOURCES, sources)
  await json(page, '**/api/v1/secrets**', [
    { id: 'sec_aws', name: 'aws-docs-reader', created_at: NOW, updated_at: NOW },
    { id: 'sec_other', name: 'other-key', created_at: NOW, updated_at: NOW },
  ])
}

async function openSources(page: Page) {
  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs').getByRole('button', { name: /^Sources/ }).click()
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('the Sources tab lists each source with its schedule, last sync and next sync', async ({ page }) => {
  await mockDetail(page)

  await openSources(page)

  const rows = page.getByTestId('knowledge-source-row')
  await expect(rows).toHaveCount(2)
  const bucket = rows.filter({ hasText: 'handbook bucket' })
  await expect(bucket).toContainText('S3-compatible storage')
  await expect(bucket).toContainText('Daily at 02:00')
  await expect(bucket).toContainText('Succeeded')
  await expect(bucket).toContainText('+3 ~1')
  await expect(bucket).toContainText(/in \d+d/)

  const site = rows.filter({ hasText: 'docs site' })
  await expect(site).toContainText('manual only')
  await expect(site).toContainText('Failed')
  await expect(site).toContainText('The seed URL was not found')
  // The header carries the count and the soonest schedule.
  await expect(page.locator('.rd-meta')).toContainText('2 source(s)')
})

test('an empty library invites the first source', async ({ page }) => {
  await mockDetail(page, [])

  await openSources(page)

  await expect(page.getByText('No sources yet.')).toBeVisible()
})

test('adding an S3 source renders the connector fields and creates it with a secret and a schedule', async ({
  page,
}) => {
  await mockDetail(page, [])
  let created: Record<string, unknown> | null = null
  await page.route(SOURCES, (route) => {
    if (route.request().method() !== 'POST') return fulfil(route, [])
    created = route.request().postDataJSON()
    return fulfil(route, { ...bucketSource, id: 'ksrc_new' }, 201)
  })

  await openSources(page)
  await page.getByRole('button', { name: 'Add source' }).click()

  const modal = page.locator('.console-modal')
  await expect(modal.getByRole('heading', { name: 'Add source' })).toBeVisible()
  const create = modal.getByRole('button', { name: 'Create' })
  // Nothing can be created before the name, the required setting and the secret are in.
  await expect(create).toBeDisabled()

  await modal.getByLabel('Name', { exact: true }).fill('handbook bucket')
  await modal.getByLabel('Bucket').fill('handbook')
  await expect(create).toBeDisabled()
  await modal.getByLabel('Secret').selectOption('sec_aws')
  await modal.getByLabel('Include patterns').fill('*.pdf\ndocs/*')
  await modal.getByLabel('Schedule', { exact: true }).selectOption('daily')
  await modal.getByLabel('Time zone').fill('Europe/Berlin')
  await expect(create).toBeEnabled()
  await create.click()

  await expect.poll(() => created).not.toBeNull()
  expect(created).toMatchObject({
    name: 'handbook bucket',
    connector_kind: 's3',
    secret_id: 'sec_aws',
    schedule_cron: '0 2 * * *',
    schedule_timezone: 'Europe/Berlin',
    enabled: true,
    delete_removed: false,
    config: { bucket: 'handbook', region: 'us-east-1', include: ['*.pdf', 'docs/*'] },
  })
})

test('a website source takes no secret and offers a custom cron', async ({ page }) => {
  await mockDetail(page, [])
  let created: Record<string, unknown> | null = null
  await page.route(SOURCES, (route) => {
    if (route.request().method() !== 'POST') return fulfil(route, [])
    created = route.request().postDataJSON()
    return fulfil(route, { ...siteSource, id: 'ksrc_new' }, 201)
  })

  await openSources(page)
  await page.getByRole('button', { name: 'Add source' }).click()
  const modal = page.locator('.console-modal')
  await modal.getByLabel('Connector').selectOption('web')

  await expect(modal.getByLabel('Secret')).toHaveCount(0)
  await modal.getByLabel('Name', { exact: true }).fill('docs site')
  await modal.getByLabel('Seed URLs').fill('https://docs.acme.io/')
  await modal.getByLabel('Schedule', { exact: true }).selectOption('custom')
  await modal.getByLabel('Cron expression').fill('*/30 * * * *')
  await modal.getByRole('checkbox', { name: /^When an item disappears/ }).check()
  await modal.getByRole('button', { name: 'Create' }).click()

  await expect.poll(() => created).not.toBeNull()
  expect(created).toMatchObject({
    connector_kind: 'web',
    secret_id: null,
    schedule_cron: '*/30 * * * *',
    delete_removed: true,
    config: { seed_urls: ['https://docs.acme.io/'], max_depth: 2 },
  })
})

test('the form tests an unsaved connection and shows the sample or the refusal', async ({ page }) => {
  await mockDetail(page, [])
  let attempt = 0
  let posted: Record<string, unknown> | null = null
  await page.route(`${SOURCES}/test`, (route) => {
    attempt += 1
    posted = route.request().postDataJSON()
    return fulfil(
      route,
      attempt === 1
        ? {
            ok: false,
            message:
              'Outbound access to minio.internal was refused by the egress policy. Allow the host in the workspace egress policy.',
            sample: [],
          }
        : {
            ok: true,
            message: 'Connected to bucket handbook; 2 matching objects in the sample',
            sample: [
              { external_id: 'handbook/a.pdf', name: 'a.pdf' },
              { external_id: 'handbook/b.md', name: 'b.md' },
            ],
          },
    )
  })

  await openSources(page)
  await page.getByRole('button', { name: 'Add source' }).click()
  const modal = page.locator('.console-modal')
  const test_ = modal.getByRole('button', { name: 'Test connection' })
  await expect(test_).toBeDisabled()
  await modal.getByLabel('Bucket').fill('handbook')
  await modal.getByLabel('Secret').selectOption('sec_aws')

  await test_.click()
  await expect(modal.getByTestId('source-test-result')).toContainText('refused by the egress policy')
  expect(posted).toMatchObject({ connector_kind: 's3', secret_id: 'sec_aws', config: { bucket: 'handbook' } })

  await test_.click()
  const result = modal.getByTestId('source-test-result')
  await expect(result).toContainText('The connection works.')
  await expect(result).toContainText('handbook/a.pdf')
  await expect(result).toContainText('handbook/b.md')
})

test('Sync now queues a run, and a refusal from the server is shown', async ({ page }) => {
  await mockDetail(page)
  let calls = 0
  await page.route(`${SOURCES}/ksrc_1/sync`, (route) => {
    calls += 1
    if (calls === 1) return fulfil(route, runs[0], 202)
    return route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({
        success: false,
        code: 'CONFLICT',
        message: 'A sync is already queued or running for this source',
      }),
    })
  })

  await openSources(page)
  const row = page.getByTestId('knowledge-source-row').filter({ hasText: 'handbook bucket' })
  await row.getByRole('button', { name: 'Sync now' }).click()
  await expect(page.getByText('Sync queued.')).toBeVisible()

  await row.getByRole('button', { name: 'Sync now' }).click()
  // The request layer toasts the refusal as well as the panel, so two copies show.
  await expect(page.getByText('A sync is already queued or running for this source').first()).toBeVisible()
  expect(calls).toBe(2)
})

test('the enable switch patches the source', async ({ page }) => {
  await mockDetail(page)
  let patched: Record<string, unknown> | null = null
  await page.route(`${SOURCES}/ksrc_1`, (route) => {
    patched = route.request().postDataJSON()
    return fulfil(route, { ...bucketSource, enabled: false })
  })

  await openSources(page)
  await page.getByRole('switch', { name: 'Enable handbook bucket' }).click()

  await expect.poll(() => patched).toEqual({ enabled: false })
})

test('a saved source is tested from its row', async ({ page }) => {
  await mockDetail(page)
  await page.route(`${SOURCES}/ksrc_1/test`, (route) =>
    fulfil(route, {
      ok: true,
      message: 'Connected to bucket handbook; 1 matching objects in the sample',
      sample: [{ external_id: 'handbook/a.pdf', name: 'a.pdf' }],
    }),
  )

  await openSources(page)
  await page
    .getByTestId('knowledge-source-row')
    .filter({ hasText: 'handbook bucket' })
    .getByRole('button', { name: 'Test', exact: true })
    .click()

  await expect(page.getByTestId('source-test-result')).toContainText('handbook/a.pdf')
})

test('the history lists runs, opens a run for its outcomes and cancels one that is running', async ({
  page,
}) => {
  await mockDetail(page)
  let canceled: string | null = null
  await page.route(`${SOURCES}/ksrc_1/runs**`, (route) => fulfil(route, runs))
  await page.route(`${SOURCES}/ksrc_1/runs/ksync_1`, (route) => fulfil(route, runDetail))
  await page.route(`${SOURCES}/ksrc_1/runs/ksync_2/cancel`, (route) => {
    canceled = route.request().method()
    return fulfil(route, { ...runs[0], cancel_requested: true })
  })

  await openSources(page)
  await page
    .getByTestId('knowledge-source-row')
    .filter({ hasText: 'handbook bucket' })
    .getByRole('button', { name: 'History' })
    .click()

  const modal = page.locator('.console-modal')
  const rows = modal.getByTestId('sync-run-row')
  await expect(rows).toHaveCount(2)
  await expect(rows.nth(0)).toContainText('Running')
  await expect(rows.nth(1)).toContainText('Degraded')
  await expect(rows.nth(1)).toContainText('1m 05s')

  await rows.nth(1).click()
  const detail = modal.getByTestId('sync-run-detail')
  await expect(detail).toContainText('handbook/a.pdf')
  await expect(detail).toContainText('access denied')

  await rows.nth(0).getByRole('button', { name: 'Cancel' }).click()
  await expect.poll(() => canceled).toBe('POST')
})

test('deleting a source goes through a confirm modal', async ({ page }) => {
  await mockDetail(page)
  let deleted: string | null = null
  await page.route(`${SOURCES}/ksrc_2`, (route) => {
    deleted = route.request().method()
    return fulfil(route, null)
  })

  await openSources(page)
  await page
    .getByTestId('knowledge-source-row')
    .filter({ hasText: 'docs site' })
    .getByRole('button', { name: 'Delete' })
    .click()

  await expect(page.getByRole('heading', { name: 'Delete source' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Delete' }).click()

  await expect.poll(() => deleted).toBe('DELETE')
})

test('editing a source loads its settings and sends only what changed', async ({ page }) => {
  await mockDetail(page)
  let patched: Record<string, unknown> | null = null
  await page.route(`${SOURCES}/ksrc_1`, (route) => {
    if (route.request().method() === 'PATCH') patched = route.request().postDataJSON()
    return fulfil(route, bucketSource)
  })

  await openSources(page)
  await page
    .getByTestId('knowledge-source-row')
    .filter({ hasText: 'handbook bucket' })
    .getByRole('button', { name: 'Edit' })
    .click()

  const modal = page.locator('.console-modal')
  await expect(modal.getByRole('heading', { name: 'Edit source' })).toBeVisible()
  await expect(modal.getByLabel('Bucket')).toHaveValue('handbook')
  await expect(modal.getByLabel('Region')).toHaveValue('eu-west-1')
  await expect(modal.getByLabel('Secret')).toHaveValue('sec_aws')
  await expect(modal.getByLabel('Schedule', { exact: true })).toHaveValue('daily')
  // The connector cannot be switched on a saved source.
  await expect(modal.getByLabel('Connector')).toBeDisabled()

  await modal.getByLabel('Max item size (MB)').fill('10')
  await modal.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({
    name: 'handbook bucket',
    secret_id: 'sec_aws',
    schedule_cron: '0 2 * * *',
    limits: { max_item_bytes: 10 * 1024 * 1024 },
  })
  expect((patched as unknown as { limits: Record<string, unknown> }).limits).not.toHaveProperty('max_items')
})
