import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'
import { useNavigate } from '@/hooks/use-navigate'
import type { TranslationKey } from '@/i18n/types'
import type { KnowledgeIngestTask as IngestTask } from '@/services/knowledge-service'

interface IngestTasksDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  tasks: IngestTask[]
  loading: boolean
  onRefresh: () => void
  onRetry: (task: IngestTask) => void
  onCancel: (task: IngestTask) => void
}

const statusColor: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  queued: 'outline',
  running: 'secondary',
  succeeded: 'default',
  failed: 'destructive',
  canceled: 'destructive',
}

export function IngestTasksDialog({ open, onOpenChange, tasks, loading, onRefresh, onRetry, onCancel }: IngestTasksDialogProps) {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t('knowledge.document.tasks.title')}</DialogTitle>
        </DialogHeader>
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">{t('knowledge.document.tasks.count', { count: tasks.length })}</div>
          <Button variant="outline" size="sm" onClick={onRefresh} disabled={loading}>
            <RefreshCw className="mr-2 h-4 w-4" />
            {t('knowledge.document.tasks.refresh')}
          </Button>
        </div>
        <div className="border rounded-md">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('knowledge.document.tasks.columns.status')}</TableHead>
                <TableHead>{t('knowledge.document.tasks.columns.doc')}</TableHead>
                <TableHead>{t('knowledge.document.tasks.columns.retries')}</TableHead>
                <TableHead>{t('knowledge.document.tasks.columns.updatedAt' as TranslationKey)}</TableHead>
                <TableHead>{t('knowledge.document.tasks.columns.error')}</TableHead>
                <TableHead className="w-[200px]">{t('knowledge.document.tasks.columns.actions')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tasks.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={6} className="text-center text-sm text-muted-foreground">
                    {t('knowledge.document.tasks.empty')}
                  </TableCell>
                </TableRow>
              ) : (
                tasks.map((task) => (
                  <TableRow key={task.id}>
                    <TableCell>
                      <Badge variant={statusColor[task.status] || 'outline'}>{task.status}</Badge>
                    </TableCell>
                    <TableCell className="text-sm">
                      {((task.payload_json as { title?: string; doc_key?: string } | null)?.title) ||
                        ((task.payload_json as { title?: string; doc_key?: string } | null)?.doc_key) ||
                        task.document_id ||
                        '-'}
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.retry_count}/{task.max_retries}
                    </TableCell>
                    <TableCell className="text-sm">
                      {task.updated_at ? new Date(task.updated_at).toLocaleString() : '-'}
                    </TableCell>
                    <TableCell>
                      {task.last_error_message ? (
                        <span className="text-xs text-muted-foreground line-clamp-2">{task.last_error_message}</span>
                      ) : (
                        <span className="text-xs text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-2">
                        {(task.status === 'failed' || task.status === 'canceled') && (
                          <Button variant="outline" size="sm" onClick={() => onRetry(task)}>
                            {t('knowledge.document.tasks.retry')}
                          </Button>
                        )}
                        {(task.status === 'queued' || task.status === 'running') && (
                          <Button variant="ghost" size="sm" onClick={() => onCancel(task)}>
                            {t('knowledge.document.tasks.cancel')}
                          </Button>
                        )}
                        {((task.payload_json as { run_id?: string } | null)?.run_id) && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => navigate(`/run/${(task.payload_json as { run_id?: string }).run_id}`)}
                          >
                            {t('knowledge.document.tasks.viewRun')}
                          </Button>
                        )}
                        {task.status !== 'failed' && task.status !== 'canceled' && task.status !== 'queued' && task.status !== 'running' && (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </DialogContent>
    </Dialog>
  )
}
