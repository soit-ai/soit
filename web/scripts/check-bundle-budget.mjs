import { existsSync, readFileSync, readdirSync, statSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const scriptDirectory = dirname(fileURLToPath(import.meta.url))
const webRoot = resolve(scriptDirectory, '..')
const clientBuildDirectory = join(webRoot, 'build', 'client')
const assetDirectory = join(clientBuildDirectory, 'assets')
const indexPath = join(clientBuildDirectory, 'index.html')
const configPath = join(webRoot, 'bundle-budget.json')

for (const requiredPath of [indexPath, assetDirectory, configPath]) {
  if (!existsSync(requiredPath)) {
    console.error(`Bundle budget input is missing: ${requiredPath}`)
    console.error('Run npm run build before npm run budget.')
    process.exit(1)
  }
}

const config = JSON.parse(readFileSync(configPath, 'utf8'))
const indexHtml = readFileSync(indexPath, 'utf8')
const initialAssetUrls = [
  ...new Set(indexHtml.match(/\/assets\/[^"']+\.js/g) || []),
]

if (initialAssetUrls.length === 0) {
  console.error('No initial JavaScript assets were found in build/client/index.html.')
  process.exit(1)
}

const initialAssets = initialAssetUrls.map((assetUrl) => {
  const path = join(clientBuildDirectory, assetUrl.replace(/^\//, ''))
  if (!existsSync(path)) {
    console.error(`Initial JavaScript asset is missing: ${path}`)
    process.exit(1)
  }
  return { assetUrl, bytes: statSync(path).size }
})
const initialJavaScriptBytes = initialAssets.reduce((total, asset) => total + asset.bytes, 0)

const chunks = readdirSync(assetDirectory)
  .filter((name) => name.endsWith('.js'))
  .map((name) => ({ name, bytes: statSync(join(assetDirectory, name)).size }))
  .sort((left, right) => right.bytes - left.bytes)

if (chunks.length === 0) {
  console.error('No JavaScript chunks were found in build/client/assets.')
  process.exit(1)
}

const largestChunk = chunks[0]
const initialLimit = Number(config.initialJavaScriptLimitBytes)
const maximumChunkLimit = Number(config.maximumChunkLimitBytes)

if (
  !Number.isFinite(initialLimit) ||
  initialLimit <= 0 ||
  !Number.isFinite(maximumChunkLimit) ||
  maximumChunkLimit <= 0
) {
  console.error('Bundle budget limits must be positive finite numbers.')
  process.exit(1)
}

console.log(`Initial JavaScript: ${initialJavaScriptBytes} bytes (limit: ${initialLimit})`)
console.log(`Largest chunk: ${largestChunk.name} at ${largestChunk.bytes} bytes (limit: ${maximumChunkLimit})`)

const violations = []
if (initialJavaScriptBytes > initialLimit) {
  violations.push(`Initial JavaScript exceeds the limit by ${initialJavaScriptBytes - initialLimit} bytes.`)
}
if (largestChunk.bytes > maximumChunkLimit) {
  violations.push(`Largest chunk exceeds the limit by ${largestChunk.bytes - maximumChunkLimit} bytes.`)
}

if (violations.length > 0) {
  for (const violation of violations) console.error(violation)
  process.exit(1)
}

console.log('Bundle budget passed.')
