import {
  Activity,
  Blocks,
  LayoutDashboard,
  ListChecks,
  MessageSquareDot,
  MessagesSquare,
  Settings,
  ShieldCheck,
} from 'lucide-react'
import { NavLink, useLocation } from 'react-router'

import logoIcon from '@/assets/logo-m.png'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { useUserStore } from '@/stores/user'

import { PANEL_CONFIG, pillarForPathname, type ConsolePillar } from './panel-config'
import { useConsoleNavigate } from './use-console-navigate'

const PILLAR_ICON: Record<ConsolePillar, React.ComponentType<{ className?: string }>> = {
  overview: LayoutDashboard,
  chat: MessagesSquare,
  build: Blocks,
  execute: ListChecks,
  observe: Activity,
  govern: ShieldCheck,
  settings: Settings,
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
        <img src={logoIcon} alt="SOIT" className="size-6" />
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
            <Icon className="size-[18px]" />
          </button>
        )
      })}

      <span className="flex-1" />

      <a
        href="https://github.com/soit-ai/soit"
        target="_blank"
        rel="noreferrer"
        title={t('console.shell.docs')}
        className="grid h-8 w-9 place-items-center rounded-[9px] text-muted-foreground transition-colors hover:bg-hover-wash hover:text-foreground"
      >
        <MessageSquareDot className="size-4" />
      </a>

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
          <Settings className="size-[18px]" />
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
