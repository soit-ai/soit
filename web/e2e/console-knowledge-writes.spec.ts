import { expect, test, type Page } from '@playwright/test'

import { mockShellApi } from './helpers'

const ok = (data: unknown) =>
  JSON.stringify({ success: true, code: 'OK', message: 'OK', data })

const json = (page: Page, pattern: string, data: unknown) =>
  page.route(pattern, (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: ok(data) }),
  )

const NOW = '2026-08-29T13:00:00Z'
const KB = 'product-docs'

const base = {
  id: KB,
  tenant_id: 't1',
  workspace_id: 'w1',
  name: 'product-docs',
  description: 'public docs site',
  status: 'active',
  visibility: 'workspace',
  knowledge_type: 'vector',
  settings_json: { source_uri: 'https://docs.acme.io' },
  chunking_json: { chunk_size: 512, chunk_overlap: 64 },
  retrieval_json: { top_k: 5, use_rerank: true, keyword_min_score: 0.42 },
  doc_count: 2,
  chunk_count: 2,
  tags: [],
  created_at: NOW,
  updated_at: NOW,
}

const documents = [
  {
    id: 'doc_1',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    doc_key: 'guides/getting-started.md',
    version: 1,
    is_latest: true,
    source_kind: 'upload',
    title: 'Getting started',
    filename: 'getting-started.md',
    source_uri: '/guides/getting-started.md',
    status: 'indexed',
    index_meta_json: { chunk_count: 12 },
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 'doc_2',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    doc_key: 'guides/billing.pdf',
    version: 1,
    is_latest: true,
    source_kind: 'upload',
    title: 'Billing',
    filename: 'billing.pdf',
    source_uri: '/guides/billing.pdf',
    status: 'failed',
    error_message: 'ocr timeout',
    index_meta_json: {},
    created_at: NOW,
    updated_at: NOW,
  },
]

const indexes = [
  {
    id: 'idx_1',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    name: 'primary',
    is_primary: true,
    provider: 'milvus',
    embedding_model_ref: 'bge-m3',
    dimension: 1024,
    metric_type: 'cosine',
    status: 'ready',
    build_version: 3,
    last_build_at: NOW,
    last_run_id: 'run_01J9KD84QF',
    doc_count: 2,
    chunk_count: 2,
    vector_count: 2,
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 'idx_2',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    name: 'voyage-trial',
    is_primary: false,
    provider: 'milvus',
    embedding_model_ref: 'voyage-3',
    dimension: 1024,
    metric_type: 'cosine',
    status: 'building',
    build_version: 1,
    last_build_at: NOW,
    last_run_id: null,
    doc_count: 2,
    chunk_count: 2,
    vector_count: 1200,
    created_at: NOW,
    updated_at: NOW,
  }
]

const chunks = [
  {
    id: 'ck_1',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    document_id: 'doc_1',
    document_version: 1,
    chunk_no: 3,
    chunk_key: 'ck_1#3',
    text_preview: 'Secrets are referenced as vault:name.',
    section_path: [],
    token_count: 88,
    index_status: 'indexed',
    created_at: NOW,
    updated_at: NOW,
  },
]

const ingestTasks = [
  {
    id: 'task_1',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    document_id: 'doc_2',
    status: 'failed',
    error_message: 'ocr timeout',
    max_retries: 3,
    retry_count: 1,
    payload_json: {},
    created_at: NOW,
    updated_at: NOW,
  },
  {
    id: 'task_2',
    tenant_id: 't1',
    workspace_id: 'w1',
    knowledge_id: KB,
    document_id: 'doc_1',
    status: 'running',
    max_retries: 3,
    retry_count: 0,
    payload_json: {},
    created_at: NOW,
    updated_at: NOW,
    started_at: NOW,
  },
]

const workbench = {
  summary: {
    total_knowledge_bases: 1,
    ready_knowledge_bases: 0,
    total_documents: 2,
    total_chunks: 2,
    today_calls: 12,
    avg_latency_ms: 210,
    hit_rate: 0.9,
    recent_exceptions: 3,
    updated_at: NOW,
  },
  tabs: { all: 1, high_volume: 0, low_hit: 0, slow: 0, unconfigured: 0 },
  items: [
    {
      id: KB,
      name: 'product-docs',
      description: 'public docs site',
      status: 'error',
      knowledge_type: 'vector',
      content_source: 'Upload',
      document_count: 2,
      chunk_count: 2,
      today_calls: 12,
      avg_latency_ms: 210,
      hit_rate: 0.9,
      recent_exception_count: 3,
      owner: 'Jude',
      last_sync_at: NOW,
      action_enabled: true,
      updated_at: NOW,
    },
  ],
  next_page_token: null,
  page_size: 50,
}

/** GET mocks the detail page needs before any write can be exercised. */
async function mockDetail(page: Page) {
  await json(page, `**/api/v1/knowledge/${KB}`, base)
  await json(page, `**/api/v1/knowledge/${KB}/documents**`, documents)
  await json(page, `**/api/v1/knowledge/${KB}/indexes**`, indexes)
  await json(page, `**/api/v1/knowledge/${KB}/usages**`, [])
  await json(page, `**/api/v1/knowledge/${KB}/runs/costs/summary**`, {
    request_count: 12,
    ms_total: 2400,
    embedding_count: 12,
    rerank_count: 4,
  })
  // Registered after the `documents**` glob so it wins for the chunk listing.
  await json(page, `**/api/v1/knowledge/${KB}/documents/doc_1/chunks**`, chunks)
}

/** GET mocks the list page needs, including the per-library ingest fan-out. */
async function mockList(page: Page) {
  await json(page, '**/api/v1/knowledge/workbench**', workbench)
  await json(page, `**/api/v1/knowledge/${KB}/ingest-tasks**`, ingestTasks)
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-token')
    localStorage.setItem('soit-console-theme', 'dark')
  })
  await mockShellApi(page)
})

test('adding documents uploads each file as multipart', async ({ page }) => {
  await mockDetail(page)

  let upload: { url: string; method: string; contentType: string; body: string } | null = null
  await page.route(`**/api/v1/knowledge/${KB}/documents`, async (route) => {
    if (route.request().method() !== 'POST') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(documents) })
    }
    upload = {
      url: route.request().url(),
      method: route.request().method(),
      contentType: route.request().headers()['content-type'] || '',
      body: route.request().postData() || '',
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...documents[0], id: 'doc_3' }),
    })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Add documents' }).click()

  await expect(page.getByRole('heading', { name: 'Add documents' })).toBeVisible()
  const confirm = page.locator('.console-modal').getByRole('button', { name: 'Upload' })
  // Upload stays disabled until a file is picked.
  await expect(confirm).toBeDisabled()

  await page.locator('.console-modal input[type="file"]').setInputFiles({
    name: 'runbook.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# runbook\n'),
  })
  await expect(confirm).toBeEnabled()
  await confirm.click()

  await expect.poll(() => upload).not.toBeNull()
  expect(upload!.url).toContain(`/api/v1/knowledge/${KB}/documents`)
  expect(upload!.contentType).toContain('multipart/form-data')
  // The legacy upload payload: an upload-kind document carrying the file name.
  expect(upload!.body).toContain('name="source_kind"')
  expect(upload!.body).toContain('upload')
  expect(upload!.body).toContain('runbook.md')
})

test('a document row deletes through a confirm modal', async ({ page }) => {
  await mockDetail(page)

  let deleted: string | null = null
  await page.route(`**/api/v1/knowledge/${KB}/documents/doc_1`, (route) => {
    deleted = route.request().method()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page
    .locator('tr', { hasText: 'getting-started.md' })
    .getByRole('button', { name: 'Delete' })
    .click()

  await expect(page.getByRole('heading', { name: 'Delete document' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Delete' }).click()

  await expect.poll(() => deleted).toBe('DELETE')
})

test('a failed document reprocesses through retry-ingest', async ({ page }) => {
  await mockDetail(page)

  let retried: string | null = null
  await page.route(`**/api/v1/knowledge/${KB}/documents/doc_2/retry-ingest**`, (route) => {
    retried = route.request().url()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok(ingestTasks[0]),
    })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Reprocess with OCR' }).click()

  await expect.poll(() => retried).not.toBeNull()
  // The service pins a retry budget on the query string.
  expect(retried!).toContain('max_retries=1')
})

test('sync now rebuilds the primary index', async ({ page }) => {
  await mockDetail(page)

  let rebuilt: { url: string; method: string } | null = null
  await page.route(`**/api/v1/knowledge/${KB}/indexes/idx_1/rebuild`, (route) => {
    rebuilt = { url: route.request().url(), method: route.request().method() }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(indexes[0]) })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  const sync = page.getByRole('button', { name: 'Sync now' })
  await expect(sync).toBeEnabled()
  await sync.click()

  await expect.poll(() => rebuilt).not.toBeNull()
  expect(rebuilt!.method).toBe('POST')
})

test('a chunk edit patches only what changed', async ({ page }) => {
  await mockDetail(page)

  let patched: Record<string, unknown> | null = null
  await page.route(`**/api/v1/knowledge/${KB}/documents/doc_1/chunks/ck_1`, (route) => {
    patched = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(chunks[0]) })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Chunks' }).click()
  await page.locator('tr', { hasText: 'ck_1#3' }).click()

  await expect(page.getByRole('heading', { name: 'Edit chunk' })).toBeVisible()
  const save = page.locator('.console-modal').getByRole('button', { name: 'Save' })
  // Nothing edited yet, so there is nothing to send.
  await expect(save).toBeDisabled()

  await page.locator('.console-modal textarea.input').fill('Secrets resolve at call time.')
  await save.click()

  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({ content: 'Secrets resolve at call time.' })
  // The status was untouched, so it must not be sent.
  expect(patched && 'index_status' in patched).toBe(false)
})

test('library settings save name, source and threshold', async ({ page }) => {
  await mockDetail(page)

  let put: Record<string, unknown> | null = null
  await page.route(`**/api/v1/knowledge/${KB}`, (route) => {
    if (route.request().method() !== 'PUT') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(base) })
    }
    put = route.request().postDataJSON()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(base) })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Settings' }).click()

  const fields = page.locator('.frow input.input')
  await fields.nth(0).fill('product-docs-renamed')
  await fields.nth(1).fill('https://docs.acme.io/en')
  await fields.nth(2).fill('score ≥ 0.9')
  await page.getByRole('button', { name: 'Save' }).click()

  await expect.poll(() => put).not.toBeNull()
  expect(put).toMatchObject({
    name: 'product-docs-renamed',
    settings_json: { source_uri: 'https://docs.acme.io/en' },
    // Existing retrieval settings survive; only the threshold moves.
    retrieval_json: { top_k: 5, use_rerank: true, keyword_min_score: 0.9 },
  })
})

test('deleting the library confirms and returns to the list', async ({ page }) => {
  await mockDetail(page)
  await mockList(page)

  let deleted: string | null = null
  await page.route(`**/api/v1/knowledge/${KB}`, (route) => {
    if (route.request().method() !== 'DELETE') {
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(base) })
    }
    deleted = route.request().method()
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(null) })
  })

  await page.goto(`/build/knowledge/${KB}`, { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Settings' }).click()
  await page.locator('.frow').getByRole('button', { name: 'Delete…' }).click()

  await expect(page.getByRole('heading', { name: 'Delete library' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Delete…' }).click()

  await expect.poll(() => deleted).toBe('DELETE')
  await expect(page).toHaveURL(/\/build\/knowledge$/)
})

test('an ingest job retries from the queue tab', async ({ page }) => {
  await mockList(page)

  let retried: { url: string; method: string } | null = null
  await page.route(`**/api/v1/knowledge/${KB}/ingest-tasks/task_1/retry`, (route) => {
    retried = { url: route.request().url(), method: route.request().method() }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok(ingestTasks[0]),
    })
  })

  await page.goto('/build/knowledge', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Ingest queue' }).click()
  await page.getByRole('button', { name: 'Retry' }).click()

  await expect.poll(() => retried).not.toBeNull()
  expect(retried!.method).toBe('POST')
})

test('a running ingest job cancels through a confirm modal', async ({ page }) => {
  await mockList(page)

  let cancelled: { url: string; method: string } | null = null
  await page.route(`**/api/v1/knowledge/${KB}/ingest-tasks/task_2/cancel`, (route) => {
    cancelled = { url: route.request().url(), method: route.request().method() }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok({ ...ingestTasks[1], status: 'canceled' }),
    })
  })

  await page.goto('/build/knowledge', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Ingest queue' }).click()
  await page.getByRole('button', { name: 'Cancel job' }).click()

  await expect(page.getByRole('heading', { name: 'Cancel ingest job' })).toBeVisible()
  await page.locator('.console-modal').getByRole('button', { name: 'Cancel job' }).click()

  await expect.poll(() => cancelled).not.toBeNull()
  expect(cancelled!.method).toBe('POST')
})

test('the exceptions tab replays a library stopped ingest jobs', async ({ page }) => {
  await mockList(page)

  let retried: string | null = null
  await page.route(`**/api/v1/knowledge/${KB}/ingest-tasks/task_1/retry`, (route) => {
    retried = route.request().method()
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: ok(ingestTasks[0]),
    })
  })

  await page.goto('/build/knowledge', { waitUntil: 'domcontentloaded' })
  await page.locator('.tabs button', { hasText: 'Exceptions' }).click()
  await page.getByRole('button', { name: 'Reprocess with OCR' }).click()

  await expect.poll(() => retried).toBe('POST')
})

test('knowledge indexes can be created, edited and deleted', async ({ page }) => {
  let created: Record<string, unknown> | null = null
  let patched: Record<string, unknown> | null = null
  let deleted: string | null = null

  await page.route('**/api/v1/knowledge/product-docs/indexes', (route) => {
    if (route.request().method() === 'POST') {
      created = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok({ id: 'idx_new' }) })
    }
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(indexes) })
  })
  await page.route('**/api/v1/knowledge/product-docs/indexes/idx_2', (route) => {
    if (route.request().method() === 'PATCH') {
      patched = route.request().postDataJSON()
      return route.fulfill({ status: 200, contentType: 'application/json', body: ok(indexes[1]) })
    }
    if (route.request().method() === 'DELETE') {
      deleted = 'idx_2'
      return route.fulfill({ status: 204, body: '' })
    }
    return route.fallback()
  })

  await page.goto('/build/knowledge/product-docs', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: /Indexes/ }).click()

  // The index serving retrieval offers no delete; only the candidate does.
  await expect(page.getByRole('button', { name: 'Delete' })).toHaveCount(1)

  await page.getByRole('button', { name: 'New index' }).click()
  await page.locator('.console-modal input.input').first().fill('voyage-trial')
  await page.locator('.console-modal input.input').nth(1).fill('voyage-3')
  await page.locator('.console-modal .btn.primary').click()
  await expect.poll(() => created).not.toBeNull()
  expect(created).toMatchObject({ name: 'voyage-trial', embedding_model_ref: 'voyage-3', metric_type: 'cosine' })

  // Renaming must not carry the embedding model, which would invalidate vectors.
  await page.getByRole('button', { name: 'Edit' }).nth(1).click()
  await page.locator('.console-modal input.input').first().fill('voyage-candidate')
  await page.locator('.console-modal .btn.primary').click()
  await expect.poll(() => patched).not.toBeNull()
  expect(patched).toMatchObject({ name: 'voyage-candidate' })
  expect(patched && 'embedding_model_ref' in patched).toBe(false)

  // A row's Rebuild must name its own index, not the one serving retrieval.
  let rebuilt: string | null = null
  await page.route('**/api/v1/knowledge/product-docs/indexes/*/rebuild', (route) => {
    rebuilt = new URL(route.request().url()).pathname.split('/').slice(-2)[0]
    return route.fulfill({ status: 200, contentType: 'application/json', body: ok(indexes[1]) })
  })
  await page.getByRole('button', { name: 'Rebuild' }).nth(1).click()
  await expect.poll(() => rebuilt).toBe('idx_2')

  await page.getByRole('button', { name: 'Delete' }).click()
  await page.locator('.console-modal .btn.primary').click()
  await expect.poll(() => deleted).toBe('idx_2')
})
