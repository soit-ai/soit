import { NavLink, useLocation, useSearchParams } from 'react-router'

import { IconChevronLeft } from '@/console/components/icons'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

import { pillarForPathname } from './panel-config'

interface ContextPanelProps {
  onCollapse: () => void
}

/**
 * The 230px contextual panel (prototype .subnav): declarative caption groups
 * from panel-config for the active pillar. Counts, saved views, recents and
 * attention rows join as their backing services land phase by phase.
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
    <aside className="subnav">
      <div className="subnav-head">
        <span className="min-w-0">
          <b>{t(config.labelKey)}</b>
          {config.hintKey && (
            <span className="mono block truncate">{t(config.hintKey)}</span>
          )}
        </span>
        <button
          type="button"
          className="subnav-collapse"
          onClick={onCollapse}
          title={t('console.shell.collapsePanel')}
        >
          <IconChevronLeft size={13} />
        </button>
      </div>

      <div className="subnav-body">
        <div className="sub-panel on">
          {config.sections.map((section) => (
            <div key={section.captionKey}>
              <div className="sub-cap">{t(section.captionKey)}</div>
              {section.links.map((link) => (
                <NavLink
                  key={link.to + link.labelKey}
                  to={withNosider(link.to)}
                  end={link.end}
                  className={({ isActive }) => cn('sl', isActive && 'active')}
                >
                  {t(link.labelKey)}
                </NavLink>
              ))}
            </div>
          ))}
        </div>
      </div>

      <div className="subnav-foot">
        <i aria-hidden />
        soit console v2
      </div>
    </aside>
  )
}
