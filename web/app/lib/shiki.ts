import { createHighlighterCore, type HighlighterCore } from 'shiki/core'
import { createJavaScriptRegexEngine } from 'shiki/engine/javascript'

export type SupportedShikiLanguage =
  | 'bash'
  | 'css'
  | 'html'
  | 'javascript'
  | 'json'
  | 'jsx'
  | 'markdown'
  | 'python'
  | 'shellscript'
  | 'typescript'
  | 'tsx'

type SupportedShikiTheme = 'github-dark' | 'github-light'
type ShikiModule = { default: any }

const languageLoaders: Record<SupportedShikiLanguage, () => Promise<ShikiModule>> = {
  bash: () => import('@shikijs/langs/bash'),
  css: () => import('@shikijs/langs/css'),
  html: () => import('@shikijs/langs/html'),
  javascript: () => import('@shikijs/langs/javascript'),
  json: () => import('@shikijs/langs/json'),
  jsx: () => import('@shikijs/langs/jsx'),
  markdown: () => import('@shikijs/langs/markdown'),
  python: () => import('@shikijs/langs/python'),
  shellscript: () => import('@shikijs/langs/shellscript'),
  typescript: () => import('@shikijs/langs/typescript'),
  tsx: () => import('@shikijs/langs/tsx'),
}

const themeLoaders: Record<SupportedShikiTheme, () => Promise<ShikiModule>> = {
  'github-dark': () => import('@shikijs/themes/github-dark'),
  'github-light': () => import('@shikijs/themes/github-light'),
}

const loadedLanguages = new Set<SupportedShikiLanguage>()
let highlighterPromise: Promise<HighlighterCore> | null = null

export function normalizeShikiLanguage(language?: string): SupportedShikiLanguage | null {
  const normalized = (language || 'text').trim().toLowerCase()
  if (!normalized || normalized === 'text' || normalized === 'plain' || normalized === 'plaintext') {
    return null
  }

  const aliases: Record<string, SupportedShikiLanguage> = {
    bash: 'bash',
    css: 'css',
    html: 'html',
    javascript: 'javascript',
    js: 'javascript',
    json: 'json',
    jsx: 'jsx',
    markdown: 'markdown',
    md: 'markdown',
    py: 'python',
    python: 'python',
    sh: 'shellscript',
    shell: 'shellscript',
    shellscript: 'shellscript',
    ts: 'typescript',
    tsx: 'tsx',
    typescript: 'typescript',
  }

  return aliases[normalized] ?? null
}

export function plainCodeToHtml(code: string) {
  return `<pre><code>${escapeHtml(code)}</code></pre>`
}

export async function highlightCodeToHtml({
  code,
  language,
  theme,
  showLineNumbers,
}: {
  code: string
  language?: string
  theme: SupportedShikiTheme
  showLineNumbers?: boolean
}) {
  const normalizedLanguage = normalizeShikiLanguage(language)
  if (!normalizedLanguage) {
    return plainCodeToHtml(code)
  }

  const highlighter = await getHighlighter()
  await loadLanguage(highlighter, normalizedLanguage)

  return highlighter.codeToHtml(code, {
    lang: normalizedLanguage,
    theme,
    transformers: showLineNumbers
      ? [
        {
          line(element, index) {
            element.properties.class = 'line'
            element.properties['line-number'] = String(index + 1)
            return element
          },
        },
      ]
      : undefined,
  })
}

async function getHighlighter() {
  if (!highlighterPromise) {
    highlighterPromise = Promise.all([themeLoaders['github-dark'](), themeLoaders['github-light']()]).then(
      ([githubDark, githubLight]) =>
        createHighlighterCore({
          engine: createJavaScriptRegexEngine(),
          langs: [],
          themes: [githubDark.default, githubLight.default],
        })
    )
  }

  return highlighterPromise
}

async function loadLanguage(highlighter: HighlighterCore, language: SupportedShikiLanguage) {
  if (loadedLanguages.has(language)) {
    return
  }

  const languageModule = await languageLoaders[language]()
  await highlighter.loadLanguage(languageModule.default)
  loadedLanguages.add(language)
}

function escapeHtml(value: string) {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}
