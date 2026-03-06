import { useEffect, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { listRuns, type RunResponse } from '@/services/run-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'
import { useNavigate } from '@/hooks/use-navigate'

function Page() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const navigate = useNavigate()
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loading, setLoading] = useState(false)

  const fetchRuns = async () => {
    if (!datasetId) return
    try {
      setLoading(true)
      const data = await listRuns({ app_version_id: datasetId, page_size: 50 })
      setRuns(data.items || [])
    } catch (error) {
      toast.error(t('dataset.log.toast.fetchError'))
      console.error('Failed to fetch runs:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
  }, [datasetId])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex justify-end">
        <Button variant="outline" onClick={fetchRuns} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.log.title')}</CardTitle>
          <CardDescription>{t('dataset.log.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {runs.length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.log.empty')}</div>
          )}
          {runs.map((run) => (
            <div key={run.id} className="border-b pb-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{run.mode}</div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-muted-foreground">{run.status}</span>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => datasetId && navigate(`/dataset/${datasetId}/runs/${run.id}`)}
                    disabled={!datasetId}
                  >
                    {t('dataset.log.view')}
                  </Button>
                </div>
              </div>
              <div className="text-xs text-muted-foreground">{run.started_at}</div>
              {run.input_summary && (
                <div className="text-xs text-muted-foreground">
                  {t('dataset.log.input', { input: run.input_summary })}
                </div>
              )}
              {run.error_message && (
                <div className="text-xs text-destructive">
                  {t('dataset.log.error', { error: run.error_message })}
                </div>
              )}
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
