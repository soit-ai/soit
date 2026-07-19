import { expect, test, type Page } from '@playwright/test'
import { mockShellApi } from './helpers'

const seedLocalStorage = () => {
  localStorage.setItem('token', 'test-token')
  localStorage.setItem('workspace_id', 'workspace-1')
  localStorage.setItem('i18nextLng', 'zh-CN')
}

type FeedbackRecord = {
  id: string
  title: string
  description: string
  category: string
  priority: string
  status: string
  created_by: string
  created_at: string
  updated_at: string
  resolution_note: string | null
}

type FeedbackApiState = {
  submitted: Record<string, unknown> | null
  updated: Record<string, unknown> | null
  items: FeedbackRecord[]
}

async function mockFeedbackApi(
  page: Page,
  state: FeedbackApiState,
  role = 'Owner',
) {
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: {
          id: 'user-1',
          email: 'owner@example.com',
          name: 'Workspace Owner',
          is_active: true,
          created_at: '2026-07-18T00:00:00Z',
          tenant_id: 'tenant-1',
          workspace_id: 'workspace-1',
          tenant_role: role,
          workspace_role: role,
        },
      }),
    })
  })

  await page.route('**/api/v1/feedback**', async (route) => {
    const pathname = new URL(route.request().url()).pathname
    if (pathname.endsWith('/feedback/summary')) {
      const resolved = state.items.filter((item) => item.status === 'resolved').length
      const open = state.items.filter((item) => item.status === 'open').length
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          code: 'OK',
          message: 'OK',
          data: {
            total: state.items.length,
            by_status: { open, in_progress: 0, resolved, closed: 0 },
            by_category: { bug: state.items.length, feature: 0, performance: 0, usability: 0, other: 0 },
            by_priority: { low: 0, medium: 0, high: state.items.length, critical: 0 },
          },
        }),
      })
      return
    }

    if (route.request().method() === 'POST') {
      state.submitted = JSON.parse(route.request().postData() || '{}')
      const created: FeedbackRecord = {
        id: 'fbk-created',
        title: String(state.submitted?.title || ''),
        description: String(state.submitted?.description || ''),
        category: String(state.submitted?.category || 'other'),
        priority: String(state.submitted?.priority || 'medium'),
        status: 'open',
        created_by: 'user-1',
        created_at: '2026-07-18T01:00:00Z',
        updated_at: '2026-07-18T01:00:00Z',
        resolution_note: null,
      }
      state.items.unshift(created)
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: created }),
      })
      return
    }

    if (route.request().method() === 'PATCH') {
      state.updated = JSON.parse(route.request().postData() || '{}')
      const feedbackId = pathname.split('/').at(-1)
      const item = state.items.find((candidate) => candidate.id === feedbackId)
      if (!item) {
        await route.fulfill({ status: 404, body: '{}' })
        return
      }
      Object.assign(item, state.updated, { updated_at: '2026-07-18T02:00:00Z' })
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: item }),
      })
      return
    }

    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true,
        code: 'OK',
        message: 'OK',
        data: { items: state.items, page_size: state.items.length, next_page_token: null },
      }),
    })
  })
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(seedLocalStorage)
  await mockShellApi(page)
})

test('workspace owner submits and reviews product feedback', async ({ page }) => {
  const state: FeedbackApiState = {
    submitted: null,
    updated: null,
    items: [],
  }
  await mockFeedbackApi(page, state)

  await page.goto('/feedback', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('heading', { name: '产品反馈' })).toBeVisible()
  await page.getByLabel('标题').fill('Workflow editor loses changes')
  await page.getByLabel('详细描述').fill('Switching tabs discards the selected node configuration.')
  await page.getByRole('button', { name: '提交反馈' }).click()

  await expect.poll(() => state.submitted).toMatchObject({
    title: 'Workflow editor loses changes',
    description: 'Switching tabs discards the selected node configuration.',
    category: 'bug',
    priority: 'medium',
  })

  await page.getByRole('tab', { name: '我的工单' }).click()
  await expect(page.getByText('Workflow editor loses changes')).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Workspace 队列' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '统计' })).toBeVisible()
})

test('workspace owner resolves a feedback ticket with a resolution note', async ({ page }) => {
  const state: FeedbackApiState = {
    submitted: null,
    updated: null,
    items: [
      {
        id: 'fbk-open',
        title: 'Legacy adapter is still visible',
        description: 'The publish panel still offers an unsupported adapter.',
        category: 'bug',
        priority: 'high',
        status: 'open',
        created_by: 'user-2',
        created_at: '2026-07-18T01:00:00Z',
        updated_at: '2026-07-18T01:00:00Z',
        resolution_note: null,
      },
    ],
  }
  await mockFeedbackApi(page, state)

  await page.goto('/feedback', { waitUntil: 'domcontentloaded' })
  await page.getByRole('tab', { name: 'Workspace 队列' }).click()
  await page.getByRole('button', { name: '处理: Legacy adapter is still visible' }).click()
  await page.getByLabel('状态').click()
  await page.getByRole('option', { name: '已解决' }).click()
  await page.getByLabel('处理说明').fill('Removed the unsupported adapter from the publish panel.')
  await page.getByRole('button', { name: '保存更新' }).click()

  await expect.poll(() => state.updated).toMatchObject({
    status: 'resolved',
    resolution_note: 'Removed the unsupported adapter from the publish panel.',
  })
  await expect(page.getByText('已解决').first()).toBeVisible()
})

test('non-owner only sees submission and own tickets', async ({ page }) => {
  const state: FeedbackApiState = {
    submitted: null,
    updated: null,
    items: [],
  }
  await mockFeedbackApi(page, state, 'Viewer')

  await page.goto('/feedback', { waitUntil: 'domcontentloaded' })

  await expect(page.getByRole('tab', { name: '提交反馈' })).toBeVisible()
  await expect(page.getByRole('tab', { name: '我的工单' })).toBeVisible()
  await expect(page.getByRole('tab', { name: 'Workspace 队列' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '统计' })).toHaveCount(0)
})
