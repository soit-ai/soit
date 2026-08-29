import { NavLink, useLocation } from 'react-router'

import {
  IconBuild,
  IconChat,
  IconDocs,
  IconExecute,
  IconFeedback,
  IconGovern,
  IconLogo,
  IconMoon,
  IconObserve,
  IconOverview,
  IconSettings,
  IconSun,
} from '@/console/components/icons'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { useUserStore } from '@/stores/user'

import { useConsoleTheme } from './console-theme'
import { PANEL_CONFIG, pillarForPathname, type ConsolePillar } from './panel-config'
import { useConsoleNavigate } from './use-console-navigate'

const PILLAR_ICON: Record<ConsolePillar, React.ComponentType<{ className?: string }>> = {
  overview: IconOverview,
  chat: IconChat,
  build: IconBuild,
  execute: IconExecute,
  observe: IconObserve,
  govern: IconGovern,
  settings: IconSettings,
}

function RailPillarButton({ pillar }: { pillar: ConsolePillar }) {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useConsoleNavigate()
  const entry = PANEL_CONFIG.find((item) => item.pillar === pillar)
  if (!entry) return null

  const Icon = PILLAR_ICON[entry.pillar]
  const active = pillarForPathname(location.pathname).pillar === entry.pillar
  const hint = entry.hintKey
    ? `${t(entry.labelKey)} — ${t(entry.hintKey)}`
    : t(entry.labelKey)

  return (
    <button
      type="button"
      className={cn('rail-btn', active && 'active')}
      title={hint}
      aria-label={hint}
      aria-current={active ? 'page' : undefined}
      onClick={() => navigate(entry.to)}
    >
      <Icon />
    </button>
  )
}

export function IconRail() {
  const { t } = useTranslation()
  const navigate = useConsoleNavigate()
  const { theme, toggleTheme } = useConsoleTheme()
  const currentUser = useUserStore((state) => state.currentUser)

  const initials = (currentUser?.name || currentUser?.email || 'S')
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part: string) => part[0]?.toUpperCase())
    .join('')

  return (
    <nav className="navrail">
      <NavLink to="/v2" className="rail-logo" aria-label="SOIT">
        <IconLogo size={24} />
      </NavLink>

      <RailPillarButton pillar="overview" />
      <div className="rail-sep" />
      <RailPillarButton pillar="chat" />
      <RailPillarButton pillar="build" />
      <RailPillarButton pillar="execute" />
      <RailPillarButton pillar="observe" />
      <RailPillarButton pillar="govern" />
      <div className="rail-sep" />
      <RailPillarButton pillar="settings" />

      <div className="grow" />

      <button
        type="button"
        className="rail-btn util"
        title={t('console.shell.feedback')}
        aria-label={t('console.shell.feedback')}
        onClick={() => navigate('/feedback')}
      >
        <IconFeedback />
      </button>
      <a
        href="https://github.com/soit-ai/soit"
        target="_blank"
        rel="noreferrer"
        className="rail-btn util"
        title={t('console.shell.docs')}
      >
        <IconDocs />
      </a>
      <button
        type="button"
        className="rail-btn util"
        title={t('console.shell.toggleTheme')}
        aria-label={t('console.shell.toggleTheme')}
        onClick={toggleTheme}
      >
        {theme === 'dark' ? <IconSun /> : <IconMoon />}
      </button>

      <span className="avatar mt-1" title={currentUser?.name || undefined}>
        {initials || 'S'}
      </span>
    </nav>
  )
}
