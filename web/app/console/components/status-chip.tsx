import { useTranslation } from '@/i18n'
import type { TranslationKey } from '@/i18n/types'
import { cn } from '@/lib/utils'

/**
 * Single source of truth for status vocabulary in the console.
 * Status hues (success/warning/danger) are reserved for state; anything that
 * differs in kind rather than state belongs to KindChip's categorical palette.
 *
 * Covers the three families used across the v13 prototype:
 * - governance verdicts: pass / warn / block / na
 * - run & task states: running / queued / succeeded / failed / cancelled /
 *   degraded / blocked
 * - release states: draft / staged / published / rolled_back
 * plus generic enabled / disabled / info.
 */
export type ConsoleStatus =
  | 'pass'
  | 'warn'
  | 'block'
  | 'na'
  | 'running'
  | 'queued'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'degraded'
  | 'blocked'
  | 'draft'
  | 'staged'
  | 'published'
  | 'rolled_back'
  | 'paused'
  | 'enabled'
  | 'disabled'
  | 'info'

type StatusTone = 'ok' | 'warn' | 'bad' | 'brand' | 'info' | 'neutral'

export const CONSOLE_STATUS_TONE: Record<ConsoleStatus, StatusTone> = {
  pass: 'ok',
  warn: 'warn',
  block: 'bad',
  na: 'neutral',
  running: 'brand',
  queued: 'info',
  succeeded: 'ok',
  failed: 'bad',
  cancelled: 'neutral',
  degraded: 'warn',
  blocked: 'bad',
  draft: 'info',
  staged: 'warn',
  published: 'ok',
  rolled_back: 'bad',
  paused: 'warn',
  enabled: 'ok',
  disabled: 'neutral',
  info: 'info',
}

const STATUS_LABEL_KEY: Record<ConsoleStatus, TranslationKey> = {
  pass: 'console.status.pass',
  warn: 'console.status.warn',
  block: 'console.status.block',
  na: 'console.status.na',
  running: 'console.status.running',
  queued: 'console.status.queued',
  succeeded: 'console.status.succeeded',
  failed: 'console.status.failed',
  cancelled: 'console.status.cancelled',
  degraded: 'console.status.degraded',
  blocked: 'console.status.blocked',
  draft: 'console.status.draft',
  staged: 'console.status.staged',
  published: 'console.status.published',
  rolled_back: 'console.status.rolledBack',
  paused: 'console.status.paused',
  enabled: 'console.status.enabled',
  disabled: 'console.status.disabled',
  info: 'console.status.info',
}

/** Prototype chip state classes: .chip.st-* (tone → visual). */
const TONE_CHIP_CLASS: Record<StatusTone, string | undefined> = {
  ok: 'st-pass',
  warn: 'st-degraded',
  bad: 'st-blocked',
  brand: 'st-running',
  info: 'st-info',
  neutral: undefined, // bare .chip: bordered, muted
}

/**
 * Maps a backend run/task status string onto the console vocabulary so every
 * module renders the same chip for the same state.
 */
export function runStatusToConsole(status: string): ConsoleStatus {
  switch (status) {
    case 'succeeded':
      return 'succeeded'
    case 'failed':
      return 'failed'
    case 'running':
      return 'running'
    case 'queued':
      return 'queued'
    case 'paused':
      return 'paused'
    case 'canceled':
    case 'cancelled':
      return 'cancelled'
    default:
      return 'info'
  }
}

interface StatusChipProps {
  status: ConsoleStatus
  /** Overrides the dictionary label; keep for values like "PASS 12/13". */
  label?: React.ReactNode
  className?: string
}

export function StatusChip({ status, label, className }: StatusChipProps) {
  const { t } = useTranslation()
  const tone = CONSOLE_STATUS_TONE[status]

  return (
    <span className={cn('chip', TONE_CHIP_CLASS[tone], className)}>
      <i aria-hidden />
      {label ?? t(STATUS_LABEL_KEY[status])}
    </span>
  )
}
