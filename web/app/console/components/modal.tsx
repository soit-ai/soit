import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from './ui'
import { ConsoleButton } from './button'
import { useTranslation } from '@/i18n'
import { cn } from '@/lib/utils'

/**
 * Prototype `.modal-box` — the console's write dialog. Built on the shared
 * Dialog so focus trapping, Escape and scroll locking come for free, with the
 * prototype's head / body / foot bands over it.
 *
 * `busy` disables both the confirm button and dismissal, so a submit in flight
 * cannot be escaped out from under.
 */
export interface ConsoleModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  title: React.ReactNode
  /** Screen-reader description; falls back to the title. */
  description?: React.ReactNode
  /** Mono note pinned to the left of the footer, as in the prototype. */
  note?: React.ReactNode
  confirmLabel: React.ReactNode
  onConfirm: () => void
  confirmDisabled?: boolean
  /** Tones the confirm button as destructive. */
  destructive?: boolean
  busy?: boolean
  children: React.ReactNode
  className?: string
}

export function ConsoleModal({
  open,
  onOpenChange,
  title,
  description,
  note,
  confirmLabel,
  onConfirm,
  confirmDisabled,
  destructive,
  busy,
  children,
  className,
}: ConsoleModalProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={(next) => (busy ? undefined : onOpenChange(next))}>
      <DialogContent
        className={cn('modal-box console-modal', className)}
        showCloseButton={false}
      >
        <div className="modal-head">
          <DialogTitle render={<h2 />}>{title}</DialogTitle>
        </div>
        <DialogDescription className="sr-only">
          {description ?? title}
        </DialogDescription>

        <div className="modal-body">{children}</div>

        <div className="modal-foot">
          {note && <span className="note">{note}</span>}
          <DialogClose
            render={<ConsoleButton disabled={busy}>{t('console.common.cancel')}</ConsoleButton>}
          />
          <ConsoleButton
            variant="primary"
            disabled={confirmDisabled || busy}
            style={destructive ? { color: 'var(--danger-foreground)' } : undefined}
            onClick={onConfirm}
          >
            {confirmLabel}
          </ConsoleButton>
        </div>
      </DialogContent>
    </Dialog>
  )
}
