import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Progress } from '@/components/ui/progress'
import { RefreshCw, CheckCircle2, AlertCircle, Download } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useTranslation } from '@/i18n'

interface ProcessingStats {
  chunks: number
  tokens: number
  vectors: number
}

interface ChunkConfig {
  chunkSize: number
  chunkOverlap: number
  separator: string
}

interface Chunk {
  id: string
  content: string
  tokens: number
  embedding?: number[]
  metadata: {
    startIndex: number
    endIndex: number
    page?: number
  }
}

export type ProcessingStage = 'parsing' | 'chunking' | 'embedding' | 'indexing' | 'completed'

interface ProcessingInfo {
  stage: ProcessingStage
  progress: number
  error: string | null
  stats: ProcessingStats
  chunks: Chunk[]
  config: ChunkConfig
}

interface ProgressDialogProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  processingInfo?: ProcessingInfo
  docTitle?: string
}

export default function ProgressDialog({ open, onOpenChange, processingInfo, docTitle }: ProgressDialogProps) {
  const { t } = useTranslation()

  if (!processingInfo) return null

  const stageConfig: Record<ProcessingStage, { label: string; description: string }> = {
    parsing: {
      label: t('dataset.document.processing.stage.parsing.label'),
      description: t('dataset.document.processing.stage.parsing.description'),
    },
    chunking: {
      label: t('dataset.document.processing.stage.chunking.label'),
      description: t('dataset.document.processing.stage.chunking.description'),
    },
    embedding: {
      label: t('dataset.document.processing.stage.embedding.label'),
      description: t('dataset.document.processing.stage.embedding.description'),
    },
    indexing: {
      label: t('dataset.document.processing.stage.indexing.label'),
      description: t('dataset.document.processing.stage.indexing.description'),
    },
    completed: {
      label: t('dataset.document.processing.stage.completed.label'),
      description: t('dataset.document.processing.stage.completed.description'),
    },
  }

  const stats = processingInfo.stats
  const stages = Object.entries(stageConfig)
  const currentStageIndex = stages.findIndex(([key]) => key === processingInfo.stage)

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('dataset.document.processing.title')}</DialogTitle>
          <DialogDescription>
            {t('dataset.document.processing.description', { title: docTitle || '' })}
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-6">
          <div className="space-y-4">
            {stages.map(([key, stage], index) => {
              const isCompleted = index < currentStageIndex
              const isCurrent = index === currentStageIndex
              return (
                <div key={key} className="flex items-start gap-4">
                  <div className="flex flex-col items-center">
                    {isCompleted ? (
                      <CheckCircle2 className="h-5 w-5 text-green-500" />
                    ) : isCurrent ? (
                      <RefreshCw className="h-5 w-5 text-blue-500 animate-spin" />
                    ) : (
                      <div className="h-5 w-5 rounded-full border-2 border-gray-300" />
                    )}
                    {index < stages.length - 1 && (
                      <div className={`w-0.5 h-8 ${isCompleted ? 'bg-green-500' : 'bg-gray-200'}`} />
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
              <div className="text-sm font-medium">{t('dataset.document.processing.stats.chunks')}</div>
              <div className="text-2xl font-bold">{stats.chunks}</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm font-medium">{t('dataset.document.processing.stats.tokens')}</div>
              <div className="text-2xl font-bold">{stats.tokens}</div>
            </div>
            <div className="p-4 rounded-lg border">
              <div className="text-sm font-medium">{t('dataset.document.processing.stats.vectors')}</div>
              <div className="text-2xl font-bold">{stats.vectors}</div>
            </div>
          </div>

          {processingInfo.error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>{t('dataset.document.processing.error.title')}</AlertTitle>
              <AlertDescription>{processingInfo.error}</AlertDescription>
            </Alert>
          )}

          <div className="flex justify-end gap-2">
            <Button variant="outline">
              <Download className="mr-2 h-4 w-4" />
              {t('dataset.document.processing.actions.export')}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  )
} 
