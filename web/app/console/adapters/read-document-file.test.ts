import { describe, expect, it } from 'vitest'

import { readDocumentFile } from './read-document-file'

const file = (name: string, text: string) => new File([text], name)

describe('readDocumentFile', () => {
  it('reads the YAML `soit agent export` writes', async () => {
    const document = await readDocumentFile(
      file('triage.yaml', 'soit: agent/v1\nagent:\n  name: Triage\n  tags: [support]\n'),
    )
    expect(document).toEqual({ soit: 'agent/v1', agent: { name: 'Triage', tags: ['support'] } })
  })

  it('reads JSON', async () => {
    expect(await readDocumentFile(file('flow.json', '{"name": "Flow"}'))).toEqual({ name: 'Flow' })
  })

  it('refuses anything but a single object', async () => {
    await expect(readDocumentFile(file('list.yaml', '- a\n- b\n'))).rejects.toThrow()
    await expect(readDocumentFile(file('scalar.yaml', 'just text'))).rejects.toThrow()
    await expect(readDocumentFile(file('broken.json', '{"name":'))).rejects.toThrow()
  })
})
