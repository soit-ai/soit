import { expect, test } from '@playwright/test'

import {
  authHeaders,
  getData,
  postData,
  publishAgent,
  signUpFreshWorkspace,
} from './helpers'

/**
 * Observe is where SOIT's claim to be auditable is either true or not. These
 * assertions go against a real PostgreSQL: a mocked run would prove only that
 * the component renders whatever it is handed.
 */
test('an executed agent leaves queryable run evidence', async ({ page, request }) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const agentId = await publishAgent(request, headers, suffix)

  const run = await postData<{ run_id: string; output: string }>(
    request,
    `/agents/${agentId}/execute`,
    headers,
    { input: 'Produce evidence for the observe journey.' },
  )
  expect(run.run_id).toBeTruthy()

  const detail = await getData<{
    run: { id: string; status: string; mode: string; sandbox?: boolean }
    steps: unknown[]
  }>(request, `/runs/${run.run_id}`, headers)

  expect(detail.run.id).toBe(run.run_id)
  expect(detail.run.status).toBe('succeeded')
  // Ordinary product traffic must never be marked as a rehearsal, or real
  // spend would be excluded from the workspace's cost.
  expect(detail.run.sandbox ?? false).toBe(false)
  expect(Array.isArray(detail.steps)).toBe(true)
  expect(detail.steps.length).toBeGreaterThan(0)

  const listed = await getData<{ items: Array<{ id: string }> }>(
    request,
    '/runs?page_size=20',
    headers,
  )
  expect(listed.items.some((item) => item.id === run.run_id)).toBe(true)

  await page.goto(`/observe/runs/${run.run_id}`, { waitUntil: 'domcontentloaded' })
  await expect(page.getByText('Step ledger', { exact: true })).toBeVisible()
  await expect(page.getByText('Cost breakdown', { exact: true })).toBeVisible()
})

test('the dead letter view answers on an empty workspace', async ({ page, request }) => {
  await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)

  const letters = await getData<unknown[]>(request, '/observe/dead-letters', headers)

  // A workspace that has failed nothing must report nothing, rather than
  // erroring because a source could not be read.
  expect(Array.isArray(letters)).toBe(true)
  expect(letters).toHaveLength(0)
})
