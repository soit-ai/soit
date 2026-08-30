import { expect, test } from '@playwright/test'

import { apiBaseURL, authHeaders, getData, postData, signUpFreshWorkspace } from './helpers'

type KnowledgeDocument = { id: string; status: string; doc_key: string }

/**
 * Ingestion runs in a dedicated worker that leases each task. Only a live
 * stack shows the handoff actually completing: the request returns while the
 * document is still queued, and a separate process has to pick it up.
 */
test('an uploaded document is ingested by the worker and becomes queryable', async ({
  page,
  request,
}) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)

  // Binding an embedding model is what gives the base its index. Without one
  // the upload is still accepted and the worker still runs, but every document
  // ends at `failed: Knowledge has no index configured` -- so a base created
  // without it cannot prove ingestion at all.
  const knowledge = await postData<{ id: string }>(request, '/knowledge', headers, {
    name: `E2E knowledge ${suffix}`,
    description: 'Real backend ingestion',
    default_embedding_model_ref: `model:test:embed-${suffix}`,
  })

  const uploaded = await request.post(
    `${apiBaseURL}/knowledge/${knowledge.id}/documents`,
    {
      headers,
      multipart: {
        doc_key: `refund-policy-${suffix}.md`,
        source_kind: 'upload',
        title: 'Refund policy',
        mime_type: 'text/markdown',
        async_ingest: 'true',
        file: {
          name: `refund-policy-${suffix}.md`,
          mimeType: 'text/markdown',
          buffer: Buffer.from(
            '# Refund policy\n\nRefunds are issued within 14 days of purchase.\n',
            'utf-8',
          ),
        },
      },
    },
  )
  const uploadBody = (await uploaded.json()) as { data: KnowledgeDocument; message: string }
  expect(uploaded.ok(), `upload failed: ${uploadBody.message}`).toBeTruthy()
  const documentId = uploadBody.data.id

  // The upload returns before ingestion runs; the worker owns the rest.
  await expect
    .poll(
      async () => {
        const doc = await getData<KnowledgeDocument>(
          request,
          `/knowledge/${knowledge.id}/documents/${documentId}`,
          headers,
        )
        return doc.status
      },
      {
        timeout: 120_000,
        intervals: [1_000],
        message: 'the ingest worker should drive the document to a terminal status',
      },
    )
    // parsing/parsed/chunking/indexing are transient; only these two are final.
    .toMatch(/^(indexed|failed)$/)

  const document = await getData<KnowledgeDocument>(
    request,
    `/knowledge/${knowledge.id}/documents/${documentId}`,
    headers,
  )
  // `indexed` is the only outcome that means ingestion worked. Accepting
  // `failed` as well -- which this once did, to catch a document stuck in
  // "queued" -- let a pipeline that failed every document pass as green.
  expect(document.status).toBe('indexed')
})

test('a knowledge base starts empty and reports no documents', async ({ page, request }) => {
  const { suffix } = await signUpFreshWorkspace(page)
  const headers = await authHeaders(page)

  const knowledge = await postData<{ id: string }>(request, '/knowledge', headers, {
    name: `Empty knowledge ${suffix}`,
    description: 'nothing uploaded',
  })

  const documents = await getData<unknown[]>(
    request,
    `/knowledge/${knowledge.id}/documents`,
    headers,
  )

  expect(documents).toHaveLength(0)
})
