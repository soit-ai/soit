import { readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const here = dirname(fileURLToPath(import.meta.url))

/** Every dotted key path in a nested translation object. */
function keyPaths(value: unknown, prefix = ''): string[] {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return [prefix]
  return Object.entries(value as Record<string, unknown>).flatMap(([key, child]) =>
    keyPaths(child, prefix ? `${prefix}.${key}` : key),
  )
}

const namespaces = readdirSync(join(here, 'en-US'))
  .filter((file) => file.endsWith('.ts'))
  .map((file) => file.replace(/\.ts$/, ''))

// Keys the English copy has and the Chinese copy may lack, each for a reason.
const ALLOWED_MISSING: Record<string, string[]> = {}

describe('zh-CN has every key en-US has', () => {
  it.each(namespaces)('%s', async (namespace) => {
    const english = (await import(`./en-US/${namespace}.ts`)).default
    const chinese = (await import(`./zh-CN/${namespace}.ts`)).default
    const present = new Set(keyPaths(chinese))
    const missing = keyPaths(english).filter(
      (key) => !present.has(key) && !(ALLOWED_MISSING[namespace] || []).includes(key),
    )
    expect(missing).toEqual([])
  })
})
