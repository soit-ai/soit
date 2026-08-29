import { useLocation } from 'react-router'

import {
  IconBell,
  IconChevronRight,
  IconMoon,
  IconSearch,
  IconSun,
} from '@/console/components/icons'
import { useTranslation } from '@/i18n'
import { useUserStore } from '@/stores/user'

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
  const currentUser = useUserStore((state) => state.currentUser)
  const config = pillarForPathname(location.pathname)

  const initials = (currentUser?.name || currentUser?.email || 'S')
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part: string) => part[0]?.toUpperCase())
    .join('')

  return (
    <header className="topbar">
      <button
        type="button"
        className="subnav-open"
        onClick={onExpandPanel}
        title={t('console.shell.expandPanel')}
        aria-hidden={!panelCollapsed}
        tabIndex={panelCollapsed ? 0 : -1}
      >
        <IconChevronRight />
      </button>

      <div className="crumb">
        <b>{t(config.labelKey)}</b>
      </div>

      <div className="top-actions">
        <button type="button" className="searchbtn" onClick={onOpenSearch}>
          <IconSearch />
          {t('console.shell.searchPlaceholder')}
          <kbd>⌘K</kbd>
        </button>

        <button
          type="button"
          className="iconbtn"
          onClick={toggleTheme}
          title={t('console.shell.toggleTheme')}
        >
          {theme === 'dark' ? <IconSun /> : <IconMoon />}
        </button>

        <button type="button" className="iconbtn" title={t('console.shell.notifications')}>
          <IconBell />
        </button>

        <span
          className="avatar"
          style={{ width: 28, height: 28 }}
          title={currentUser?.name || undefined}
        >
          {initials || 'S'}
        </span>
      </div>
    </header>
  )
}
