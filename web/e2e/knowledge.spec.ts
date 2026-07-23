import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'
import type { KnowledgeIndex, KnowledgeIngestTask } from '../app/services/knowledge-service'

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

const mockKnowledgeWorkbench = {
  summary: {
    total_knowledge_bases: 1,
    ready_knowledge_bases: 1,
    total_documents: 2,
    total_chunks: 8,
    today_calls: 12,
    avg_latency_ms: 900,
    hit_rate: 100,
    recent_exceptions: 0,
    updated_at: '2026-02-16T10:00:00.000Z',
  },
  tabs: {
    all: 1,
    high_volume: 0,
    low_hit: 0,
    slow: 0,
    unconfigured: 0,
  },
  items: [
    {
      id: 'kb-1',
      name: 'Knowledge Alpha',
      description: 'Runtime-backed knowledge row',
      status: 'ready',
      knowledge_type: 'document',
      content_source: 'Upload',
      document_count: 2,
      chunk_count: 8,
      today_calls: 12,
      avg_latency_ms: 900,
      hit_rate: 100,
      recent_exception_count: 0,
      owner: 'user-1',
      last_sync_at: '2026-02-16T10:00:00.000Z',
      action_enabled: true,
      updated_at: '2026-02-16T10:00:00.000Z',
    },
  ],
  page_size: 1,
  next_page_token: null,
}

async function mockKnowledgeApi(page: Page) {
  let indexes: KnowledgeIndex[] = [
    {
      id: 'idx-1',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      knowledge_id: 'kb-1',
      name: 'primary',
      is_primary: true,
      provider: 'milvus',
      embedding_model_ref: 'model:test:embedding',
      dimension: 3,
      metric_type: 'cosine',
      status: 'ready',
      build_version: 3,
      last_build_at: '2026-02-16T10:00:00.000Z',
      last_run_id: 'run-index-1',
      doc_count: 1,
      chunk_count: 2,
      vector_count: 2,
      last_error_code: null,
      last_error_message: null,
      created_at: '2026-02-15T00:00:00.000Z',
      updated_at: '2026-02-16T10:00:00.000Z',
    },
    {
      id: 'idx-failed',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      knowledge_id: 'kb-1',
      name: 'failed-index',
      is_primary: false,
      provider: 'milvus',
      embedding_model_ref: 'model:test:embedding',
      dimension: 3,
      metric_type: 'cosine',
      status: 'failed',
      build_version: 1,
      last_build_at: null,
      last_run_id: 'run-index-failed',
      doc_count: 1,
      chunk_count: 2,
      vector_count: 0,
      last_error_code: 'BUILD_ERROR',
      last_error_message: 'Embedding backend unavailable',
      created_at: '2026-02-15T00:00:00.000Z',
      updated_at: '2026-02-16T09:00:00.000Z',
    },
  ]

  let tasks: KnowledgeIngestTask[] = [
    {
      id: 'task-failed',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      knowledge_id: 'kb-1',
      document_id: 'doc-1',
      status: 'failed',
      run_id: 'run-ingest-failed',
      error_code: 'INGEST_ERROR',
      error_message: 'Parser failed on page 2',
      max_retries: 2,
      retry_count: 2,
      payload_json: { title: 'Failed upload', doc_key: 'failed-upload' },
      created_by: 'user-1',
      updated_by: 'user-1',
      created_at: '2026-02-16T09:00:00.000Z',
      updated_at: '2026-02-16T09:05:00.000Z',
      started_at: '2026-02-16T09:01:00.000Z',
      finished_at: '2026-02-16T09:05:00.000Z',
    },
    {
      id: 'task-queued',
      tenant_id: 'tenant-1',
      workspace_id: 'workspace-1',
      knowledge_id: 'kb-1',
      document_id: 'doc-2',
      status: 'queued',
      run_id: 'run-ingest-queued',
      error_code: null,
      error_message: null,
      max_retries: 1,
      retry_count: 0,
      payload_json: { title: 'Queued upload', doc_key: 'queued-upload' },
      created_by: 'user-1',
      updated_by: 'user-1',
      created_at: '2026-02-16T09:10:00.000Z',
      updated_at: '2026-02-16T09:10:00.000Z',
      started_at: null,
      finished_at: null,
    },
  ]

  await page.route('**/api/v1/knowledge**', async (route) => {
    const url = new URL(route.request().url())
    if (url.pathname.includes('/knowledge/workbench/items')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            items: mockKnowledgeWorkbench.items,
            page_size: 1,
            next_page_token: null,
          },
        }),
      })
      return
    }

    if (url.pathname.includes('/knowledge/workbench')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockKnowledgeWorkbench }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/documents')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [
            {
              id: 'doc-1',
              tenant_id: 'tenant-1',
              workspace_id: 'workspace-1',
              knowledge_id: 'kb-1',
              doc_key: 'support-runbook',
              version: 1,
              is_latest: true,
              source_kind: 'upload',
              title: 'Support Runbook',
              language: 'en',
              mime_type: 'text/plain',
              filename: 'support.txt',
              size_bytes: 128,
              source_uri: 'file://support.txt',
              status: 'indexed',
              created_at: '2026-02-16T09:00:00.000Z',
              updated_at: '2026-02-16T09:05:00.000Z',
            },
          ],
        }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/ingest-tasks/task-failed/retry')) {
      tasks = tasks.map((task) =>
        task.id === 'task-failed'
          ? { ...task, status: 'queued', error_code: null, error_message: null, retry_count: 0 }
          : task
      )
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: tasks[0] }) })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/ingest-tasks/task-queued/cancel')) {
      tasks = tasks.map((task) => (task.id === 'task-queued' ? { ...task, status: 'canceled' } : task))
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: tasks[1] }) })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/ingest-tasks')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: tasks }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/indexes/idx-1/rebuild')) {
      indexes = indexes.map((item) =>
        item.id === 'idx-1'
          ? { ...item, build_version: 4, last_run_id: 'run-index-2', last_build_at: '2026-02-16T10:30:00.000Z' }
          : item
      )
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: indexes[0] }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/indexes')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: indexes }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/query')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            results: [
              {
                chunk_id: 'chunk-1',
                document_id: 'doc-1',
                score: 0.93,
                text: 'Reset the router and confirm the support ticket status.',
                snippets: ['confirm the support ticket status'],
                metadata: {
                  knowledge_id: 'kb-1',
                  doc_key: 'support-runbook',
                  title: 'Support Runbook',
                  source_uri: 'file://support.txt',
                  chunk_no: 1,
                },
              },
            ],
            total: 1,
            citations: [
              {
                chunk_id: 'chunk-1',
                document_id: 'doc-1',
                rank: 1,
                score: 0.93,
                knowledge_id: 'kb-1',
                doc_key: 'support-runbook',
                title: 'Support Runbook',
                source_uri: 'file://support.txt',
                chunk_no: 1,
                page_no: null,
                section_path: ['Troubleshooting'],
                snippet: 'confirm the support ticket status',
              },
            ],
          },
        }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: mockKnowledge }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/usages')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
      })
      return
    }

    if (url.pathname.endsWith('/knowledge/kb-1/runs')) {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
            items: [],
            page_size: 5,
            next_page_token: null,
          },
        }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
  await mockShellApi(page)
  await mockKnowledgeApi(page)
})

test('empty workspace creates a knowledge base from the create dialog', async ({ page }) => {
  let createPayload: Record<string, unknown> | null = null
  await page.route('**/api/v1/knowledge', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    createPayload = JSON.parse(route.request().postData() || '{}')
    await route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          ...mockKnowledge,
          id: 'kb-created',
          name: 'Support handbook',
          description: 'Customer support policies',
        },
      }),
    })
  })

  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create Knowledge Base' }).click()
  await page.getByLabel('Name').fill('Support handbook')
  await page.getByLabel('Description').fill('Customer support policies')
  await page.getByRole('dialog').getByRole('button', { name: 'Create Knowledge Base' }).click()

  await expect.poll(() => createPayload).toMatchObject({
    name: 'Support handbook',
    description: 'Customer support policies',
    knowledge_type: 'document',
    visibility: 'workspace',
  })
  await expect(page).toHaveURL(/\/knowledge\/kb-created$/)
})

test('knowledge creation error keeps the dialog open for correction and retry', async ({ page }) => {
  let attempts = 0
  await page.route('**/api/v1/knowledge', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    attempts += 1
    await route.fulfill({
      status: 409,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'CONFLICT', message: 'Knowledge base name already exists', data: null }),
    })
  })

  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create Knowledge Base' }).click()
  await page.getByLabel('Name').fill('Duplicate handbook')
  const submit = page.getByRole('dialog').getByRole('button', { name: 'Create Knowledge Base' })
  await submit.click()

  await expect.poll(() => attempts).toBe(1)
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('Name')).toHaveValue('Duplicate handbook')
  await expect(page.getByText('Knowledge base name already exists')).toBeVisible()
  await expect(submit).toBeEnabled()
})

test('knowledge permission failure does not clear the authenticated workspace', async ({ page }) => {
  await page.route('**/api/v1/knowledge', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    await route.fulfill({
      status: 403,
      contentType: 'application/json',
      body: JSON.stringify({ success: false, code: 'FORBIDDEN', message: 'You cannot create knowledge bases in this workspace', data: null }),
    })
  })

  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create Knowledge Base' }).click()
  await page.getByLabel('Name').fill('Restricted handbook')
  await page.getByRole('dialog').getByRole('button', { name: 'Create Knowledge Base' }).click()

  await expect(page.getByText('You cannot create knowledge bases in this workspace')).toBeVisible()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page).toHaveURL(/\/knowledge$/)
  await expect.poll(() => page.evaluate(() => localStorage.getItem('token'))).toBe('test-token')
})

test('knowledge network failure preserves the form for retry', async ({ page }) => {
  await page.route('**/api/v1/knowledge', async (route) => {
    if (route.request().method() !== 'POST') {
      await route.fallback()
      return
    }
    await route.abort('connectionfailed')
  })

  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Create Knowledge Base' }).click()
  await page.getByLabel('Name').fill('Offline handbook')
  const submit = page.getByRole('dialog').getByRole('button', { name: 'Create Knowledge Base' })
  await submit.click()

  await expect(page.getByText('Network Error')).toBeVisible()
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByLabel('Name')).toHaveValue('Offline handbook')
  await expect(submit).toBeEnabled()
})

test('knowledge list renders api data', async ({ page }) => {
  await page.goto('/knowledge', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Knowledge Alpha', { exact: true })).toBeVisible({ timeout: 15_000 })
  await expect(page.getByText('Runtime-backed knowledge row')).toBeVisible()
  await expect(page.getByRole('table').getByText('100%')).toBeVisible()
})

test('knowledge detail renders inventory data', async ({ page }) => {
  await page.goto('/knowledge/kb-1', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Knowledge Alpha')).toBeVisible()
  await expect(page.getByText('Documents: 2')).toBeVisible()
})

test('knowledge documents show failed ingest retry and run link', async ({ page }) => {
  await page.goto('/knowledge/kb-1/document', { waitUntil: 'domcontentloaded' })
  await page.getByRole('button', { name: 'Processing Queue' }).click()

  await expect(page.getByText('Parser failed on page 2')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Retry' })).toBeVisible()
  await page.getByRole('button', { name: 'View Run' }).first().click()
  await expect(page).toHaveURL(/\/observe\/runs\/run-ingest-failed/)
})

test('knowledge indexes expose rebuild state and run links', async ({ page }) => {
  await page.goto('/knowledge/kb-1/setting', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Indexes' }).click()

  await expect(page.getByText('v3')).toBeVisible()
  await expect(page.getByText('Embedding backend unavailable')).toBeVisible()
  await page.getByRole('row', { name: /primary/ }).getByRole('button', { name: 'Rebuild' }).click()
  await expect(page.getByText('v4')).toBeVisible()

  await page.getByRole('row', { name: /primary/ }).getByRole('button', { name: 'View Run' }).click()
  await expect(page).toHaveURL(/\/observe\/runs\/run-index-2/)
})

test('knowledge query renders citation title snippet and source', async ({ page }) => {
  await page.goto('/knowledge/kb-1/setting', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Query' }).click()

  await expect(page.getByText('Strategy')).toBeVisible()
  await expect(page.getByText('Index', { exact: true })).toBeVisible()
  await expect(page.getByText('Rerank')).toBeVisible()
  await page.getByLabel('Query Text').fill('support ticket status')
  await page.getByRole('button', { name: 'Run Query' }).click()

  await expect(page.getByText('Support Runbook').last()).toBeVisible()
  await expect(page.getByText('confirm the support ticket status').last()).toBeVisible()
  await expect(page.getByText('Source: file://support.txt')).toBeVisible()
})
