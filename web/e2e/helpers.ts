import type { Page } from '@playwright/test'

export async function mockShellApi(page: Page) {
  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          id: 'user-1',
          email: 'user@example.com',
          name: 'Test User',
          tenant_id: 'tenant-1',
          workspace_id: 'workspace-1',
        },
      }),
    })
  })

  await page.route('**/api/v1/notifications/unread-count', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ data: { count: 0 } }),
    })
  })

  await page.route('**/api/v1/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/agents**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          items: [],
          page_size: 100,
          next_page_token: null,
        },
      }),
    })
  })

  await page.route('**/api/v1/responses/*/cancel', async (route) => {
    const parts = new URL(route.request().url()).pathname.split('/')
    const responseId = parts[parts.length - 2] || 'response'
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        data: {
          action: 'cancel',
          response: {
            id: responseId,
            status: 'canceled',
          },
        },
      }),
    })
  })
}
