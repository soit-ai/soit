import { expect, test } from '@playwright/test'

import {
  authHeaders,
  getData,
  publishAgent,
  signUpFreshWorkspace,
  webBaseURL,
} from './helpers'

/**
 * Chat is the surface most users touch first, and it exercises the durable
 * response path end to end: the composer posts to `/responses`, the stream is
 * AG-UI over SSE, and the thread ledger is what the UI re-renders from. A
 * mocked backend would prove none of that survives a real PostgreSQL round
 * trip.
 */
test('a chat message streams back and survives a reload from the thread ledger', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const agentId = await publishAgent(request, headers, suffix)

  await page.goto(`/chat/${agentId}`, { waitUntil: 'domcontentloaded' })

  // The deterministic test model echoes the last user message, so a unique
  // marker distinguishes the assistant's reply from any static copy.
  const marker = `Prove the chat surface reaches the real runtime ${suffix}`
  const composer = page.getByPlaceholder('Send a message to the current agent...')
  await composer.fill(marker)

  const responsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === 'POST' &&
      new URL(response.url()).pathname.endsWith('/api/v1/responses'),
  )
  await page.getByRole('button', { name: 'Send message' }).click()
  const transport = await responsePromise
  // The transport is an AG-UI SSE stream, not a JSON envelope; its status is
  // all this layer can assert without consuming the page's own stream.
  expect(transport.ok()).toBeTruthy()

  // The echo must appear beyond the user's own bubble — as the assistant's
  // streamed reply (the sidebar also titles the thread with it, so the exact
  // count is presentation detail; fewer than two means nothing came back).
  await expect
    .poll(() => page.getByText(marker).count(), { timeout: 30_000 })
    .toBeGreaterThanOrEqual(2)

  // The conversation must come from the thread ledger, not client state.
  const threads = await getData<{ items: Array<{ id: string; agent_id: string | null }> }>(
    request,
    `/threads?agent_id=${agentId}&page_size=10`,
    headers,
  )
  expect(threads.items.length).toBe(1)
  const threadId = threads.items[0].id

  const detail = await getData<{
    messages: Array<{ role: string; content: string | null }>
  }>(request, `/threads/${threadId}`, headers)
  const ledgerRoles = detail.messages
    .filter((message) => (message.content || '').includes(marker))
    .map((message) => message.role)
  expect(ledgerRoles).toContain('user')
  expect(ledgerRoles).toContain('assistant')

  await page.goto(`/chat/${agentId}/${threadId}`, { waitUntil: 'domcontentloaded' })
  await expect
    .poll(() => page.getByText(marker).count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(2)

  // The turn must have left run evidence, or Observe has nothing to audit.
  const runs = await getData<{ items: Array<{ id: string; status: string }> }>(
    request,
    '/runs?page_size=20',
    headers,
  )
  expect(runs.items.length).toBeGreaterThan(0)
  expect(runs.items.some((run) => run.status === 'succeeded')).toBe(true)

  // Guard against silently landing on an error page that swallowed the URL.
  expect(page.url().startsWith(webBaseURL)).toBe(true)
})
