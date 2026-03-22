import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { ScrollArea } from '@/components/ui/scroll-area'
import { useTranslation } from '@/i18n'

export interface DocumentVersion {
  version: number
  created_at: string
}

export interface VersionHistoryDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  loading?: boolean
  versions: DocumentVersion[]
  onRollback: (version: number) => Promise<void>
}

export function VersionHistoryDialog({
  open,
  onOpenChange,
  loading,
  versions,
  onRollback,
}: VersionHistoryDialogProps) {
  const { t } = useTranslation()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('knowledge.document.version.title')}</DialogTitle>
        </DialogHeader>
        <ScrollArea className="h-[300px]">
          {loading && (
            <div className="text-sm text-muted-foreground">{t('knowledge.document.version.loading')}</div>
          )}
          {!loading && versions.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('knowledge.document.version.empty')}</div>
          )}
          <div className="space-y-4">
            {versions.map((version) => (
              <div key={version.version} className="flex items-center justify-between p-2 rounded-lg border">
                <div>
                  <div className="font-medium">v{version.version}</div>
                  <div className="text-sm text-muted-foreground">{version.created_at}</div>
                </div>
                <div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => onRollback(version.version)}
                  >
                    {t('knowledge.document.version.actions.rollback')}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>
      </DialogContent>
    </Dialog>
  )
}

