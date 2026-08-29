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

function ThemeToggleRailButton() {
  const { t } = useTranslation()
  const { theme, toggleTheme } = useConsoleTheme()

  return (
    <button
      type="button"
      title={t('console.shell.toggleTheme')}
      aria-label={t('console.shell.toggleTheme')}
      onClick={toggleTheme}
      className="grid h-8 w-9 cursor-pointer place-items-center rounded-[9px] text-muted-foreground transition-colors hover:bg-hover-wash hover:text-foreground"
    >
      {theme === 'dark' ? <IconSun /> : <IconMoon />}
    </button>
  )
}

const PILLAR_ICON: Record<ConsolePillar, React.ComponentType<{ className?: string }>> = {
  overview: IconOverview,
  chat: IconChat,
  build: IconBuild,
  execute: IconExecute,
  observe: IconObserve,
  govern: IconGovern,
  settings: IconSettings,
}

export function IconRail() {
  const { t } = useTranslation()
  const location = useLocation()
  const navigate = useConsoleNavigate()
  const currentUser = useUserStore((state) => state.currentUser)
  const activePillar = pillarForPathname(location.pathname).pillar

  const initials = (currentUser?.name || currentUser?.email || 'S')
    .split(/[\s@._-]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part: string) => part[0]?.toUpperCase())
    .join('')

  const pillars = PANEL_CONFIG.filter((entry) => entry.pillar !== 'settings')
  const settingsPillar = PANEL_CONFIG.find((entry) => entry.pillar === 'settings')

  return (
    <nav className="flex w-[58px] flex-none flex-col items-center gap-1 border-r border-border bg-shell py-2.5 pb-3">
      <NavLink
        to="/v2"
        className="mb-2 grid size-[34px] place-items-center rounded-lg border border-border bg-panel transition-shadow hover:ring-[3px] hover:ring-ring"
        aria-label="SOIT"
      >
        <IconLogo size={24} />
      </NavLink>

      {pillars.map((entry) => {
        const Icon = PILLAR_ICON[entry.pillar]
        const active = activePillar === entry.pillar
        const hint = entry.hintKey
          ? `${t(entry.labelKey)} — ${t(entry.hintKey)}`
          : t(entry.labelKey)

        return (
          <button
            key={entry.pillar}
            type="button"
            title={hint}
            aria-label={hint}
            aria-current={active ? 'page' : undefined}
            onClick={() => navigate(entry.to)}
            className={cn(
              'relative grid size-10 cursor-pointer place-items-center rounded-[9px] text-muted-foreground transition-colors',
              active
                ? 'bg-primary-subtle text-primary-subtle-foreground before:absolute before:-left-[9px] before:bottom-2.5 before:top-2.5 before:w-[3px] before:rounded-r-[3px] before:bg-primary'
                : 'hover:bg-hover-wash hover:text-foreground',
            )}
          >
            <Icon />
          </button>
        )
      })}

      <span className="flex-1" />

      <button
        type="button"
        title={t('console.shell.feedback')}
        aria-label={t('console.shell.feedback')}
        onClick={() => navigate('/feedback')}
        className="grid h-8 w-9 cursor-pointer place-items-center rounded-[9px] text-muted-foreground transition-colors hover:bg-hover-wash hover:text-foreground"
      >
        <IconFeedback />
      </button>

      <a
        href="https://github.com/soit-ai/soit"
        target="_blank"
        rel="noreferrer"
        title={t('console.shell.docs')}
        className="grid h-8 w-9 place-items-center rounded-[9px] text-muted-foreground transition-colors hover:bg-hover-wash hover:text-foreground"
      >
        <IconDocs />
      </a>

      <ThemeToggleRailButton />

      {settingsPillar && (
        <button
          type="button"
          title={t('console.nav.settings')}
          aria-label={t('console.nav.settings')}
          aria-current={activePillar === 'settings' ? 'page' : undefined}
          onClick={() => navigate(settingsPillar.to)}
          className={cn(
            'relative grid size-10 cursor-pointer place-items-center rounded-[9px] text-muted-foreground transition-colors',
            activePillar === 'settings'
              ? 'bg-primary-subtle text-primary-subtle-foreground before:absolute before:-left-[9px] before:bottom-2.5 before:top-2.5 before:w-[3px] before:rounded-r-[3px] before:bg-primary'
              : 'hover:bg-hover-wash hover:text-foreground',
          )}
        >
          <IconSettings />
        </button>
      )}

      <span
        title={currentUser?.name || undefined}
        className="mt-1 grid size-[26px] flex-none place-items-center rounded-full bg-primary-subtle text-[11px] font-semibold text-primary-subtle-foreground"
      >
        {initials || 'S'}
      </span>
    </nav>
  )
}
