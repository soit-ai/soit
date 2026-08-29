import { readFileSync, readdirSync } from 'node:fs'

import { describe, expect, it } from 'vitest'

/**
 * Console (v2) design-system contract, ported from soit-site's test and
 * scoped to app/console/**. Guards the P0 foundation: token-only styling,
 * status hues reserved for state, the engineering type stack and the flat
 * v13 button spec. CI runs this via `npm test`.
 */

function read(path: string) {
  return readFileSync(path, 'utf-8')
}

function readConsoleFiles(extensions = /\.(ts|tsx)$/) {
  const files: { file: string; content: string }[] = []

  function walk(dir: string) {
    for (const entry of readdirSync(dir, { withFileTypes: true })) {
      const path = `${dir}/${entry.name}`
      if (entry.isDirectory()) {
        walk(path)
      } else if (extensions.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) {
        files.push({ file: path, content: read(path) })
      }
    }
  }

  walk('app/console')
  return files
}

describe('console v2 design system', () => {
  it('runs Tailwind 4 through the Vite plugin with the shared token baseline', () => {
    expect(read('package.json')).toContain('@tailwindcss/vite')
    expect(read('vite.config.ts')).toContain('tailwindcss()')
    expect(read('app/app.css')).toContain('@import "tailwindcss"')
  })

  it('keeps the shared token baseline intact and maps the console increments', () => {
    const css = read('app/app.css')

    // Existing ramps stay the source of truth.
    expect(css).toContain('--brand-blue-600: #0073d5')
    expect(css).toContain('--primary: var(--brand-blue-600)')
    expect(css).toContain('--contrast: var(--brand-blue-900)')

    // Console increments are registered as utilities.
    expect(css).toContain('--color-primary-press: var(--primary-press)')
    expect(css).toContain('--color-border-strong: var(--border-strong)')
    expect(css).toContain('--color-raised: var(--raised)')
    expect(css).toContain('--color-hover-wash: var(--hover-wash)')

    // P0 cleanups hold: no raw-palette remnant, exactly one dark variant
    // declaration, and it is the ancestor-class form container theming needs.
    expect(css).not.toContain('bg-white dark:bg-gray-950')
    expect(css.match(/@custom-variant dark/g)).toHaveLength(1)
    expect(css).toContain('@custom-variant dark (&:is(.dark *))')
  })

  it('defines the console token increments on the scoped root', () => {
    const css = read('app/console/styles/console.css')

    expect(css).toContain('.console-root')
    expect(css).toContain("'IBM Plex Sans'")
    expect(css).toContain("'JetBrains Mono'")
    expect(css).toContain('--primary-press: var(--brand-blue-700)')
    expect(css).toContain('--shadow-1')
    expect(css).toContain('--shadow-2')
    expect(css).toContain('tabular-nums')
    expect(css).toContain('prefers-reduced-motion')

    // Dark values only redefine tokens, still inside the console scope.
    expect(css).toContain('.console-root.dark')
  })

  it('ships the engineering type stack locally and wires it in the shell', () => {
    const packageJson = read('package.json')
    const layout = read('app/console/shell/console-layout.tsx')

    expect(packageJson).toContain('@fontsource/ibm-plex-sans')
    expect(packageJson).toContain('@fontsource/jetbrains-mono')
    expect(layout).toContain("@fontsource/ibm-plex-sans/400.css")
    expect(layout).toContain("@fontsource/ibm-plex-sans/600.css")
    expect(layout).toContain("@fontsource/jetbrains-mono/400.css")
    expect(layout).toContain("@/console/styles/console.css")
  })

  it('serves the console from the application root', () => {
    const routes = read('app/routes.ts')

    expect(routes).toContain("layout('./console/shell/console-layout.tsx'")
    expect(routes).toContain("index('./console/routes/overview.tsx')")
    // The pre-rebuild tree is backed up, not registered as a second app.
    expect(routes).not.toContain("layout('./components/layout/root-layout.tsx'")
    // Renamed paths and the parallel-development prefix keep resolving.
    expect(routes).toContain("route('/v2/*'")
    expect(routes).toContain("route('/workflow'")
  })

  it('themes the console independently, defaulting to dark at container level', () => {
    const theme = read('app/console/shell/console-theme.tsx')
    const layout = read('app/console/shell/console-layout.tsx')

    expect(theme).toContain("'soit-console-theme'")
    expect(theme).toContain("DEFAULT_THEME: ConsoleTheme = 'dark'")
    expect(layout).toContain("theme === 'dark' && 'dark'")
    expect(layout).toContain('console-root')
  })

  it('uses tokens only: no raw hex colours in console components', () => {
    for (const { file, content } of readConsoleFiles(/\.tsx$/)) {
      expect(content, `${file} should not hardcode hex colours`).not.toMatch(
        /#[0-9a-fA-F]{3,8}\b/,
      )
    }
  })

  it('uses tokens only: no raw Tailwind palette classes in the console', () => {
    const rawPalette =
      /(bg|text|border|ring|fill|stroke|from|via|to|outline|decoration|shadow)-(slate|gray|zinc|neutral|stone|red|orange|amber|yellow|lime|green|emerald|teal|cyan|sky|blue|indigo|violet|purple|fuchsia|pink|rose)-[0-9]{2,3}/

    for (const { file, content } of readConsoleFiles()) {
      expect(content, `${file} should style through tokens, not raw palette stops`).not.toMatch(
        rawPalette,
      )
    }
  })

  it('keeps the status vocabulary in one place', () => {
    const statusChip = read('app/console/components/status-chip.tsx')

    expect(statusChip).toContain('CONSOLE_STATUS_TONE')
    expect(statusChip).toContain("'console.status.")

    // Verdicts, run states and release states all resolve through the chip.
    for (const status of ['pass', 'warn', 'block', 'na', 'running', 'failed', 'published', 'rolled_back']) {
      expect(statusChip).toContain(`${status}:`)
    }

    // No second dictionary: outside the chip, console files must not map
    // status names onto colour tones themselves.
    for (const { file, content } of readConsoleFiles(/\.tsx$/)) {
      if (file.endsWith('status-chip.tsx')) continue
      expect(content, `${file} should resolve status colours via StatusChip`).not.toMatch(
        /(pass|failed|blocked)['"]?\s*:\s*['"](bg|text)-(success|danger|warning)/,
      )
    }
  })

  it('keeps categorical identity separate from status', () => {
    const kindChip = read('app/console/components/kind-chip.tsx')

    expect(kindChip).toContain('CONSOLE_KIND_COLOR')
    expect(kindChip).toContain('--cat-')
    // Identity never borrows status tokens.
    expect(kindChip).not.toContain('--success')
    expect(kindChip).not.toContain('--danger')
    expect(kindChip).not.toContain('--warning')
  })

  it('enforces the v13 flat button spec', () => {
    const button = read('app/console/components/button.tsx')

    // The flat spec lives in the ported prototype stylesheet: solid fill,
    // hover one stop darker, no gradient, no shadow.
    const css = read('app/console/styles/console.css')
    expect(css).toContain('.btn.primary:hover{background:var(--primary-press)}')
    expect(css).not.toContain('.btn.primary{background:linear-gradient')

    expect(button).toContain("'btn'")
    expect(button).not.toContain('bg-gradient')
    expect(button).not.toMatch(/\bshadow-(?!none)/)

    // No decorative gradients anywhere in console components.
    for (const { file, content } of readConsoleFiles(/\.tsx$/)) {
      expect(content, `${file} should not use gradient backgrounds`).not.toContain('bg-gradient')
    }
  })

  it('draws shell chrome with the prototype icon set, not a generic library', () => {
    const icons = read('app/console/components/icons.tsx')

    // Traced from the v13 prototype; stroke-based 24x24, currentColor.
    expect(icons).toContain('viewBox="0 0 24 24"')
    expect(icons).toContain('IconLogo')
    expect(icons).toContain('var(--brand-blue-600)')
    expect(icons).toContain('var(--brand-teal-500)')

    for (const file of ['app/console/shell/icon-rail.tsx', 'app/console/shell/topbar.tsx']) {
      const content = read(file)
      expect(content, `${file} should use the prototype icon set`).toContain(
        "@/console/components/icons"
      )
      expect(content, `${file} should not pull shell chrome icons from lucide`).not.toContain(
        'lucide-react'
      )
    }
  })

  it('skins the shared shadcn primitives to prototype forms for reuse', () => {
    const css = read('app/console/styles/console.css').replace(/\r\n/g, '\n')

    // The skin layer restyles by data-slot inside both scopes.
    expect(css).toContain(':is(.console-root,.console-theme) [data-slot="button"]')
    expect(css).toContain('[data-slot="tabs-trigger"][data-active]')
    expect(css).toContain('[data-slot="table-head"]')
    expect(css).toContain('[data-slot="dialog-content"]')

    // Tokens serve both the page scope and portalled overlays.
    expect(css).toContain('.console-root,\n.console-theme {')
    expect(css).toContain('.console-root.dark,\n.console-theme.dark {')

    // The facade wraps every portalled *Content with the overlay scope class.
    const facade = read('app/console/components/ui.tsx')
    expect(facade).toContain("'console-theme'")
    for (const name of [
      'DialogContent',
      'AlertDialogContent',
      'SheetContent',
      'DrawerContent',
      'SelectContent',
      'DropdownMenuContent',
      'PopoverContent',
      'TooltipContent',
    ]) {
      expect(facade, `${name} must re-enter the console scope`).toContain(
        `withConsoleTheme(Shared${name}`
      )
    }
  })

  it('builds the workbench template on the shared Box suite', () => {
    const index = read('app/console/components/index.ts')

    expect(index).toContain("from '@/components/box'")
    expect(index).toContain('BoxDataTable')
    expect(index).toContain('BoxPagination')
    expect(index).toContain('MetricStrip')
    expect(read('app/console/components/workbench.tsx')).toContain('Workbench')
  })

  it('routes all console copy through i18n with the console namespace', () => {
    expect(read('app/i18n/types.ts')).toContain("console: typeof import('./en-US/console').default")
    expect(read('app/i18n/i18next-config.ts')).toContain('console.ts')
    expect(read('app/i18n/en-US/console.ts')).toContain('status')
    expect(read('app/i18n/zh-CN/console.ts')).toContain("from '../en-US/console'")

    // Console screens call t('console.…') rather than hardcoding copy.
    for (const { file, content } of readConsoleFiles(/\.tsx$/)) {
      if (!content.includes('useTranslation')) continue
      expect(content, `${file} should use console.* translation keys`).toMatch(/'console\./)
    }
  })
})
