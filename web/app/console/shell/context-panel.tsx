import { Fragment } from 'react'
import { NavLink, useLocation, useSearchParams } from 'react-router'

import { IconChevronLeft } from '@/console/components/icons'
import { useQuery } from '@/hooks/use-query'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'
import { getDiagnosticsSnapshot } from '@/services/diagnostics-service'
import { getWorkspace } from '@/services/identity-service'
import { useUserStore } from '@/stores/user'

import { pillarForPathname, type PanelSection } from './panel-config'
import { useConsolePanelData, type PanelRow } from './use-console-counts'

/** Attention dots reuse the status ramp rather than inventing new hues. */
const TONE_VAR: Record<'primary' | 'warn' | 'bad', string> = {
  primary: 'primary',
  warn: 'warning',
  bad: 'destructive',
}

interface ContextPanelProps {
  onCollapse: () => void
}

/**
 * The 230px contextual panel (prototype `.subnav`): the active pillar's caption
 * groups, each either a set of navigation links or a slot filled from
 * `useConsolePanelData`. A group with nothing in it drops its caption too — an
 * empty heading reads as a failure rather than as an absence.
 */
export function ContextPanel({ onCollapse }: ContextPanelProps) {
  const { t } = useTranslation()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const config = pillarForPathname(location.pathname)

  const workspaceId =
    useUserStore((state) => state.currentUser?.workspace_id) ||
    (typeof window === 'undefined' ? '' : localStorage.getItem('workspace_id') || '')

  const { counts, groups } = useConsolePanelData(config.pillar, workspaceId)

  const workspace = useQuery({
    queryKey: ['console', 'panel', 'workspace', workspaceId],
    queryFn: () => getWorkspace(workspaceId),
    options: { retry: false, refetchOnWindowFocus: false, enabled: !!workspaceId },
  })

  // The foot's health line and the head's environment come from one snapshot.
  const diagnostics = useQuery({
    queryKey: ['console', 'panel', 'diagnostics'],
    queryFn: () => getDiagnosticsSnapshot(),
    options: { retry: false, refetchOnWindowFocus: false, staleTime: 60_000 },
  })

  // Preserve the embed flag on declarative links (use-navigate does this for
  // imperative navigation; NavLink needs it appended explicitly).
  const withNosider = (to: string) =>
    searchParams.get('nosider') ? `${to}${to.includes('?') ? '&' : '?'}nosider=true` : to

  // Slot rows address a filter or an object, not a section. Their target often
  // differs from the current page only by a query string, which NavLink cannot
  // match on — left to its default every saved view on /observe/runs would
  // light up at once, and claim aria-current with it.
  const renderRow = (row: PanelRow) => {
    switch (row.kind) {
      case 'stat':
        return (
          <NavLink key={row.id} to={withNosider(row.to)} className={() => 'sl'}>
            {row.label}
            <span className="ct">{row.value}</span>
          </NavLink>
        )
      case 'mini':
        return (
          <NavLink key={row.id} to={withNosider(row.to)} className={() => 'sub-mini'}>
            <b>
              <span className="truncate">{row.label}</span>
              <span className="mono">{row.meta}</span>
            </b>
            <small>{row.note}</small>
          </NavLink>
        )
      case 'idm':
        return (
          <NavLink key={row.id} to={withNosider(row.to)} className={() => 'sl'}>
            <span className="idm" style={{ '--c': row.color } as React.CSSProperties}>
              <i />
              {row.label}
            </span>
            {row.value != null && <span className="ct">{row.value}</span>}
          </NavLink>
        )
      case 'note':
        return (
          <NavLink key={row.id} to={withNosider(row.to)} className={() => 'sub-note'}>
            <i style={{ background: `var(--${TONE_VAR[row.tone]})` }} aria-hidden />
            {row.label}
            {row.live ? (
              <span className="livedot" style={{ marginLeft: 6 }} aria-hidden />
            ) : (
              row.value != null && <span className="ct">{row.value}</span>
            )}
          </NavLink>
        )
    }
  }

  const renderSection = (section: PanelSection, index: number) => {
    const rows = section.slot ? groups[section.slot] || [] : []
    const links = section.links || []
    if (links.length === 0 && rows.length === 0) return null

    // Flat, not wrapped: the prototype's `.sub-panel .sub-cap:first-child` gives
    // only the panel's opening caption its tighter top padding. A wrapper per
    // section would make every caption a first-child and flatten all the gaps.
    return (
      <Fragment key={`${section.captionKey}:${index}`}>
        <div className="sub-cap">{t(section.captionKey)}</div>
        {links.map((link) => {
          const count = link.count ? counts[link.count] : undefined
          const Icon = link.icon
          return (
            <NavLink
              key={link.to + link.labelKey}
              to={withNosider(link.to)}
              end={link.end}
              className={({ isActive }) => cn('sl', isActive && !link.action && 'active')}
            >
              {Icon && <Icon size={14} />}
              {t(link.labelKey)}
              {count != null && <span className="ct">{count}</span>}
            </NavLink>
          )
        })}
        {rows.map(renderRow)}
      </Fragment>
    )
  }

  const health = diagnostics.data
  const healthy = health?.overall_status === 'healthy'

  return (
    <aside className="subnav">
      <div className="subnav-head">
        <span className="min-w-0">
          <b>{t(config.labelKey)}</b>
          {/* Which workspace, which environment. The name needs a fetch, but
              the id is already in hand — it stands in rather than leaving the
              line blank. The environment shows only when diagnostics reports
              it, since guessing it would misname where the operator is. */}
          <span className="mono block truncate">
            {[workspace.data?.name || workspaceId, health?.environment]
              .filter(Boolean)
              .join(' · ')}
          </span>
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
        <div className="sub-panel on">{config.sections.map(renderSection)}</div>
      </div>

      <div className="subnav-foot">
        {/* The dot is only green on a snapshot that actually says healthy; with
            no snapshot it stays neutral rather than claiming all is well. */}
        <i
          aria-hidden
          style={
            health
              ? { background: `var(--${healthy ? 'success' : 'warning'})` }
              : { background: 'var(--faint)' }
          }
        />
        {health
          ? `${healthy ? t('console.shell.allSystemsNormal') : t('console.shell.systemsDegraded')} · v${health.version}`
          : t('console.shell.healthUnknown')}
        <span className="ml-auto">{t('console.shell.jumpHint')}</span>
      </div>
    </aside>
  )
}
