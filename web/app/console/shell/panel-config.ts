import {
  IconChat,
  IconGovern,
  IconNavAccess,
  IconNavAgents,
  IconNavApprovals,
  IconNavAudit,
  IconNavEvents,
  IconNavKnowledge,
  IconNavModels,
  IconNavPlugins,
  IconNavSchedules,
  IconNavSecrets,
  IconNavTasks,
  IconNavTraces,
  IconNavWorkflows,
  IconObserve,
  IconOverview,
  IconPlus,
} from '@/console/components/icons'
import type { TranslationKey } from '@/i18n/types'

/**
 * Declarative configuration for the contextual side panel (230px, prototype
 * `.subnav`). A pillar is a list of caption groups; a group is either a set of
 * navigation links or a named slot the shell fills with rows it resolves at
 * render — recents, queues, live runs. Ordering lives here so a slot lands
 * between the right captions rather than being appended at the end.
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

/** A caption group whose rows are resolved at render rather than declared. */
export type PanelSlot =
  | 'today'
  | 'pinned'
  | 'chatActive'
  | 'chatByAgent'
  | 'guarantee'
  | 'recents'
  | 'draftReviews'
  | 'queue'
  | 'nextUp'
  | 'savedViews'
  | 'live'
  | 'governAttention'
  | 'governRecent'

export interface PanelLink {
  labelKey: TranslationKey
  to: string
  /** Matches child routes too (section landing pages). */
  end?: boolean
  /** Renders the prototype's `.ct` badge once the figure resolves. */
  count?: ConsoleCountKey
  /** The prototype draws a 14px glyph on every primary link. */
  icon?: React.ComponentType<{ size?: number }>
  /** An affordance rather than a destination: never marked active. */
  action?: boolean
}

export interface PanelSection {
  captionKey: TranslationKey
  links?: PanelLink[]
  slot?: PanelSlot
}

export interface PillarConfig {
  pillar: ConsolePillar
  labelKey: TranslationKey
  /** The rail's tooltip gloss; the panel head shows the workspace instead. */
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
        links: [
          { labelKey: 'console.nav.overview', to: '/', end: true, icon: IconOverview },
        ],
      },
      { captionKey: 'console.shell.today', slot: 'today' },
      { captionKey: 'console.shell.pinned', slot: 'pinned' },
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
          { labelKey: 'console.nav.newThread', to: '/chat', end: true, action: true, icon: IconPlus },
          { labelKey: 'console.nav.allThreads', to: '/chat', count: 'threads', icon: IconChat },
        ],
      },
      { captionKey: 'console.shell.active', slot: 'chatActive' },
      { captionKey: 'console.shell.byAgent', slot: 'chatByAgent' },
      { captionKey: 'console.shell.guarantee', slot: 'guarantee' },
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
          { labelKey: 'console.nav.agents', to: '/build/agents', count: 'agents', icon: IconNavAgents },
          { labelKey: 'console.nav.workflows', to: '/build/workflows', count: 'workflows', icon: IconNavWorkflows },
          { labelKey: 'console.nav.knowledge', to: '/build/knowledge', count: 'knowledge', icon: IconNavKnowledge },
          { labelKey: 'console.nav.plugins', to: '/build/plugins', count: 'plugins', icon: IconNavPlugins },
          { labelKey: 'console.nav.models', to: '/build/models', count: 'models', icon: IconNavModels },
        ],
      },
      { captionKey: 'console.shell.recentlyEdited', slot: 'recents' },
      { captionKey: 'console.shell.draftsAwaitingReview', slot: 'draftReviews' },
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
          { labelKey: 'console.nav.tasks', to: '/execute/tasks', count: 'tasks', icon: IconNavTasks },
          { labelKey: 'console.nav.schedules', to: '/execute/schedules', count: 'schedules', icon: IconNavSchedules },
          { labelKey: 'console.nav.events', to: '/execute/events', count: 'events', icon: IconNavEvents },
        ],
      },
      { captionKey: 'console.shell.queue', slot: 'queue' },
      { captionKey: 'console.shell.nextUp', slot: 'nextUp' },
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
          { labelKey: 'console.nav.runs', to: '/observe/runs', icon: IconObserve },
          { labelKey: 'console.nav.traces', to: '/observe/traces', icon: IconNavTraces },
        ],
      },
      { captionKey: 'console.shell.savedViews', slot: 'savedViews' },
      { captionKey: 'console.shell.live', slot: 'live' },
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
          { labelKey: 'console.nav.approvals', to: '/govern/approvals', count: 'approvals', icon: IconNavApprovals },
          { labelKey: 'console.nav.policies', to: '/govern/policies', icon: IconGovern },
          { labelKey: 'console.nav.audit', to: '/govern/audit', icon: IconNavAudit },
          { labelKey: 'console.nav.access', to: '/govern/access', icon: IconNavAccess },
          { labelKey: 'console.nav.secrets', to: '/govern/secrets', count: 'secrets', icon: IconNavSecrets },
        ],
      },
      { captionKey: 'console.shell.needsAttention', slot: 'governAttention' },
      { captionKey: 'console.shell.recent', slot: 'governRecent' },
    ],
  },
  {
    pillar: 'settings',
    labelKey: 'console.nav.settings',
    to: '/settings',
    match: '/settings',
    // Settings is the one pillar the prototype draws without link glyphs.
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
