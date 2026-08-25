import {
  useAgUiInterrupts,
  useAgUiSubmitInterruptResponses,
} from '@assistant-ui/react-ag-ui'
import { ShieldAlert } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type ApprovalDecision = 'approved' | 'rejected'

export const ApprovalInterrupts = () => {
  const { t } = useTranslation()
  const interrupts = useAgUiInterrupts()
  const submitResponses = useAgUiSubmitInterruptResponses()
  const [decisions, setDecisions] = useState<Record<string, ApprovalDecision>>({})
  const [submitting, setSubmitting] = useState(false)

  const interruptIds = useMemo(
    () => interrupts.map((interrupt) => interrupt.id).join('|'),
    [interrupts]
  )

  useEffect(() => {
    setDecisions({})
  }, [interruptIds])

  if (interrupts.length === 0) {
    return null
  }

  const allDecided = interrupts.every((interrupt) => decisions[interrupt.id])

  const handleSubmit = async () => {
    if (!allDecided || submitting) {
      return
    }
    setSubmitting(true)
    try {
      await submitResponses(
        interrupts.map((interrupt) => ({
          interruptId: interrupt.id,
          status: 'resolved' as const,
          payload: { decision: decisions[interrupt.id] },
        }))
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : t('chat.thread.approval.submitFailed')
      toast.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section
      aria-live="polite"
      aria-label={t('chat.thread.approval.title')}
      className="mx-auto mb-3 w-[calc(100%-1rem)] max-w-[var(--thread-max-width)] rounded-xl border border-warning/35 bg-warning/5 p-3 shadow-sm"
    >
      <div className="mb-3 flex items-start gap-3">
        <span className="rounded-lg bg-warning/15 p-2 text-warning-foreground">
          <ShieldAlert className="size-4" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold">{t('chat.thread.approval.title')}</h3>
          <p className="text-xs text-muted-foreground">{t('chat.thread.approval.description')}</p>
        </div>
      </div>

      <div className="space-y-2">
        {interrupts.map((interrupt) => {
          const metadata = interrupt.metadata || {}
          const toolRef = typeof metadata.toolRef === 'string' ? metadata.toolRef : undefined
          const selected = decisions[interrupt.id]
          return (
            <article key={interrupt.id} className="rounded-lg border bg-background/85 p-3">
              <p className="break-words text-sm font-medium">
                {interrupt.message || toolRef || t('chat.thread.approval.defaultMessage')}
              </p>
              {toolRef ? (
                <p className="mt-1 truncate font-mono text-xs text-muted-foreground" title={toolRef}>
                  {toolRef}
                </p>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant={selected === 'approved' ? 'default' : 'outline'}
                  className={cn(selected === 'approved' && 'bg-success hover:bg-success/90')}
                  onClick={() => setDecisions((current) => ({ ...current, [interrupt.id]: 'approved' }))}
                  disabled={submitting}
                >
                  {t('chat.thread.approval.approve')}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={selected === 'rejected' ? 'destructive' : 'outline'}
                  onClick={() => setDecisions((current) => ({ ...current, [interrupt.id]: 'rejected' }))}
                  disabled={submitting}
                >
                  {t('chat.thread.approval.reject')}
                </Button>
              </div>
            </article>
          )
        })}
      </div>

      <div className="mt-3 flex justify-end">
        <Button type="button" size="sm" onClick={handleSubmit} disabled={!allDecided || submitting}>
          {submitting ? t('chat.thread.approval.submitting') : t('chat.thread.approval.continue')}
        </Button>
      </div>
    </section>
  )
}
