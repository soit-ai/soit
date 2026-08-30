import type { Page } from '@playwright/test'

export async function mockShellApi(page: Page) {
  // Registered first so every later route wins over it: Playwright matches the
  // most recently registered handler.
  //
  // The built client reads VITE_BASE_URL, which points at a real API port. With
  // nothing listening there an unmocked call failed instantly, which is the
  // behaviour every spec was written against; start a real backend on that port
  // and the same calls start returning live data, and the suite quietly tests a
  // different application. Aborting here makes the run hermetic either way.
  await page.route('**/api/v1/**', (route) => route.abort())

  await page.route('**/api/v1/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: { count: 0 } }),
    })
  })

  await page.route('**/api/v1/notifications**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
          items: [],
          page_size: 20,
          next_page_token: null,
        },
      }),
    })
  })

  // Answers with a list, because the endpoint does. The catch-all below
  // answers with a page, and a page is not something callers can map over.
  await page.route('**/api/v1/agents/drafts/awaiting-review**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: [] }),
    })
  })

  await page.route('**/api/v1/agents**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
      body: JSON.stringify({ success: true, code: 'OK', message: 'OK', data: {
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
