import { useEffect, useRef, useState } from 'react'

import { CornerDownLeft } from 'lucide-react'

import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { searchWorkspace, type GlobalSearchResult } from '@/services/global-search-service'

import { useConsoleNavigate } from './use-console-navigate'

/**
 * ⌘K palette. Rendered as a fixed overlay inside .console-root on purpose:
 * a portalled dialog would land on <body>, outside the console's scoped
 * theme and type tokens.
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
    <div
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 pt-[14vh] backdrop-blur-[2px]"
      onClick={onClose}
    >
      <div
        className="console-depth w-[520px] overflow-hidden rounded-xl border border-border-strong bg-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <Command shouldFilter={results.length === 0} className="bg-transparent">
          <CommandInput
            autoFocus
            value={query}
            onValueChange={setQuery}
            placeholder={t('console.shell.searchPlaceholder')}
            onKeyDown={(event) => {
              if (event.key === 'Escape') onClose()
            }}
          />
          <CommandList className="max-h-[300px]">
            <CommandEmpty className="py-6 text-center text-xs text-muted-foreground">
              {t('console.shell.searchEmpty')}
            </CommandEmpty>
            {results.length > 0 && (
              <CommandGroup heading={t('console.shell.results')}>
                {results.map((item) => (
                  <CommandItem
                    key={`${item.kind}-${item.id}`}
                    value={`${item.kind}-${item.id}`}
                    onSelect={() => go(item.url)}
                  >
                    <span className="font-mono text-[10.5px] text-muted-foreground/70">{item.kind}</span>
                    <span className="truncate">{item.title}</span>
                    {item.subtitle && (
                      <span className="truncate text-muted-foreground">{item.subtitle}</span>
                    )}
                  </CommandItem>
                ))}
              </CommandGroup>
            )}
            <CommandGroup heading={t('console.shell.jumpTo')}>
              {JUMP_TARGETS.map((target) => (
                <CommandItem key={target.to} value={t(target.labelKey)} onSelect={() => go(target.to)}>
                  {t(target.labelKey)}
                  <CornerDownLeft className="ml-auto size-3 text-muted-foreground/50" />
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </div>
    </div>
  )
}
