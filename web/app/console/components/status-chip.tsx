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
  enabled: 'console.status.enabled',
  disabled: 'console.status.disabled',
  info: 'console.status.info',
}

const TONE_CHIP_CLASS: Record<StatusTone, string> = {
  ok: 'bg-success/12 text-success-foreground',
  warn: 'bg-warning/12 text-warning-foreground',
  bad: 'bg-danger/12 text-danger-foreground',
  brand: 'bg-primary-subtle text-primary-subtle-foreground',
  info: 'bg-info/12 text-info-foreground',
  neutral: 'border border-border text-muted-foreground',
}

const TONE_DOT_CLASS: Record<StatusTone, string> = {
  ok: 'bg-success',
  warn: 'bg-warning',
  bad: 'bg-danger',
  brand: 'bg-primary animate-pulse',
  info: 'bg-info',
  neutral: 'bg-muted-foreground/60',
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
    <span
      className={cn(
        'inline-flex h-5 items-center gap-1.5 whitespace-nowrap rounded-full px-2 font-mono text-[10.5px] tracking-wider',
        TONE_CHIP_CLASS[tone],
        className,
      )}
    >
      <i aria-hidden className={cn('size-1.5 flex-none rounded-full', TONE_DOT_CLASS[tone])} />
      {label ?? t(STATUS_LABEL_KEY[status])}
    </span>
  )
}
