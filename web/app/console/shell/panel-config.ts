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

export interface PanelLink {
  labelKey: TranslationKey
  to: string
  /** Matches child routes too (section landing pages). */
  end?: boolean
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
    to: '/v2',
    match: '/v2',
    sections: [
      {
        captionKey: 'console.shell.workspace',
        links: [{ labelKey: 'console.nav.overview', to: '/v2', end: true }],
      },
    ],
  },
  {
    pillar: 'chat',
    labelKey: 'console.nav.chat',
    hintKey: 'console.pillar.chatHint',
    to: '/v2/chat',
    match: '/v2/chat',
    sections: [
      {
        captionKey: 'console.nav.chat',
        links: [
          { labelKey: 'console.nav.newThread', to: '/v2/chat', end: true },
          { labelKey: 'console.nav.allThreads', to: '/v2/chat' },
        ],
      },
    ],
  },
  {
    pillar: 'build',
    labelKey: 'console.nav.build',
    hintKey: 'console.pillar.buildHint',
    to: '/v2/build/agents',
    match: '/v2/build',
    sections: [
      {
        captionKey: 'console.nav.build',
        links: [
          { labelKey: 'console.nav.agents', to: '/v2/build/agents' },
          { labelKey: 'console.nav.workflows', to: '/v2/build/workflows' },
          { labelKey: 'console.nav.knowledge', to: '/v2/build/knowledge' },
          { labelKey: 'console.nav.plugins', to: '/v2/build/plugins' },
          { labelKey: 'console.nav.models', to: '/v2/build/models' },
        ],
      },
    ],
  },
  {
    pillar: 'execute',
    labelKey: 'console.nav.execute',
    hintKey: 'console.pillar.executeHint',
    to: '/v2/execute/tasks',
    match: '/v2/execute',
    sections: [
      {
        captionKey: 'console.nav.execute',
        links: [
          { labelKey: 'console.nav.tasks', to: '/v2/execute/tasks' },
          { labelKey: 'console.nav.schedules', to: '/v2/execute/schedules' },
          { labelKey: 'console.nav.events', to: '/v2/execute/events' },
        ],
      },
    ],
  },
  {
    pillar: 'observe',
    labelKey: 'console.nav.observe',
    hintKey: 'console.pillar.observeHint',
    to: '/v2/observe/runs',
    match: '/v2/observe',
    sections: [
      {
        captionKey: 'console.nav.observe',
        links: [
          { labelKey: 'console.nav.runs', to: '/v2/observe/runs' },
          { labelKey: 'console.nav.traces', to: '/v2/observe/traces' },
        ],
      },
    ],
  },
  {
    pillar: 'govern',
    labelKey: 'console.nav.govern',
    hintKey: 'console.pillar.governHint',
    to: '/v2/govern/approvals',
    match: '/v2/govern',
    sections: [
      {
        captionKey: 'console.nav.govern',
        links: [
          { labelKey: 'console.nav.approvals', to: '/v2/govern/approvals' },
          { labelKey: 'console.nav.policies', to: '/v2/govern/policies' },
          { labelKey: 'console.nav.audit', to: '/v2/govern/audit' },
          { labelKey: 'console.nav.secrets', to: '/v2/govern/secrets' },
        ],
      },
    ],
  },
  {
    pillar: 'settings',
    labelKey: 'console.nav.settings',
    to: '/v2/settings',
    match: '/v2/settings',
    sections: [
      {
        captionKey: 'console.settings.groupWorkspace',
        links: [
          { labelKey: 'console.settings.account', to: '/v2/settings/account' },
          { labelKey: 'console.settings.team', to: '/v2/settings/team' },
          { labelKey: 'console.settings.api', to: '/v2/settings/api' },
          { labelKey: 'console.settings.security', to: '/v2/settings/security' },
          { labelKey: 'console.settings.secrets', to: '/v2/settings/secrets' },
        ],
      },
      {
        captionKey: 'console.settings.groupPreferences',
        links: [
          { labelKey: 'console.settings.notifications', to: '/v2/settings/notifications' },
          { labelKey: 'console.settings.appearance', to: '/v2/settings/appearance' },
        ],
      },
      {
        captionKey: 'console.settings.groupPlan',
        links: [
          { labelKey: 'console.settings.billing', to: '/v2/settings/billing' },
          { labelKey: 'console.settings.about', to: '/v2/settings/about' },
        ],
      },
    ],
  },
]

export function pillarForPathname(pathname: string): PillarConfig {
  // Longest match wins so /v2 (overview) does not shadow the other pillars.
  const match = [...PANEL_CONFIG]
    .sort((a, b) => b.match.length - a.match.length)
    .find((entry) => pathname === entry.match || pathname.startsWith(`${entry.match}/`))
  return match ?? PANEL_CONFIG[0]
}
