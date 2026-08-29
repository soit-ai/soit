import { PanelLeftClose } from 'lucide-react'
import { NavLink, useLocation, useSearchParams } from 'react-router'

import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

import { pillarForPathname } from './panel-config'

interface ContextPanelProps {
  onCollapse: () => void
}

/**
 * The 230px contextual panel: declarative sections from panel-config for the
 * active pillar. Counts, saved views, recents and attention rows join the
 * config as their backing services land phase by phase.
 */
export function ContextPanel({ onCollapse }: ContextPanelProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const config = pillarForPathname(location.pathname)

  // Preserve the embed flag on declarative links (use-navigate does this for
  // imperative navigation; NavLink needs it appended explicitly).
  const withNosider = (to: string) =>
    searchParams.get('nosider') ? `${to}${to.includes('?') ? '&' : '?'}nosider=true` : to

  return (
    <aside className="flex w-[230px] min-w-0 flex-none flex-col border-r border-border bg-shell">
      <div className="flex items-center gap-2 border-b border-border px-3 py-3">
        <span className="min-w-0">
          <b className="block text-xs font-semibold">{t(config.labelKey)}</b>
          {config.hintKey && (
            <span className="block truncate font-mono text-[9.5px] text-muted-foreground/70">
              {t(config.hintKey)}
            </span>
          )}
        </span>
        <button
          type="button"
          onClick={onCollapse}
          title={t('console.shell.collapsePanel')}
          className="ml-auto grid size-6 cursor-pointer place-items-center rounded-md text-muted-foreground/70 hover:bg-hover-wash hover:text-foreground"
        >
          <PanelLeftClose className="size-3.5" />
        </button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {config.sections.map((section) => (
          <div key={section.captionKey}>
            <div className="flex items-center gap-2 px-2 pb-1 pt-3 text-[10px] font-semibold uppercase tracking-[0.11em] text-muted-foreground/70 first:pt-0.5 after:h-px after:flex-1 after:bg-border">
              {t(section.captionKey)}
            </div>
            {section.links.map((link) => (
              <NavLink
                key={link.to + link.labelKey}
                to={withNosider(link.to)}
                end={link.end}
                className={({ isActive }) =>
                  cn(
                    'mb-px flex items-center gap-2 rounded-[7px] px-2 py-1.5 text-xs font-medium',
                    isActive
                      ? 'bg-primary-subtle text-primary-subtle-foreground'
                      : 'text-muted-foreground hover:bg-hover-wash hover:text-foreground',
                  )
                }
              >
                {t(link.labelKey)}
              </NavLink>
            ))}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 border-t border-border px-3 py-2 font-mono text-[10px] text-muted-foreground/70">
        <i aria-hidden className="size-[7px] flex-none rounded-full bg-success" />
        soit console v2
      </div>
    </aside>
  )
}
