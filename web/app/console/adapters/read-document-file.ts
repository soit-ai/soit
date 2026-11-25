/**
 * Read a JSON or YAML document a user picked from disk.
 *
 * The YAML parser is loaded on first use, so it never reaches the console's
 * initial JavaScript: importing a file is rare.
 */
export async function readDocumentFile(file: File): Promise<Record<string, unknown>> {
  const text = await file.text()
  const trimmed = text.trimStart()
  let parsed: unknown
  if (trimmed.startsWith('{')) {
    parsed = JSON.parse(text)
  } else {
    const { parse } = await import('yaml')
    parsed = parse(text)
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('The file does not hold a single document object')
  }
  return parsed as Record<string, unknown>
}
