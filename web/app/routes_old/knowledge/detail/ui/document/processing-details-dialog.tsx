import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { AlertCircle, CheckCircle2, Download, RefreshCw } from 'lucide-react'
import { useTranslation } from '@/i18n'

// Processing stages for embedding pipeline.
type ProcessingStage = 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed'

// Processing statistics model.
interface ProcessingStats {
  chunks: number
  tokens: number
  vectors: number
}

// Processing status model.
interface ProcessingInfo {
  stage: ProcessingStage
  progress: number
  error: string | null
  stats: ProcessingStats
}

// Document model.
interface Document {
  id: string
  title: string
  status: string
  processing: ProcessingInfo
}

export interface ProcessingDetailsDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  document: Document | undefined
  processingStatus: {
    stage: string
    progress: number
    error: string | null
    stats: {
      chunks: number
      tokens: number
      vectors: number
    }
  } | null
}

export function ProcessingDetailsDialog({
  open,
  onOpenChange,
  document,
  processingStatus
}: ProcessingDetailsDialogProps) {
  const { t } = useTranslation()

  if (!document?.processing) return null

  const stageConfig: Record<ProcessingStage, { label: string; description: string }> = {
    parsing: {
      label: t('knowledge.document.processing.stage.parsing.label'),
      description: t('knowledge.document.processing.stage.parsing.description'),
    },
    chunking: {
      label: t('knowledge.document.processing.stage.chunking.label'),
      description: t('knowledge.document.processing.stage.chunking.description'),
    },
    embedding: {
      label: t('knowledge.document.processing.stage.embedding.label'),
      description: t('knowledge.document.processing.stage.embedding.description'),
    },
    indexing: {
      label: t('knowledge.document.processing.stage.indexing.label'),
      description: t('knowledge.document.processing.stage.indexing.description'),
    },
    completed: {
      label: t('knowledge.document.processing.stage.completed.label'),
      description: t('knowledge.document.processing.stage.completed.description'),
    },
  }

  const stats = document.processing.stats
  const stages = Object.entries(stageConfig)
  const currentStageIndex = stages.findIndex(([key]) => key === document.processing.stage)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('knowledge.document.processing.title')}</DialogTitle>
          <DialogDescription>
            {t('knowledge.document.processing.description', { title: document.title })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6">
          <div className="space-y-4">
            {stages.map(([key, stage], index) => {
              const isCompleted = index < currentStageIndex
              const isCurrent = index === currentStageIndex
              const isPending = index > currentStageIndex

              return (
                <div key={key} className="flex items-start gap-4">
                  <div className="flex flex-col items-center">
                    {isCompleted ? (
                      <CheckCircle2 className="h-5 w-5 text-success-foreground" />
                    ) : isCurrent ? (
                      <RefreshCw className="h-5 w-5 text-primary animate-spin" />
                    ) : (
                      <div className="h-5 w-5 rounded-full border-2 border-border" />
                    )}
                    {index < stages.length - 1 && (
                      <div className={`w-0.5 h-8 ${isCompleted ? 'bg-success' : 'bg-muted'}`} />
                    )}
                  </div>
                  <div className="flex-1">
                    <div className="font-medium">{stage.label}</div>
                    <div className="text-sm text-muted-foreground">{stage.description}</div>
                  </div>
                </div>
              )
            })}
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-lg border">
              <div className="text-sm font-medium">{t('knowledge.document.processing.stats.chunks')}</div>
              <div className="text-2xl font-bold">{stats.chunks}</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm font-medium">{t('knowledge.document.processing.stats.tokens')}</div>
              <div className="text-2xl font-bold">{stats.tokens}</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm font-medium">{t('knowledge.document.processing.stats.vectors')}</div>
              <div className="text-2xl font-bold">{stats.vectors}</div>
            </div>
          </div>

          {document.processing.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t('knowledge.document.processing.error.title')}</AlertTitle>
              <AlertDescription>{document.processing.error}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-end gap-2">
            {document.status === 'failed' && (
              <Button variant="outline">
                <RefreshCw className="mr-2 h-4 w-4" />
                {t('knowledge.document.processing.actions.retry')}
              </Button>
            )}
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              {t('knowledge.document.processing.actions.export')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
