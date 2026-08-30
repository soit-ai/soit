import type { TranslationKey } from '@/i18n/types'

/**
 * Declarative configuration for the contextual side panel (230px).
 * Each pillar declares caption groups of navigation links; dynamic slots
 * (counts, saved views, recents, attention rows) are wired per phase as the
 * backing services land — a link with no `count` simply renders without one.
 */
export type ConsolePillar =
  | 'overview'
  | 'chat'
  | 'build'
  | 'execute'
  | 'observe'
  | 'govern'
  | 'settings'

/**
 * Names the live figure a panel link shows beside its label, matching the
 * prototype's `.ct` counts. `use-console-counts` resolves these, fetching only
 * what the pillar on screen actually needs.
 */
export type ConsoleCountKey =
  | 'agents'
  | 'workflows'
  | 'knowledge'
  | 'plugins'
  | 'models'
  | 'tasks'
  | 'schedules'
  | 'events'
  | 'approvals'
  | 'secrets'
  | 'threads'

export interface PanelLink {
  labelKey: TranslationKey
  to: string
  /** Matches child routes too (section landing pages). */
  end?: boolean
  /** Renders the prototype's `.ct` badge once the figure resolves. */
  count?: ConsoleCountKey
}

export interface PanelSection {
  captionKey: TranslationKey
  links: PanelLink[]
}

export interface PillarConfig {
  pillar: ConsolePillar
  labelKey: TranslationKey
  hintKey?: TranslationKey
  /** Rail target when the pillar icon is clicked. */
  to: string
  /** Route prefix that marks the pillar active. */
  match: string
  sections: PanelSection[]
}

export const PANEL_CONFIG: PillarConfig[] = [
  {
    pillar: 'overview',
    labelKey: 'console.nav.overview',
    to: '/',
    match: '/',
    sections: [
      {
        captionKey: 'console.shell.workspace',
        links: [{ labelKey: 'console.nav.overview', to: '/', end: true }],
      },
    ],
  },
  {
    pillar: 'chat',
    labelKey: 'console.nav.chat',
    hintKey: 'console.pillar.chatHint',
    to: '/chat',
    match: '/chat',
    sections: [
      {
        captionKey: 'console.nav.chat',
        links: [
          { labelKey: 'console.nav.newThread', to: '/chat', end: true },
          { labelKey: 'console.nav.allThreads', to: '/chat', count: 'threads' },
        ],
      },
    ],
  },
  {
    pillar: 'build',
    labelKey: 'console.nav.build',
    hintKey: 'console.pillar.buildHint',
    to: '/build/agents',
    match: '/build',
    sections: [
      {
        captionKey: 'console.nav.build',
        links: [
          { labelKey: 'console.nav.agents', to: '/build/agents', count: 'agents' },
          { labelKey: 'console.nav.workflows', to: '/build/workflows', count: 'workflows' },
          { labelKey: 'console.nav.knowledge', to: '/build/knowledge', count: 'knowledge' },
          { labelKey: 'console.nav.plugins', to: '/build/plugins', count: 'plugins' },
          { labelKey: 'console.nav.models', to: '/build/models', count: 'models' },
        ],
      },
    ],
  },
  {
    pillar: 'execute',
    labelKey: 'console.nav.execute',
    hintKey: 'console.pillar.executeHint',
    to: '/execute/tasks',
    match: '/execute',
    sections: [
      {
        captionKey: 'console.nav.execute',
        links: [
          { labelKey: 'console.nav.tasks', to: '/execute/tasks', count: 'tasks' },
          { labelKey: 'console.nav.schedules', to: '/execute/schedules', count: 'schedules' },
          { labelKey: 'console.nav.events', to: '/execute/events', count: 'events' },
        ],
      },
    ],
  },
  {
    pillar: 'observe',
    labelKey: 'console.nav.observe',
    hintKey: 'console.pillar.observeHint',
    to: '/observe/runs',
    match: '/observe',
    sections: [
      {
        captionKey: 'console.nav.observe',
        links: [
          { labelKey: 'console.nav.runs', to: '/observe/runs' },
          { labelKey: 'console.nav.traces', to: '/observe/traces' },
        ],
      },
    ],
  },
  {
    pillar: 'govern',
    labelKey: 'console.nav.govern',
    hintKey: 'console.pillar.governHint',
    to: '/govern/approvals',
    match: '/govern',
    sections: [
      {
        captionKey: 'console.nav.govern',
        links: [
          { labelKey: 'console.nav.approvals', to: '/govern/approvals', count: 'approvals' },
          { labelKey: 'console.nav.policies', to: '/govern/policies' },
          { labelKey: 'console.nav.audit', to: '/govern/audit' },
          { labelKey: 'console.nav.access', to: '/govern/access' },
          { labelKey: 'console.nav.secrets', to: '/govern/secrets', count: 'secrets' },
        ],
      },
    ],
  },
  {
    pillar: 'settings',
    labelKey: 'console.nav.settings',
    to: '/settings',
    match: '/settings',
    sections: [
      {
        captionKey: 'console.settings.groupWorkspace',
        links: [
          { labelKey: 'console.settings.account', to: '/settings/account' },
          { labelKey: 'console.settings.team', to: '/settings/team' },
          { labelKey: 'console.settings.api', to: '/settings/api' },
          { labelKey: 'console.settings.security', to: '/settings/security' },
          { labelKey: 'console.settings.secrets', to: '/settings/secrets' },
        ],
      },
      {
        captionKey: 'console.settings.groupPreferences',
        links: [
          { labelKey: 'console.settings.notifications', to: '/settings/notifications' },
          { labelKey: 'console.settings.appearance', to: '/settings/appearance' },
        ],
      },
      {
        captionKey: 'console.settings.groupPlan',
        links: [
          { labelKey: 'console.settings.billing', to: '/settings/billing' },
          { labelKey: 'console.settings.about', to: '/settings/about' },
        ],
      },
    ],
  },
]

export function pillarForPathname(pathname: string): PillarConfig {
  // Longest match wins so the root (overview) does not shadow the others.
  const match = [...PANEL_CONFIG]
    .sort((a, b) => b.match.length - a.match.length)
    .find((entry) => pathname === entry.match || pathname.startsWith(`${entry.match}/`))
  return match ?? PANEL_CONFIG[0]
}
