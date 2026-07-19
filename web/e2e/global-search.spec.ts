import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('i18nextLng', 'en-US')
}

const searchItems = [
  {
    kind: 'agent',
    id: 'agt_customer',
    title: 'Customer support agent',
    subtitle: 'Answers customer questions',
    status: 'active',
    url: '/agents/agt_customer',
    updated_at: '2026-07-18T01:00:00Z',
  },
  {
    kind: 'workflow',
    id: 'wf_customer',
    title: 'Customer triage workflow',
    subtitle: 'Routes incoming customer requests',
    status: 'active',
    url: '/workflow/wf_customer/build',
    updated_at: '2026-07-18T01:00:00Z',
  },
  {
    kind: 'thread',
    id: 'thr_customer',
    title: 'Customer incident',
    subtitle: 'Escalation from a customer conversation',
    status: 'active',
    url: '/chat/agt_customer/thr_customer',
    updated_at: '2026-07-18T01:00:00Z',
  },
]

async function mockGlobalSearch(page: Page) {
  await page.route('**/api/v1/search**', async (route) => {
    const url = new URL(route.request().url())
    const types = url.searchParams.getAll('types')
    const items = types.length
      ? searchItems.filter((item) => types.includes(item.kind))
      : searchItems
    const counts = Object.fromEntries(
      [...new Set(items.map((item) => item.kind))].map((kind) => [
        kind,
        items.filter((item) => item.kind === kind).length,
      ]),
    )
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { query: url.searchParams.get('q'), items, counts },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
  await mockGlobalSearch(page)
})

test('header search opens workspace results and filters by resource kind', async ({ page }) => {
  await page.goto('/', { waitUntil: 'domcontentloaded' })
  const search = page.getByPlaceholder('Search models, knowledge, workflows...')
  await search.fill('customer')
  await search.press('Enter')

  await expect(page).toHaveURL(/\/search\?q=customer/)
  await expect(page.getByRole('heading', { name: 'Search workspace' })).toBeVisible()
  await expect(page.getByText('Customer support agent')).toBeVisible()
  await expect(page.getByText('Customer triage workflow')).toBeVisible()
  await expect(page.getByText('Customer incident')).toBeVisible()

  await page.getByRole('button', { name: 'Agents' }).click()
  await expect(page.getByText('Customer support agent')).toBeVisible()
  await expect(page.getByText('Customer triage workflow')).toHaveCount(0)

  await page.getByRole('button', { name: 'Customer support agent' }).click()
  await expect(page).toHaveURL(/\/agents\/agt_customer$/)
})
