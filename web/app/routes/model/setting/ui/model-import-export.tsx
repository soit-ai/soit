import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { useToast } from '@/hooks/use-toast'
import { Download, Upload, Loader2, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import type { ModelConfig } from './types'
import { useTranslation } from '@/i18n'

interface ModelImportExportProps {
  providerId: string
  modelId: string
  modelName: string
  onImport?: (model: ModelConfig) => void
  onExport?: () => void
}

export function ModelImportExport({ 
  providerId, 
  modelId, 
  modelName, 
  onImport,
  onExport 
}: ModelImportExportProps) {
  const { t } = useTranslation()
  const { toast } = useToast()
  const [loading, setLoading] = useState<'export' | 'import' | null>(null)
  const [error, setError] = useState<string | null>(null)

  const handleExport = async () => {
    toast({
      title: t('model.importExport.unavailableTitle'),
      description: t('model.importExport.unavailableDescription'),
      type: 'error',
    })
  }

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    toast({
      title: t('model.importExport.unavailableTitle'),
      description: t('model.importExport.unavailableDescription'),
      type: 'error',
    })
    event.target.value = ''
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('model.importExport.title')}</CardTitle>
        <CardDescription>
          {t('model.importExport.description', { modelName })}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <AlertCircle className="h-4 w-4" />
            <AlertTitle>{t('model.importExport.errorTitle')}</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="grid grid-cols-2 gap-4">
          <div>
            <Button
              variant="outline"
              className="w-full"
              onClick={handleExport}
              disabled={loading === 'export'}
            >
              {loading === 'export' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Download className="w-4 h-4 mr-2" />
              )}
              {t('model.importExport.export')}
            </Button>
          </div>
          <div>
            <input
              type="file"
              id="import-file"
              className="hidden"
              accept=".json"
              onChange={handleImport}
              disabled={loading === 'import'}
            />
            <Button
              variant="outline"
              className="w-full"
              onClick={() => document.getElementById('import-file')?.click()}
              disabled={loading === 'import'}
            >
              {loading === 'import' ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Upload className="w-4 h-4 mr-2" />
              )}
              {t('model.importExport.import')}
            </Button>
          </div>
        </div>
      </CardContent>
      <CardFooter className="flex flex-col items-start gap-2 text-sm text-muted-foreground">
        <p>{t('model.importExport.notes.support')}</p>
        <ul className="list-disc list-inside space-y-1">
          <li>{t('model.importExport.notes.sizeLimit')}</li>
          <li>{t('model.importExport.notes.format')}</li>
          <li>{t('model.importExport.notes.validate')}</li>
        </ul>
      </CardFooter>
    </Card>
  )
} 
