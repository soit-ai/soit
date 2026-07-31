import { expect, test } from '@playwright/test'

import { apiBaseURL, authHeaders, getData, postData, signUpFreshWorkspace } from './helpers'

/**
 * Governance is only real if the API enforces it. These run against the live
 * backend because a mocked response proves the frontend's assumption, not the
 * server's rule.
 */
test('an API key is scoped and expiring, and its scope caps the owner role', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)

  // The signed-up user owns this workspace, so anything the key cannot do is
  // the scope talking, not the role.
  const me = await getData<{ workspace_role: string }>(request, '/me', headers)
  expect(['Owner', 'Admin']).toContain(me.workspace_role)

  const created = await postData<{ api_key: string; item: { scopes: string[]; expires_at: string } }>(
    request,
    '/api-keys',
    headers,
    { name: `read only ${suffix}`, scopes: ['read'], expires_in_days: 30 },
  )
  expect(created.item.scopes).toEqual(['read'])
  expect(created.item.expires_at).toBeTruthy()

  const keyHeaders = {
    'X-API-Key': created.api_key,
    'X-Workspace-Id': headers['X-Workspace-Id'],
  }

  const readResponse = await request.get(`${apiBaseURL}/agents?page_size=5`, {
    headers: keyHeaders,
  })
  expect(readResponse.ok(), 'a read-scoped key must still read').toBeTruthy()

  const writeResponse = await request.post(`${apiBaseURL}/agents`, {
    headers: keyHeaders,
    data: { name: `blocked ${suffix}`, description: 'should not be created' },
  })
  // A leaked read key must not be able to create anything, however privileged
  // its owner is.
  expect(writeResponse.status()).toBe(403)
})

test('creating an API key without a scope or lifetime is rejected', async ({ page, request }) => {
  await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)

  const noScope = await request.post(`${apiBaseURL}/api-keys`, {
    headers,
    data: { name: 'no scope', scopes: [], expires_in_days: 30 },
  })
  const noExpiry = await request.post(`${apiBaseURL}/api-keys`, {
    headers,
    data: { name: 'no expiry', scopes: ['read'], expires_in_days: 0 },
  })
  const unknownScope = await request.post(`${apiBaseURL}/api-keys`, {
    headers,
    data: { name: 'bad scope', scopes: ['superuser'], expires_in_days: 30 },
  })

  // A key that inherits everything and never expires is what this replaced.
  // The API maps request validation failures to 400.
  expect(noScope.status()).toBe(400)
  expect(noExpiry.status()).toBe(400)
  expect(unknownScope.status()).toBe(400)
})

test('an unauthenticated caller reaches nothing', async ({ request }) => {
  const response = await request.get(`${apiBaseURL}/agents`)

  expect([401, 403]).toContain(response.status())
})
