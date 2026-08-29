import { Bell, Moon, PanelLeftOpen, Sun } from 'lucide-react'
import { useLocation } from 'react-router'

import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

import { useConsoleTheme } from './console-theme'
import { pillarForPathname } from './panel-config'

interface TopbarProps {
  panelCollapsed: boolean
  onExpandPanel: () => void
  onOpenSearch: () => void
}

export function Topbar({ panelCollapsed, onExpandPanel, onOpenSearch }: TopbarProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const { theme, toggleTheme } = useConsoleTheme()
  const config = pillarForPathname(location.pathname)

  return (
    <header className="flex h-[52px] flex-none items-center gap-3 border-b border-border bg-background px-5">
      {panelCollapsed && (
        <button
          type="button"
          onClick={onExpandPanel}
          title={t('console.shell.expandPanel')}
          className="grid size-[26px] cursor-pointer place-items-center rounded-[7px] border border-border bg-panel text-muted-foreground hover:border-border-strong hover:text-foreground"
        >
          <PanelLeftOpen className="size-3.5" />
        </button>
      )}

      <div className="flex min-w-0 items-center gap-2 text-[13px]">
        <b className="font-semibold">{t(config.labelKey)}</b>
      </div>

      <span className="ml-auto flex items-center gap-2">
        <button
          type="button"
          onClick={onOpenSearch}
          className="flex h-[30px] w-[230px] cursor-pointer items-center gap-2 rounded-[7px] border border-border bg-panel px-2.5 text-xs text-muted-foreground/70 hover:border-border-strong"
        >
          {t('console.shell.searchPlaceholder')}
          <kbd className="ml-auto rounded-[4px] border border-border bg-background px-1.5 py-px font-mono text-[10px] text-muted-foreground">
            ⌘K
          </kbd>
        </button>

        <button
          type="button"
          onClick={toggleTheme}
          title={t('console.shell.toggleTheme')}
          className="grid size-[30px] cursor-pointer place-items-center rounded-[7px] text-muted-foreground hover:bg-hover-wash hover:text-foreground"
        >
          {theme === 'dark' ? <Sun className="size-4" /> : <Moon className="size-4" />}
        </button>

        <button
          type="button"
          title={t('console.shell.notifications')}
          className={cn(
            'relative grid size-[30px] cursor-pointer place-items-center rounded-[7px] text-muted-foreground',
            'hover:bg-hover-wash hover:text-foreground',
          )}
        >
          <Bell className="size-4" />
        </button>
      </span>
    </header>
  )
}
