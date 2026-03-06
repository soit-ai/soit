import { test, expect, type Page } from '@playwright/test'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockDataset = {
  id: 'ds-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Knowledge Alpha',
  type: 'document',
  description: 'Dataset for e2e',
  status: 'published',
  visibility: 'workspace',
  settings_json: {},
  chunking_json: {},
  retrieval_json: {},
  default_embedding_model_ref: null,
  default_reranker_ref: null,
  default_index_id: null,
  doc_count: 2,
  chunk_count: 8,
  last_ingested_at: null,
  last_indexed_at: null,
  tags: [],
  created_at: '2026-02-15T00:00:00.000Z',
  updated_at: '2026-02-15T00:00:00.000Z',
}

const mockDocuments = [
  {
    id: 'doc-1',
    tenant_id: 'tenant-1',
    workspace_id: 'workspace-1',
    dataset_id: 'ds-1',
    doc_key: 'doc-1',
    version: 1,
    is_latest: true,
    source_type: 'upload',
    title: 'Playwright Guide',
    language: 'en',
    mime_type: 'text/plain',
    filename: 'guide.txt',
    size_bytes: 128,
    checksum: null,
    content_hash: null,
    source_uri: null,
    file_id: null,
    error_code: null,
    error_message: null,
    retry_count: 0,
    status: 'indexed',
    parse_meta_json: {},
    index_meta_json: {},
    created_at: '2026-02-15T00:00:00.000Z',
    updated_at: '2026-02-15T00:00:00.000Z',
    deleted_at: null,
  },
]

async function mockDatasetApi(page: Page) {
  await page.route('**/api/v1/datasets/ds-1/documents**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: mockDocuments }),
    })
  })

  await page.route('**/api/v1/datasets/ds-1/ingest-tasks**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: [] }),
    })
  })

  await page.route('**/api/v1/datasets/ds-1', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: mockDataset }),
    })
  })

  await page.route('**/api/v1/datasets**', async (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockDataset }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockDataset],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockDatasetApi(page)
})

test('dataset list renders api data', async ({ page }) => {
  await page.goto('/dataset', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Knowledge Alpha')).toBeVisible()
})

test('dataset document page renders documents', async ({ page }) => {
  await page.goto('/dataset/ds-1/document', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Playwright Guide')).toBeVisible()
})
