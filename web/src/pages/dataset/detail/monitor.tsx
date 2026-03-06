import { useEffect, useMemo, useState } from 'react'
import { useParams } from 'react-router'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { RefreshCw } from 'lucide-react'
import { listRuns, type RunResponse } from '@/services/run-service'
import { toast } from 'sonner'
import { useTranslation } from '@/i18n'

function Page() {
  const { t } = useTranslation()
  const { datasetId } = useParams<{ datasetId: string }>()
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [loading, setLoading] = useState(false)

  const fetchRuns = async () => {
    if (!datasetId) return
    try {
      setLoading(true)
      const data = await listRuns({ app_version_id: datasetId, page_size: 50 })
      setRuns(data.items || [])
    } catch (error) {
      toast.error(t('dataset.monitor.toast.fetchError'))
      console.error('Failed to fetch runs:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchRuns()
  }, [datasetId])

  const statusSummary = useMemo(() => {
    return runs.reduce(
      (acc, run) => {
        acc[run.status] = (acc[run.status] || 0) + 1
        return acc
      },
      {} as Record<string, number>
    )
  }, [runs])

  return (
    <div className="flex flex-1 flex-col gap-4 p-4">
      <div className="flex justify-end">
        <Button variant="outline" onClick={fetchRuns} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
        </Button>
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.monitor.summary.title')}</CardTitle>
          <CardDescription>{t('dataset.monitor.summary.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {Object.keys(statusSummary).length === 0 && (
            <div className="text-sm text-muted-foreground">{t('dataset.monitor.summary.empty')}</div>
          )}
          {Object.entries(statusSummary).map(([status, count]) => (
            <div key={status} className="flex items-center justify-between border-b pb-2">
              <span className="text-sm font-medium">{status}</span>
              <span className="text-sm text-muted-foreground">{count}</span>
            </div>
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t('dataset.monitor.recent.title')}</CardTitle>
          <CardDescription>{t('dataset.monitor.recent.description')}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          {runs.slice(0, 10).map((run) => (
            <div key={run.id} className="border-b pb-2">
              <div className="flex items-center justify-between">
                <div className="text-sm font-medium">{run.mode}</div>
                <div className="text-xs text-muted-foreground">{run.status}</div>
              </div>
              <div className="text-xs text-muted-foreground">{run.started_at}</div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default Page
