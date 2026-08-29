import type { CSSProperties } from 'react'

import { cn } from '@/lib/utils'

/**
 * Categorical identity for object kinds — never used to encode status.
 * Colours come exclusively from the --cat-* palette in app/app.css.
 */
export type ConsoleKind =
  | 'agent'
  | 'workflow'
  | 'knowledge'
  | 'plugin'
  | 'tool'
  | 'skill'
  | 'model'
  | 'task'
  | 'schedule'
  | 'event'
  | 'policy'
  | 'secret'

export const CONSOLE_KIND_COLOR: Record<ConsoleKind, string> = {
  agent: 'var(--cat-blue)',
  workflow: 'var(--cat-purple)',
  knowledge: 'var(--cat-teal)',
  plugin: 'var(--cat-cyan)',
  tool: 'var(--cat-indigo)',
  skill: 'var(--cat-pink)',
  model: 'var(--cat-slate)',
  task: 'var(--cat-blue)',
  schedule: 'var(--cat-indigo)',
  event: 'var(--cat-cyan)',
  policy: 'var(--cat-purple)',
  secret: 'var(--cat-slate)',
}

interface KindChipProps {
  kind: ConsoleKind
  label?: React.ReactNode
  /** Renders the small mark only, without a text label. */
  markOnly?: boolean
  className?: string
}

export function KindChip({ kind, label, markOnly, className }: KindChipProps) {
  const style = { '--c': CONSOLE_KIND_COLOR[kind] } as CSSProperties

  if (markOnly) {
    return <i aria-hidden className={cn('console-idm', className)} style={style} />
  }

  return (
    <span className={cn('inline-flex items-center gap-2', className)} style={style}>
      <i aria-hidden className="console-idm" />
      <span className="font-mono text-[10.5px] text-muted-foreground">{label ?? kind}</span>
    </span>
  )
}
