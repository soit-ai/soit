import { useEffect, useRef, useState } from 'react'

import { Command } from 'cmdk'

import { IconSearch } from '@/console/components/icons'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { searchWorkspace, type GlobalSearchResult } from '@/services/global-search-service'

import { useConsoleNavigate } from './use-console-navigate'

/**
 * ⌘K palette (prototype .cmdk). Rendered as a fixed overlay inside
 * .console-root on purpose: a portalled dialog would land on <body>,
 * outside the console's scoped theme and type tokens.
 */
const JUMP_TARGETS: { labelKey: TranslationKey; to: string }[] = [
  { labelKey: 'console.nav.overview', to: '/v2' },
  { labelKey: 'console.nav.chat', to: '/v2/chat' },
  { labelKey: 'console.nav.agents', to: '/v2/build/agents' },
  { labelKey: 'console.nav.workflows', to: '/v2/build/workflows' },
  { labelKey: 'console.nav.knowledge', to: '/v2/build/knowledge' },
  { labelKey: 'console.nav.plugins', to: '/v2/build/plugins' },
  { labelKey: 'console.nav.models', to: '/v2/build/models' },
  { labelKey: 'console.nav.tasks', to: '/v2/execute/tasks' },
  { labelKey: 'console.nav.schedules', to: '/v2/execute/schedules' },
  { labelKey: 'console.nav.events', to: '/v2/execute/events' },
  { labelKey: 'console.nav.runs', to: '/v2/observe/runs' },
  { labelKey: 'console.nav.traces', to: '/v2/observe/traces' },
  { labelKey: 'console.nav.approvals', to: '/v2/govern/approvals' },
  { labelKey: 'console.nav.policies', to: '/v2/govern/policies' },
  { labelKey: 'console.nav.audit', to: '/v2/govern/audit' },
  { labelKey: 'console.nav.secrets', to: '/v2/govern/secrets' },
  { labelKey: 'console.nav.settings', to: '/v2/settings' },
]

interface CommandPaletteProps {
  open: boolean
  onClose: () => void
}

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<GlobalSearchResult[]>([])
  const debounceTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => {
    if (!open) {
      setQuery('')
      setResults([])
    }
  }, [open])

  useEffect(() => {
    clearTimeout(debounceTimer.current)
    const trimmed = query.trim()
    if (trimmed.length < 2) {
      setResults([])
      return
    }
    debounceTimer.current = setTimeout(async () => {
      try {
        const response = await searchWorkspace(trimmed, { limit: 6 })
        setResults(response.items)
      } catch {
        setResults([])
      }
    }, 250)
    return () => clearTimeout(debounceTimer.current)
  }, [query])

  if (!open) return null

  const go = (to: string) => {
    onClose()
    navigate(to)
  }

  return (
    <div className="cmdk open" onClick={onClose}>
      <div className="cmdk-box" onClick={(event) => event.stopPropagation()}>
        <Command shouldFilter={results.length === 0}>
          <div className="cmdk-in">
            <IconSearch style={{ color: 'var(--faint)' }} />
            <Command.Input
              autoFocus
              value={query}
              onValueChange={setQuery}
              placeholder={t('console.shell.searchPlaceholder')}
              onKeyDown={(event) => {
                if (event.key === 'Escape') onClose()
              }}
            />
          </div>
          <Command.List className="cmdk-list">
            <Command.Empty>
              <div className="empty-note">{t('console.shell.searchEmpty')}</div>
            </Command.Empty>
            {results.length > 0 && (
              <Command.Group heading={<div className="cap">{t('console.shell.results')}</div>}>
                {results.map((item) => (
                  <Command.Item
                    key={`${item.kind}-${item.id}`}
                    value={`${item.kind}-${item.id}`}
                    onSelect={() => go(item.url)}
                  >
                    <span className="mono dimmer">{item.kind}</span>
                    <span className="truncate">{item.title}</span>
                    {item.subtitle && <span className="dim truncate">{item.subtitle}</span>}
                  </Command.Item>
                ))}
              </Command.Group>
            )}
            <Command.Group heading={<div className="cap">{t('console.shell.jumpTo')}</div>}>
              {JUMP_TARGETS.map((target) => (
                <Command.Item
                  key={target.to}
                  value={t(target.labelKey)}
                  onSelect={() => go(target.to)}
                >
                  {t(target.labelKey)}
                  <kbd>↵</kbd>
                </Command.Item>
              ))}
            </Command.Group>
          </Command.List>
          <div className="cmdk-foot">
            <span>↑↓ navigate</span>
            <span>↵ open</span>
            <span>esc close</span>
          </div>
        </Command>
      </div>
    </div>
  )
}
