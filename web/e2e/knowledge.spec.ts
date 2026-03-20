import { expect, test, type Page } from '@playwright/test'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockKnowledge = {
  id: 'kb-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Knowledge Alpha',
  description: 'Knowledge base for e2e',
  status: 'active',
  visibility: 'workspace',
  knowledge_type: 'document',
  source_type: 'document',
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

async function mockKnowledgeApi(page: Page) {
  await page.route('**/api/v1/knowledge**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.endsWith('/knowledge/kb-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockKnowledge }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockKnowledge],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockKnowledgeApi(page)
})

test('knowledge list renders api data', async ({ page }) => {
  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Knowledge Alpha')).toBeVisible()
})

test('knowledge detail renders inventory data', async ({ page }) => {
  await page.goto('/knowledge/kb-1', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Knowledge Alpha')).toBeVisible()
  await expect(page.getByText('Documents: 2')).toBeVisible()
})
