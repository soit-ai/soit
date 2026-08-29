import { useCallback, useEffect, useRef, useState } from 'react'

import { Check, Copy } from 'lucide-react'

import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

interface IdBadgeProps {
  id: string
  /** Contrast tone marks run/trace ids per the prototype's `.runid` rule. */
  tone?: 'default' | 'contrast'
  /** Truncation width; ids keep a single line and clip with an ellipsis. */
  maxWidth?: number
  className?: string
}

export function IdBadge({ id, tone = 'default', maxWidth = 200, className }: IdBadgeProps) {
  const { t } = useTranslation()
  const [copied, setCopied] = useState(false)
  const resetTimer = useRef<ReturnType<typeof setTimeout>>(undefined)

  useEffect(() => () => clearTimeout(resetTimer.current), [])

  const copy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(id)
      setCopied(true)
      clearTimeout(resetTimer.current)
      resetTimer.current = setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard unavailable (permissions / insecure context): stay silent.
    }
  }, [id])

  return (
    <span className={cn('group/id inline-flex min-w-0 items-center gap-1', className)}>
      <span
        className={cn(
          'truncate font-mono text-xs',
          tone === 'contrast' ? 'text-contrast' : 'text-muted-foreground',
        )}
        style={{ maxWidth }}
        title={id}
      >
        {id}
      </span>
      <button
        type="button"
        onClick={copy}
        aria-label={t(copied ? 'console.common.copied' : 'console.common.copy')}
        className="grid size-5 flex-none cursor-pointer place-items-center rounded-sm text-muted-foreground opacity-0 transition-opacity hover:bg-hover-wash hover:text-foreground focus-visible:opacity-100 group-hover/id:opacity-100"
      >
        {copied ? <Check className="size-3 text-success" /> : <Copy className="size-3" />}
      </button>
    </span>
  )
}
