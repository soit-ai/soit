import { expect, test } from '@playwright/test'

import {
  apiBaseURL,
  authHeaders,
  getData,
  postData,
  publishAgent,
  signUpFreshWorkspace,
} from './helpers'

type ResponseRead = {
  id: string
  run_id: string | null
  status: string
  thread_id: string | null
}

/**
 * `/responses` is the supported agent transport and the path the chat UI uses.
 * It claims an interaction before executing, so the run is recoverable rather
 * than request-local; that only holds against a live server.
 */
test('a response persists its run, events and timeline', async ({ page, request }) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const agentId = await publishAgent(request, headers, suffix)

  const created = await postData<ResponseRead>(request, '/responses', headers, {
    agent_id: agentId,
    input: 'Say something through the supported transport.',
  })

  expect(created.id).toBeTruthy()
  expect(created.run_id).toBeTruthy()
  expect(created.status).toBe('succeeded')

  const timeline = await getData<{
    run_id: string
    items: Array<{ response: ResponseRead; events: unknown[] }>
  }>(request, `/responses/by-run/${created.run_id}`, headers)

  expect(timeline.run_id).toBe(created.run_id)
  expect(timeline.items.length).toBeGreaterThan(0)
  // Events are the replayable record; a response with none would leave the
  // conversation unreconstructable.
  expect(timeline.items[0].events.length).toBeGreaterThan(0)

  const detail = await getData<{ run: { id: string; status: string } }>(
    request,
    `/runs/${created.run_id}`,
    headers,
  )
  expect(detail.run.status).toBe('succeeded')
})

test('the deprecated agent stream route is gone from the supported surface', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)
  const agentId = await publishAgent(request, headers, suffix)

  const response = await request.post(`${apiBaseURL}/agents/${agentId}/stream`, {
    headers,
    data: { input: 'hello' },
  })

  // The route now delegates to the durable worker and refuses when it is off,
  // rather than executing inside the request as it used to. The Deprecation
  // header rides on the stream itself, so it is absent from this refusal; the
  // schema-level deprecation is asserted in the backend entrypoint tests.
  expect(response.status()).toBe(409)
})
