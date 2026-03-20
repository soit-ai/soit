import { expect, test, type Page } from '@playwright/test'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
}

const mockAgent = {
  id: 'agent-1',
  tenant_id: 'tenant-1',
  workspace_id: 'workspace-1',
  name: 'Demo Agent',
  description: 'Agent for e2e test',
  status: 'active',
  visibility: 'private',
  icon_url: null,
  category: null,
  is_public: false,
  featured: false,
  downloads_count: 0,
  rating: null,
  reviews_count: 0,
  published_at: null,
  tags: ['demo'],
  current_version_id: 'ver-1',
  published_version_id: 'ver-1',
  created_by: 'user-1',
  updated_by: 'user-1',
  created_at: '2026-02-16T10:00:00.000Z',
  updated_at: '2026-02-16T10:00:00.000Z',
  deleted_at: null,
}

async function mockAgentApi(page: Page) {
  await page.route('**/api/v1/agents**', async (route) => {
    const method = route.request().method()
    if (method === 'POST') {
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ data: mockAgent }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [mockAgent],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockAgentApi(page)
})

test('agent list renders api data', async ({ page }) => {
  await page.goto('/agents', { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Demo Agent')).toBeVisible()
})

test('agent create form accepts current agent semantics', async ({ page }) => {
  await page.goto('/agents', { waitUntil: 'domcontentloaded' })

  await page.getByPlaceholder('Agent name').fill('New Agent')
  await page.getByPlaceholder('Short description').fill('Created through e2e')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('Demo Agent')).toBeVisible()
})
